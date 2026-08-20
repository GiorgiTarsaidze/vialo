"""How many stops a day should actually contain.

A four-hour day that returns one stop is a failure even when every remaining
candidate was honestly excluded. This module defines the target density used to
decide whether the pipeline should ask the selector for replacement candidates
before it gives up on filling the window.

The 90-minute unit covers one bounded visit plus the walk to it. It is a target,
never a guarantee: real opening hours and real travel times still decide what
fits, and the solver remains exact.
"""

from __future__ import annotations

import datetime as dt
import math

MAX_STOPS = 9
MINUTES_PER_STOP_SLOT = 90
# Candidates at this priority are proposed as spare ideas: they are dropped first
# when the day cannot fit everything, and they surface as suggestions instead.
RESERVE_PRIORITY = 3
RESERVE_CANDIDATE_COUNT = 2


def target_stop_count(window_start: dt.datetime, window_end: dt.datetime) -> int:
    """Return how many stops a window of this length should aim to contain."""
    window_minutes = (window_end - window_start).total_seconds() / 60
    if window_minutes <= 0:
        return 1
    slots = math.ceil(window_minutes / MINUTES_PER_STOP_SLOT)
    return max(1, min(MAX_STOPS, slots))


def top_up_shortfall(
    retained_stops: int, window_start: dt.datetime, window_end: dt.datetime
) -> int:
    """Return how many extra candidates to request, or 0 when the day is full enough."""
    target = target_stop_count(window_start, window_end)
    if retained_stops >= target:
        return 0
    # Ask for the shortfall plus one spare, without exceeding the product cap.
    return min(MAX_STOPS - retained_stops, target - retained_stops + 1)


def is_complete_day(
    retained_stops: int, window_start: dt.datetime, window_end: dt.datetime
) -> bool:
    """Whether the scheduled day fills its window, regardless of unused spare ideas."""
    return retained_stops >= target_stop_count(window_start, window_end)
