"""Anthropic Claude adapter behind the provider-neutral candidate selector boundary."""

from __future__ import annotations

import json
from typing import Any

import anthropic
from pydantic import ValidationError

from vialo.domain.duration_bounds import (
    parse_duration_text,
    validate_model_duration,
    validate_user_duration,
)
from vialo.models.diagnostics import DiagnosticCode
from vialo.models.providers import ParsedIntent
from vialo.services.candidate_selector import SelectorError

SYSTEM_PROMPT = """\
Extract a typed one-day city itinerary request. Return JSON only with:
locality_query, origin_query, requested_date (YYYY-MM-DD or null), local_start_time
(HH:MM), local_end_time (HH:MM), travel_mode (WALK or DRIVE), return_to_origin,
and 1-9 candidates. Candidate indices must be unique and sequential from zero.
Each candidate has name, category, priority 1-3, visit_duration_minutes,
duration_source, and duration_evidence.

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


class AnthropicCandidateSelector:
    """Production Claude adapter implementing CandidateSelector."""

    def __init__(self, api_key: str, model_id: str, timeout: float = 25.0) -> None:
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        self._model_id = model_id

    def select(self, prompt: str) -> ParsedIntent:
        """Call Claude, validate deterministically, and allow one repair attempt."""
        try:
            response = self._client.messages.create(
                model=self._model_id,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
        except (anthropic.APITimeoutError, anthropic.APIError) as exc:
            raise SelectorError(
                code=DiagnosticCode.PROVIDER_UNAVAILABLE,
                message="Candidate provider unavailable",
            ) from exc

        text = self._extract_text(response)
        intent = self._parse_response(text, prompt) if text is not None else None
        if intent is not None:
            return intent

        repaired = self._repair(prompt, text or "")
        if repaired is None:
            raise SelectorError(
                code=DiagnosticCode.MODEL_OUTPUT_INVALID,
                message="Model output failed validation after repair attempt",
            )
        return repaired

    def _extract_text(self, response: Any) -> str | None:
        """Extract the first text content block."""
        for block in response.content:
            if block.type == "text":
                return str(block.text)
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

    def _repair(self, prompt: str, failed_output: str) -> ParsedIntent | None:
        """Request one schema-and-bound repair without logging provider content."""
        messages: list[dict[str, str]] = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": failed_output},
            {
                "role": "user",
                "content": (
                    "Repair the JSON to satisfy the schema, sequential indices, exact "
                    "user-duration evidence, and category bounds in the system prompt. "
                    "Return JSON only."
                ),
            },
        ]
        try:
            response = self._client.messages.create(
                model=self._model_id,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=messages,  # type: ignore[arg-type]
            )
        except anthropic.APIError:
            return None
        text = self._extract_text(response)
        return self._parse_response(text, prompt) if text is not None else None
