"""Deterministic stop dropping when no feasible itinerary exists."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable

from vialo.domain.candidate_targets import target_stop_count
from vialo.domain.route_matrix import MatrixEdge
from vialo.domain.solver import FeasibleSchedule, solve_exact
from vialo.models.diagnostics import DiagnosticCode, DroppedStop
from vialo.models.itinerary import GroundedStop
from vialo.models.providers import TravelMode

# Re-adding is bounded so a thin day cannot turn into a long solve. Each attempt
# is one exhaustive solve over a set that is, by construction, smaller than the
# set that already failed, and the pass stops as soon as the day is full enough.
MAX_BACKFILL_ATTEMPTS = 6


def _backfill(
    *,
    schedule: FeasibleSchedule,
    dropped: list[DroppedStop],
    dropped_candidates: list[tuple[int, GroundedStop]],
    remaining_stops: list[GroundedStop],
    remaining_indices: list[int],
    window_start: dt.datetime,
    window_end: dt.datetime,
    attempt: Callable[[list[GroundedStop], list[int]], FeasibleSchedule | None],
) -> tuple[FeasibleSchedule, list[DroppedStop]]:
    """Put back stops that turn out to fit once the day became feasible.

    Progressive dropping is greedy: it removes the least essential stop until the
    whole set solves, and never reconsiders. That can leave a day far emptier than
    it needs to be, because one badly constrained stop forces a drop and the stops
    removed before it are never tried again.

    A real six-hour Venice day retained 2 stops of 8 and finished at 11:48, more
    than three hours before the window closed, with dropped stops reported as not
    fitting. They did fit; nothing had asked them again.

    This pass reconsiders each dropped stop, most essential first, which is the
    reverse of the order they were removed in. It costs solver time only: no
    provider call, no model call, no spend.
    """
    if not dropped_candidates:
        return schedule, dropped

    target = target_stop_count(window_start, window_end)
    if len(remaining_stops) >= target:
        return schedule, dropped

    restored: set[int] = set()
    attempts = 0

    # The final drop is the one that made the set solvable, so re-adding it is
    # provably infeasible and is not worth an attempt. Everything removed before
    # it was only ever tested alongside stops that have since gone.
    reconsider = list(reversed(dropped_candidates[:-1]))

    # Most recently dropped first, which is the most essential of those removed.
    for original_index, stop in reconsider:
        if attempts >= MAX_BACKFILL_ATTEMPTS or len(remaining_stops) >= target:
            break
        attempts += 1

        trial_stops = [*remaining_stops, stop]
        trial_indices = [*remaining_indices, original_index]
        # Keep candidate order stable so the solver sees the same shape it would
        # have seen had this stop never been removed.
        order = sorted(range(len(trial_stops)), key=lambda i: trial_stops[i].candidate_index)
        trial_stops = [trial_stops[i] for i in order]
        trial_indices = [trial_indices[i] for i in order]

        improved = attempt(trial_stops, trial_indices)
        if improved is None:
            continue

        schedule = improved
        remaining_stops = trial_stops
        remaining_indices = trial_indices
        restored.add(original_index)

    if restored:
        kept = {stop.candidate_index for stop in remaining_stops}
        dropped = [record for record in dropped if record.candidate_index not in kept]

    return schedule, dropped


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
    # Each feasibility drop is remembered with its stop and original index so the
    # backfill pass below can put it back if it turns out to fit after all.
    dropped_candidates: list[tuple[int, GroundedStop]] = []
    remaining_indices = list(range(len(stops)))
    remaining_stops = list(stops)

    def attempt(
        candidate_stops: list[GroundedStop], candidate_indices: list[int]
    ) -> FeasibleSchedule | None:
        """Solve one candidate set, projecting the full matrix onto it."""
        orig_indices = [origin_index] + [idx + 1 for idx in candidate_indices]

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

        return solve_exact(
            stops=candidate_stops,
            origin_index=0,
            matrix=sub_matrix,
            window_start=window_start,
            window_end=window_end,
            return_to_origin=return_to_origin,
            travel_mode=travel_mode,
            destination_index=sub_dest_index,
        )

    while remaining_stops:
        schedule = attempt(remaining_stops, remaining_indices)

        if schedule is not None:
            return _backfill(
                schedule=schedule,
                dropped=dropped,
                dropped_candidates=dropped_candidates,
                remaining_stops=remaining_stops,
                remaining_indices=remaining_indices,
                window_start=window_start,
                window_end=window_end,
                attempt=attempt,
            )

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

        dropped_candidates.append((remaining_indices[drop_idx], dropped_stop))
        remaining_stops.pop(drop_idx)
        remaining_indices.pop(drop_idx)

    return None
