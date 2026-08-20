"""Pipeline step: bounded evidence-based repair pass for failed candidates.

After initial grounding, failed candidates get one repair attempt where Claude
receives typed diagnostics plus actual Google alternatives and may select a
supplied alternative or emit a concrete replacement query. Re-grounds once.
Never invents/overrides hours. No loop.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from vialo.models.diagnostics import DiagnosticCode
from vialo.models.providers import CandidateStop
from vialo.pipeline.ground_places import GroundingDiagnostic
from vialo.services.places_client import PlacesClient

logger = logging.getLogger(__name__)


@dataclass
class RepairCandidate:
    """A failed candidate with its diagnostic and Google alternatives."""

    candidate: CandidateStop
    diagnostic: GroundingDiagnostic
    alternatives: list[dict[str, str]]


@dataclass
class RepairDecision:
    """Claude's repair decision for one failed candidate."""

    candidate_index: int
    action: str  # "select_alternative" | "replace_query" | "skip"
    selected_place_id: str | None = None
    replacement_query: str | None = None


@dataclass
class RepairResult:
    """Result of the repair pass."""

    repaired_candidates: list[CandidateStop]
    repair_diagnostics: list[GroundingDiagnostic]


def build_repair_context(
    failed: list[GroundingDiagnostic],
    candidates: list[CandidateStop],
    accepted_names: list[str],
    locality: str,
    alternatives_by_index: dict[int, list[dict[str, str]]],
    original_prompt: str,
) -> str:
    """Build typed repair context for Claude."""
    failed_info = []
    for diag in failed:
        alt_list = alternatives_by_index.get(diag.candidate_index, [])
        failed_info.append(
            {
                "candidate_index": diag.candidate_index,
                "name": diag.name,
                "failure_code": diag.code.value,
                "failure_detail": diag.detail,
                "google_alternatives": alt_list[:5],
            }
        )

    context = {
        "task": "repair_failed_candidates",
        "locality": locality,
        "original_intent_summary": original_prompt[:200],
        "accepted_candidates": accepted_names,
        "failed_candidates": failed_info,
        "instructions": (
            "For each failed candidate, either: "
            "(1) select an alternative by its place_id if one matches the original intent, "
            "(2) emit a concrete replacement search query (a specific venue name, not a category), "
            "or (3) skip if no good replacement exists. "
            "Generic categories like 'restaurant' or 'park' are not valid replacement queries — "
            "use specific venue names. Return JSON array of decisions."
        ),
        "response_schema": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "candidate_index": {"type": "integer"},
                    "action": {
                        "type": "string",
                        "enum": ["select_alternative", "replace_query", "skip"],
                    },
                    "selected_place_id": {
                        "type": "string",
                        "description": "Required if action=select_alternative",
                    },
                    "replacement_query": {
                        "type": "string",
                        "description": "Required if action=replace_query",
                    },
                },
                "required": ["candidate_index", "action"],
            },
        },
    }
    return json.dumps(context)


def parse_repair_decisions(response_text: str) -> list[RepairDecision]:
    """Parse Claude's repair decisions from JSON response."""
    try:
        # Strip markdown fences if present
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        data = json.loads(text)
        if not isinstance(data, list):
            return []

        decisions: list[RepairDecision] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            ci = item.get("candidate_index")
            action = item.get("action", "skip")
            if ci is None or action not in ("select_alternative", "replace_query", "skip"):
                continue
            decisions.append(
                RepairDecision(
                    candidate_index=int(ci),
                    action=action,
                    selected_place_id=item.get("selected_place_id"),
                    replacement_query=item.get("replacement_query"),
                )
            )
        return decisions
    except (json.JSONDecodeError, ValueError, TypeError):
        return []


def collect_alternatives(
    failed_diagnostics: list[GroundingDiagnostic],
    candidates: list[CandidateStop],
    locality: str,
    client: PlacesClient,
) -> dict[int, list[dict[str, str]]]:
    """Collect Google alternatives for each failed candidate.

    Uses the original candidate name search results that were already fetched
    during grounding (results that didn't pass the disambiguation filter).
    Re-fetches to get actual alternatives.
    """
    alternatives: dict[int, list[dict[str, str]]] = {}
    candidate_by_index = {c.candidate_index: c for c in candidates}

    for diag in failed_diagnostics:
        if diag.code not in (
            DiagnosticCode.PLACE_NOT_FOUND,
            DiagnosticCode.CLOSED_ON_DATE,
        ):
            continue

        candidate = candidate_by_index.get(diag.candidate_index)
        if candidate is None:
            continue

        try:
            results = client.search_text(candidate.name, locality)
            alt_list: list[dict[str, str]] = []
            for r in results[:5]:
                if r.place_id and r.display_name:
                    alt_list.append(
                        {
                            "place_id": r.place_id,
                            "display_name": r.display_name,
                            "formatted_address": r.formatted_address,
                            "primary_type": r.primary_type or "",
                        }
                    )
            alternatives[diag.candidate_index] = alt_list
        except Exception:
            logger.debug("Failed to collect alternatives for %s", candidate.name)
            alternatives[diag.candidate_index] = []

    return alternatives


def build_top_up_context(
    *,
    locality: str,
    travel_mode: str,
    local_start: str,
    local_end: str,
    requested_date: str,
    accepted_names: list[str],
    rejected_names: list[str],
    wanted: int,
) -> str:
    """Describe the thin day so the selector can propose replacement stops.

    Contains no user prompt text and no provider bodies: only the locality, the
    window, what is already scheduled, and what must not be repeated.
    """
    payload = {
        "locality": locality,
        "travel_mode": travel_mode,
        "date": requested_date,
        "local_start_time": local_start,
        "local_end_time": local_end,
        "already_accepted": accepted_names,
        "do_not_repeat": rejected_names,
        "candidates_wanted": wanted,
    }
    return json.dumps(payload, ensure_ascii=False)
