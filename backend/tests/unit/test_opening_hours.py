"""Tests for opening hours normalization and coverage window."""

from __future__ import annotations

import datetime as dt
from typing import Any

from vialo.domain.opening_hours import (
    derive_coverage_window,
    normalize_opening_hours,
)
from vialo.models.diagnostics import DiagnosticCode


class TestCoverageWindow:
    def test_seven_day_window(self) -> None:
        start, end = derive_coverage_window(dt.date(2026, 8, 13))
        assert start == dt.date(2026, 8, 13)
        assert end == dt.date(2026, 8, 19)

    def test_window_spans_month_boundary(self) -> None:
        start, end = derive_coverage_window(dt.date(2026, 7, 28))
        assert end == dt.date(2026, 8, 3)


class TestNormalizeOpeningHours:
    """Test the full normalization logic."""

    def test_current_hours_hit_date(self) -> None:
        """Current hours cover the requested date — use them."""
        current = {
            "periods": [
                {
                    "open": {
                        "day": 6,
                        "hour": 9,
                        "minute": 30,
                        "date": {"year": 2026, "month": 8, "day": 15},
                    },
                    "close": {
                        "day": 6,
                        "hour": 17,
                        "minute": 15,
                        "date": {"year": 2026, "month": 8, "day": 15},
                    },
                }
            ]
        }
        fetch = dt.datetime(2026, 8, 13, 12, 0, tzinfo=dt.UTC)
        result = normalize_opening_hours(
            current_hours=current,
            regular_hours=None,
            requested_date=dt.date(2026, 8, 15),
            tz_id="Europe/Rome",
            fetch_instant=fetch,
        )
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].local_start == "09:30"
        assert result[0].local_end == "17:15"

    def test_current_hours_no_match_means_closed(self) -> None:
        """Date within coverage window but no period for that day = closed."""
        current = {
            "periods": [
                {
                    "open": {
                        "day": 1,
                        "hour": 9,
                        "minute": 0,
                        "date": {"year": 2026, "month": 8, "day": 17},
                    },
                    "close": {
                        "day": 1,
                        "hour": 17,
                        "minute": 0,
                        "date": {"year": 2026, "month": 8, "day": 17},
                    },
                }
            ]
        }
        fetch = dt.datetime(2026, 8, 15, 12, 0, tzinfo=dt.UTC)
        result = normalize_opening_hours(
            current_hours=current,
            regular_hours=None,
            requested_date=dt.date(2026, 8, 16),  # Sunday, no period
            tz_id="Europe/Rome",
            fetch_instant=fetch,
        )
        assert result == DiagnosticCode.CLOSED_ON_DATE

    def test_outside_coverage_uses_regular(self) -> None:
        """Date outside coverage window falls back to regular hours."""
        regular = {
            "periods": [
                {
                    "open": {"day": 1, "hour": 9, "minute": 30},
                    "close": {"day": 1, "hour": 17, "minute": 15},
                }
            ]
        }
        fetch = dt.datetime(2026, 8, 1, 12, 0, tzinfo=dt.UTC)
        # Request date far outside coverage — Monday Aug 24
        result = normalize_opening_hours(
            current_hours=None,
            regular_hours=regular,
            requested_date=dt.date(2026, 8, 24),  # Monday
            tz_id="Europe/Rome",
            fetch_instant=fetch,
        )
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].local_start == "09:30"

    def test_no_source_returns_unavailable(self) -> None:
        """No current or regular hours = HOURS_UNAVAILABLE."""
        fetch = dt.datetime(2026, 8, 15, 12, 0, tzinfo=dt.UTC)
        result = normalize_opening_hours(
            current_hours=None,
            regular_hours=None,
            requested_date=dt.date(2026, 8, 15),
            tz_id="Europe/Rome",
            fetch_instant=fetch,
        )
        assert result == DiagnosticCode.HOURS_UNAVAILABLE

    def test_regular_hours_closed_day(self) -> None:
        """Regular hours exist but not for the requested weekday."""
        # Only Monday open
        regular = {
            "periods": [
                {
                    "open": {"day": 1, "hour": 9, "minute": 0},
                    "close": {"day": 1, "hour": 17, "minute": 0},
                }
            ]
        }
        fetch = dt.datetime(2026, 8, 1, 12, 0, tzinfo=dt.UTC)
        # Request Saturday (day 6)
        result = normalize_opening_hours(
            current_hours=None,
            regular_hours=regular,
            requested_date=dt.date(2026, 8, 22),  # Saturday
            tz_id="Europe/Rome",
            fetch_instant=fetch,
        )
        assert result == DiagnosticCode.CLOSED_ON_DATE

    def test_multiple_periods_same_day(self) -> None:
        """Multiple periods for the same day (split hours)."""
        current = {
            "periods": [
                {
                    "open": {
                        "day": 6,
                        "hour": 9,
                        "minute": 0,
                        "date": {"year": 2026, "month": 8, "day": 15},
                    },
                    "close": {
                        "day": 6,
                        "hour": 12,
                        "minute": 30,
                        "date": {"year": 2026, "month": 8, "day": 15},
                    },
                },
                {
                    "open": {
                        "day": 6,
                        "hour": 14,
                        "minute": 0,
                        "date": {"year": 2026, "month": 8, "day": 15},
                    },
                    "close": {
                        "day": 6,
                        "hour": 18,
                        "minute": 0,
                        "date": {"year": 2026, "month": 8, "day": 15},
                    },
                },
            ]
        }
        fetch = dt.datetime(2026, 8, 13, 12, 0, tzinfo=dt.UTC)
        result = normalize_opening_hours(
            current_hours=current,
            regular_hours=None,
            requested_date=dt.date(2026, 8, 15),
            tz_id="Europe/Rome",
            fetch_instant=fetch,
        )
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].local_start == "09:00"
        assert result[1].local_start == "14:00"

    def test_canonical_fixture(self, places_san_marco_fixture: dict[str, Any]) -> None:
        """Test with the canonical San Marco fixture."""
        place = places_san_marco_fixture["places"][0]
        current = place["currentOpeningHours"]
        regular = place["regularOpeningHours"]
        fetch = dt.datetime(2026, 8, 13, 12, 0, tzinfo=dt.UTC)

        # Saturday Aug 15
        result = normalize_opening_hours(
            current_hours=current,
            regular_hours=regular,
            requested_date=dt.date(2026, 8, 15),
            tz_id="Europe/Rome",
            fetch_instant=fetch,
        )
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].local_start == "09:30"
        assert result[0].local_end == "17:15"


class TestOpeningHoursAdversarialBoundaries:
    def test_previous_day_current_period_is_clipped_into_requested_date(self) -> None:
        current = {
            "periods": [
                {
                    "open": {
                        "date": {"year": 2026, "month": 8, "day": 14},
                        "hour": 22,
                        "minute": 0,
                    },
                    "close": {
                        "date": {"year": 2026, "month": 8, "day": 15},
                        "hour": 2,
                        "minute": 0,
                    },
                }
            ]
        }
        result = normalize_opening_hours(
            current,
            None,
            dt.date(2026, 8, 15),
            "Europe/Rome",
            dt.datetime(2026, 8, 14, 12, tzinfo=dt.UTC),
        )
        assert isinstance(result, list)
        assert result[0].local_start == "00:00"
        assert result[0].local_end == "02:00"

    def test_previous_weekday_regular_period_spills_into_requested_date(self) -> None:
        regular = {
            "periods": [
                {
                    "open": {"day": 0, "hour": 22, "minute": 0},
                    "close": {"day": 1, "hour": 2, "minute": 0},
                }
            ]
        }
        result = normalize_opening_hours(
            None,
            regular,
            dt.date(2026, 8, 17),  # Monday
            "Europe/Rome",
            dt.datetime(2026, 8, 1, 12, tzinfo=dt.UTC),
        )
        assert isinstance(result, list)
        assert result[0].local_start == "00:00"
        assert result[0].local_end == "02:00"

    def test_regular_always_open_period_covers_any_weekday(self) -> None:
        regular = {"periods": [{"open": {"day": 0, "hour": 0, "minute": 0}}]}
        result = normalize_opening_hours(
            None,
            regular,
            dt.date(2026, 8, 19),  # Wednesday
            "Europe/Rome",
            dt.datetime(2026, 8, 1, 12, tzinfo=dt.UTC),
        )
        assert isinstance(result, list)
        assert result[0].local_start == "00:00"
        assert result[0].local_end == "24:00"

    def test_ambiguous_dst_opening_boundary_returns_typed_diagnostic(self) -> None:
        current = {
            "periods": [
                {
                    "open": {
                        "date": {"year": 2026, "month": 10, "day": 25},
                        "hour": 2,
                        "minute": 30,
                    },
                    "close": {
                        "date": {"year": 2026, "month": 10, "day": 25},
                        "hour": 5,
                        "minute": 0,
                    },
                }
            ]
        }
        result = normalize_opening_hours(
            current,
            None,
            dt.date(2026, 10, 25),
            "Europe/Rome",
            dt.datetime(2026, 10, 24, 12, tzinfo=dt.UTC),
        )
        assert result == DiagnosticCode.LOCAL_TIME_AMBIGUOUS
