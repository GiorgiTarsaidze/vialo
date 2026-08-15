"""Itinerary response models: timeline, comparison, handoff, and full response."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from pydantic import Field

from vialo.models.base import ApiModel
from vialo.models.diagnostics import Diagnostic, DroppedStop
from vialo.models.providers import (
    DurationSource,
    GroundedPlace,
    HoursSource,
    StopCategory,
    TravelMode,
)


class OpenInterval(ApiModel):
    """A time interval when a place is open."""

    start: dt.datetime
    end: dt.datetime
    local_start: str
    local_end: str


class GroundedStop(ApiModel):
    """A verified stop with place data and opening intervals."""

    candidate_index: int
    name: str
    category: StopCategory
    priority: int
    visit_duration_minutes: int = Field(ge=15, le=240)
    duration_source: DurationSource
    place: GroundedPlace
    hours_source: HoursSource
    open_intervals: list[OpenInterval]


class TravelEntry(ApiModel):
    """A travel leg between two stops."""

    type: Literal["travel"] = "travel"
    from_index: int
    to_index: int
    mode: TravelMode
    duration_seconds: int
    distance_meters: int
    departure: dt.datetime
    arrival: dt.datetime


class WaitEntry(ApiModel):
    """A wait period before a stop opens."""

    type: Literal["wait"] = "wait"
    stop_index: int
    duration_seconds: int
    wait_start: dt.datetime
    wait_end: dt.datetime
    reason: str


class VisitEntry(ApiModel):
    """Time spent at a stop."""

    type: Literal["visit"] = "visit"
    stop_index: int
    arrival: dt.datetime
    departure: dt.datetime
    duration_minutes: int
    interval_used: OpenInterval


TimelineEntry = Annotated[
    TravelEntry | WaitEntry | VisitEntry,
    Field(discriminator="type"),
]


class TimeWindow(ApiModel):
    """The user's requested time window."""

    start: dt.datetime
    end: dt.datetime
    local_start: str
    local_end: str
    date: dt.date


class Locality(ApiModel):
    """The resolved city/locality."""

    name: str
    time_zone_id: str


class RouteMetrics(ApiModel):
    """Distance and duration totals for a route order."""

    total_distance_meters: int
    total_duration_seconds: int
    stop_order: list[int]


class RouteComparison(ApiModel):
    """Available naive-vs-optimized comparison."""

    status: Literal["available"] = "available"
    naive: RouteMetrics
    optimized: RouteMetrics
    naive_polyline: str
    optimized_polyline: str
    distance_delta_meters: int
    duration_delta_seconds: int
    naive_feasible: bool
    naive_infeasibility_codes: list[str] = Field(default_factory=list)
    outcome: Literal["improved", "same_order", "no_reordering_needed", "metrics_diverged"]


class ComparisonUnavailable(ApiModel):
    """Comparison cannot be computed."""

    status: Literal["unavailable"] = "unavailable"
    reason_code: str


class MapsHandoffPart(ApiModel):
    """One browser-safe segment of the Google Maps URL."""

    part: int
    total_parts: int
    start_stop_index: int
    end_stop_index: int
    url: str


class MapsHandoff(ApiModel):
    """Google Maps handoff URLs."""

    full_route_url: str | None = None
    full_route_universally_supported: bool
    browser_safe_parts: list[MapsHandoffPart]
    warning_code: Literal["MOBILE_WAYPOINT_LIMIT", "FULL_URL_TOO_LONG"] | None = None
    error_code: Literal["HANDOFF_UNAVAILABLE"] | None = None


class Totals(ApiModel):
    """Aggregate time totals for the itinerary."""

    visit_seconds: int
    travel_seconds: int
    wait_seconds: int
    elapsed_seconds: int


class ShareProof(ApiModel):
    """Proof of itinerary authorship for sharing."""

    expires_at: dt.datetime
    hmac: str


ComparisonResult = Annotated[
    RouteComparison | ComparisonUnavailable,
    Field(discriminator="status"),
]


class ItineraryResponse(ApiModel):
    """The complete itinerary response."""

    schema_version: Literal[1] = 1
    request_id: str
    status: Literal["complete", "partial"]
    locality: Locality
    travel_mode: TravelMode
    window: TimeWindow
    origin: GroundedPlace
    stops: list[GroundedStop]
    timeline: list[TimelineEntry]
    dropped_stops: list[DroppedStop]
    comparison: ComparisonResult
    maps_handoff: MapsHandoff
    totals: Totals
    diagnostics: list[Diagnostic]
    share_proof: ShareProof | None = None
