"""Pipeline step 1: Select candidate stops via CandidateSelector."""

from __future__ import annotations

from vialo.models.providers import ParsedIntent
from vialo.services.candidate_selector import CandidateSelector


def select_stops(selector: CandidateSelector, prompt: str) -> ParsedIntent:
    """Orchestrate candidate selection from user prompt.

    Delegates to the configured CandidateSelector implementation.
    """
    return selector.select(prompt)
