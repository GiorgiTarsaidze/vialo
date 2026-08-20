"""Tests for target stop density and the top-up decision."""

from __future__ import annotations

import datetime as dt

from vialo.domain.candidate_targets import (
    MAX_STOPS,
    is_complete_day,
    target_stop_count,
    top_up_shortfall,
)


def _window(hours: float) -> tuple[dt.datetime, dt.datetime]:
    start = dt.datetime(2026, 9, 15, 9, 0, tzinfo=dt.UTC)
    return start, start + dt.timedelta(hours=hours)


class TestTargetStopCount:
    def test_four_hour_day_targets_three_stops(self) -> None:
        start, end = _window(4)
        assert target_stop_count(start, end) == 3

    def test_eight_hour_day_targets_six_stops(self) -> None:
        start, end = _window(8)
        assert target_stop_count(start, end) == 6

    def test_short_window_still_targets_one_stop(self) -> None:
        start, end = _window(0.5)
        assert target_stop_count(start, end) == 1

    def test_target_is_capped_at_the_product_maximum(self) -> None:
        start, end = _window(20)
        assert target_stop_count(start, end) == MAX_STOPS

    def test_nonpositive_window_returns_one(self) -> None:
        start, end = _window(0)
        assert target_stop_count(start, end) == 1


class TestTopUpShortfall:
    def test_thin_day_requests_the_shortfall_plus_one_spare(self) -> None:
        start, end = _window(4)  # target 3
        assert top_up_shortfall(1, start, end) == 3

    def test_full_day_requests_nothing(self) -> None:
        start, end = _window(4)
        assert top_up_shortfall(3, start, end) == 0
        assert top_up_shortfall(5, start, end) == 0

    def test_request_never_exceeds_the_product_cap(self) -> None:
        start, end = _window(20)  # target 9
        assert top_up_shortfall(8, start, end) == 1
        assert top_up_shortfall(9, start, end) == 0


class TestIsCompleteDay:
    def test_day_that_fills_its_window_is_complete(self) -> None:
        start, end = _window(6)  # target 4
        assert is_complete_day(4, start, end) is True
        assert is_complete_day(5, start, end) is True

    def test_thin_day_is_not_complete(self) -> None:
        start, end = _window(6)
        assert is_complete_day(1, start, end) is False
        assert is_complete_day(3, start, end) is False
