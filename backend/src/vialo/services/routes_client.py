"""Direct Google Routes API REST client via httpx."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Sequence
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class RoutePoint:
    """A routing waypoint that prefers a verified place ID over raw coordinates.

    Raw `latLng` is snapped by Google to the nearest routable edge, which in
    cities with sparse pedestrian data lands on a car road or the wrong side of
    a block. A `placeId` routes to the establishment's own entrance instead, so
    both the measured matrix and the drawn geometry follow the way a person
    actually walks. Coordinates remain as the fallback when no ID is available.
    """

    location: Location
    place_id: str | None = None


RoutePointLike = Location | RoutePoint


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


def _as_route_point(value: RoutePointLike) -> RoutePoint:
    """Accept either a bare Location or a RoutePoint."""
    if isinstance(value, RoutePoint):
        return value
    return RoutePoint(location=value)


def _waypoint_body(value: RoutePointLike) -> dict[str, Any]:
    """Build one Routes API waypoint, preferring the verified place ID."""
    point = _as_route_point(value)
    if point.place_id:
        return {"placeId": point.place_id}
    return {
        "location": {
            "latLng": {
                "latitude": point.location.latitude,
                "longitude": point.location.longitude,
            }
        }
    }


def _location_to_waypoint(value: RoutePointLike) -> dict[str, Any]:
    """Wrap a waypoint for the matrix request shape."""
    return {"waypoint": _waypoint_body(value)}


class RoutesClient:
    """Direct REST wrapper for Google Routes API."""

    def __init__(self, api_key: str, timeout: float = 10.0) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def compute_route_matrix(
        self,
        origins: Sequence[RoutePointLike],
        destinations: Sequence[RoutePointLike],
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
        origin: RoutePointLike,
        intermediates: Sequence[RoutePointLike],
        destination: RoutePointLike,
        travel_mode: TravelMode,
        optimize_waypoint_order: bool = False,
    ) -> dict[str, Any]:
        """Compute a route with optional intermediate waypoints.

        Returns the full API response dict.
        """
        body: dict[str, Any] = {
            "origin": _waypoint_body(origin),
            "destination": _waypoint_body(destination),
            "travelMode": _travel_mode_api(travel_mode),
            "polylineQuality": "HIGH_QUALITY",
            "polylineEncoding": "ENCODED_POLYLINE",
            "optimizeWaypointOrder": optimize_waypoint_order,
        }
        if travel_mode == "DRIVE":
            body["routingPreference"] = "TRAFFIC_UNAWARE"
        else:
            # Walking only: keep the drawn route outdoors instead of cutting
            # through malls, stations, and passages a visitor cannot rely on.
            body["routeModifiers"] = {"avoidIndoor": True}

        if intermediates:
            body["intermediates"] = [_waypoint_body(point) for point in intermediates]

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
