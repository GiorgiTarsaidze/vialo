"""Provider-neutral Protocol for candidate stop selection."""

from __future__ import annotations

from typing import Protocol

from vialo.models.providers import CandidateStop, ParsedIntent


class CandidateSelector(Protocol):
    """Protocol for selecting candidate stops from a user prompt."""

    def select(self, prompt: str) -> ParsedIntent:
        """Parse user prompt and return structured intent with candidate stops.

        Raises:
            SelectorError: If the model output is invalid or the provider is unavailable.
        """
        ...

    def top_up(self, top_up_context: str, next_candidate_index: int) -> list[CandidateStop]:
        """Return extra validated candidates when grounding left the day too thin.

        Implementations must renumber candidates from next_candidate_index and
        must never return prose. An empty list means no usable suggestion.

        Raises:
            SelectorError: If the provider is unavailable.
        """
        ...


class SelectorError(Exception):
    """Raised when candidate selection fails."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)
