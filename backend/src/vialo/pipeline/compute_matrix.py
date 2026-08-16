"""Pipeline step 3: Compute travel-time matrix via Routes API.

Supports two layouts:
1. Legacy square: [origin, stop0..stopN] as both origins and destinations → (N+1)² elements
2. Rectangular with destination sink: origins=[origin, stops], destinations=[stops, dest]
   → remapped into internal (N+2)×(N+2) matrix. Max elements for N=9: 10×10=100.

The internal matrix is always indexed as:
  0 = origin
  1..N = stops (in grounded order)
  N+1 = destination (if present)

Matrix edges are DIRECTED: matrix[i][j] ≠ matrix[j][i].
"""

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
    destination: GroundedPlace | None = None,
) -> list[list[MatrixEdge]]:
    """Compute the directed travel-time matrix.

    When destination is None (legacy):
        Points: [origin, stop_0, ..., stop_N]
        Matrix: (N+1) × (N+1) square, all-to-all directed.

    When destination is provided:
        Internal matrix: (N+2) × (N+2) where index N+1 = destination.
        API call uses rectangular layout for efficiency:
          origins = [origin, stop_0, ..., stop_N]  (N+1 points)
          destinations = [stop_0, ..., stop_N, destination]  (N+1 points)
        This gives (N+1)² elements. For N=9: 10×10=100 ≤ max 100.

        The origin→origin edge is trivial (0), stop→origin edges are not needed
        (solver goes forward only), and destination→anything is not needed (sink).

    Returns:
        (N+1)×(N+1) or (N+2)×(N+2) directed matrix.
    """
    if destination is None:
        # Legacy square layout
        locations: list[Location] = [origin.location]
        for stop in stops:
            locations.append(stop.place.location)

        elements = client.compute_route_matrix(
            origins=locations,
            destinations=locations,
            travel_mode=travel_mode,
        )
        return build_matrix(elements, len(locations))

    # --- Rectangular layout with destination sink ---
    n_stops = len(stops)
    # Internal matrix size: origin + N stops + destination = N+2
    matrix_size = n_stops + 2

    # Origins: [origin, stop_0, ..., stop_N]  (indices 0..N in call)
    api_origins: list[Location] = [origin.location]
    for stop in stops:
        api_origins.append(stop.place.location)

    # Destinations: [stop_0, ..., stop_N, destination]  (indices 0..N in call)
    api_destinations: list[Location] = []
    for stop in stops:
        api_destinations.append(stop.place.location)
    api_destinations.append(destination.location)

    # Element count: len(api_origins) × len(api_destinations) = (N+1) × (N+1)
    # For N=9: 10 × 10 = 100 ≤ max 100
    elements = client.compute_route_matrix(
        origins=api_origins,
        destinations=api_destinations,
        travel_mode=travel_mode,
    )

    # Build internal (N+2)×(N+2) matrix with explicit remapping
    # Initialize with unreachable defaults and trivial diagonal
    matrix: list[list[MatrixEdge]] = []
    for i in range(matrix_size):
        row: list[MatrixEdge] = []
        for j in range(matrix_size):
            if i == j:
                row.append(
                    MatrixEdge(
                        origin_index=i,
                        destination_index=j,
                        distance_meters=0,
                        duration_seconds=0,
                        reachable=True,
                    )
                )
            else:
                row.append(
                    MatrixEdge(
                        origin_index=i,
                        destination_index=j,
                        distance_meters=None,
                        duration_seconds=None,
                        reachable=False,
                    )
                )
        matrix.append(row)

    # Remap API elements into internal matrix
    # API origin index i maps to internal index i (0=origin, 1..N=stops)
    # API dest index j maps to internal index j+1 (stop_0=1, ..., dest=N+1)
    for elem in elements:
        api_orig_idx = elem.get("originIndex")
        api_dest_idx = elem.get("destinationIndex")
        if api_orig_idx is None or api_dest_idx is None:
            continue

        # Map to internal indices
        internal_orig = api_orig_idx  # 0=origin, 1..N=stops
        internal_dest = api_dest_idx + 1  # 0→1=stop_0, ..., N→N+1=dest

        if internal_orig == internal_dest:
            continue  # diagonal already set

        if internal_orig >= matrix_size or internal_dest >= matrix_size:
            continue

        from vialo.domain.route_matrix import parse_protobuf_duration

        condition = elem.get("condition", "")
        is_reachable = condition == "ROUTE_EXISTS"
        distance = elem.get("distanceMeters")
        duration = parse_protobuf_duration(elem.get("duration"))

        matrix[internal_orig][internal_dest] = MatrixEdge(
            origin_index=internal_orig,
            destination_index=internal_dest,
            distance_meters=distance if is_reachable else None,
            duration_seconds=duration if is_reachable else None,
            reachable=is_reachable,
        )

    return matrix
