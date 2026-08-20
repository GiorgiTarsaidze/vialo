"""Models for provider interactions: Claude intent, Places, Routes."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field

from vialo.models.base import ApiModel

TravelMode = Literal["WALK", "DRIVE"]
DurationSource = Literal["user", "model_estimate"]
HoursSource = Literal["current", "regular", "unverified"]


class StopCategory(StrEnum):
    QUICK_VIEWPOINT = "quick_viewpoint"
    LANDMARK = "landmark"
    MUSEUM_GALLERY = "museum_gallery"
    HISTORIC_RELIGIOUS_SITE = "historic_religious_site"
    NEIGHBORHOOD_MARKET_PARK = "neighborhood_market_park"
    FOOD_BREAK = "food_break"
    EXPERIENCE_TOUR = "experience_tour"
    OTHER = "other"


class DurationEvidence(ApiModel):
    """Substring evidence from the user prompt supporting a duration claim."""

    start: int
    end: int
    # A quote can never exceed the 500-character prompt cap it is taken from.
    quote: Annotated[str, Field(min_length=1, max_length=500)]


class CandidateStop(ApiModel):
    """A single candidate stop from the model output."""

    candidate_index: int
    # Model-authored strings are length-bounded because a dropped candidate name
    # is rendered (escaped) in the UI and can persist in an anonymous share.
    name: Annotated[str, Field(min_length=1, max_length=120)]
    category: StopCategory
    priority: int = Field(ge=1, le=3)
    visit_duration_minutes: int = Field(ge=15, le=240)
    duration_source: DurationSource
    duration_evidence: DurationEvidence | None = None


class ParsedIntent(ApiModel):
    """Structured intent parsed from the user's natural-language request."""

    # Bounded for the same reason as CandidateStop.name: the locality label is
    # displayed, and an over-long or injected value must fail validation early.
    locality_query: Annotated[str, Field(min_length=1, max_length=120)]
    origin_query: Annotated[str, Field(min_length=1, max_length=200)]
    requested_date: dt.date | None = None
    local_start_time: dt.time
    local_end_time: dt.time
    travel_mode: TravelMode
    return_to_origin: bool
    candidates: list[CandidateStop] = Field(min_length=1, max_length=9)


class Location(ApiModel):
    """Geographic coordinates."""

    latitude: float
    longitude: float


class PhotoAttribution(ApiModel):
    """Attribution data for a place photo."""

    display_name: str
    uri: str
    photo_uri: str | None = None


class PlacePhoto(ApiModel):
    """A photo resource from Places API."""

    name: str
    width_px: int
    height_px: int
    author_attributions: list[PhotoAttribution]


class GroundedPlace(ApiModel):
    """A place resolved against Google Places API."""

    place_id: str
    display_name: str
    formatted_address: str
    location: Location
    primary_type: str | None = None
    time_zone_id: str
    photos: list[PlacePhoto] = Field(default_factory=list)
    rating: float | None = None
    user_rating_count: int | None = None
    photo_url: str | None = None  # same-origin /api/photos?... URL for first valid photo
