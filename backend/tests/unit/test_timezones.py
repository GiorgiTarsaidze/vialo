"""Tests for timezone helpers: DST detection, UTC conversion."""

from __future__ import annotations

import datetime as dt

import pytest

from vialo.domain.timezones import (
    LocalTimeAmbiguousError,
    is_same_timezone,
    local_today,
    make_aware,
    to_utc,
    validate_local_time,
)


class TestMakeAware:
    def test_attaches_timezone(self) -> None:
        naive = dt.datetime(2026, 8, 15, 9, 30)
        aware = make_aware(naive, "Europe/Rome")
        assert aware.tzinfo is not None
        assert aware.hour == 9
        assert aware.minute == 30

    def test_utc_roundtrip(self) -> None:
        naive = dt.datetime(2026, 8, 15, 9, 0)
        aware = make_aware(naive, "Europe/Rome")
        utc = to_utc(aware)
        # CEST is UTC+2
        assert utc.hour == 7


class TestValidateLocalTime:
    def test_normal_time_succeeds(self) -> None:
        result = validate_local_time(dt.time(9, 30), dt.date(2026, 8, 15), "Europe/Rome")
        assert result.hour == 9
        assert result.minute == 30
        assert result.tzinfo is not None

    def test_dst_spring_forward_gap(self) -> None:
        """In Europe/Rome, clocks spring forward on last Sunday of March.
        2026-03-29: 02:00 -> 03:00 (02:30 doesn't exist)."""
        with pytest.raises(LocalTimeAmbiguousError):
            validate_local_time(dt.time(2, 30), dt.date(2026, 3, 29), "Europe/Rome")

    def test_dst_fall_back_fold(self) -> None:
        """In Europe/Rome, clocks fall back on last Sunday of October.
        2026-10-25: 03:00 -> 02:00 (02:30 is ambiguous)."""
        with pytest.raises(LocalTimeAmbiguousError):
            validate_local_time(dt.time(2, 30), dt.date(2026, 10, 25), "Europe/Rome")

    def test_midnight_valid(self) -> None:
        result = validate_local_time(dt.time(0, 0), dt.date(2026, 8, 15), "Europe/Rome")
        assert result.hour == 0


class TestLocalToday:
    def test_returns_date(self) -> None:
        today = local_today("Europe/Rome")
        assert isinstance(today, dt.date)


class TestIsSameTimezone:
    def test_same_zone(self) -> None:
        assert is_same_timezone("Europe/Rome", "Europe/Rome") is True

    def test_different_zones(self) -> None:
        assert is_same_timezone("Europe/Rome", "America/New_York") is False
