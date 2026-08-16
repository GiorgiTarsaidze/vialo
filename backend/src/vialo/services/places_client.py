"""Direct Google Places API REST client via httpx."""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

PLACES_BASE_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_GET_URL = "https://places.googleapis.com/v1/places/"
FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,places.location,"
    "places.primaryType,places.timeZone,places.currentOpeningHours,"
    "places.regularOpeningHours,places.photos,places.rating,places.userRatingCount"
)
FIELD_MASK_GET = (
    "id,displayName,formattedAddress,location,primaryType,timeZone,"
    "currentOpeningHours,regularOpeningHours,photos,rating,userRatingCount"
)
AUTOCOMPLETE_FIELD_MASK = "places.id,places.displayName,places.formattedAddress,places.location"


@dataclass
class PlacesSearchResult:
    """A single result from Places searchText."""

    place_id: str
    display_name: str
    formatted_address: str
    latitude: float
    longitude: float
    primary_type: str | None
    time_zone_id: str | None
    current_opening_hours: dict[str, Any] | None
    regular_opening_hours: dict[str, Any] | None
    photos: list[dict[str, Any]]
    rating: float | None = None
    user_rating_count: int | None = None


class PlacesClientError(Exception):
    """Raised when Places API call fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class PlacesClient:
    """Direct REST wrapper for Google Places API (New)."""

    def __init__(self, api_key: str, timeout: float = 10.0) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def search_text(
        self,
        query: str,
        locality: str,
        *,
        field_mask: str = FIELD_MASK,
    ) -> list[PlacesSearchResult]:
        """Search for places by text, optionally constrained to a locality.

        Retries up to 2 times on 429/5xx with jitter. Callers such as
        autocomplete may request a smaller field mask than full grounding.
        """
        text_query = f"{query} in {locality}" if locality.strip() else query
        body: dict[str, Any] = {
            "textQuery": text_query,
            "pageSize": 5,
            "languageCode": "en",
        }
        headers = {
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": field_mask,
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self._client.post(
                    PLACES_BASE_URL,
                    json=body,
                    headers=headers,
                )
                if response.status_code == 200:
                    return self._parse_response(response.json())
                if response.status_code in (429, 500, 502, 503):
                    last_error = PlacesClientError(
                        f"Places API {response.status_code}",
                        status_code=response.status_code,
                    )
                    if attempt < 2:
                        time.sleep(0.5 * (2**attempt) + random.uniform(0, 0.3))
                        continue
                else:
                    raise PlacesClientError(
                        f"Places API request failed with status {response.status_code}",
                        status_code=response.status_code,
                    )
            except httpx.RequestError:
                last_error = PlacesClientError("Places API transport unavailable")
                if attempt < 2:
                    time.sleep(0.5 * (2**attempt) + random.uniform(0, 0.3))
                    continue

        raise last_error or PlacesClientError("Places API request failed")

    def _parse_response(self, data: dict[str, Any]) -> list[PlacesSearchResult]:
        """Parse Places API response into typed results."""
        results: list[PlacesSearchResult] = []
        places = data.get("places", [])

        for place in places:
            place_id = place.get("id", "")
            display_name_obj = place.get("displayName", {})
            display_name = (
                display_name_obj.get("text", "")
                if isinstance(display_name_obj, dict)
                else str(display_name_obj)
            )
            formatted_address = place.get("formattedAddress", "")
            location = place.get("location", {})
            latitude = location.get("latitude", 0.0)
            longitude = location.get("longitude", 0.0)
            primary_type = place.get("primaryType")

            # Parse IANA timezone from timeZone.id field
            time_zone_obj = place.get("timeZone")
            time_zone_id: str | None = None
            if isinstance(time_zone_obj, dict):
                time_zone_id = time_zone_obj.get("id")

            current_hours = place.get("currentOpeningHours")
            regular_hours = place.get("regularOpeningHours")
            photos = place.get("photos", [])
            rating = place.get("rating")
            user_rating_count = place.get("userRatingCount")

            results.append(
                PlacesSearchResult(
                    place_id=place_id,
                    display_name=display_name,
                    formatted_address=formatted_address,
                    latitude=latitude,
                    longitude=longitude,
                    primary_type=primary_type,
                    time_zone_id=time_zone_id,
                    current_opening_hours=current_hours,
                    regular_opening_hours=regular_hours,
                    photos=photos,
                    rating=float(rating) if rating is not None else None,
                    user_rating_count=(
                        int(user_rating_count) if user_rating_count is not None else None
                    ),
                )
            )

        return results

    def get_place(self, place_id: str) -> PlacesSearchResult | None:
        """Get a single place by ID. Returns None if not found."""
        url = f"{PLACES_GET_URL}{place_id}"
        headers = {
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": FIELD_MASK_GET,
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self._client.get(url, headers=headers)
                if response.status_code == 200:
                    place = response.json()
                    return self._parse_single_place(place)
                if response.status_code == 404:
                    return None
                if response.status_code in (429, 500, 502, 503):
                    last_error = PlacesClientError(
                        f"Places API {response.status_code}",
                        status_code=response.status_code,
                    )
                    if attempt < 2:
                        time.sleep(0.5 * (2**attempt) + random.uniform(0, 0.3))
                        continue
                else:
                    raise PlacesClientError(
                        f"Places API get request failed with status {response.status_code}",
                        status_code=response.status_code,
                    )
            except httpx.RequestError:
                last_error = PlacesClientError("Places API transport unavailable")
                if attempt < 2:
                    time.sleep(0.5 * (2**attempt) + random.uniform(0, 0.3))
                    continue

        raise last_error or PlacesClientError("Places API get request failed")

    def _parse_single_place(self, place: dict[str, Any]) -> PlacesSearchResult:
        """Parse a single Places API place response."""
        place_id = place.get("id", "")
        display_name_obj = place.get("displayName", {})
        display_name = (
            display_name_obj.get("text", "")
            if isinstance(display_name_obj, dict)
            else str(display_name_obj)
        )
        formatted_address = place.get("formattedAddress", "")
        location = place.get("location", {})
        latitude = location.get("latitude", 0.0)
        longitude = location.get("longitude", 0.0)
        primary_type = place.get("primaryType")

        time_zone_obj = place.get("timeZone")
        time_zone_id: str | None = None
        if isinstance(time_zone_obj, dict):
            time_zone_id = time_zone_obj.get("id")

        current_hours = place.get("currentOpeningHours")
        regular_hours = place.get("regularOpeningHours")
        photos = place.get("photos", [])
        rating = place.get("rating")
        user_rating_count = place.get("userRatingCount")

        return PlacesSearchResult(
            place_id=place_id,
            display_name=display_name,
            formatted_address=formatted_address,
            latitude=latitude,
            longitude=longitude,
            primary_type=primary_type,
            time_zone_id=time_zone_id,
            current_opening_hours=current_hours,
            regular_opening_hours=regular_hours,
            photos=photos,
            rating=float(rating) if rating is not None else None,
            user_rating_count=int(user_rating_count) if user_rating_count is not None else None,
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()
