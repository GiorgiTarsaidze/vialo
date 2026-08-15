"""Opening-hours normalization for one requested local date."""

from __future__ import annotations

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

from vialo.domain.timezones import LocalTimeAmbiguousError, validate_local_time
from vialo.models.diagnostics import DiagnosticCode
from vialo.models.itinerary import OpenInterval


def derive_coverage_window(fetch_date_local: dt.date) -> tuple[dt.date, dt.date]:
    """Return the documented seven-local-date current-hours window."""
    return fetch_date_local, fetch_date_local + dt.timedelta(days=6)


def _parse_period_date(part: dict[str, Any]) -> dt.date | None:
    value = part.get("date")
    if not isinstance(value, dict):
        return None
    try:
        return dt.date(int(value["year"]), int(value["month"]), int(value["day"]))
    except (KeyError, TypeError, ValueError):
        return None


def _localize(date: dt.date, hour: int, minute: int, tz_id: str) -> dt.datetime:
    """Construct an aware boundary and reject gaps and folds."""
    return validate_local_time(dt.time(hour, minute), date, tz_id)


def _parse_period_time(part: dict[str, Any]) -> tuple[int, int] | None:
    try:
        hour = int(part.get("hour", 0))
        minute = int(part.get("minute", 0))
    except (TypeError, ValueError):
        return None
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return None
    return hour, minute


def _period_to_interval(
    period: dict[str, Any],
    default_open_date: dt.date,
    tz_id: str,
) -> OpenInterval | DiagnosticCode | None:
    open_part = period.get("open")
    close_part = period.get("close")
    if not isinstance(open_part, dict):
        return None
    open_time = _parse_period_time(open_part)
    if open_time is None:
        return None
    open_hour, open_minute = open_time
    open_date = _parse_period_date(open_part) or default_open_date

    try:
        open_at = _localize(open_date, open_hour, open_minute, tz_id)
    except LocalTimeAmbiguousError:
        return DiagnosticCode.LOCAL_TIME_AMBIGUOUS

    if isinstance(close_part, dict):
        close_time = _parse_period_time(close_part)
        if close_time is None:
            return None
        close_hour, close_minute = close_time
        close_date = _parse_period_date(close_part)
        if close_date is None:
            close_date = open_date
            if close_time <= open_time:
                close_date += dt.timedelta(days=1)
        try:
            close_at = _localize(close_date, close_hour, close_minute, tz_id)
        except LocalTimeAmbiguousError:
            return DiagnosticCode.LOCAL_TIME_AMBIGUOUS
        local_end = f"{close_hour:02d}:{close_minute:02d}"
    else:
        try:
            close_at = _localize(open_date + dt.timedelta(days=1), 0, 0, tz_id)
        except LocalTimeAmbiguousError:
            return DiagnosticCode.LOCAL_TIME_AMBIGUOUS
        local_end = "24:00"

    if close_at <= open_at:
        return None
    return OpenInterval(
        start=open_at,
        end=close_at,
        local_start=f"{open_hour:02d}:{open_minute:02d}",
        local_end=local_end,
    )


def _clip_to_date(
    interval: OpenInterval,
    requested_date: dt.date,
    tz_id: str,
) -> OpenInterval | DiagnosticCode | None:
    try:
        day_start = _localize(requested_date, 0, 0, tz_id)
        day_end = _localize(requested_date + dt.timedelta(days=1), 0, 0, tz_id)
    except LocalTimeAmbiguousError:
        return DiagnosticCode.LOCAL_TIME_AMBIGUOUS

    start = max(interval.start, day_start)
    end = min(interval.end, day_end)
    if end <= start:
        return None
    return OpenInterval(
        start=start,
        end=end,
        local_start=start.astimezone(ZoneInfo(tz_id)).strftime("%H:%M"),
        local_end=(
            "24:00" if end == day_end else end.astimezone(ZoneInfo(tz_id)).strftime("%H:%M")
        ),
    )


def _current_period_intersects(period: dict[str, Any], requested_date: dt.date) -> bool:
    open_part = period.get("open")
    if not isinstance(open_part, dict):
        return False
    open_date = _parse_period_date(open_part)
    open_time = _parse_period_time(open_part)
    if open_date is None or open_time is None or open_date > requested_date:
        return False

    close_part = period.get("close")
    if not isinstance(close_part, dict):
        return True
    close_time = _parse_period_time(close_part)
    if close_time is None:
        return False

    close_date = _parse_period_date(close_part)
    if close_date is not None:
        return (
            close_date > requested_date
            or (close_date == requested_date and close_time > (0, 0))
            or open_date == requested_date
        )

    inferred_close = open_date + dt.timedelta(days=close_time <= open_time)
    return open_date <= requested_date <= inferred_close


def _extract_current_periods_for_date(
    current_hours: dict[str, Any], requested_date: dt.date, tz_id: str
) -> list[OpenInterval] | DiagnosticCode | None:
    periods = current_hours.get("periods")
    if not isinstance(periods, list) or not periods:
        return None

    intervals: list[OpenInterval] = []
    for raw_period in periods:
        if not isinstance(raw_period, dict) or not _current_period_intersects(
            raw_period, requested_date
        ):
            continue
        period = raw_period
        open_part = period.get("open", {})
        open_date = _parse_period_date(open_part)
        if open_date is None:
            continue

        # An ongoing no-close period opened before this date covers this whole date.
        if period.get("close") is None and open_date < requested_date:
            period = {
                "open": {
                    "date": {
                        "year": requested_date.year,
                        "month": requested_date.month,
                        "day": requested_date.day,
                    },
                    "hour": 0,
                    "minute": 0,
                }
            }
            open_date = requested_date

        interval = _period_to_interval(period, open_date, tz_id)
        if isinstance(interval, DiagnosticCode):
            return interval
        if not isinstance(interval, OpenInterval):
            continue
        clipped = _clip_to_date(interval, requested_date, tz_id)
        if isinstance(clipped, DiagnosticCode):
            return clipped
        if isinstance(clipped, OpenInterval):
            intervals.append(clipped)

    return intervals or None


def _extract_regular_periods_for_weekday(
    regular_hours: dict[str, Any], requested_date: dt.date, tz_id: str
) -> list[OpenInterval] | DiagnosticCode:
    periods = regular_hours.get("periods")
    if not isinstance(periods, list):
        return []

    google_day = (requested_date.weekday() + 1) % 7
    previous_google_day = (google_day - 1) % 7
    intervals: list[OpenInterval] = []

    for period in periods:
        if not isinstance(period, dict):
            continue
        open_part = period.get("open")
        if not isinstance(open_part, dict):
            continue
        open_day = open_part.get("day")
        open_time = _parse_period_time(open_part)
        if open_time is None:
            continue

        # Places represents 24/7 regular hours as Sunday 00:00 with no close.
        always_open = period.get("close") is None and open_day == 0 and open_time == (0, 0)
        if always_open or open_day == google_day:
            base_date = requested_date
        elif open_day == previous_google_day:
            base_date = requested_date - dt.timedelta(days=1)
        else:
            continue

        interval = _period_to_interval(period, base_date, tz_id)
        if isinstance(interval, DiagnosticCode):
            return interval
        if not isinstance(interval, OpenInterval):
            continue
        clipped = _clip_to_date(interval, requested_date, tz_id)
        if isinstance(clipped, DiagnosticCode):
            return clipped
        if isinstance(clipped, OpenInterval):
            intervals.append(clipped)

    return intervals


def normalize_opening_hours(
    current_hours: dict[str, Any] | None,
    regular_hours: dict[str, Any] | None,
    requested_date: dt.date,
    tz_id: str,
    fetch_instant: dt.datetime,
) -> list[OpenInterval] | DiagnosticCode:
    """Choose authoritative current hours or recurring fallback for one date."""
    fetch_local_date = fetch_instant.astimezone(ZoneInfo(tz_id)).date()
    coverage_start, coverage_end = derive_coverage_window(fetch_local_date)

    if current_hours is not None and coverage_start <= requested_date <= coverage_end:
        intervals = _extract_current_periods_for_date(current_hours, requested_date, tz_id)
        if isinstance(intervals, DiagnosticCode):
            return intervals
        if isinstance(intervals, list) and intervals:
            return sorted(intervals, key=lambda value: value.start)
        return DiagnosticCode.CLOSED_ON_DATE

    if regular_hours is not None:
        intervals = _extract_regular_periods_for_weekday(regular_hours, requested_date, tz_id)
        if isinstance(intervals, DiagnosticCode):
            return intervals
        if intervals:
            return sorted(intervals, key=lambda value: value.start)
        return DiagnosticCode.CLOSED_ON_DATE

    return DiagnosticCode.HOURS_UNAVAILABLE
