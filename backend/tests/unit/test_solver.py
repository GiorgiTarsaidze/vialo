"""Tests for the exact permutation solver."""

from __future__ import annotations

import datetime as dt

from vialo.domain.route_matrix import MatrixEdge
from vialo.domain.solver import solve_exact
from vialo.models.itinerary import GroundedStop, OpenInterval
from vialo.models.providers import GroundedPlace, Location, StopCategory


def _make_stop(
    index: int,
    duration_min: int,
    open_start: dt.datetime,
    open_end: dt.datetime,
    priority: int = 1,
) -> GroundedStop:
    """Helper to create a test stop."""
    return GroundedStop(
        candidate_index=index,
        name=f"Stop {index}",
        category=StopCategory.LANDMARK,
        priority=priority,
        visit_duration_minutes=duration_min,
        duration_source="model_estimate",
        place=GroundedPlace(
            place_id=f"place_{index}",
            display_name=f"Stop {index}",
            formatted_address=f"Address {index}",
            location=Location(latitude=45.0 + index * 0.01, longitude=12.0 + index * 0.01),
            time_zone_id="Europe/Rome",
        ),
        hours_source="current",
        open_intervals=[
            OpenInterval(
                start=open_start,
                end=open_end,
                local_start=open_start.strftime("%H:%M"),
                local_end=open_end.strftime("%H:%M"),
            )
        ],
    )


def _make_simple_matrix(durations: list[list[int]]) -> list[list[MatrixEdge]]:
    """Create a matrix from a 2D list of durations in seconds."""
    n = len(durations)
    matrix: list[list[MatrixEdge]] = []
    for i in range(n):
        row: list[MatrixEdge] = []
        for j in range(n):
            if i == j:
                row.append(MatrixEdge(i, j, 0, 0, True))
            else:
                d = durations[i][j]
                row.append(MatrixEdge(i, j, d * 2, d, d > 0))
        matrix.append(row)
    return matrix


class TestSolverBasic:
    def test_single_stop_feasible(self) -> None:
        """One stop that fits within the window."""
        tz = dt.timezone(dt.timedelta(hours=2))
        window_start = dt.datetime(2026, 8, 15, 9, 0, tzinfo=tz)
        window_end = dt.datetime(2026, 8, 15, 19, 0, tzinfo=tz)

        stop = _make_stop(0, 50, window_start, window_end)
        # Matrix: origin(0) + 1 stop = 2x2
        matrix = _make_simple_matrix([[0, 300], [300, 0]])

        result = solve_exact(
            stops=[stop],
            origin_index=0,
            matrix=matrix,
            window_start=window_start,
            window_end=window_end,
            return_to_origin=False,
            travel_mode="WALK",
        )
        assert result is not None
        assert result.order == [0]

    def test_two_stops_optimal_order(self) -> None:
        """Two stops where one order is shorter than the other."""
        tz = dt.timezone(dt.timedelta(hours=2))
        window_start = dt.datetime(2026, 8, 15, 9, 0, tzinfo=tz)
        window_end = dt.datetime(2026, 8, 15, 19, 0, tzinfo=tz)

        stops = [
            _make_stop(0, 30, window_start, window_end),
            _make_stop(1, 30, window_start, window_end),
        ]

        # Asymmetric matrix:
        # Origin(0) -> Stop0(1): 600s, Origin(0) -> Stop1(2): 300s
        # Stop0(1) -> Stop1(2): 200s, Stop1(2) -> Stop0(1): 800s
        matrix = _make_simple_matrix(
            [
                [0, 600, 300],  # from origin
                [600, 0, 200],  # from stop 0
                [300, 800, 0],  # from stop 1
            ]
        )

        result = solve_exact(
            stops=stops,
            origin_index=0,
            matrix=matrix,
            window_start=window_start,
            window_end=window_end,
            return_to_origin=False,
            travel_mode="WALK",
        )
        assert result is not None
        # Optimal: origin -> stop0 (600s) -> stop1 (200s) = 800s total travel
        # vs: origin -> stop1 (300s) -> stop0 (800s) = 1100s total travel
        assert result.order == [0, 1]
        assert result.objective.travel_seconds == 800

    def test_window_overflow_rejected(self) -> None:
        """Stop that doesn't fit in the time window."""
        tz = dt.timezone(dt.timedelta(hours=2))
        window_start = dt.datetime(2026, 8, 15, 9, 0, tzinfo=tz)
        window_end = dt.datetime(2026, 8, 15, 9, 30, tzinfo=tz)  # Only 30 min window

        stop = _make_stop(0, 60, window_start, window_end)  # 60 min visit
        matrix = _make_simple_matrix([[0, 300], [300, 0]])  # 5 min travel

        result = solve_exact(
            stops=[stop],
            origin_index=0,
            matrix=matrix,
            window_start=window_start,
            window_end=window_end,
            return_to_origin=False,
            travel_mode="WALK",
        )
        assert result is None

    def test_return_to_origin(self) -> None:
        """Schedule includes return travel to origin."""
        tz = dt.timezone(dt.timedelta(hours=2))
        window_start = dt.datetime(2026, 8, 15, 9, 0, tzinfo=tz)
        window_end = dt.datetime(2026, 8, 15, 19, 0, tzinfo=tz)

        stop = _make_stop(0, 30, window_start, window_end)
        matrix = _make_simple_matrix([[0, 600], [600, 0]])

        result = solve_exact(
            stops=[stop],
            origin_index=0,
            matrix=matrix,
            window_start=window_start,
            window_end=window_end,
            return_to_origin=True,
            travel_mode="WALK",
        )
        assert result is not None
        # Should include return travel: 600 + 600 = 1200s travel
        assert result.objective.travel_seconds == 1200

    def test_unreachable_edge_rejected(self) -> None:
        """If there's no route to a stop, it's infeasible."""
        tz = dt.timezone(dt.timedelta(hours=2))
        window_start = dt.datetime(2026, 8, 15, 9, 0, tzinfo=tz)
        window_end = dt.datetime(2026, 8, 15, 19, 0, tzinfo=tz)

        stop = _make_stop(0, 30, window_start, window_end)
        # Unreachable: 0 duration means edge exists but -1 would need different approach
        matrix = [
            [MatrixEdge(0, 0, 0, 0, True), MatrixEdge(0, 1, None, None, False)],
            [MatrixEdge(1, 0, None, None, False), MatrixEdge(1, 1, 0, 0, True)],
        ]

        result = solve_exact(
            stops=[stop],
            origin_index=0,
            matrix=matrix,
            window_start=window_start,
            window_end=window_end,
            return_to_origin=False,
            travel_mode="WALK",
        )
        assert result is None


class TestSolverWaiting:
    def test_wait_for_opening(self) -> None:
        """Solver inserts a wait when arriving before opening."""
        tz = dt.timezone(dt.timedelta(hours=2))
        window_start = dt.datetime(2026, 8, 15, 8, 0, tzinfo=tz)
        window_end = dt.datetime(2026, 8, 15, 19, 0, tzinfo=tz)
        open_start = dt.datetime(2026, 8, 15, 9, 30, tzinfo=tz)
        open_end = dt.datetime(2026, 8, 15, 17, 15, tzinfo=tz)

        stop = _make_stop(0, 50, open_start, open_end)
        # 5 min travel from origin -> arrives at 8:05, must wait until 9:30
        matrix = _make_simple_matrix([[0, 300], [300, 0]])

        result = solve_exact(
            stops=[stop],
            origin_index=0,
            matrix=matrix,
            window_start=window_start,
            window_end=window_end,
            return_to_origin=False,
            travel_mode="WALK",
        )
        assert result is not None
        assert result.objective.wait_seconds > 0
        # Should have travel, wait, visit in timeline
        types = [e.type for e in result.timeline]
        assert types == ["travel", "wait", "visit"]


class TestSolverTieBreaking:
    def test_less_travel_wins(self) -> None:
        """When two orders are feasible, less travel time wins."""
        tz = dt.timezone(dt.timedelta(hours=2))
        window_start = dt.datetime(2026, 8, 15, 9, 0, tzinfo=tz)
        window_end = dt.datetime(2026, 8, 15, 19, 0, tzinfo=tz)

        stops = [
            _make_stop(0, 30, window_start, window_end),
            _make_stop(1, 30, window_start, window_end),
        ]

        # Make order [0,1] clearly shorter
        matrix = _make_simple_matrix(
            [
                [0, 100, 500],
                [100, 0, 100],
                [500, 100, 0],
            ]
        )

        result = solve_exact(
            stops=stops,
            origin_index=0,
            matrix=matrix,
            window_start=window_start,
            window_end=window_end,
            return_to_origin=False,
            travel_mode="WALK",
        )
        assert result is not None
        assert result.order == [0, 1]
        assert result.objective.travel_seconds == 200  # 100 + 100

    def test_less_waiting_as_tiebreak(self) -> None:
        """Equal travel time: less waiting wins."""
        tz = dt.timezone(dt.timedelta(hours=2))
        window_start = dt.datetime(2026, 8, 15, 9, 0, tzinfo=tz)
        window_end = dt.datetime(2026, 8, 15, 19, 0, tzinfo=tz)
        late_open = dt.datetime(2026, 8, 15, 11, 0, tzinfo=tz)

        stops = [
            _make_stop(0, 30, window_start, window_end),
            _make_stop(1, 30, late_open, window_end),  # Opens later
        ]

        # Symmetric travel so both orders have same travel time
        matrix = _make_simple_matrix(
            [
                [0, 300, 300],
                [300, 0, 300],
                [300, 300, 0],
            ]
        )

        result = solve_exact(
            stops=stops,
            origin_index=0,
            matrix=matrix,
            window_start=window_start,
            window_end=window_end,
            return_to_origin=False,
            travel_mode="WALK",
        )
        assert result is not None
        # Order [0, 1]: arrive stop0 at 9:05, visit 30min, leave 9:35
        # Travel to stop1: arrive 9:40, wait until 11:00, visit 30min
        # Order [1, 0]: arrive stop1 at 9:05, wait until 11:00, visit 30min, leave 11:30
        # Travel to stop0: arrive 11:35, visit 30min
        # Travel is 600s in both. Wait: [0,1]=4800s; [1,0]=6900s
        # So [0,1] has less waiting
        assert result.order == [0, 1]
