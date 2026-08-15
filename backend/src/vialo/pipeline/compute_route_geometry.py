"""Pipeline step 5a: Compute route geometry for both orders."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from vialo.domain.route_matrix import parse_protobuf_duration
from vialo.models.itinerary import GroundedStop
from vialo.models.providers import GroundedPlace, TravelMode
from vialo.services.routes_client import RoutesClient, RoutesClientError

logger = logging.getLogger(__name__)


@dataclass
class RouteGeometry:
    """Geometry and metrics for a single route order."""

    polyline: str
    total_distance_meters: int
    total_duration_seconds: int
    stop_order: list[int]


def compute_route_geometry(
    origin: GroundedPlace,
    ordered_stops: list[GroundedStop],
    travel_mode: TravelMode,
    client: RoutesClient,
    return_to_origin: bool,
) -> RouteGeometry | None:
    """Compute route geometry for a given stop order.

    Returns None if the geometry call fails.
    """
    if not ordered_stops:
        return None

    intermediates = [s.place.location for s in ordered_stops[:-1]] if len(ordered_stops) > 1 else []

    if return_to_origin:
        destination = origin.location
        if ordered_stops:
            intermediates = [s.place.location for s in ordered_stops]
    else:
        destination = ordered_stops[-1].place.location

    try:
        response = client.compute_routes(
            origin=origin.location,
            intermediates=intermediates,
            destination=destination,
            travel_mode=travel_mode,
            optimize_waypoint_order=False,
        )
    except RoutesClientError as e:
        logger.warning("Route geometry computation failed: %s", e)
        return None

    routes = response.get("routes", [])
    if not routes:
        return None

    route = routes[0]
    polyline = route.get("polyline", {}).get("encodedPolyline", "")
    if not polyline:
        return None

    # Parse total metrics using the shared protobuf duration parser
    total_distance = route.get("distanceMeters", 0)
    total_duration = parse_protobuf_duration(route.get("duration")) or 0

    stop_order = [s.candidate_index for s in ordered_stops]

    return RouteGeometry(
        polyline=polyline,
        total_distance_meters=total_distance,
        total_duration_seconds=total_duration,
        stop_order=stop_order,
    )
