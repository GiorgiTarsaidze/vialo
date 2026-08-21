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


class TestFeasibilityBackfill:
    """Greedy dropping must not leave a day emptier than it needs to be.

    Progressive dropping removes the least essential stop until the whole set
    solves, and never reconsiders. One badly constrained stop can therefore force
    several drops, and the stops removed before it are never asked again.

    A real six-hour Venice day retained 2 stops of 8 and finished at 11:48, more
    than three hours before its window closed, reporting the rest as not fitting.
    """

    @staticmethod
    def _uniform_matrix(n: int, seconds: int = 300) -> list[list[MatrixEdge]]:
        return [
            [
                MatrixEdge(i, j, seconds * 2, seconds, True)
                if i != j
                else MatrixEdge(i, j, 0, 0, True)
                for j in range(n)
            ]
            for i in range(n)
        ]

    def _narrow_stop(self, index: int, priority: int, duration_min: int) -> GroundedStop:
        """A stop open for one hour only, which is what forces the drops."""
        stop = _make_stop(index, priority, duration_min, open_seconds=3600)
        return stop

    def test_a_stop_dropped_before_the_blocking_one_is_reconsidered(self) -> None:
        """The stop removed first is never retested against the final set.

        Greedy dropping removes the least essential stop, finds the set still
        infeasible because of a different stop entirely, and moves on. By the time
        the blocking stop is finally removed, the innocent one is long gone and
        nothing asks again whether it would have fitted. It usually would.
        """
        tz = dt.timezone(dt.timedelta(hours=2))
        window_start = dt.datetime(2026, 8, 15, 9, 0, tzinfo=tz)
        window_end = dt.datetime(2026, 8, 15, 13, 0, tzinfo=tz)

        stops = [
            # Least essential, easy to fit, and therefore dropped first.
            _make_stop(0, 3, 30),
            # The real blocker: open for two hours but needing all of them, so it
            # can never fit once travel from the origin is counted.
            _make_stop(1, 2, 120, open_seconds=7200),
            _make_stop(2, 1, 30),
            _make_stop(3, 1, 30),
        ]

        result = solve_with_dropping(
            stops=stops,
            origin_index=0,
            matrix=self._uniform_matrix(len(stops) + 1),
            window_start=window_start,
            window_end=window_end,
            return_to_origin=False,
            travel_mode="WALK",
        )

        assert result is not None
        schedule, dropped = result

        kept = set(schedule.order)
        dropped_indices = {d.candidate_index for d in dropped}

        # Stop 1 genuinely cannot fit and must stay out.
        assert 1 in dropped_indices
        # Stop 0 was collateral damage and must come back.
        assert 0 in kept, (
            f"stop 0 was dropped before the blocker and never reconsidered: {dropped_indices}"
        )
        assert kept == {0, 2, 3}
        assert dropped_indices == {1}
        assert not kept & dropped_indices

    def test_a_stop_that_genuinely_cannot_fit_stays_dropped(self) -> None:
        """The backfill must not resurrect something that does not fit."""
        tz = dt.timezone(dt.timedelta(hours=2))
        window_start = dt.datetime(2026, 8, 15, 9, 0, tzinfo=tz)
        window_end = dt.datetime(2026, 8, 15, 11, 0, tzinfo=tz)

        stops = [
            _make_stop(0, 1, 60),
            _make_stop(1, 2, 60),
            _make_stop(2, 3, 60),
        ]

        result = solve_with_dropping(
            stops=stops,
            origin_index=0,
            matrix=self._uniform_matrix(len(stops) + 1),
            window_start=window_start,
            window_end=window_end,
            return_to_origin=False,
            travel_mode="WALK",
        )

        assert result is not None
        schedule, dropped = result
        # Two hours cannot hold three hour-long visits plus travel.
        assert len(dropped) > 0
        assert len(schedule.order) + len(dropped) == len(stops)
        # Every retained stop must be absent from the dropped list and vice versa.
        kept = set(schedule.order)
        assert not kept & {d.candidate_index for d in dropped}

    def test_kept_and_dropped_never_overlap_after_backfill(self) -> None:
        tz = dt.timezone(dt.timedelta(hours=2))
        window_start = dt.datetime(2026, 8, 15, 9, 0, tzinfo=tz)
        window_end = dt.datetime(2026, 8, 15, 16, 0, tzinfo=tz)

        stops = [self._narrow_stop(0, 1, 55)] + [_make_stop(i, 2, 25) for i in range(1, 5)]

        result = solve_with_dropping(
            stops=stops,
            origin_index=0,
            matrix=self._uniform_matrix(len(stops) + 1),
            window_start=window_start,
            window_end=window_end,
            return_to_origin=False,
            travel_mode="WALK",
        )
        assert result is not None
        schedule, dropped = result
        kept = set(schedule.order)
        assert not kept & {d.candidate_index for d in dropped}
        assert len(kept) + len(dropped) == len(stops)
