"""Diagnostic codes, messages, and dropped-stop records."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from vialo.models.base import ApiModel


class DiagnosticCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    INVALID_DATE = "INVALID_DATE"
    INVALID_TIME_WINDOW = "INVALID_TIME_WINDOW"
    OFF_TOPIC = "OFF_TOPIC"
    RATE_LIMITED = "RATE_LIMITED"
    MODEL_OUTPUT_INVALID = "MODEL_OUTPUT_INVALID"
    ORIGIN_NOT_FOUND = "ORIGIN_NOT_FOUND"
    PLACE_NOT_FOUND = "PLACE_NOT_FOUND"
    DUPLICATE_PLACE = "DUPLICATE_PLACE"
    OUTSIDE_LOCALITY = "OUTSIDE_LOCALITY"
    HOURS_UNAVAILABLE = "HOURS_UNAVAILABLE"
    CLOSED_ON_DATE = "CLOSED_ON_DATE"
    LOCAL_TIME_AMBIGUOUS = "LOCAL_TIME_AMBIGUOUS"
    ROUTE_NOT_FOUND = "ROUTE_NOT_FOUND"
    NO_REACHABLE_STOPS = "NO_REACHABLE_STOPS"
    NO_FEASIBLE_ITINERARY = "NO_FEASIBLE_ITINERARY"
    COMPARISON_UNAVAILABLE = "COMPARISON_UNAVAILABLE"
    METRICS_DIVERGED = "METRICS_DIVERGED"
    HANDOFF_UNAVAILABLE = "HANDOFF_UNAVAILABLE"
    SHARE_NOT_FOUND = "SHARE_NOT_FOUND"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    AI_BUDGET_EXCEEDED = "AI_BUDGET_EXCEEDED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    WALKING_ROUTES_BETA = "WALKING_ROUTES_BETA"
    GROUNDING_EXCLUSION = "GROUNDING_EXCLUSION"


class Diagnostic(ApiModel):
    """A single diagnostic entry for the response."""

    code: DiagnosticCode
    message: str
    stop_name: str | None = None
    candidate_index: int | None = None
    detail: dict[str, str | int | bool] | None = Field(default=None)


class DroppedStop(ApiModel):
    """Record for a stop that could not be scheduled."""

    candidate_index: int
    name: str
    reason_code: DiagnosticCode
    reason_detail: str
