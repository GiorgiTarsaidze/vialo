"""Direct Google Routes API REST client via httpx."""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import httpx

from vialo.models.providers import Location, TravelMode

logger = logging.getLogger(__name__)

MATRIX_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

MATRIX_FIELD_MASK = "originIndex,destinationIndex,status,condition,distanceMeters,duration"
ROUTES_FIELD_MASK = (
    "routes.distanceMeters,routes.duration,"
    "routes.polyline.encodedPolyline,"
    "routes.legs.distanceMeters,routes.legs.duration"
)


class RoutesClientError(Exception):
    """Raised when Routes API call fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


def _travel_mode_api(mode: TravelMode) -> str:
    """Convert internal travel mode to Routes API enum."""
    if mode == "WALK":
        return "WALK"
    return "DRIVE"


def _location_to_waypoint(loc: Location) -> dict[str, Any]:
    """Convert Location to Routes API waypoint."""
    return {
        "waypoint": {
            "location": {
                "latLng": {
                    "latitude": loc.latitude,
                    "longitude": loc.longitude,
                }
            }
        }
    }


class RoutesClient:
    """Direct REST wrapper for Google Routes API."""

    def __init__(self, api_key: str, timeout: float = 10.0) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def compute_route_matrix(
        self,
        origins: list[Location],
        destinations: list[Location],
        travel_mode: TravelMode,
    ) -> list[dict[str, Any]]:
        """Compute distance/duration matrix between origins and destinations.

        Returns raw element dicts from the API response.
        """
        body: dict[str, Any] = {
            "origins": [_location_to_waypoint(o) for o in origins],
            "destinations": [_location_to_waypoint(d) for d in destinations],
            "travelMode": _travel_mode_api(travel_mode),
        }
        if travel_mode == "DRIVE":
            body["routingPreference"] = "TRAFFIC_UNAWARE"
        headers = {
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": MATRIX_FIELD_MASK,
            "Content-Type": "application/json",
        }

        return self._post_with_retry(MATRIX_URL, body, headers)

    def compute_routes(
        self,
        origin: Location,
        intermediates: list[Location],
        destination: Location,
        travel_mode: TravelMode,
        optimize_waypoint_order: bool = False,
    ) -> dict[str, Any]:
        """Compute a route with optional intermediate waypoints.

        Returns the full API response dict.
        """
        body: dict[str, Any] = {
            "origin": {
                "location": {
                    "latLng": {
                        "latitude": origin.latitude,
                        "longitude": origin.longitude,
                    }
                }
            },
            "destination": {
                "location": {
                    "latLng": {
                        "latitude": destination.latitude,
                        "longitude": destination.longitude,
                    }
                }
            },
            "travelMode": _travel_mode_api(travel_mode),
            "polylineQuality": "HIGH_QUALITY",
            "polylineEncoding": "ENCODED_POLYLINE",
            "optimizeWaypointOrder": optimize_waypoint_order,
        }
        if travel_mode == "DRIVE":
            body["routingPreference"] = "TRAFFIC_UNAWARE"

        if intermediates:
            body["intermediates"] = [
                {
                    "location": {
                        "latLng": {
                            "latitude": loc.latitude,
                            "longitude": loc.longitude,
                        }
                    }
                }
                for loc in intermediates
            ]

        headers = {
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": ROUTES_FIELD_MASK,
            "Content-Type": "application/json",
        }

        response = self._post_with_retry_single(ROUTES_URL, body, headers)
        return response

    def _post_with_retry(
        self, url: str, body: dict[str, Any], headers: dict[str, str]
    ) -> list[dict[str, Any]]:
        """POST with retry, returns list of elements (matrix response is array)."""
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self._client.post(url, json=body, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        return data
                    result: list[dict[str, Any]] = data.get("elements", data.get("rows", []))
                    return result
                if response.status_code in (429, 500, 502, 503):
                    last_error = RoutesClientError(
                        f"Routes API {response.status_code}",
                        status_code=response.status_code,
                    )
                    if attempt < 2:
                        time.sleep(0.5 * (2**attempt) + random.uniform(0, 0.3))
                        continue
                else:
                    raise RoutesClientError(
                        f"Routes API request failed with status {response.status_code}",
                        status_code=response.status_code,
                    )
            except httpx.RequestError:
                last_error = RoutesClientError("Routes API transport unavailable")
                if attempt < 2:
                    time.sleep(0.5 * (2**attempt) + random.uniform(0, 0.3))
                    continue

        raise last_error or RoutesClientError("Routes API request failed")

    def _post_with_retry_single(
        self, url: str, body: dict[str, Any], headers: dict[str, str]
    ) -> dict[str, Any]:
        """POST with retry, returns single dict response."""
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self._client.post(url, json=body, headers=headers)
                if response.status_code == 200:
                    result: dict[str, Any] = response.json()
                    return result
                if response.status_code in (429, 500, 502, 503):
                    last_error = RoutesClientError(
                        f"Routes API {response.status_code}",
                        status_code=response.status_code,
                    )
                    if attempt < 2:
                        time.sleep(0.5 * (2**attempt) + random.uniform(0, 0.3))
                        continue
                else:
                    raise RoutesClientError(
                        f"Routes API request failed with status {response.status_code}",
                        status_code=response.status_code,
                    )
            except httpx.RequestError:
                last_error = RoutesClientError("Routes API transport unavailable")
                if attempt < 2:
                    time.sleep(0.5 * (2**attempt) + random.uniform(0, 0.3))
                    continue

        raise last_error or RoutesClientError("Routes API request failed")

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()
