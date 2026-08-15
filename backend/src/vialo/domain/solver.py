"""Exact permutation solver for optimal stop ordering with time-window constraints."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from itertools import permutations

from vialo.domain.route_matrix import MatrixEdge
from vialo.models.itinerary import (
    GroundedStop,
    OpenInterval,
    Totals,
    TravelEntry,
    VisitEntry,
    WaitEntry,
)
from vialo.models.providers import TravelMode


@dataclass(frozen=True)
class SolverObjective:
    """Objective values for comparing permutations."""

    travel_seconds: int
    wait_seconds: int
    completion_epoch: int
    index_sequence: tuple[int, ...]


@dataclass
class FeasibleSchedule:
    """A feasible schedule with its timeline and objective."""

    order: list[int]  # candidate indices in visit order
    timeline: list[TravelEntry | WaitEntry | VisitEntry]
    objective: SolverObjective
    totals: Totals
    travel_mode: TravelMode


def _find_open_interval_epoch(
    intervals: list[tuple[int, int]],
    arrival_epoch: int,
    visit_seconds: int,
) -> tuple[int, int] | None:
    """Find an open interval that can accommodate the visit.

    intervals: list of (open_epoch, close_epoch) sorted by start.
    Returns (effective_start_epoch, interval_index) or None.
    """
    for idx, (open_ep, close_ep) in enumerate(intervals):
        effective_start = max(arrival_epoch, open_ep)
        effective_end = effective_start + visit_seconds
        if effective_end <= close_ep:
            return (effective_start, idx)
    return None


def _evaluate_permutation(
    perm: tuple[int, ...],
    stop_visit_seconds: list[int],
    stop_intervals_epochs: list[list[tuple[int, int]]],
    stop_candidate_indices: list[int],
    matrix: list[list[MatrixEdge]],
    window_start_epoch: int,
    window_end_epoch: int,
    return_to_origin: bool,
    origin_index: int,
) -> SolverObjective | None:
    """Evaluate a permutation using only primitive arithmetic. No Pydantic models.

    Returns SolverObjective if feasible, None otherwise.
    """
    current_epoch = window_start_epoch
    total_travel = 0
    total_wait = 0
    prev_matrix_idx = origin_index

    for stop_list_idx in perm:
        stop_matrix_idx = stop_list_idx + 1

        edge = matrix[prev_matrix_idx][stop_matrix_idx]
        if not edge.reachable or edge.duration_seconds is None:
            return None

        travel_seconds = edge.duration_seconds
        current_epoch += travel_seconds
        total_travel += travel_seconds

        # Find valid open interval
        visit_seconds = stop_visit_seconds[stop_list_idx]
        intervals = stop_intervals_epochs[stop_list_idx]
        result = _find_open_interval_epoch(intervals, current_epoch, visit_seconds)
        if result is None:
            return None

        effective_start, _ = result

        # Wait if needed
        if effective_start > current_epoch:
            wait = effective_start - current_epoch
            # Check if visit after wait exceeds window
            if effective_start + visit_seconds > window_end_epoch:
                return None
            total_wait += wait
            current_epoch = effective_start

        # Visit
        visit_end = current_epoch + visit_seconds
        if visit_end > window_end_epoch:
            return None

        current_epoch = visit_end
        prev_matrix_idx = stop_matrix_idx

    # Return to origin if required
    if return_to_origin:
        edge = matrix[prev_matrix_idx][origin_index]
        if not edge.reachable or edge.duration_seconds is None:
            return None
        travel_seconds = edge.duration_seconds
        current_epoch += travel_seconds
        if current_epoch > window_end_epoch:
            return None
        total_travel += travel_seconds

    candidate_indices = tuple(stop_candidate_indices[i] for i in perm)

    return SolverObjective(
        travel_seconds=total_travel,
        wait_seconds=total_wait,
        completion_epoch=current_epoch,
        index_sequence=candidate_indices,
    )


def _compare_objectives(a: SolverObjective, b: SolverObjective) -> int:
    """Compare two objectives. Returns <0 if a is better, >0 if b is better.

    Tie-breaking order:
    1. Less total travel time
    2. Less waiting time
    3. Earlier completion
    4. Lower candidate-index sequence (lexicographic)
    """
    if a.travel_seconds != b.travel_seconds:
        return a.travel_seconds - b.travel_seconds
    if a.wait_seconds != b.wait_seconds:
        return a.wait_seconds - b.wait_seconds
    if a.completion_epoch != b.completion_epoch:
        return a.completion_epoch - b.completion_epoch
    # Lexicographic comparison of index sequences
    if a.index_sequence < b.index_sequence:
        return -1
    if a.index_sequence > b.index_sequence:
        return 1
    return 0


def _materialize_timeline(
    perm: tuple[int, ...],
    stops: list[GroundedStop],
    origin_index: int,
    matrix: list[list[MatrixEdge]],
    window_start: dt.datetime,
    window_end: dt.datetime,
    return_to_origin: bool,
    travel_mode: TravelMode,
) -> FeasibleSchedule | None:
    """Build the full timeline with Pydantic models for the winning permutation."""
    timeline: list[TravelEntry | WaitEntry | VisitEntry] = []
    current_time = window_start
    total_travel = 0
    total_wait = 0
    total_visit = 0
    prev_matrix_idx = origin_index

    for stop_list_idx in perm:
        stop = stops[stop_list_idx]
        stop_matrix_idx = stop_list_idx + 1

        edge = matrix[prev_matrix_idx][stop_matrix_idx]
        if not edge.reachable or edge.duration_seconds is None:
            return None

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
        total_travel += travel_seconds
        current_time = arrival

        visit_duration = dt.timedelta(minutes=stop.visit_duration_minutes)

        # Find the right interval
        interval: OpenInterval | None = None
        for iv in stop.open_intervals:
            effective_start = max(current_time, iv.start)
            effective_end = effective_start + visit_duration
            if effective_end <= iv.end:
                interval = iv
                break

        if interval is None:
            return None

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
            total_wait += wait_seconds
            current_time = interval.start

        # Visit
        visit_end = current_time + visit_duration
        if visit_end > window_end or visit_end > interval.end:
            return None

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
        total_visit += int(visit_duration.total_seconds())
        current_time = visit_end
        prev_matrix_idx = stop_matrix_idx

    # Return to origin
    if return_to_origin:
        edge = matrix[prev_matrix_idx][origin_index]
        if not edge.reachable or edge.duration_seconds is None:
            return None
        travel_seconds = edge.duration_seconds
        distance_meters = edge.distance_meters or 0
        departure = current_time
        arrival = current_time + dt.timedelta(seconds=travel_seconds)

        if arrival > window_end:
            return None

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
        total_travel += travel_seconds
        current_time = arrival

    elapsed = int((current_time - window_start).total_seconds())
    candidate_indices = [stops[i].candidate_index for i in perm]

    objective = SolverObjective(
        travel_seconds=total_travel,
        wait_seconds=total_wait,
        completion_epoch=int(current_time.timestamp()),
        index_sequence=tuple(candidate_indices),
    )

    totals = Totals(
        visit_seconds=total_visit,
        travel_seconds=total_travel,
        wait_seconds=total_wait,
        elapsed_seconds=elapsed,
    )

    return FeasibleSchedule(
        order=candidate_indices,
        timeline=timeline,
        objective=objective,
        totals=totals,
        travel_mode=travel_mode,
    )


def solve_exact(
    stops: list[GroundedStop],
    origin_index: int,
    matrix: list[list[MatrixEdge]],
    window_start: dt.datetime,
    window_end: dt.datetime,
    return_to_origin: bool,
    travel_mode: TravelMode = "WALK",
) -> FeasibleSchedule | None:
    """Find the provably optimal stop order via exhaustive permutation search.

    Evaluates objectives using primitive arithmetic (no Pydantic model creation per
    permutation), then materializes the full timeline once for the winning permutation.

    Args:
        stops: Grounded stops to schedule (max 9).
        origin_index: Matrix index of the origin point (always 0).
        matrix: Directed NxN travel-time matrix.
        window_start: UTC-aware start of the time window.
        window_end: UTC-aware end of the time window.
        return_to_origin: Whether to route back to origin at the end.
        travel_mode: WALK or DRIVE.

    Returns:
        The optimal FeasibleSchedule, or None if no permutation is feasible.
    """
    n = len(stops)
    if n == 0:
        return None

    # Pre-compute epoch values and interval data for fast evaluation
    window_start_epoch = int(window_start.timestamp())
    window_end_epoch = int(window_end.timestamp())

    stop_visit_seconds = [s.visit_duration_minutes * 60 for s in stops]
    stop_candidate_indices = [s.candidate_index for s in stops]

    # Convert intervals to epoch pairs for fast comparison
    stop_intervals_epochs: list[list[tuple[int, int]]] = []
    for stop in stops:
        intervals = [
            (int(iv.start.timestamp()), int(iv.end.timestamp())) for iv in stop.open_intervals
        ]
        stop_intervals_epochs.append(intervals)

    best_obj: SolverObjective | None = None
    best_perm: tuple[int, ...] | None = None

    for perm in permutations(range(n)):
        obj = _evaluate_permutation(
            perm=perm,
            stop_visit_seconds=stop_visit_seconds,
            stop_intervals_epochs=stop_intervals_epochs,
            stop_candidate_indices=stop_candidate_indices,
            matrix=matrix,
            window_start_epoch=window_start_epoch,
            window_end_epoch=window_end_epoch,
            return_to_origin=return_to_origin,
            origin_index=origin_index,
        )
        if obj is None:
            continue
        if best_obj is None or _compare_objectives(obj, best_obj) < 0:
            best_obj = obj
            best_perm = perm

    if best_perm is None:
        return None

    # Materialize the full timeline only once for the winning permutation
    return _materialize_timeline(
        perm=best_perm,
        stops=stops,
        origin_index=origin_index,
        matrix=matrix,
        window_start=window_start,
        window_end=window_end,
        return_to_origin=return_to_origin,
        travel_mode=travel_mode,
    )
