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
from vialo.models.providers import CandidateStop, ParsedIntent
from vialo.services.candidate_selector import SelectorError
from vialo.services.spend_limiter import BedrockSpendLimiter, BudgetExceededError

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Extract a typed one-day city itinerary request. Return JSON only with:
locality_query, origin_query, requested_date (YYYY-MM-DD or null), local_start_time
(HH:MM), local_end_time (HH:MM), travel_mode (WALK or DRIVE), return_to_origin,
and candidates. Every candidate object must contain the exact key candidate_index
(not index), with unique integer values sequential from zero. Each candidate also has name,
category, priority 1-3, visit_duration_minutes, duration_source, and duration_evidence.

## Candidate count: fit the time budget, then add spares

Determine the number of candidates based on the explicit time budget, then append
2 extra spare ideas so the day can still be filled if a stop turns out to be
unverifiable or closed. Do NOT default to 9.

Calculation:
- Total available time = local_end_time minus local_start_time.
- Estimate walking transit overhead: WALK ~8-12 min between nearby stops; DRIVE ~10-20 min
  between city-scale stops.
- Sum estimated visit durations plus transit overhead. The primary candidates must plausibly
  fit within the total available time.
- For a 3-hour walking window, 2-4 primary candidates is typical.
- For a 5-hour walking window, 4-6 primary candidates is typical.
- For an 8-10 hour full day, 6-9 primary candidates may be appropriate.
- Then add 2 spare candidates with priority 3, ordered last, never exceeding 9 candidates
  in total. Spares are genuinely worth seeing, geographically coherent with the others, and
  ideally shorter or closer than the primaries. They are dropped first if the day cannot fit
  everything, so never place an essential sight at priority 3.
- Never pad with filler. If there is nothing else worth seeing nearby, return fewer.

## Travel mode determines candidate character

WALK means PEDESTRIAN travel between stops:
- All candidates must be pedestrian-appropriate: reachable on foot from neighboring stops.
- Prefer stops within a walkable radius (typically 2-4 km total route extent for a half day).
- Do not suggest stops that require a car, ferry, or transit to reach from the general area.

DRIVE means VEHICLE travel between stops:
- Candidates may be spread across a wider geographic area.
- Include destinations that make sense as driving stops (parking availability, roadside access).
- A driving day can cover suburbs, coastal towns, viewpoints outside the city center, etc.

## Geographic layout of candidates

A deterministic solver (not you) will choose the final visit order using real travel-time
data. Your job is to propose candidates that are geographically coherent so that an
efficient route EXISTS among them.

When return_to_origin is FALSE (distinct start and end points):
- Prefer candidates that lie in a forward corridor between origin and destination.
- Minimize candidates that would require significant backtracking from the general
  origin-to-destination direction.

When return_to_origin is TRUE (loop back to start):
- Prefer candidates that can form a compact loop from the origin.
- Favor varied streets and neighborhoods where your knowledge supports it, but never
  claim or guarantee any specific route geometry or scenic quality — that depends on the
  real route the solver computes.

In both cases:
- Geographic clustering is good: candidates near each other reduce transit waste.
- Do NOT choose the order of visits — the exact solver handles that optimally.
- Do NOT claim route-level guarantees about scenery, minimal backtracking in the final
  route, or specific walking paths. You select WHAT to visit; the solver decides WHEN
  and in what ORDER.

## Categories and duration bounds (min/default/max minutes)

- quick_viewpoint: 15/20/30
- landmark: 30/45/75
- museum_gallery: 60/90/180
- historic_religious_site: 30/60/120
- neighborhood_market_park: 30/60/120
- food_break: 30/60/120
- experience_tour: 60/120/240
- other: 30/60/90

## Duration evidence rules

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

# Upper bound on how many stops a single top-up call may contribute.
MAX_TOP_UP_CANDIDATES = 6


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

    def repair(self, repair_context: str) -> str:
        """Call Bedrock Converse for candidate repair exactly once.

        Uses the same spend limiter for atomic budget control.
        Returns the raw text response for parsing by the caller.

        Raises:
            BudgetExceededError: If budget cap would be exceeded.
            SelectorError: If Bedrock call fails.
        """
        system = [
            {
                "text": (
                    "You are a repair agent for a travel itinerary planner. "
                    "Given failed candidates with their diagnostics and "
                    "Google-supplied alternatives, "
                    "decide how to fix each one. "
                    "Return ONLY a JSON array of decisions. "
                    "Do not emit prose or markdown fences."
                )
            }
        ]
        messages: list[dict[str, Any]] = [{"role": "user", "content": [{"text": repair_context}]}]

        try:
            response = self._call_converse_with_budget(system, messages)
        except BudgetExceededError:
            raise
        except (BotoCoreError, ClientError) as exc:
            raise SelectorError(
                code=DiagnosticCode.PROVIDER_UNAVAILABLE,
                message="Repair provider unavailable",
            ) from exc

        text = self._extract_text(response)
        if text is None:
            raise SelectorError(
                code=DiagnosticCode.MODEL_OUTPUT_INVALID,
                message="Repair returned empty response",
            )
        return text

    def top_up(self, top_up_context: str, next_candidate_index: int) -> list[CandidateStop]:
        """Ask for replacement candidates when grounding left the day too thin.

        One bounded call, its own reservation, and no prose. Every returned
        candidate is schema-validated and category-bounded exactly like an
        initial selection, then grounded through Places like any other stop, so
        a top-up can never inject an unverified place or invented hours.

        Returns an empty list when the model returns nothing usable.

        Raises:
            BudgetExceededError: If budget cap would be exceeded.
            SelectorError: If the provider is unavailable.
        """
        system = [
            {
                "text": (
                    "You extend a partially built one-day city itinerary. Some stops could "
                    "not be verified against Google Places, so the day is too thin. Return "
                    'ONLY JSON of the form {"candidates": [...]} with additional stops that '
                    "are worth visiting, are inside the stated locality, and are "
                    "geographically coherent with the stops already accepted. Never repeat an "
                    "accepted or rejected name. Each candidate object contains the exact keys "
                    "candidate_index, name, category, priority, visit_duration_minutes, "
                    "duration_source, and duration_evidence. Use duration_source "
                    '"model_estimate" and duration_evidence null. Respect the category '
                    "duration ranges: quick_viewpoint 15-30, landmark 30-75, museum_gallery "
                    "60-180, historic_religious_site 30-120, neighborhood_market_park 30-120, "
                    "food_break 30-120, experience_tour 60-240, other 30-90. Prefer stops "
                    "that are open long hours and well known enough to be findable. Do not "
                    "emit prose or markdown fences."
                )
            }
        ]
        messages: list[dict[str, Any]] = [{"role": "user", "content": [{"text": top_up_context}]}]

        try:
            response = self._call_converse_with_budget(system, messages)
        except BudgetExceededError:
            raise
        except (BotoCoreError, ClientError) as exc:
            raise SelectorError(
                code=DiagnosticCode.PROVIDER_UNAVAILABLE,
                message="Top-up provider unavailable",
            ) from exc

        text = self._extract_text(response)
        if text is None:
            return []
        return self._parse_top_up(text, next_candidate_index)

    def _parse_top_up(self, text: str, next_candidate_index: int) -> list[CandidateStop]:
        """Validate top-up candidates and renumber them after the existing ones."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()[1:]
            if lines and lines[-1].strip() == "```":
                lines.pop()
            cleaned = "\n".join(lines)

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            return []

        raw_candidates = payload.get("candidates") if isinstance(payload, dict) else payload
        if not isinstance(raw_candidates, list):
            return []

        accepted: list[CandidateStop] = []
        for raw in raw_candidates:
            if not isinstance(raw, dict):
                continue
            data = dict(raw)
            # The index is ours to assign; the model must not renumber existing stops.
            data["candidate_index"] = next_candidate_index + len(accepted)
            data["duration_source"] = "model_estimate"
            data["duration_evidence"] = None
            try:
                # JSON mode: the strict Python-mode validator rejects plain
                # strings for enums, and the model speaks JSON.
                candidate = CandidateStop.model_validate_json(json.dumps(data, ensure_ascii=False))
            except (ValidationError, TypeError, ValueError):
                continue
            if not validate_model_duration(candidate.category, candidate.visit_duration_minutes):
                continue
            accepted.append(candidate)
            if len(accepted) >= MAX_TOP_UP_CANDIDATES:
                break
        return accepted

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
