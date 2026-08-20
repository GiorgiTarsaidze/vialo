"""Tests for the bounded top-up candidate pass."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from vialo.pipeline.repair_candidates import build_top_up_context
from vialo.services.bedrock_selector import BedrockCandidateSelector
from vialo.services.candidate_selector import SelectorError
from vialo.services.spend_limiter import BudgetExceededError


def _selector(response_text: str | None) -> tuple[BedrockCandidateSelector, MagicMock]:
    limiter = MagicMock()
    limiter.reserve.return_value = 1000
    selector = BedrockCandidateSelector(spend_limiter=limiter, region_name="us-east-1")
    client = MagicMock()
    content: list[dict[str, Any]] = [] if response_text is None else [{"text": response_text}]
    client.converse.return_value = {
        "output": {"message": {"content": content}},
        "usage": {"inputTokens": 100, "outputTokens": 50},
    }
    selector._client = client
    return selector, limiter


def _candidate(name: str, category: str = "landmark", minutes: int = 45) -> dict[str, Any]:
    return {
        "name": name,
        "category": category,
        "priority": 2,
        "visit_duration_minutes": minutes,
    }


class TestTopUpParsing:
    def test_accepts_candidates_and_renumbers_from_the_supplied_index(self) -> None:
        selector, _ = _selector(json.dumps({"candidates": [_candidate("A"), _candidate("B")]}))
        result = selector.top_up("{}", 5)
        assert [c.candidate_index for c in result] == [5, 6]
        assert [c.name for c in result] == ["A", "B"]

    def test_forces_model_estimate_provenance_and_drops_supplied_evidence(self) -> None:
        payload = {
            "candidates": [
                {
                    **_candidate("A"),
                    "duration_source": "user",
                    "duration_evidence": {
                        "start": 0,
                        "end": 5,
                        "quote": "45 min",
                    },
                }
            ]
        }
        selector, _ = _selector(json.dumps(payload))
        result = selector.top_up("{}", 0)
        assert len(result) == 1
        # A top-up stop is never attributable to the user's own prompt.
        assert result[0].duration_source == "model_estimate"
        assert result[0].duration_evidence is None

    def test_rejects_durations_outside_the_category_bounds(self) -> None:
        selector, _ = _selector(
            json.dumps({"candidates": [_candidate("Too long", "quick_viewpoint", 240)]})
        )
        assert selector.top_up("{}", 0) == []

    def test_skips_malformed_entries_but_keeps_valid_ones(self) -> None:
        selector, _ = _selector(
            json.dumps({"candidates": ["not an object", _candidate("Good"), {"name": "no cat"}]})
        )
        result = selector.top_up("{}", 0)
        assert [c.name for c in result] == ["Good"]

    def test_tolerates_a_bare_array_and_markdown_fences(self) -> None:
        selector, _ = _selector("```json\n" + json.dumps([_candidate("A")]) + "\n```")
        assert [c.name for c in selector.top_up("{}", 3)] == ["A"]

    def test_non_json_returns_no_candidates(self) -> None:
        selector, _ = _selector("Here are some ideas you might like!")
        assert selector.top_up("{}", 0) == []

    def test_empty_response_returns_no_candidates(self) -> None:
        selector, _ = _selector(None)
        assert selector.top_up("{}", 0) == []

    def test_caps_the_number_of_added_candidates(self) -> None:
        many = {"candidates": [_candidate(f"S{i}") for i in range(12)]}
        selector, _ = _selector(json.dumps(many))
        assert len(selector.top_up("{}", 0)) == 6


class TestTopUpBudgetAndFailure:
    def test_budget_exceeded_propagates_so_the_caller_can_skip(self) -> None:
        selector, limiter = _selector(json.dumps({"candidates": []}))
        limiter.reserve.side_effect = BudgetExceededError("cap reached")
        with pytest.raises(BudgetExceededError):
            selector.top_up("{}", 0)

    def test_provider_failure_raises_selector_error(self) -> None:
        from botocore.exceptions import BotoCoreError

        selector, _ = _selector(json.dumps({"candidates": []}))
        selector._client.converse.side_effect = BotoCoreError()
        with pytest.raises(SelectorError):
            selector.top_up("{}", 0)

    def test_each_call_reserves_budget(self) -> None:
        selector, limiter = _selector(json.dumps({"candidates": [_candidate("A")]}))
        selector.top_up("{}", 0)
        limiter.reserve.assert_called_once()


class TestTopUpContext:
    def test_context_carries_only_locality_window_and_names(self) -> None:
        context = build_top_up_context(
            locality="Tbilisi",
            travel_mode="WALK",
            local_start="10:00",
            local_end="16:00",
            requested_date="2026-08-21",
            accepted_names=["Metekhi Church"],
            rejected_names=["Narikala Fortress"],
            wanted=3,
        )
        payload = json.loads(context)
        assert payload["locality"] == "Tbilisi"
        assert payload["already_accepted"] == ["Metekhi Church"]
        assert payload["do_not_repeat"] == ["Narikala Fortress"]
        assert payload["candidates_wanted"] == 3
        # No user prompt text is forwarded.
        assert "prompt" not in payload
