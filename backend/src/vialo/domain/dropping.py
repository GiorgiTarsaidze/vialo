"""Deterministic stop dropping when no feasible itinerary exists."""

from __future__ import annotations

import datetime as dt

from vialo.domain.route_matrix import MatrixEdge
from vialo.domain.solver import FeasibleSchedule, solve_exact
from vialo.models.diagnostics import DiagnosticCode, DroppedStop
from vialo.models.itinerary import GroundedStop
from vialo.models.providers import TravelMode


def rank_for_dropping(stops: list[GroundedStop]) -> list[int]:
    """Return stop list indices in deterministic removal order.

    Priority for dropping (first dropped = least essential):
    1. Lower priority number = less essential (priority 3 dropped first? No: priority 1 is highest)
       Actually: priority 1 = most important, 3 = least important. Drop priority 3 first.
    2. Among same priority: narrower open windows (harder to schedule)
    3. Among same priority and windows: longer visit duration
    4. Among ties: later candidate_index
    """

    def drop_sort_key(idx: int) -> tuple[int, int, int, int]:
        stop = stops[idx]
        # Negate priority so priority 3 sorts first (to be dropped first)
        neg_priority = -stop.priority
        # Total open window duration (less = drop first)
        total_open_seconds = sum(
            int((iv.end - iv.start).total_seconds()) for iv in stop.open_intervals
        )
        # Longer duration = harder to fit = drop first (negate for ascending sort)
        neg_duration = -stop.visit_duration_minutes
        # Later index = drop first (negate)
        neg_index = -stop.candidate_index
        return (neg_priority, total_open_seconds, neg_duration, neg_index)

    indices = list(range(len(stops)))
    indices.sort(key=drop_sort_key)
    return indices


def solve_with_dropping(
    stops: list[GroundedStop],
    origin_index: int,
    matrix: list[list[MatrixEdge]],
    window_start: dt.datetime,
    window_end: dt.datetime,
    return_to_origin: bool,
    travel_mode: TravelMode = "WALK",
    destination_index: int | None = None,
) -> tuple[FeasibleSchedule, list[DroppedStop]] | None:
    """Progressively drop stops until a feasible schedule is found.

    Returns:
        Tuple of (schedule, dropped_stops) or None if even a single stop is infeasible.
    """
    dropped: list[DroppedStop] = []
    remaining_indices = list(range(len(stops)))
    remaining_stops = list(stops)

    while remaining_stops:
        # Build a sub-matrix for current stops
        # Matrix indices: 0=origin, 1..N = stops in remaining order
        # If destination_index is set, include it as the last index
        orig_indices = [origin_index] + [idx + 1 for idx in remaining_indices]

        # If destination exists, include it in sub-matrix
        sub_dest_index: int | None = None
        if destination_index is not None:
            orig_indices.append(destination_index)
            sub_dest_index = len(orig_indices) - 1

        n = len(orig_indices)
        sub_matrix: list[list[MatrixEdge]] = []

        for i in range(n):
            row: list[MatrixEdge] = []
            for j in range(n):
                orig_edge = matrix[orig_indices[i]][orig_indices[j]]
                row.append(
                    MatrixEdge(
                        origin_index=i,
                        destination_index=j,
                        distance_meters=orig_edge.distance_meters,
                        duration_seconds=orig_edge.duration_seconds,
                        reachable=orig_edge.reachable,
                    )
                )
            sub_matrix.append(row)

        schedule = solve_exact(
            stops=remaining_stops,
            origin_index=0,
            matrix=sub_matrix,
            window_start=window_start,
            window_end=window_end,
            return_to_origin=return_to_origin,
            travel_mode=travel_mode,
            destination_index=sub_dest_index,
        )

        if schedule is not None:
            return schedule, dropped

        # Drop the least essential stop
        drop_order = rank_for_dropping(remaining_stops)
        drop_idx = drop_order[0]
        dropped_stop = remaining_stops[drop_idx]

        dropped.append(
            DroppedStop(
                candidate_index=dropped_stop.candidate_index,
                name=dropped_stop.name,
                reason_code=DiagnosticCode.NO_FEASIBLE_ITINERARY,
                reason_detail=(
                    f"Dropped to find a feasible schedule; "
                    f"visit requires {dropped_stop.visit_duration_minutes} min"
                ),
            )
        )

        remaining_stops.pop(drop_idx)
        remaining_indices.pop(drop_idx)

    return None
