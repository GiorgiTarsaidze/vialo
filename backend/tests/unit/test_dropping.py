"""Tests for deterministic stop dropping logic."""

from __future__ import annotations

import datetime as dt

from vialo.domain.dropping import rank_for_dropping, solve_with_dropping
from vialo.domain.route_matrix import MatrixEdge
from vialo.models.itinerary import GroundedStop, OpenInterval
from vialo.models.providers import GroundedPlace, Location, StopCategory


def _make_stop(
    index: int,
    priority: int,
    duration_min: int,
    open_seconds: int = 36000,
) -> GroundedStop:
    tz = dt.timezone(dt.timedelta(hours=2))
    start = dt.datetime(2026, 8, 15, 9, 0, tzinfo=tz)
    end = start + dt.timedelta(seconds=open_seconds)
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
            formatted_address=f"Addr {index}",
            location=Location(latitude=45.0, longitude=12.0),
            time_zone_id="Europe/Rome",
        ),
        hours_source="current",
        open_intervals=[
            OpenInterval(
                start=start,
                end=end,
                local_start="09:00",
                local_end=end.strftime("%H:%M"),
            )
        ],
    )


class TestRankForDropping:
    def test_priority_3_dropped_first(self) -> None:
        stops = [
            _make_stop(0, 1, 30),  # priority 1 = most important
            _make_stop(1, 3, 30),  # priority 3 = least important
            _make_stop(2, 2, 30),  # priority 2
        ]
        rank = rank_for_dropping(stops)
        # Priority 3 (index 1) should be dropped first
        assert rank[0] == 1

    def test_same_priority_longer_duration_dropped_first(self) -> None:
        stops = [
            _make_stop(0, 2, 30),
            _make_stop(1, 2, 90),  # Longer duration
            _make_stop(2, 2, 45),
        ]
        rank = rank_for_dropping(stops)
        # Among same priority, longer duration (harder to fit) dropped first
        assert rank[0] == 1

    def test_same_priority_narrower_window_dropped_first(self) -> None:
        stops = [
            _make_stop(0, 2, 30, open_seconds=36000),  # 10 hours open
            _make_stop(1, 2, 30, open_seconds=7200),  # 2 hours open (narrower)
            _make_stop(2, 2, 30, open_seconds=36000),  # 10 hours open
        ]
        rank = rank_for_dropping(stops)
        # Narrower window sorts first (less open seconds)
        assert rank[0] == 1


class TestSolveWithDropping:
    def test_drops_until_feasible(self) -> None:
        """With a tight window, solver drops stops to find a feasible solution."""
        tz = dt.timezone(dt.timedelta(hours=2))
        window_start = dt.datetime(2026, 8, 15, 9, 0, tzinfo=tz)
        window_end = dt.datetime(2026, 8, 15, 10, 30, tzinfo=tz)  # Only 90 min

        stops = [
            _make_stop(0, 1, 30),  # Important, 30 min
            _make_stop(1, 3, 30),  # Least important, 30 min
            _make_stop(2, 2, 30),  # Medium, 30 min
        ]

        # All 300s travel between any two points
        n = 4
        matrix = [
            [
                MatrixEdge(i, j, 600, 300, True) if i != j else MatrixEdge(i, j, 0, 0, True)
                for j in range(n)
            ]
            for i in range(n)
        ]

        result = solve_with_dropping(
            stops=stops,
            origin_index=0,
            matrix=matrix,
            window_start=window_start,
            window_end=window_end,
            return_to_origin=False,
            travel_mode="WALK",
        )

        assert result is not None
        schedule, dropped = result
        assert len(dropped) > 0
        # Priority 3 should be dropped first
        assert any(d.candidate_index == 1 for d in dropped)
