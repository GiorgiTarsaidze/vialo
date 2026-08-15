"""Timezone helpers using zoneinfo. No external dependencies beyond stdlib."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from vialo.models.diagnostics import DiagnosticCode


class LocalTimeAmbiguousError(Exception):
    """Raised when a local time is ambiguous (fold) or nonexistent (gap)."""

    def __init__(self, code: DiagnosticCode = DiagnosticCode.LOCAL_TIME_AMBIGUOUS) -> None:
        self.code = code
        super().__init__(f"Local time error: {code}")


def make_aware(dt_naive: dt.datetime, tz_id: str) -> dt.datetime:
    """Attach a timezone only after rejecting ambiguous or nonexistent local time."""
    if dt_naive.tzinfo is not None:
        raise ValueError("make_aware requires a naive datetime")
    return validate_local_time(dt_naive.time(), dt_naive.date(), tz_id)


def validate_local_time(t: dt.time, date: dt.date, tz_id: str) -> dt.datetime:
    """Convert a local time+date to a UTC-aware datetime.

    Raises LocalTimeAmbiguousError if the time falls in a DST fold or gap.
    """
    tz = ZoneInfo(tz_id)
    naive = dt.datetime.combine(date, t)

    # Check for gap (nonexistent) or fold (ambiguous)
    aware_fold0 = naive.replace(tzinfo=tz, fold=0)
    aware_fold1 = naive.replace(tzinfo=tz, fold=1)

    utc_fold0 = aware_fold0.astimezone(dt.UTC)
    utc_fold1 = aware_fold1.astimezone(dt.UTC)

    # If converting back gives a different local time, it's in a gap
    back0 = utc_fold0.astimezone(tz).replace(tzinfo=None)
    if back0 != naive:
        raise LocalTimeAmbiguousError()

    # If the two folds give different UTC times, it's ambiguous
    if utc_fold0 != utc_fold1:
        raise LocalTimeAmbiguousError()

    return aware_fold0


def local_today(tz_id: str) -> dt.date:
    """Get today's date in the specified timezone."""
    tz = ZoneInfo(tz_id)
    return dt.datetime.now(tz).date()


def to_utc(aware_dt: dt.datetime) -> dt.datetime:
    """Convert any aware datetime to UTC."""
    return aware_dt.astimezone(dt.UTC)


def is_same_timezone(tz_a: str, tz_b: str) -> bool:
    """Check if two IANA timezone IDs resolve to the same zone."""
    return ZoneInfo(tz_a) == ZoneInfo(tz_b)
