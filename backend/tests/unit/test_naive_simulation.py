"""Tests for naive order simulation."""

from __future__ import annotations

import datetime as dt

from vialo.domain.naive_simulation import simulate_naive_order
from vialo.domain.route_matrix import MatrixEdge
from vialo.models.itinerary import GroundedStop, OpenInterval
from vialo.models.providers import GroundedPlace, Location, StopCategory


def _make_stop(
    index: int, duration_min: int, open_start: dt.datetime, open_end: dt.datetime
) -> GroundedStop:
    return GroundedStop(
        candidate_index=index,
        name=f"Stop {index}",
        category=StopCategory.LANDMARK,
        priority=1,
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
                start=open_start,
                end=open_end,
                local_start=open_start.strftime("%H:%M"),
                local_end=open_end.strftime("%H:%M"),
            )
        ],
    )


class TestNaiveSimulation:
    def test_feasible_naive_order(self) -> None:
        tz = dt.timezone(dt.timedelta(hours=2))
        ws = dt.datetime(2026, 8, 15, 9, 0, tzinfo=tz)
        we = dt.datetime(2026, 8, 15, 19, 0, tzinfo=tz)

        stops = [
            _make_stop(0, 30, ws, we),
            _make_stop(1, 30, ws, we),
        ]

        matrix = [
            [
                MatrixEdge(i, j, 600, 300, True) if i != j else MatrixEdge(i, j, 0, 0, True)
                for j in range(3)
            ]
            for i in range(3)
        ]

        timeline, feasible, codes = simulate_naive_order(
            retained_stops=stops,
            candidate_order=[0, 1],
            origin_index=0,
            matrix=matrix,
            window_start=ws,
            window_end=we,
            return_to_origin=False,
            travel_mode="WALK",
            original_matrix_indices={0: 1, 1: 2},
        )

        assert feasible is True
        assert len(codes) == 0
        assert len(timeline) > 0

    def test_infeasible_window_exceeded(self) -> None:
        tz = dt.timezone(dt.timedelta(hours=2))
        ws = dt.datetime(2026, 8, 15, 9, 0, tzinfo=tz)
        we = dt.datetime(2026, 8, 15, 9, 30, tzinfo=tz)  # Very tight window

        stops = [
            _make_stop(0, 30, ws, we),
            _make_stop(1, 30, ws, we),
        ]

        matrix = [
            [
                MatrixEdge(i, j, 600, 300, True) if i != j else MatrixEdge(i, j, 0, 0, True)
                for j in range(3)
            ]
            for i in range(3)
        ]

        timeline, feasible, codes = simulate_naive_order(
            retained_stops=stops,
            candidate_order=[0, 1],
            origin_index=0,
            matrix=matrix,
            window_start=ws,
            window_end=we,
            return_to_origin=False,
            travel_mode="WALK",
            original_matrix_indices={0: 1, 1: 2},
        )

        assert feasible is False
        assert len(codes) > 0

    def test_dropped_first_stop_keeps_original_directed_matrix_indices(self) -> None:
        tz = dt.timezone(dt.timedelta(hours=2))
        window_start = dt.datetime(2026, 8, 15, 9, 0, tzinfo=tz)
        window_end = dt.datetime(2026, 8, 15, 19, 0, tzinfo=tz)
        retained = [
            _make_stop(1, 30, window_start, window_end),
            _make_stop(2, 30, window_start, window_end),
        ]
        matrix = [
            [
                MatrixEdge(i, j, 10, 10, True) if i != j else MatrixEdge(i, j, 0, 0, True)
                for j in range(4)
            ]
            for i in range(4)
        ]
        matrix[0][2] = MatrixEdge(0, 2, 1110, 111, True)
        matrix[2][3] = MatrixEdge(2, 3, 2220, 222, True)

        timeline, feasible, codes = simulate_naive_order(
            retained_stops=retained,
            candidate_order=[0, 1, 2],
            origin_index=0,
            matrix=matrix,
            window_start=window_start,
            window_end=window_end,
            return_to_origin=False,
            travel_mode="WALK",
            original_matrix_indices={0: 1, 1: 2, 2: 3},
        )

        travel_entries = [entry for entry in timeline if entry.type == "travel"]
        assert feasible is True
        assert codes == []
        assert [entry.duration_seconds for entry in travel_entries] == [111, 222]
        assert [(entry.from_index, entry.to_index) for entry in travel_entries] == [
            (0, 2),
            (2, 3),
        ]
