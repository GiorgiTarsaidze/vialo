"""Opening-hours safety policy.

When Google supplies no usable hours (HOURS_UNAVAILABLE), the stop is retained
for all categories with an open interval exactly covering the user's requested
scheduling window and hours_source='unverified'. The solver treats it as
schedule-unconstrained. CLOSED_ON_DATE remains an exclusion.
"""

from __future__ import annotations

from vialo.models.providers import StopCategory


def requires_verified_hours(category: StopCategory) -> bool:
    """Return whether a category requires provider-backed opening hours.

    Returns False for all categories: missing hours are handled by retaining the
    stop with an unverified window-covering interval. CLOSED_ON_DATE (explicit
    closure) is still excluded at the grounding level before this policy applies.
    """
    del category
    return False
