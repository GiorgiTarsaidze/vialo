"""Category-based duration bounds and validation.

Spec values (min/default/max):
  quick: 15/20/30
  landmark: 30/45/75
  museum: 60/90/180
  historic: 30/60/120
  neighborhood: 30/60/120
  food: 30/60/120
  experience: 60/120/240
  other: 30/60/90
"""

from __future__ import annotations

import re

from vialo.models.providers import StopCategory

# (min_minutes, default_minutes, max_minutes) per category — committed spec values
CATEGORY_BOUNDS: dict[StopCategory, tuple[int, int, int]] = {
    StopCategory.QUICK_VIEWPOINT: (15, 20, 30),
    StopCategory.LANDMARK: (30, 45, 75),
    StopCategory.MUSEUM_GALLERY: (60, 90, 180),
    StopCategory.HISTORIC_RELIGIOUS_SITE: (30, 60, 120),
    StopCategory.NEIGHBORHOOD_MARKET_PARK: (30, 60, 120),
    StopCategory.FOOD_BREAK: (30, 60, 120),
    StopCategory.EXPERIENCE_TOUR: (60, 120, 240),
    StopCategory.OTHER: (30, 60, 90),
}

# Regex patterns for parsing human-readable duration strings
_MINUTES_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:min(?:ute)?s?|m)\s*$", re.IGNORECASE)
_HOURS_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:hour|hr|h)s?\s*$", re.IGNORECASE)
_HOURS_MINUTES_RE = re.compile(
    r"^\s*(\d+)\s*(?:hour|hr|h)s?\s*(?:and\s*)?(\d+)\s*(?:min(?:ute)?s?|m)\s*$",
    re.IGNORECASE,
)
_BARE_NUMBER_RE = re.compile(r"^\s*(\d+)\s*$")
_HALF_HOUR_RE = re.compile(r"^\s*(?:a\s+)?half\s+(?:an?\s+)?hour\s*$", re.IGNORECASE)


def parse_duration_text(text: str | None) -> int | None:
    """Parse a human-readable duration string into minutes.

    Handles:
      "30 minutes", "30 min", "30m", "30"
      "1.5 hours", "1 hour 30 minutes", "2h", "1hr"
      "90" (bare number interpreted as minutes)

    Returns None if unparseable or invalid.
    """
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None

    # Try idiomatic half-hour forms.
    if _HALF_HOUR_RE.match(text):
        return 30

    # Try hours + minutes: "1 hour 30 minutes"
    m = _HOURS_MINUTES_RE.match(text)
    if m:
        hours = int(m.group(1))
        minutes = int(m.group(2))
        total = hours * 60 + minutes
        return total if total > 0 else None

    # Try hours: "1.5 hours"
    m = _HOURS_RE.match(text)
    if m:
        hours_f = float(m.group(1))
        total = int(hours_f * 60)
        return total if total > 0 else None

    # Try minutes: "30 minutes"
    m = _MINUTES_RE.match(text)
    if m:
        minutes_f = float(m.group(1))
        total = int(minutes_f)
        return total if total > 0 else None

    # Try bare number
    m = _BARE_NUMBER_RE.match(text)
    if m:
        total = int(m.group(1))
        return total if total > 0 else None

    return None


def validate_model_duration(category: StopCategory, minutes: int) -> bool:
    """Check if a model-estimated duration is within the category bounds."""
    bounds = CATEGORY_BOUNDS.get(category)
    if bounds is None:
        return 15 <= minutes <= 240
    min_val, _, max_val = bounds
    return min_val <= minutes <= max_val


def validate_user_duration(minutes: int) -> bool:
    """Check if a user-specified duration is in the global allowed range."""
    return 15 <= minutes <= 240


def default_duration(category: StopCategory) -> int:
    """Return the default visit duration for a category."""
    bounds = CATEGORY_BOUNDS.get(category)
    if bounds is None:
        return 60
    return bounds[1]
