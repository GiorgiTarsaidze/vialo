"""DynamoDB place cache repository with split-freshness items."""

from __future__ import annotations

import datetime as dt
import logging
import time
from decimal import Decimal
from typing import Any

import boto3

from vialo.models.cache import (
    CacheDateHours,
    CacheProfile,
    CacheQueryResolution,
    CacheRegularHours,
)
from vialo.models.providers import Location, PhotoAttribution, PlacePhoto

logger = logging.getLogger(__name__)


def _now_epoch() -> int:
    return int(time.time())


def _decimal_to_native(obj: Any) -> Any:
    """Convert DynamoDB Decimal types to Python native types."""
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_native(i) for i in obj]
    return obj


def _get_int(item: dict[str, Any], key: str, default: int = 0) -> int:
    """Safely get an int from a DynamoDB item dict."""
    val = item.get(key, default)
    if isinstance(val, int | Decimal):
        return int(val)
    return default


def _get_str(item: dict[str, Any], key: str, default: str = "") -> str:
    """Safely get a string from a DynamoDB item dict."""
    val = item.get(key, default)
    if isinstance(val, str):
        return val
    return default


def _get_dict(item: dict[str, Any], key: str) -> dict[str, Any]:
    """Safely get a dict from a DynamoDB item."""
    val = item.get(key)
    if isinstance(val, dict):
        return val
    return {}


class PlaceCacheRepository:
    """DynamoDB repository for cached place data with application-checked expiry."""

    def __init__(self, table_name: str, region_name: str = "us-east-1") -> None:
        self._table_name = table_name
        dynamodb = boto3.resource("dynamodb", region_name=region_name)
        self._table = dynamodb.Table(table_name)
        self.hits = 0
        self.misses = 0
        self.errors = 0

    def _get_fresh_item(self, key: dict[str, str]) -> dict[str, Any] | None:
        try:
            raw_item = self._table.get_item(Key=key).get("Item")
        except Exception:
            self.errors += 1
            raise
        if not raw_item or not isinstance(raw_item, dict):
            self.misses += 1
            return None
        item: dict[str, Any] = _decimal_to_native(raw_item)
        if _get_int(item, "expiresAt") <= _now_epoch():
            self.misses += 1
            return None
        self.hits += 1
        return item

    def get_profile(self, place_id: str) -> CacheProfile | None:
        """Get cached profile, returning None if expired or missing."""
        item = self._get_fresh_item({"pk": f"PLACE#{place_id}", "sk": "PROFILE"})
        if item is None:
            return None
        data = _get_dict(item, "data")
        return CacheProfile(
            place_id=data.get("placeId", place_id),
            display_name=data.get("displayName", ""),
            formatted_address=data.get("formattedAddress", ""),
            location=Location(
                latitude=data.get("latitude", 0.0),
                longitude=data.get("longitude", 0.0),
            ),
            primary_type=data.get("primaryType"),
            time_zone_id=data.get("timeZoneId", ""),
            photos=self._parse_photos(data.get("photos", [])),
            fetched_at=dt.datetime.fromisoformat(
                _get_str(item, "fetchedAt", "2000-01-01T00:00:00+00:00")
            ),
            expires_at=_get_int(item, "expiresAt"),
        )

    def get_regular_hours(self, place_id: str) -> CacheRegularHours | None:
        """Get cached regular hours."""
        item = self._get_fresh_item({"pk": f"PLACE#{place_id}", "sk": "HOURS#REGULAR"})
        if item is None:
            return None
        data = _get_dict(item, "data")
        return CacheRegularHours(
            place_id=place_id,
            periods=data.get("periods", []),
            fetched_at=dt.datetime.fromisoformat(
                _get_str(item, "fetchedAt", "2000-01-01T00:00:00+00:00")
            ),
            expires_at=_get_int(item, "expiresAt"),
        )

    def get_date_hours(self, place_id: str, date: str) -> CacheDateHours | None:
        """Get cached date-specific hours."""
        item = self._get_fresh_item({"pk": f"PLACE#{place_id}", "sk": f"HOURS#DATE#{date}"})
        if item is None:
            return None
        data = _get_dict(item, "data")
        return CacheDateHours(
            place_id=place_id,
            date=date,
            periods=data.get("periods", []),
            source=data.get("source", "current"),
            fetched_at=dt.datetime.fromisoformat(
                _get_str(item, "fetchedAt", "2000-01-01T00:00:00+00:00")
            ),
            expires_at=_get_int(item, "expiresAt"),
        )

    def get_query_resolution(self, query_hash: str) -> str | None:
        """Get cached query-to-place_id resolution."""
        item = self._get_fresh_item({"pk": f"QUERY#{query_hash}", "sk": "RESOLUTION"})
        if item is None:
            return None
        data = _get_dict(item, "data")
        place_id = data.get("placeId")
        if isinstance(place_id, str):
            return place_id
        return None

    def put_profile(self, item: CacheProfile) -> None:
        """Store a profile cache item."""
        photos_data = [
            {
                "name": p.name,
                "widthPx": p.width_px,
                "heightPx": p.height_px,
                "authorAttributions": [
                    {"displayName": a.display_name, "uri": a.uri, "photoUri": a.photo_uri}
                    for a in p.author_attributions
                ],
            }
            for p in item.photos
        ]
        self._table.put_item(
            Item={
                "pk": f"PLACE#{item.place_id}",
                "sk": "PROFILE",
                "data": {
                    "placeId": item.place_id,
                    "displayName": item.display_name,
                    "formattedAddress": item.formatted_address,
                    "latitude": Decimal(str(item.location.latitude)),
                    "longitude": Decimal(str(item.location.longitude)),
                    "primaryType": item.primary_type,
                    "timeZoneId": item.time_zone_id,
                    "photos": photos_data,
                },
                "fetchedAt": item.fetched_at.isoformat(),
                "expiresAt": item.expires_at,
            }
        )

    def put_regular_hours(self, item: CacheRegularHours) -> None:
        """Store regular hours cache item."""
        self._table.put_item(
            Item={
                "pk": f"PLACE#{item.place_id}",
                "sk": "HOURS#REGULAR",
                "data": {"periods": item.periods},
                "fetchedAt": item.fetched_at.isoformat(),
                "expiresAt": item.expires_at,
            }
        )

    def put_date_hours(self, item: CacheDateHours) -> None:
        """Store date-specific hours cache item."""
        self._table.put_item(
            Item={
                "pk": f"PLACE#{item.place_id}",
                "sk": f"HOURS#DATE#{item.date}",
                "data": {"periods": item.periods, "source": item.source},
                "fetchedAt": item.fetched_at.isoformat(),
                "expiresAt": item.expires_at,
            }
        )

    def put_query_resolution(self, item: CacheQueryResolution) -> None:
        """Store query resolution cache item."""
        self._table.put_item(
            Item={
                "pk": f"QUERY#{item.query_hash}",
                "sk": "RESOLUTION",
                "data": {"placeId": item.place_id},
                "fetchedAt": item.fetched_at.isoformat(),
                "expiresAt": item.expires_at,
            }
        )

    def _parse_photos(self, photos_data: list[Any]) -> list[PlacePhoto]:
        """Parse photo data from cache."""
        photos: list[PlacePhoto] = []
        for p in photos_data:
            if not isinstance(p, dict):
                continue
            attributions = [
                PhotoAttribution(
                    display_name=a.get("displayName", ""),
                    uri=a.get("uri", ""),
                    photo_uri=a.get("photoUri"),
                )
                for a in p.get("authorAttributions", [])
                if isinstance(a, dict)
            ]
            photos.append(
                PlacePhoto(
                    name=p.get("name", ""),
                    width_px=p.get("widthPx", 0),
                    height_px=p.get("heightPx", 0),
                    author_attributions=attributions,
                )
            )
        return photos
