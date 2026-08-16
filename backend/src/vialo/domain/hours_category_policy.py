"""Opening-hours safety policy.

Vialo never creates availability when Google supplies no usable hours. Every
candidate category requires verified current or regular opening hours; missing
hours remain an exclusion that the bounded repair pass may replace with a
separately grounded place.
"""

from __future__ import annotations

from vialo.models.providers import StopCategory


def requires_verified_hours(category: StopCategory) -> bool:
    """Return whether a category requires provider-backed opening hours.

    The category argument keeps the policy explicit at call sites and makes
    future category additions fail safely: all current and future categories
    require verified hours.
    """
    del category
    return True
