"""Pipeline step 3: Compute travel-time matrix via Routes API."""

from __future__ import annotations

from vialo.domain.route_matrix import MatrixEdge, build_matrix
from vialo.models.itinerary import GroundedStop
from vialo.models.providers import GroundedPlace, Location, TravelMode
from vialo.services.routes_client import RoutesClient


def compute_matrix(
    origin: GroundedPlace,
    stops: list[GroundedStop],
    travel_mode: TravelMode,
    client: RoutesClient,
) -> list[list[MatrixEdge]]:
    """Compute the directed travel-time matrix.

    Points are: [origin, stop_0, stop_1, ..., stop_N]
    Matrix is (N+1) x (N+1) directed.
    """
    # Collect all locations: origin first, then stops in order
    locations: list[Location] = [origin.location]
    for stop in stops:
        locations.append(stop.place.location)

    # Call Routes API with all points as both origins and destinations
    elements = client.compute_route_matrix(
        origins=locations,
        destinations=locations,
        travel_mode=travel_mode,
    )

    return build_matrix(elements, len(locations))
