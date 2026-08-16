"""Naive-order simulation for comparison baseline.

Key fix: preserve full original matrix index mapping after solver drops.
No fallback index. The matrix indices are based on the ORIGINAL grounded stop
list position (1-indexed), not the retained-only sublist.
"""

from __future__ import annotations

import datetime as dt

from vialo.domain.route_matrix import MatrixEdge
from vialo.models.itinerary import (
    GroundedStop,
    OpenInterval,
    TravelEntry,
    VisitEntry,
    WaitEntry,
)
from vialo.models.providers import TravelMode


def _find_open_interval(
    stop: GroundedStop,
    arrival: dt.datetime,
    visit_duration: dt.timedelta,
) -> OpenInterval | None:
    """Find an interval where the stop can be visited."""
    for interval in stop.open_intervals:
        effective_start = max(arrival, interval.start)
        effective_end = effective_start + visit_duration
        if effective_end <= interval.end:
            return interval
    return None


def simulate_naive_order(
    retained_stops: list[GroundedStop],
    candidate_order: list[int],
    origin_index: int,
    matrix: list[list[MatrixEdge]],
    window_start: dt.datetime,
    window_end: dt.datetime,
    return_to_origin: bool,
    travel_mode: TravelMode = "WALK",
    original_matrix_indices: dict[int, int] | None = None,
    destination_index: int | None = None,
) -> tuple[list[TravelEntry | WaitEntry | VisitEntry], bool, list[str]]:
    """Simulate the naive (original candidate) order.

    Args:
        retained_stops: The stops that were retained after dropping.
        candidate_order: The original candidate indices in naive order.
        origin_index: Matrix index of origin (0).
        matrix: The full directed matrix (sized for ALL original grounded stops).
        window_start: Start of time window.
        window_end: End of time window.
        return_to_origin: Whether to return to origin.
        travel_mode: WALK or DRIVE.
        original_matrix_indices: Mapping from candidate_index to matrix index.
            If provided, uses this mapping directly instead of computing from
            retained_stops position. This preserves correct indices even after drops.
        destination_index: If set, mandatory final travel leg to this matrix index.
            Overrides return_to_origin in the simulation.

    Returns:
        Tuple of (timeline, feasible, infeasibility_codes).
    """
    # Sort retained stops by their position in candidate_order
    stop_map = {s.candidate_index: s for s in retained_stops}
    ordered_candidate_indices = [ci for ci in candidate_order if ci in stop_map]
    ordered_stops = [stop_map[ci] for ci in ordered_candidate_indices]

    if original_matrix_indices is None:
        raise ValueError("original_matrix_indices is required for an honest naive baseline")
    matrix_idx_map = original_matrix_indices

    timeline: list[TravelEntry | WaitEntry | VisitEntry] = []
    infeasibility_codes: list[str] = []
    feasible = True
    current_time = window_start
    prev_matrix_idx = origin_index

    for stop in ordered_stops:
        stop_matrix_idx = matrix_idx_map.get(stop.candidate_index)
        if stop_matrix_idx is None:
            feasible = False
            infeasibility_codes.append(f"MISSING_INDEX:{stop.name}")
            break

        # Bounds check
        if stop_matrix_idx >= len(matrix) or stop_matrix_idx >= len(matrix[prev_matrix_idx]):
            feasible = False
            infeasibility_codes.append(f"INDEX_OUT_OF_BOUNDS:{stop.name}")
            break

        edge = matrix[prev_matrix_idx][stop_matrix_idx]
        if not edge.reachable or edge.duration_seconds is None:
            feasible = False
            infeasibility_codes.append(f"UNREACHABLE:{stop.name}")
            break

        travel_seconds = edge.duration_seconds
        distance_meters = edge.distance_meters or 0
        departure = current_time
        arrival = current_time + dt.timedelta(seconds=travel_seconds)

        timeline.append(
            TravelEntry(
                type="travel",
                from_index=prev_matrix_idx,
                to_index=stop_matrix_idx,
                mode=travel_mode,
                duration_seconds=travel_seconds,
                distance_meters=distance_meters,
                departure=departure,
                arrival=arrival,
            )
        )
        current_time = arrival

        visit_duration = dt.timedelta(minutes=stop.visit_duration_minutes)
        interval = _find_open_interval(stop, current_time, visit_duration)

        if interval is None:
            feasible = False
            infeasibility_codes.append(f"CLOSED_ON_ARRIVAL:{stop.name}")
            break

        # Wait if needed
        if current_time < interval.start:
            wait_seconds = int((interval.start - current_time).total_seconds())
            timeline.append(
                WaitEntry(
                    type="wait",
                    stop_index=stop_matrix_idx,
                    duration_seconds=wait_seconds,
                    wait_start=current_time,
                    wait_end=interval.start,
                    reason=f"opens {interval.local_start}",
                )
            )
            current_time = interval.start

        visit_end = current_time + visit_duration
        if visit_end > window_end:
            feasible = False
            infeasibility_codes.append(f"EXCEEDS_WINDOW:{stop.name}")
            break
        if visit_end > interval.end:
            feasible = False
            infeasibility_codes.append(f"EXCEEDS_CLOSING:{stop.name}")
            break

        timeline.append(
            VisitEntry(
                type="visit",
                stop_index=stop_matrix_idx,
                arrival=current_time,
                departure=visit_end,
                duration_minutes=stop.visit_duration_minutes,
                interval_used=interval,
            )
        )
        current_time = visit_end
        prev_matrix_idx = stop_matrix_idx

    # Final leg: destination or return to origin
    if feasible and destination_index is not None:
        edge = matrix[prev_matrix_idx][destination_index]
        if not edge.reachable or edge.duration_seconds is None:
            feasible = False
            infeasibility_codes.append("DESTINATION_UNREACHABLE")
        else:
            travel_seconds = edge.duration_seconds
            distance_meters = edge.distance_meters or 0
            departure = current_time
            arrival = current_time + dt.timedelta(seconds=travel_seconds)
            if arrival > window_end:
                feasible = False
                infeasibility_codes.append("DESTINATION_EXCEEDS_WINDOW")
            else:
                timeline.append(
                    TravelEntry(
                        type="travel",
                        from_index=prev_matrix_idx,
                        to_index=destination_index,
                        mode=travel_mode,
                        duration_seconds=travel_seconds,
                        distance_meters=distance_meters,
                        departure=departure,
                        arrival=arrival,
                    )
                )
    elif feasible and return_to_origin:
        edge = matrix[prev_matrix_idx][origin_index]
        if not edge.reachable or edge.duration_seconds is None:
            feasible = False
            infeasibility_codes.append("RETURN_UNREACHABLE")
        else:
            travel_seconds = edge.duration_seconds
            distance_meters = edge.distance_meters or 0
            departure = current_time
            arrival = current_time + dt.timedelta(seconds=travel_seconds)
            if arrival > window_end:
                feasible = False
                infeasibility_codes.append("RETURN_EXCEEDS_WINDOW")
            else:
                timeline.append(
                    TravelEntry(
                        type="travel",
                        from_index=prev_matrix_idx,
                        to_index=origin_index,
                        mode=travel_mode,
                        duration_seconds=travel_seconds,
                        distance_meters=distance_meters,
                        departure=departure,
                        arrival=arrival,
                    )
                )

    return timeline, feasible, infeasibility_codes
