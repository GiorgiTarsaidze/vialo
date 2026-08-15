"""Cache item models for DynamoDB place cache."""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, ConfigDict

from vialo.models.providers import Location, PlacePhoto


class CacheModel(BaseModel):
    """Strict base for cache boundary models."""

    model_config = ConfigDict(strict=True, extra="forbid")


class CacheProfile(CacheModel):
    """Cached place profile data."""

    place_id: str
    display_name: str
    formatted_address: str
    location: Location
    primary_type: str | None = None
    time_zone_id: str
    photos: list[PlacePhoto]
    fetched_at: dt.datetime
    expires_at: int  # epoch seconds


class CacheRegularHours(CacheModel):
    """Cached regular opening hours."""

    place_id: str
    periods: list[dict[str, Any]]
    fetched_at: dt.datetime
    expires_at: int


class CacheDateHours(CacheModel):
    """Cached date-specific opening hours."""

    place_id: str
    date: str  # YYYY-MM-DD
    periods: list[dict[str, Any]]
    source: str  # "current" or "regular"
    fetched_at: dt.datetime
    expires_at: int


class CacheQueryResolution(CacheModel):
    """Cached query-to-place_id resolution."""

    query_hash: str
    place_id: str
    fetched_at: dt.datetime
    expires_at: int
