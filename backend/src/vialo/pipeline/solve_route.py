"""Pipeline step 4: Solve optimal route ordering."""

from __future__ import annotations

import datetime as dt

from vialo.domain.dropping import solve_with_dropping
from vialo.domain.route_matrix import MatrixEdge
from vialo.domain.solver import FeasibleSchedule, solve_exact
from vialo.models.diagnostics import DroppedStop
from vialo.models.itinerary import GroundedStop
from vialo.models.providers import TravelMode


def solve_route(
    stops: list[GroundedStop],
    matrix: list[list[MatrixEdge]],
    window_start: dt.datetime,
    window_end: dt.datetime,
    return_to_origin: bool,
    travel_mode: TravelMode,
) -> tuple[FeasibleSchedule, list[DroppedStop]] | None:
    """Solve the route, dropping stops if necessary.

    Returns the feasible schedule and any dropped stops, or None if completely infeasible.
    """
    # Try without dropping first
    schedule = solve_exact(
        stops=stops,
        origin_index=0,
        matrix=matrix,
        window_start=window_start,
        window_end=window_end,
        return_to_origin=return_to_origin,
        travel_mode=travel_mode,
    )

    if schedule is not None:
        return schedule, []

    # Try with progressive dropping
    return solve_with_dropping(
        stops=stops,
        origin_index=0,
        matrix=matrix,
        window_start=window_start,
        window_end=window_end,
        return_to_origin=return_to_origin,
        travel_mode=travel_mode,
    )
