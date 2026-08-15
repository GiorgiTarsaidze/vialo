"""Integration tests for Bedrock candidate selector with per-call reserve/settle.

Proves:
- Valid one-call path: reserve/settle once
- Repair path: reserve/settle twice
- Budget block on initial makes zero Converse calls
- Budget block on repair makes exactly one Converse call and no second
- DynamoDB guard failure makes zero model calls
- Estimates include repair payload and are >= UTF-8 serialized bytes + 4096
- Standard validation/repair/error behaviors
- BotoConfig disables opaque retries (total_max_attempts=1)
- Missing/malformed usage retains reservation without settlement
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, call, patch

import pytest
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError, ReadTimeoutError

from vialo.models.diagnostics import DiagnosticCode
from vialo.services.bedrock_selector import (
    _CONVERSE_FRAMING_TOKENS,
    SYSTEM_PROMPT,
    BedrockCandidateSelector,
)
from vialo.services.candidate_selector import SelectorError
from vialo.services.spend_limiter import BudgetExceededError, SpendLimiterUnavailableError

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


def _mock_converse_response(text: str, input_tokens: int = 100, output_tokens: int = 200):
    """Create a mock Bedrock Converse response."""
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": text}],
            }
        },
        "usage": {
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
        },
        "stopReason": "end_turn",
    }


def _make_selector(
    mock_bedrock: MagicMock, spend_limiter: MagicMock | None = None
) -> BedrockCandidateSelector:
    """Create a selector with mocked bedrock client and optional limiter mock."""
    if spend_limiter is None:
        spend_limiter = MagicMock()
        spend_limiter.reserve.return_value = 50000

    with patch("vialo.services.bedrock_selector.boto3.client") as mock_client:
        mock_client.return_value = mock_bedrock
        selector = BedrockCandidateSelector(
            spend_limiter=spend_limiter,
            model_id="us.anthropic.claude-sonnet-4-6",
            region_name="us-east-1",
        )
    return selector


class TestValidOneCallPathReserveSettleOnce:
    def test_valid_response_reserves_and_settles_once(self) -> None:
        """Valid one-call path: reserve called once, settle called once."""
        mock_bedrock = MagicMock()
        mock_bedrock.converse.return_value = _mock_converse_response(VALID_RESPONSE_JSON)
        mock_limiter = MagicMock()
        mock_limiter.reserve.return_value = 50000

        selector = _make_selector(mock_bedrock, mock_limiter)
        intent = selector.select("Walk Venice 6 hours from Hotel Danieli")

        assert intent.locality_query == "Venice"
        assert mock_limiter.reserve.call_count == 1
        assert mock_limiter.settle.call_count == 1
        # Settle called with actual tokens from response
        mock_limiter.settle.assert_called_once_with(
            reservation_micro_usd=50000,
            actual_input_tokens=100,
            actual_output_tokens=200,
        )
        assert mock_bedrock.converse.call_count == 1


class TestRepairPathReserveSettleTwice:
    def test_repair_path_reserves_and_settles_twice(self) -> None:
        """Repair path: reserve/settle called twice (once per Converse call)."""
        mock_bedrock = MagicMock()
        mock_bedrock.converse.side_effect = [
            _mock_converse_response("not valid json {{{", input_tokens=80, output_tokens=50),
            _mock_converse_response(VALID_RESPONSE_JSON, input_tokens=200, output_tokens=300),
        ]
        mock_limiter = MagicMock()
        mock_limiter.reserve.return_value = 50000

        selector = _make_selector(mock_bedrock, mock_limiter)
        intent = selector.select("Walk Venice today for 6 hours")

        assert intent.locality_query == "Venice"
        assert mock_limiter.reserve.call_count == 2
        assert mock_limiter.settle.call_count == 2
        assert mock_bedrock.converse.call_count == 2

        # First settle uses tokens from first (failed-parse) call
        first_settle = mock_limiter.settle.call_args_list[0]
        assert first_settle == call(
            reservation_micro_usd=50000,
            actual_input_tokens=80,
            actual_output_tokens=50,
        )
        # Second settle uses tokens from repair call
        second_settle = mock_limiter.settle.call_args_list[1]
        assert second_settle == call(
            reservation_micro_usd=50000,
            actual_input_tokens=200,
            actual_output_tokens=300,
        )


class TestBudgetBlockOnInitialMakesZeroConverseCalls:
    def test_budget_exceeded_on_initial_makes_zero_calls(self) -> None:
        """Budget block on initial reservation makes zero Converse calls."""
        mock_bedrock = MagicMock()
        mock_limiter = MagicMock()
        mock_limiter.reserve.side_effect = BudgetExceededError("cap exceeded")

        selector = _make_selector(mock_bedrock, mock_limiter)
        with pytest.raises(BudgetExceededError):
            selector.select("Walk Venice today for 6 hours")

        mock_bedrock.converse.assert_not_called()
        mock_limiter.settle.assert_not_called()


class TestBudgetBlockOnRepairMakesExactlyOneConverseCall:
    def test_budget_block_on_repair_makes_one_call_only(self) -> None:
        """Budget block on repair: exactly one Converse call, no second."""
        mock_bedrock = MagicMock()
        mock_bedrock.converse.return_value = _mock_converse_response(
            "garbage output", input_tokens=80, output_tokens=50
        )
        mock_limiter = MagicMock()
        # First reserve succeeds, second (for repair) raises BudgetExceededError
        mock_limiter.reserve.side_effect = [50000, BudgetExceededError("cap exceeded")]

        selector = _make_selector(mock_bedrock, mock_limiter)
        with pytest.raises(BudgetExceededError):
            selector.select("Walk Venice today for 6 hours")

        # Exactly one Converse call was made (the initial one)
        assert mock_bedrock.converse.call_count == 1
        # First call was settled before repair was attempted
        assert mock_limiter.settle.call_count == 1
        mock_limiter.settle.assert_called_once_with(
            reservation_micro_usd=50000,
            actual_input_tokens=80,
            actual_output_tokens=50,
        )


class TestDynamoDBGuardFailureMakesZeroModelCalls:
    def test_spend_limiter_unavailable_makes_zero_calls(self) -> None:
        """DynamoDB guard failure raises SpendLimiterUnavailableError, zero model calls."""
        mock_bedrock = MagicMock()
        mock_limiter = MagicMock()
        mock_limiter.reserve.side_effect = SpendLimiterUnavailableError("DDB down")

        selector = _make_selector(mock_bedrock, mock_limiter)
        with pytest.raises(SpendLimiterUnavailableError):
            selector.select("Walk Venice today for 6 hours")

        mock_bedrock.converse.assert_not_called()
        mock_limiter.settle.assert_not_called()


class TestEstimatesIncludeRepairPayloadAndAreSufficient:
    def test_initial_estimate_gte_utf8_bytes_plus_framing(self) -> None:
        """Initial call estimate >= UTF-8 serialized bytes of payload + 4096."""
        mock_bedrock = MagicMock()
        mock_bedrock.converse.return_value = _mock_converse_response(VALID_RESPONSE_JSON)
        mock_limiter = MagicMock()
        mock_limiter.reserve.return_value = 50000

        selector = _make_selector(mock_bedrock, mock_limiter)
        selector.select("Walk Venice 6 hours from Hotel Danieli")

        # Get what was passed to reserve
        first_reserve_args = mock_limiter.reserve.call_args_list[0]
        estimated_input = first_reserve_args[0][0]

        # Compute expected minimum: UTF-8 bytes of system+messages + 4096
        system = [{"text": SYSTEM_PROMPT}]
        prompt_text = "Walk Venice 6 hours from Hotel Danieli"
        messages = [{"role": "user", "content": [{"text": prompt_text}]}]
        payload_str = json.dumps({"system": system, "messages": messages}, ensure_ascii=False)
        payload_bytes = len(payload_str.encode("utf-8"))
        minimum = payload_bytes + _CONVERSE_FRAMING_TOKENS

        assert estimated_input >= minimum

    def test_repair_estimate_includes_failed_output_and_instruction(self) -> None:
        """Repair estimate includes failed output + repair instruction in payload."""
        failed_text = "some garbage output that is not JSON"
        mock_bedrock = MagicMock()
        mock_bedrock.converse.side_effect = [
            _mock_converse_response(failed_text, input_tokens=80, output_tokens=50),
            _mock_converse_response(VALID_RESPONSE_JSON, input_tokens=200, output_tokens=300),
        ]
        mock_limiter = MagicMock()
        mock_limiter.reserve.return_value = 50000

        prompt = "Walk Venice today for 6 hours"
        selector = _make_selector(mock_bedrock, mock_limiter)
        selector.select(prompt)

        # Second reserve call is for repair — verify its estimate
        assert mock_limiter.reserve.call_count == 2
        repair_reserve_args = mock_limiter.reserve.call_args_list[1]
        estimated_repair_input = repair_reserve_args[0][0]

        # Compute expected minimum for repair payload
        from vialo.services.bedrock_selector import REPAIR_INSTRUCTION

        system = [{"text": SYSTEM_PROMPT}]
        repair_messages = [
            {"role": "user", "content": [{"text": prompt}]},
            {"role": "assistant", "content": [{"text": failed_text}]},
            {"role": "user", "content": [{"text": REPAIR_INSTRUCTION}]},
        ]
        payload_str = json.dumps(
            {"system": system, "messages": repair_messages}, ensure_ascii=False
        )
        payload_bytes = len(payload_str.encode("utf-8"))
        minimum = payload_bytes + _CONVERSE_FRAMING_TOKENS

        assert estimated_repair_input >= minimum


class TestBedrockSelectorBasicBehavior:
    def test_valid_response(self) -> None:
        """Valid model output is parsed successfully."""
        mock_bedrock = MagicMock()
        mock_bedrock.converse.return_value = _mock_converse_response(VALID_RESPONSE_JSON)

        selector = _make_selector(mock_bedrock)
        intent = selector.select("Walk Venice 6 hours from Hotel Danieli")

        assert intent.locality_query == "Venice"
        assert intent.origin_query == "Hotel Danieli"
        assert len(intent.candidates) == 2
        assert intent.candidates[0].name == "Saint Mark's Basilica"

    def test_invalid_json_triggers_repair(self) -> None:
        """Invalid first response triggers one repair attempt."""
        mock_bedrock = MagicMock()
        mock_bedrock.converse.side_effect = [
            _mock_converse_response("not valid json {{{"),
            _mock_converse_response(VALID_RESPONSE_JSON),
        ]

        selector = _make_selector(mock_bedrock)
        intent = selector.select("Walk Venice today for 6 hours")

        assert intent.locality_query == "Venice"
        assert mock_bedrock.converse.call_count == 2

    def test_both_attempts_fail_raises(self) -> None:
        """Two failures raise MODEL_OUTPUT_INVALID."""
        mock_bedrock = MagicMock()
        mock_bedrock.converse.return_value = _mock_converse_response("garbage")

        selector = _make_selector(mock_bedrock)
        with pytest.raises(SelectorError) as exc_info:
            selector.select("Walk Venice today for 6 hours")
        assert exc_info.value.code == DiagnosticCode.MODEL_OUTPUT_INVALID

    def test_client_error_raises_provider_unavailable(self) -> None:
        """ClientError raises PROVIDER_UNAVAILABLE."""
        mock_bedrock = MagicMock()
        mock_bedrock.converse.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "Converse",
        )

        selector = _make_selector(mock_bedrock)
        with pytest.raises(SelectorError) as exc_info:
            selector.select("Walk Venice today for 6 hours")
        assert exc_info.value.code == DiagnosticCode.PROVIDER_UNAVAILABLE

    def test_timeout_raises_provider_unavailable(self) -> None:
        """Read timeout raises PROVIDER_UNAVAILABLE."""
        mock_bedrock = MagicMock()
        mock_bedrock.converse.side_effect = ReadTimeoutError(endpoint_url="https://bedrock.test")

        selector = _make_selector(mock_bedrock)
        with pytest.raises(SelectorError) as exc_info:
            selector.select("Walk Venice today for 6 hours")
        assert exc_info.value.code == DiagnosticCode.PROVIDER_UNAVAILABLE

    def test_markdown_fences_stripped(self) -> None:
        """JSON wrapped in markdown code fences is handled."""
        mock_bedrock = MagicMock()
        fenced = f"```json\n{VALID_RESPONSE_JSON}\n```"
        mock_bedrock.converse.return_value = _mock_converse_response(fenced)

        selector = _make_selector(mock_bedrock)
        intent = selector.select("Walk Venice today for 6 hours")
        assert intent.locality_query == "Venice"


class TestBedrockSelectorValidationRepair:
    def test_prompts_require_exact_candidate_index_key(self) -> None:
        from vialo.services.bedrock_selector import REPAIR_INSTRUCTION

        assert "exact key candidate_index" in SYSTEM_PROMPT
        assert "exact key candidate_index" in REPAIR_INSTRUCTION
        assert "never index" in REPAIR_INSTRUCTION

    def test_mismatched_user_duration_evidence_triggers_repair(self) -> None:
        prompt = "Walk Venice for 6 hours from Hotel Danieli"
        invalid = json.loads(VALID_RESPONSE_JSON)
        invalid["candidates"][0].update(
            {
                "duration_source": "user",
                "duration_evidence": {"start": 17, "end": 24, "quote": "6 hours"},
            }
        )
        mock_bedrock = MagicMock()
        mock_bedrock.converse.side_effect = [
            _mock_converse_response(json.dumps(invalid)),
            _mock_converse_response(VALID_RESPONSE_JSON),
        ]

        selector = _make_selector(mock_bedrock)
        intent = selector.select(prompt)

        assert mock_bedrock.converse.call_count == 2
        assert intent.candidates[0].duration_source == "model_estimate"

    def test_model_estimate_outside_category_bound_triggers_repair(self) -> None:
        invalid = json.loads(VALID_RESPONSE_JSON)
        invalid["candidates"][0]["category"] = "quick_viewpoint"
        invalid["candidates"][0]["visit_duration_minutes"] = 100
        mock_bedrock = MagicMock()
        mock_bedrock.converse.side_effect = [
            _mock_converse_response(json.dumps(invalid)),
            _mock_converse_response(VALID_RESPONSE_JSON),
        ]

        selector = _make_selector(mock_bedrock)
        selector.select("Walk Venice today for 6 hours")
        assert mock_bedrock.converse.call_count == 2

    def test_nonsequential_candidate_indices_trigger_repair(self) -> None:
        invalid = json.loads(VALID_RESPONSE_JSON)
        invalid["candidates"][1]["candidate_index"] = 3
        mock_bedrock = MagicMock()
        mock_bedrock.converse.side_effect = [
            _mock_converse_response(json.dumps(invalid)),
            _mock_converse_response(VALID_RESPONSE_JSON),
        ]

        selector = _make_selector(mock_bedrock)
        selector.select("Walk Venice today for 6 hours")
        assert mock_bedrock.converse.call_count == 2


class TestBotoConfigDisablesOpaqueRetries:
    """One reservation must map to exactly one wire invocation."""

    def test_boto_config_sets_total_max_attempts_1(self) -> None:
        """BotoConfig passed to boto3.client uses total_max_attempts=1, mode=standard."""
        mock_limiter = MagicMock()
        mock_limiter.reserve.return_value = 50000

        with patch("vialo.services.bedrock_selector.boto3.client") as mock_client_fn:
            mock_client_fn.return_value = MagicMock()
            BedrockCandidateSelector(
                spend_limiter=mock_limiter,
                model_id="us.anthropic.claude-sonnet-4-6",
                region_name="us-east-1",
            )

            # Inspect what BotoConfig was passed
            mock_client_fn.assert_called_once()
            call_kwargs = mock_client_fn.call_args
            passed_config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
            if passed_config is None:
                # positional: boto3.client("bedrock-runtime", config=...)
                passed_config = (
                    call_kwargs[1]["config"]
                    if len(call_kwargs) > 1
                    else call_kwargs.kwargs["config"]
                )

            assert isinstance(passed_config, BotoConfig)
            # BotoConfig stores retries in _user_provided_options
            retry_config = passed_config._user_provided_options["retries"]  # type: ignore[attr-defined]
            assert retry_config["total_max_attempts"] == 1
            assert retry_config["mode"] == "standard"

    def test_no_max_retries_parameter(self) -> None:
        """Constructor does not accept a max_retries parameter (removed)."""
        import inspect

        sig = inspect.signature(BedrockCandidateSelector.__init__)
        param_names = list(sig.parameters.keys())
        assert "max_retries" not in param_names


class TestMissingMalformedUsageRetainsReservation:
    """When usage is missing/malformed/negative, retain reservation, no settle."""

    def test_missing_usage_retains_reservation(self) -> None:
        """Response with no 'usage' key retains reservation (settle=0)."""
        mock_bedrock = MagicMock()
        response_no_usage = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": VALID_RESPONSE_JSON}],
                }
            },
            "stopReason": "end_turn",
        }
        mock_bedrock.converse.return_value = response_no_usage
        mock_limiter = MagicMock()
        mock_limiter.reserve.return_value = 50000

        selector = _make_selector(mock_bedrock, mock_limiter)
        intent = selector.select("Walk Venice 6 hours from Hotel Danieli")

        # Model output is still usable
        assert intent.locality_query == "Venice"
        # Exactly one reserve, zero settle, one converse call
        assert mock_limiter.reserve.call_count == 1
        assert mock_limiter.settle.call_count == 0
        assert mock_bedrock.converse.call_count == 1

    def test_usage_with_bool_input_tokens_retains_reservation(self) -> None:
        """inputTokens=True (bool, not int) triggers retention."""
        mock_bedrock = MagicMock()
        response_bool_usage = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": VALID_RESPONSE_JSON}],
                }
            },
            "usage": {"inputTokens": True, "outputTokens": 200},
            "stopReason": "end_turn",
        }
        mock_bedrock.converse.return_value = response_bool_usage
        mock_limiter = MagicMock()
        mock_limiter.reserve.return_value = 50000

        selector = _make_selector(mock_bedrock, mock_limiter)
        intent = selector.select("Walk Venice 6 hours from Hotel Danieli")

        assert intent.locality_query == "Venice"
        assert mock_limiter.reserve.call_count == 1
        assert mock_limiter.settle.call_count == 0
        assert mock_bedrock.converse.call_count == 1

    def test_usage_with_negative_output_tokens_retains_reservation(self) -> None:
        """Negative outputTokens triggers retention."""
        mock_bedrock = MagicMock()
        response_neg = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": VALID_RESPONSE_JSON}],
                }
            },
            "usage": {"inputTokens": 100, "outputTokens": -1},
            "stopReason": "end_turn",
        }
        mock_bedrock.converse.return_value = response_neg
        mock_limiter = MagicMock()
        mock_limiter.reserve.return_value = 50000

        selector = _make_selector(mock_bedrock, mock_limiter)
        intent = selector.select("Walk Venice 6 hours from Hotel Danieli")

        assert intent.locality_query == "Venice"
        assert mock_limiter.reserve.call_count == 1
        assert mock_limiter.settle.call_count == 0
        assert mock_bedrock.converse.call_count == 1

    def test_usage_with_string_tokens_retains_reservation(self) -> None:
        """String token values trigger retention."""
        mock_bedrock = MagicMock()
        response_str = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": VALID_RESPONSE_JSON}],
                }
            },
            "usage": {"inputTokens": "100", "outputTokens": "200"},
            "stopReason": "end_turn",
        }
        mock_bedrock.converse.return_value = response_str
        mock_limiter = MagicMock()
        mock_limiter.reserve.return_value = 50000

        selector = _make_selector(mock_bedrock, mock_limiter)
        intent = selector.select("Walk Venice 6 hours from Hotel Danieli")

        assert intent.locality_query == "Venice"
        assert mock_limiter.reserve.call_count == 1
        assert mock_limiter.settle.call_count == 0
        assert mock_bedrock.converse.call_count == 1

    def test_usage_none_retains_reservation(self) -> None:
        """usage=None triggers retention."""
        mock_bedrock = MagicMock()
        response_none = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": VALID_RESPONSE_JSON}],
                }
            },
            "usage": None,
            "stopReason": "end_turn",
        }
        mock_bedrock.converse.return_value = response_none
        mock_limiter = MagicMock()
        mock_limiter.reserve.return_value = 50000

        selector = _make_selector(mock_bedrock, mock_limiter)
        intent = selector.select("Walk Venice 6 hours from Hotel Danieli")

        assert intent.locality_query == "Venice"
        assert mock_limiter.reserve.call_count == 1
        assert mock_limiter.settle.call_count == 0
        assert mock_bedrock.converse.call_count == 1
