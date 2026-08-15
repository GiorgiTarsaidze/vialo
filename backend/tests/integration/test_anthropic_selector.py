"""Integration tests for Anthropic candidate selector with mocked HTTP."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from vialo.models.diagnostics import DiagnosticCode
from vialo.services.anthropic_selector import AnthropicCandidateSelector
from vialo.services.candidate_selector import SelectorError

VALID_RESPONSE_JSON = json.dumps(
    {
        "locality_query": "Venice",
        "origin_query": "Hotel Danieli",
        "requested_date": "2026-08-15",
        "local_start_time": "09:00",
        "local_end_time": "19:00",
        "travel_mode": "WALK",
        "return_to_origin": True,
        "candidates": [
            {
                "candidate_index": 0,
                "name": "Saint Mark's Basilica",
                "category": "historic_religious_site",
                "priority": 1,
                "visit_duration_minutes": 50,
                "duration_source": "model_estimate",
            },
            {
                "candidate_index": 1,
                "name": "Palazzo Ducale",
                "category": "museum_gallery",
                "priority": 1,
                "visit_duration_minutes": 70,
                "duration_source": "model_estimate",
            },
        ],
    }
)


def _mock_response(text: str):
    """Create a mock Anthropic response."""
    mock = MagicMock()
    mock.content = [MagicMock(type="text", text=text)]
    return mock


class TestAnthropicSelector:
    @patch("vialo.services.anthropic_selector.anthropic.Anthropic")
    def test_valid_response(self, mock_anthropic_class) -> None:
        """Valid model output is parsed successfully."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_response(VALID_RESPONSE_JSON)
        mock_anthropic_class.return_value = mock_client

        selector = AnthropicCandidateSelector(
            api_key="test-key",
            model_id="test-model",
        )
        intent = selector.select("Walk Venice 6 hours from Hotel Danieli")

        assert intent.locality_query == "Venice"
        assert intent.origin_query == "Hotel Danieli"
        assert len(intent.candidates) == 2
        assert intent.candidates[0].name == "Saint Mark's Basilica"

    @patch("vialo.services.anthropic_selector.anthropic.Anthropic")
    def test_invalid_json_triggers_repair(self, mock_anthropic_class) -> None:
        """Invalid first response triggers one repair attempt."""
        mock_client = MagicMock()
        # First call returns invalid JSON, second returns valid
        mock_client.messages.create.side_effect = [
            _mock_response("not valid json {{{"),
            _mock_response(VALID_RESPONSE_JSON),
        ]
        mock_anthropic_class.return_value = mock_client

        selector = AnthropicCandidateSelector(api_key="test-key", model_id="test-model")
        intent = selector.select("Walk Venice")

        assert intent.locality_query == "Venice"
        assert mock_client.messages.create.call_count == 2

    @patch("vialo.services.anthropic_selector.anthropic.Anthropic")
    def test_both_attempts_fail_raises(self, mock_anthropic_class) -> None:
        """Two failures raise MODEL_OUTPUT_INVALID."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_response("garbage")
        mock_anthropic_class.return_value = mock_client

        selector = AnthropicCandidateSelector(api_key="test-key", model_id="test-model")

        with pytest.raises(SelectorError) as exc_info:
            selector.select("Walk Venice")
        assert exc_info.value.code == DiagnosticCode.MODEL_OUTPUT_INVALID

    @patch("vialo.services.anthropic_selector.anthropic.Anthropic")
    def test_timeout_raises_provider_unavailable(self, mock_anthropic_class) -> None:
        """Timeout raises PROVIDER_UNAVAILABLE."""
        import anthropic

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic.APITimeoutError(request=MagicMock())
        mock_anthropic_class.return_value = mock_client

        selector = AnthropicCandidateSelector(api_key="test-key", model_id="test-model")

        with pytest.raises(SelectorError) as exc_info:
            selector.select("Walk Venice")
        assert exc_info.value.code == DiagnosticCode.PROVIDER_UNAVAILABLE

    @patch("vialo.services.anthropic_selector.anthropic.Anthropic")
    def test_markdown_fences_stripped(self, mock_anthropic_class) -> None:
        """JSON wrapped in markdown code fences is handled."""
        mock_client = MagicMock()
        fenced = f"```json\n{VALID_RESPONSE_JSON}\n```"
        mock_client.messages.create.return_value = _mock_response(fenced)
        mock_anthropic_class.return_value = mock_client

        selector = AnthropicCandidateSelector(api_key="test-key", model_id="test-model")
        intent = selector.select("Walk Venice")
        assert intent.locality_query == "Venice"


class TestAnthropicSelectorValidationRepair:
    @patch("vialo.services.anthropic_selector.anthropic.Anthropic")
    def test_mismatched_user_duration_evidence_triggers_repair(self, mock_anthropic_class) -> None:
        prompt = "Walk Venice for 6 hours from Hotel Danieli"
        invalid = json.loads(VALID_RESPONSE_JSON)
        invalid["candidates"][0].update(
            {
                "duration_source": "user",
                "duration_evidence": {"start": 17, "end": 24, "quote": "6 hours"},
            }
        )
        client = MagicMock()
        client.messages.create.side_effect = [
            _mock_response(json.dumps(invalid)),
            _mock_response(VALID_RESPONSE_JSON),
        ]
        mock_anthropic_class.return_value = client

        intent = AnthropicCandidateSelector("test-key", "test-model").select(prompt)

        assert client.messages.create.call_count == 2
        assert intent.candidates[0].duration_source == "model_estimate"

    @patch("vialo.services.anthropic_selector.anthropic.Anthropic")
    def test_model_estimate_outside_category_bound_triggers_repair(
        self, mock_anthropic_class
    ) -> None:
        invalid = json.loads(VALID_RESPONSE_JSON)
        invalid["candidates"][0]["category"] = "quick_viewpoint"
        invalid["candidates"][0]["visit_duration_minutes"] = 100
        client = MagicMock()
        client.messages.create.side_effect = [
            _mock_response(json.dumps(invalid)),
            _mock_response(VALID_RESPONSE_JSON),
        ]
        mock_anthropic_class.return_value = client

        AnthropicCandidateSelector("test-key", "test-model").select("Walk Venice today for 6 hours")

        assert client.messages.create.call_count == 2

    @patch("vialo.services.anthropic_selector.anthropic.Anthropic")
    def test_nonsequential_candidate_indices_trigger_repair(self, mock_anthropic_class) -> None:
        invalid = json.loads(VALID_RESPONSE_JSON)
        invalid["candidates"][1]["candidate_index"] = 3
        client = MagicMock()
        client.messages.create.side_effect = [
            _mock_response(json.dumps(invalid)),
            _mock_response(VALID_RESPONSE_JSON),
        ]
        mock_anthropic_class.return_value = client

        AnthropicCandidateSelector("test-key", "test-model").select("Walk Venice today for 6 hours")

        assert client.messages.create.call_count == 2
