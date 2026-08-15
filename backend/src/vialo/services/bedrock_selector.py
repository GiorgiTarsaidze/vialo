"""AWS Bedrock Claude adapter behind the provider-neutral candidate selector boundary."""

from __future__ import annotations

import json
import logging
from typing import Any

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import ValidationError

from vialo.domain.duration_bounds import (
    parse_duration_text,
    validate_model_duration,
    validate_user_duration,
)
from vialo.models.diagnostics import DiagnosticCode
from vialo.models.providers import ParsedIntent
from vialo.services.candidate_selector import SelectorError
from vialo.services.spend_limiter import BedrockSpendLimiter, BudgetExceededError

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Extract a typed one-day city itinerary request. Return JSON only with:
locality_query, origin_query, requested_date (YYYY-MM-DD or null), local_start_time
(HH:MM), local_end_time (HH:MM), travel_mode (WALK or DRIVE), return_to_origin,
and 1-9 candidates. Every candidate object must contain the exact key candidate_index
(not index), with unique integer values sequential from zero. Each candidate also has name,
category, priority 1-3, visit_duration_minutes, duration_source, and duration_evidence.

Allowed categories and model-estimate duration bounds (minimum/default/maximum minutes):
- quick_viewpoint: 15/20/30
- landmark: 30/45/75
- museum_gallery: 60/90/180
- historic_religious_site: 30/60/120
- neighborhood_market_park: 30/60/120
- food_break: 30/60/120
- experience_tour: 60/120/240
- other: 30/60/90

Use duration_source "user" only when the prompt explicitly states that stop's duration.
Then duration_evidence must be the exact {start, end, quote} substring and the parsed
quote must equal visit_duration_minutes. Supported forms include "30 minutes", "30 min",
"1 hour", "1.5 hours", "half an hour", and "1h 30m". Otherwise use
"model_estimate", obey the category range, and set duration_evidence to null.
Do not emit prose or markdown.
"""

REPAIR_INSTRUCTION = (
    "Repair the JSON to satisfy the schema. Every candidate must use the exact "
    "key candidate_index, never index; values must be sequential from zero. "
    "Also enforce exact user-duration evidence and category bounds from the "
    "system prompt. Return JSON only."
)

# Conservative framing overhead for Bedrock Converse (token count)
_CONVERSE_FRAMING_TOKENS = 4096


class BedrockCandidateSelector:
    """Production Bedrock Claude adapter implementing CandidateSelector.

    Owns a mandatory BedrockSpendLimiter and atomically reserves/settles around
    EACH individual Converse call, including repair calls.
    """

    def __init__(
        self,
        spend_limiter: BedrockSpendLimiter,
        model_id: str = "us.anthropic.claude-sonnet-4-6",
        region_name: str = "us-east-1",
        max_tokens: int = 2048,
        connect_timeout: float = 5.0,
        read_timeout: float = 25.0,
    ) -> None:
        # Disable botocore automatic retries so one reservation maps to exactly
        # one wire invocation. Repair is the only second call and gets its own
        # independent reservation/settlement cycle.
        boto_config = BotoConfig(
            region_name=region_name,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            retries={"total_max_attempts": 1, "mode": "standard"},
        )
        self._client = boto3.client("bedrock-runtime", config=boto_config)
        self._model_id = model_id
        self._max_tokens = max_tokens
        self._spend_limiter = spend_limiter

    @property
    def max_tokens(self) -> int:
        """Maximum output tokens configured for this selector."""
        return self._max_tokens

    def _estimate_input_tokens_from_payload(
        self, system: list[dict[str, Any]], messages: list[dict[str, Any]]
    ) -> int:
        """Conservatively estimate input tokens from the serialized payload.

        Uses the full UTF-8 byte length of the serialized system+messages payload
        (each byte counts as one token pessimistically) plus a framing allowance.
        Does NOT divide bytes by 3 or 4.
        """
        payload_str = json.dumps({"system": system, "messages": messages}, ensure_ascii=False)
        payload_bytes = len(payload_str.encode("utf-8"))
        # Each byte bounded as one token (pessimistic) plus framing overhead
        return payload_bytes + _CONVERSE_FRAMING_TOKENS

    def _call_converse_with_budget(
        self, system: list[dict[str, Any]], messages: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Call Bedrock Converse with atomic reserve/settle around the call.

        1. Estimates input tokens from the actual serialized payload.
        2. Reserves budget before calling Bedrock.
        3. On Bedrock success: settles immediately with actual usage.
        4. On Bedrock error: retains reservation (fail closed) and re-raises.

        Raises:
            BudgetExceededError: If budget cap would be exceeded.
            BotoCoreError/ClientError: If Bedrock call fails (reservation retained).
        """
        estimated_input = self._estimate_input_tokens_from_payload(system, messages)

        # Reserve budget atomically before calling Bedrock
        # BudgetExceededError and SpendLimiterUnavailableError propagate up
        reservation = self._spend_limiter.reserve(estimated_input, self._max_tokens)

        try:
            response: dict[str, Any] = self._client.converse(
                modelId=self._model_id,
                messages=messages,
                system=system,
                inferenceConfig={
                    "temperature": 0.0,
                    "maxTokens": self._max_tokens,
                },
            )
        except (BotoCoreError, ClientError):
            # Bedrock error: reservation retained (fail closed)
            raise

        # Validate usage before settling. inputTokens/outputTokens must be real
        # nonneg ints (not bool). If usage is missing/malformed/negative, retain
        # full reservation (fail closed) and log a safe warning. The model output
        # may still be used.
        usage = response.get("usage")
        if self._validate_usage(usage):
            actual_input = usage["inputTokens"]  # type: ignore[index]
            actual_output = usage["outputTokens"]  # type: ignore[index]
            self._spend_limiter.settle(
                reservation_micro_usd=reservation,
                actual_input_tokens=actual_input,
                actual_output_tokens=actual_output,
            )
        else:
            logger.warning(
                "Bedrock usage missing or malformed; retaining full reservation",
                extra={"reservation_micro_usd": reservation},
            )

        return response

    @staticmethod
    def _validate_usage(usage: Any) -> bool:
        """Check that usage contains real nonneg int inputTokens/outputTokens.

        Returns False for missing, non-dict, bool values, negative, or non-int.
        """
        if not isinstance(usage, dict):
            return False
        input_tokens = usage.get("inputTokens")
        output_tokens = usage.get("outputTokens")
        # isinstance(True, int) is True in Python, so exclude bools explicitly
        if isinstance(input_tokens, bool) or not isinstance(input_tokens, int):
            return False
        if isinstance(output_tokens, bool) or not isinstance(output_tokens, int):
            return False
        return not (input_tokens < 0 or output_tokens < 0)

    def select(self, prompt: str) -> ParsedIntent:
        """Call Bedrock Converse, validate deterministically, allow one repair attempt.

        Each Converse call (initial + optional repair) has independent budget
        reserve/settle. The initial call is settled before repair is attempted.
        A blocked repair raises BudgetExceededError with no second Bedrock call.
        """
        system = [{"text": SYSTEM_PROMPT}]
        messages: list[dict[str, Any]] = [{"role": "user", "content": [{"text": prompt}]}]

        try:
            response = self._call_converse_with_budget(system, messages)
        except BudgetExceededError:
            raise
        except (BotoCoreError, ClientError) as exc:
            raise SelectorError(
                code=DiagnosticCode.PROVIDER_UNAVAILABLE,
                message="Candidate provider unavailable",
            ) from exc

        text = self._extract_text(response)
        intent = self._parse_response(text, prompt) if text is not None else None
        if intent is not None:
            return intent

        # One repair attempt — initial call is already settled above
        repair_messages: list[dict[str, Any]] = [
            {"role": "user", "content": [{"text": prompt}]},
            {"role": "assistant", "content": [{"text": text or ""}]},
            {"role": "user", "content": [{"text": REPAIR_INSTRUCTION}]},
        ]

        try:
            repair_response = self._call_converse_with_budget(system, repair_messages)
        except BudgetExceededError:
            raise
        except (BotoCoreError, ClientError):
            raise SelectorError(
                code=DiagnosticCode.MODEL_OUTPUT_INVALID,
                message="Model output failed validation after repair attempt",
            ) from None

        repair_text = self._extract_text(repair_response)
        repaired = self._parse_response(repair_text, prompt) if repair_text is not None else None
        if repaired is None:
            raise SelectorError(
                code=DiagnosticCode.MODEL_OUTPUT_INVALID,
                message="Model output failed validation after repair attempt",
            )
        return repaired

    def _extract_text(self, response: dict[str, Any]) -> str | None:
        """Extract text from Bedrock Converse response output."""
        output = response.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [])
        for block in content:
            if "text" in block:
                return str(block["text"])
        return None

    def _parse_response(self, text: str, prompt: str) -> ParsedIntent | None:
        """Validate schema, ordering, category bounds, and exact duration evidence."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()[1:]
            if lines and lines[-1].strip() == "```":
                lines.pop()
            cleaned = "\n".join(lines)

        try:
            json.loads(cleaned)
            intent = ParsedIntent.model_validate_json(cleaned)
        except (json.JSONDecodeError, ValidationError, ValueError):
            return None

        for expected_index, candidate in enumerate(intent.candidates):
            if candidate.candidate_index != expected_index:
                return None

            if candidate.duration_source == "model_estimate":
                if candidate.duration_evidence is not None:
                    return None
                if not validate_model_duration(
                    candidate.category, candidate.visit_duration_minutes
                ):
                    return None
                continue

            evidence = candidate.duration_evidence
            if evidence is None:
                return None
            if evidence.start < 0 or evidence.end <= evidence.start or evidence.end > len(prompt):
                return None
            if prompt[evidence.start : evidence.end] != evidence.quote:
                return None
            parsed_minutes = parse_duration_text(evidence.quote)
            if parsed_minutes != candidate.visit_duration_minutes or not validate_user_duration(
                candidate.visit_duration_minutes
            ):
                return None

            # Evidence is only needed for boundary validation and must not leave memory models.
            candidate.duration_evidence = None

        return intent
