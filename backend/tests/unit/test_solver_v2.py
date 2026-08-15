"""Solver equivalence and property tests.

Verifies the optimized solver (primitive evaluation + single materialization)
produces identical results to a naive reference implementation.
"""

from __future__ import annotations

import datetime as dt
import random
from itertools import permutations

from vialo.domain.route_matrix import MatrixEdge
from vialo.domain.solver import (
    SolverObjective,
    _compare_objectives,
    _materialize_timeline,
    solve_exact,
)
from vialo.models.itinerary import GroundedStop, OpenInterval
from vialo.models.providers import GroundedPlace, Location, StopCategory


def _make_stop(
    index: int,
    window_start: dt.datetime,
    window_end: dt.datetime,
    visit_minutes: int = 30,
) -> GroundedStop:
    """Create a test stop open during the full window."""
    return GroundedStop(
        candidate_index=index,
        name=f"Stop {index}",
        category=StopCategory.LANDMARK,
        priority=1,
        visit_duration_minutes=visit_minutes,
        duration_source="model_estimate",
        place=GroundedPlace(
            place_id=f"place_{index}",
            display_name=f"Stop {index}",
            formatted_address=f"Address {index}",
            location=Location(latitude=45.0 + index * 0.005, longitude=12.0 + index * 0.005),
            time_zone_id="Europe/Rome",
        ),
        hours_source="current",
        open_intervals=[
            OpenInterval(
                start=window_start,
                end=window_end,
                local_start=window_start.strftime("%H:%M"),
                local_end=window_end.strftime("%H:%M"),
            )
        ],
    )


def _make_matrix(n: int, seed: int = 42) -> list[list[MatrixEdge]]:
    """Create a random directed matrix."""
    rng = random.Random(seed)
    matrix: list[list[MatrixEdge]] = []
    for i in range(n):
        row: list[MatrixEdge] = []
        for j in range(n):
            if i == j:
                row.append(MatrixEdge(i, j, 0, 0, True))
            else:
                dur = rng.randint(180, 900)
                dist = dur
                row.append(MatrixEdge(i, j, dist, dur, True))
        matrix.append(row)
    return matrix


class TestObjectiveComparison:
    """Tie-breaking rules are respected."""

    def test_less_travel_wins(self) -> None:
        a = SolverObjective(100, 0, 1000, (0, 1))
        b = SolverObjective(200, 0, 1000, (0, 1))
        assert _compare_objectives(a, b) < 0

    def test_less_wait_breaks_travel_tie(self) -> None:
        a = SolverObjective(100, 10, 1000, (0, 1))
        b = SolverObjective(100, 20, 1000, (0, 1))
        assert _compare_objectives(a, b) < 0

    def test_earlier_completion_breaks_wait_tie(self) -> None:
        a = SolverObjective(100, 10, 900, (0, 1))
        b = SolverObjective(100, 10, 1000, (0, 1))
        assert _compare_objectives(a, b) < 0

    def test_lower_index_sequence_breaks_completion_tie(self) -> None:
        a = SolverObjective(100, 10, 1000, (0, 1, 2))
        b = SolverObjective(100, 10, 1000, (0, 2, 1))
        assert _compare_objectives(a, b) < 0

    def test_equal_objectives(self) -> None:
        a = SolverObjective(100, 10, 1000, (0, 1))
        b = SolverObjective(100, 10, 1000, (0, 1))
        assert _compare_objectives(a, b) == 0


class TestSolverEquivalence:
    """Optimized solver produces same result as brute-force reference."""

    def _reference_solve(
        self,
        stops: list[GroundedStop],
        matrix: list[list[MatrixEdge]],
        window_start: dt.datetime,
        window_end: dt.datetime,
        return_to_origin: bool,
    ) -> tuple[int, ...] | None:
        """Naive reference: materialize timeline for every permutation, pick best."""
        n = len(stops)
        best_obj: SolverObjective | None = None
        best_perm: tuple[int, ...] | None = None

        for perm in permutations(range(n)):
            result = _materialize_timeline(
                perm=perm,
                stops=stops,
                origin_index=0,
                matrix=matrix,
                window_start=window_start,
                window_end=window_end,
                return_to_origin=return_to_origin,
                travel_mode="WALK",
            )
            if result is None:
                continue
            if best_obj is None or _compare_objectives(result.objective, best_obj) < 0:
                best_obj = result.objective
                best_perm = perm

        return best_perm

    def test_3_stops_equivalence(self) -> None:
        """3-stop solve produces identical result to reference."""
        tz = dt.timezone(dt.timedelta(hours=2))
        window_start = dt.datetime(2026, 8, 15, 9, 0, tzinfo=tz)
        window_end = dt.datetime(2026, 8, 15, 18, 0, tzinfo=tz)
        stops = [_make_stop(i, window_start, window_end) for i in range(3)]
        matrix = _make_matrix(4)  # origin + 3 stops

        optimized = solve_exact(
            stops=stops,
            origin_index=0,
            matrix=matrix,
            window_start=window_start,
            window_end=window_end,
            return_to_origin=False,
        )
        ref_perm = self._reference_solve(stops, matrix, window_start, window_end, False)

        assert optimized is not None
        assert ref_perm is not None
        expected_order = [stops[i].candidate_index for i in ref_perm]
        assert optimized.order == expected_order

    def test_5_stops_equivalence(self) -> None:
        """5-stop solve produces identical result to reference."""
        tz = dt.timezone(dt.timedelta(hours=2))
        window_start = dt.datetime(2026, 8, 15, 8, 0, tzinfo=tz)
        window_end = dt.datetime(2026, 8, 15, 20, 0, tzinfo=tz)
        stops = [_make_stop(i, window_start, window_end) for i in range(5)]
        matrix = _make_matrix(6, seed=123)

        optimized = solve_exact(
            stops=stops,
            origin_index=0,
            matrix=matrix,
            window_start=window_start,
            window_end=window_end,
            return_to_origin=True,
        )
        ref_perm = self._reference_solve(stops, matrix, window_start, window_end, True)

        assert optimized is not None
        assert ref_perm is not None
        expected_order = [stops[i].candidate_index for i in ref_perm]
        assert optimized.order == expected_order

    def test_no_feasible_returns_none(self) -> None:
        """When no permutation fits, solve returns None."""
        tz = dt.timezone(dt.timedelta(hours=2))
        window_start = dt.datetime(2026, 8, 15, 9, 0, tzinfo=tz)
        window_end = dt.datetime(2026, 8, 15, 9, 10, tzinfo=tz)  # 10 min window
        stops = [_make_stop(i, window_start, window_end, visit_minutes=30) for i in range(3)]
        matrix = _make_matrix(4)

        result = solve_exact(
            stops=stops,
            origin_index=0,
            matrix=matrix,
            window_start=window_start,
            window_end=window_end,
            return_to_origin=False,
        )
        assert result is None


class TestSolverProperties:
    """Property-based tests for solver invariants."""

    def test_result_order_has_all_stops(self) -> None:
        """Solver result includes all stops exactly once."""
        tz = dt.timezone(dt.timedelta(hours=2))
        window_start = dt.datetime(2026, 8, 15, 7, 0, tzinfo=tz)
        window_end = dt.datetime(2026, 8, 15, 22, 0, tzinfo=tz)
        stops = [_make_stop(i, window_start, window_end) for i in range(4)]
        matrix = _make_matrix(5)

        result = solve_exact(
            stops=stops,
            origin_index=0,
            matrix=matrix,
            window_start=window_start,
            window_end=window_end,
            return_to_origin=False,
        )
        assert result is not None
        assert sorted(result.order) == [0, 1, 2, 3]

    def test_timeline_times_are_monotonic(self) -> None:
        """All timeline entries have non-decreasing times."""
        tz = dt.timezone(dt.timedelta(hours=2))
        window_start = dt.datetime(2026, 8, 15, 8, 0, tzinfo=tz)
        window_end = dt.datetime(2026, 8, 15, 20, 0, tzinfo=tz)
        stops = [_make_stop(i, window_start, window_end) for i in range(4)]
        matrix = _make_matrix(5, seed=99)

        result = solve_exact(
            stops=stops,
            origin_index=0,
            matrix=matrix,
            window_start=window_start,
            window_end=window_end,
            return_to_origin=False,
        )
        assert result is not None

        prev_time = window_start
        for entry in result.timeline:
            if hasattr(entry, "departure"):
                assert entry.departure >= prev_time
            if hasattr(entry, "arrival"):
                assert entry.arrival >= prev_time
                prev_time = entry.arrival
            elif hasattr(entry, "wait_end"):
                assert entry.wait_end >= prev_time
                prev_time = entry.wait_end

    def test_totals_match_timeline(self) -> None:
        """Totals are consistent with timeline entries."""
        tz = dt.timezone(dt.timedelta(hours=2))
        window_start = dt.datetime(2026, 8, 15, 8, 0, tzinfo=tz)
        window_end = dt.datetime(2026, 8, 15, 20, 0, tzinfo=tz)
        stops = [_make_stop(i, window_start, window_end) for i in range(3)]
        matrix = _make_matrix(4, seed=77)

        result = solve_exact(
            stops=stops,
            origin_index=0,
            matrix=matrix,
            window_start=window_start,
            window_end=window_end,
            return_to_origin=False,
        )
        assert result is not None

        travel_sum = sum(e.duration_seconds for e in result.timeline if e.type == "travel")
        wait_sum = sum(e.duration_seconds for e in result.timeline if e.type == "wait")
        visit_sum = sum(e.duration_minutes * 60 for e in result.timeline if e.type == "visit")

        assert result.totals.travel_seconds == travel_sum
        assert result.totals.wait_seconds == wait_sum
        assert result.totals.visit_seconds == visit_sum
