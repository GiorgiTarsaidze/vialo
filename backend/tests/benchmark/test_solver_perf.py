"""Benchmark tests for solver performance at 8! and 9! scales."""

from __future__ import annotations

import datetime as dt
import random
import time

import pytest

from vialo.domain.route_matrix import MatrixEdge
from vialo.domain.solver import solve_exact
from vialo.models.itinerary import GroundedStop, OpenInterval
from vialo.models.providers import GroundedPlace, Location, StopCategory


def _make_stop(index: int, window_start: dt.datetime, window_end: dt.datetime) -> GroundedStop:
    """Create a test stop with open all day."""
    return GroundedStop(
        candidate_index=index,
        name=f"Stop {index}",
        category=StopCategory.LANDMARK,
        priority=1,
        visit_duration_minutes=30,
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


def _make_random_matrix(n: int, seed: int = 42) -> list[list[MatrixEdge]]:
    """Create a random but realistic directed matrix."""
    rng = random.Random(seed)
    matrix: list[list[MatrixEdge]] = []
    for i in range(n):
        row: list[MatrixEdge] = []
        for j in range(n):
            if i == j:
                row.append(MatrixEdge(i, j, 0, 0, True))
            else:
                duration = rng.randint(180, 900)  # 3-15 min walking
                distance = duration * 1  # ~1 m/s
                row.append(MatrixEdge(i, j, distance, duration, True))
        matrix.append(row)
    return matrix


@pytest.mark.benchmark
class TestSolverPerformance:
    def test_8_stops_benchmark(self) -> None:
        """8 stops = 8! = 40,320 permutations. Should complete in < 5s."""
        tz = dt.timezone(dt.timedelta(hours=2))
        window_start = dt.datetime(2026, 8, 15, 8, 0, tzinfo=tz)
        window_end = dt.datetime(2026, 8, 15, 20, 0, tzinfo=tz)  # 12 hours

        stops = [_make_stop(i, window_start, window_end) for i in range(8)]
        matrix = _make_random_matrix(9)  # 9 points: origin + 8 stops

        start_time = time.perf_counter()
        result = solve_exact(
            stops=stops,
            origin_index=0,
            matrix=matrix,
            window_start=window_start,
            window_end=window_end,
            return_to_origin=False,
            travel_mode="WALK",
        )
        elapsed = time.perf_counter() - start_time

        assert result is not None, "Should find feasible solution for 8 stops with wide window"
        assert elapsed < 5.0, f"8! solver took {elapsed:.2f}s (expected < 5s)"
        print(f"\n  8! solver: {elapsed:.3f}s, travel={result.objective.travel_seconds}s")

    def test_9_stops_benchmark(self) -> None:
        """9 stops = 9! = 362,880 permutations. Should complete in < 30s."""
        tz = dt.timezone(dt.timedelta(hours=2))
        window_start = dt.datetime(2026, 8, 15, 7, 0, tzinfo=tz)
        window_end = dt.datetime(2026, 8, 15, 21, 0, tzinfo=tz)  # 14 hours

        stops = [_make_stop(i, window_start, window_end) for i in range(9)]
        matrix = _make_random_matrix(10)  # 10 points: origin + 9 stops

        start_time = time.perf_counter()
        result = solve_exact(
            stops=stops,
            origin_index=0,
            matrix=matrix,
            window_start=window_start,
            window_end=window_end,
            return_to_origin=False,
            travel_mode="WALK",
        )
        elapsed = time.perf_counter() - start_time

        assert result is not None, "Should find feasible solution for 9 stops with wide window"
        assert elapsed < 30.0, f"9! solver took {elapsed:.2f}s (expected < 30s)"
        print(f"\n  9! solver: {elapsed:.3f}s, travel={result.objective.travel_seconds}s")
