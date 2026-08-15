"""Google Maps URL builder with official parameter format.

Official Maps URL format uses SEPARATE parameters:
  - origin (text/coords) + origin_place_id
  - destination (text/coords) + destination_place_id
  - waypoints (text/coords pipe-separated) + waypoint_place_ids (pipe-separated)
  - travelmode
  - api=1

NEVER use `origin=place_id:...` format.
Apply to full URL and overlapping browser-safe parts.
Max 3 intermediate waypoints per part for mobile browser support.
"""

from __future__ import annotations

from urllib.parse import quote

from vialo.models.itinerary import GroundedStop, MapsHandoff, MapsHandoffPart
from vialo.models.providers import GroundedPlace, Location, TravelMode

MAX_URL_LENGTH = 2048
MAX_BROWSER_INTERMEDIATES = 3


def _travel_mode_param(mode: TravelMode) -> str:
    """Convert internal travel mode to Google Maps URL parameter."""
    if mode == "WALK":
        return "walking"
    return "driving"


def _location_text(loc: Location) -> str:
    """Format coordinates as text for Maps URLs."""
    return f"{loc.latitude},{loc.longitude}"


def build_full_url(
    origin: GroundedPlace,
    waypoints: list[GroundedPlace],
    destination: GroundedPlace,
    travel_mode: TravelMode,
) -> str | None:
    """Build the full Google Maps directions URL using official parameter format.

    Uses:
      origin=<coords>&origin_place_id=<id>
      destination=<coords>&destination_place_id=<id>
      waypoints=<coords1>|<coords2>&waypoint_place_ids=<id1>|<id2>
      travelmode=<mode>&api=1

    Returns None if the URL exceeds 2048 characters.
    """
    base = "https://www.google.com/maps/dir/?api=1"

    # Origin
    origin_text = _location_text(origin.location)
    origin_param = f"&origin={quote(origin_text, safe=',')}"
    origin_pid_param = f"&origin_place_id={quote(origin.place_id, safe='')}"

    # Destination
    dest_text = _location_text(destination.location)
    dest_param = f"&destination={quote(dest_text, safe=',')}"
    dest_pid_param = f"&destination_place_id={quote(destination.place_id, safe='')}"

    # Waypoints (aligned 1:1 between waypoints and waypoint_place_ids)
    wp_param = ""
    wp_pid_param = ""
    if waypoints:
        wp_texts = [_location_text(w.location) for w in waypoints]
        wp_ids = [w.place_id for w in waypoints]
        wp_str = "|".join(wp_texts)
        wp_id_str = "|".join(wp_ids)
        wp_param = f"&waypoints={quote(wp_str, safe=',|')}"
        wp_pid_param = f"&waypoint_place_ids={quote(wp_id_str, safe='|')}"

    mode_param = f"&travelmode={_travel_mode_param(travel_mode)}"

    url = (
        f"{base}{origin_param}{origin_pid_param}"
        f"{dest_param}{dest_pid_param}"
        f"{wp_param}{wp_pid_param}{mode_param}"
    )

    if len(url) > MAX_URL_LENGTH:
        return None
    return url


def build_browser_safe_parts(
    origin: GroundedPlace,
    waypoints: list[GroundedPlace],
    destination: GroundedPlace,
    travel_mode: TravelMode,
) -> list[MapsHandoffPart]:
    """Build overlapping browser-safe URL parts with max 3 intermediates each.

    Each part overlaps with the next: the last waypoint of part N is the origin of part N+1.
    Uses the same official parameter format as build_full_url.
    """
    if not waypoints:
        # Single segment: origin to destination
        url = build_full_url(origin, [], destination, travel_mode)
        if url is None:
            return []
        return [
            MapsHandoffPart(
                part=1,
                total_parts=1,
                start_stop_index=0,
                end_stop_index=0,
                url=url,
            )
        ]

    parts: list[MapsHandoffPart] = []
    segment_start = origin
    idx = 0

    while idx < len(waypoints):
        chunk = waypoints[idx : idx + MAX_BROWSER_INTERMEDIATES]
        remaining_after = waypoints[idx + len(chunk) :]

        if remaining_after:
            # Not the last segment: last point in chunk becomes destination for this part
            # and origin for the next
            seg_waypoints = chunk[:-1]
            seg_dest = chunk[-1]
        else:
            # Last segment: all chunk items are waypoints, final destination is dest
            seg_waypoints = chunk
            seg_dest = destination

        url = build_full_url(segment_start, seg_waypoints, seg_dest, travel_mode)
        if url is None:
            # Never drop intermediates to make a URL fit.
            return []

        start_stop_index = idx
        end_stop_index = min(idx + len(chunk) - 1, len(waypoints) - 1)

        parts.append(
            MapsHandoffPart(
                part=len(parts) + 1,
                total_parts=0,  # fixed below
                start_stop_index=start_stop_index,
                end_stop_index=end_stop_index,
                url=url,
            )
        )

        if remaining_after:
            # The previous destination is the next origin; continue with the next
            # unvisited waypoint rather than repeating that destination.
            segment_start = chunk[-1]
            idx += len(chunk)
        else:
            break

        if idx >= len(waypoints):
            break

    # Fix total_parts
    total = len(parts)
    fixed_parts = [
        MapsHandoffPart(
            part=p.part,
            total_parts=total,
            start_stop_index=p.start_stop_index,
            end_stop_index=p.end_stop_index,
            url=p.url,
        )
        for p in parts
    ]
    return fixed_parts


def build_handoff(
    origin: GroundedPlace,
    ordered_stops: list[GroundedStop],
    travel_mode: TravelMode,
    return_to_origin: bool,
) -> MapsHandoff:
    """Build the complete Maps handoff with full URL and browser-safe parts.

    When return_to_origin is True, all stops are waypoints and destination = origin.
    Otherwise, last stop is the destination and preceding stops are waypoints.
    """
    if not ordered_stops:
        # No stops — origin to origin (or just origin)
        dest = origin
        waypoint_places: list[GroundedPlace] = []
    elif return_to_origin:
        # All stops are waypoints, destination = origin
        waypoint_places = [s.place for s in ordered_stops]
        dest = origin
    else:
        # Last stop is destination, rest are waypoints
        waypoint_places = [s.place for s in ordered_stops[:-1]]
        dest = ordered_stops[-1].place

    full_url = build_full_url(
        origin=origin,
        waypoints=waypoint_places,
        destination=dest,
        travel_mode=travel_mode,
    )

    # Determine warnings
    warning_code: str | None = None
    universally_supported = True

    if full_url is None:
        warning_code = "FULL_URL_TOO_LONG"
        universally_supported = False
    elif len(waypoint_places) > MAX_BROWSER_INTERMEDIATES:
        warning_code = "MOBILE_WAYPOINT_LIMIT"
        universally_supported = False

    # Build browser-safe parts
    browser_parts = build_browser_safe_parts(
        origin=origin,
        waypoints=waypoint_places,
        destination=dest,
        travel_mode=travel_mode,
    )

    error_code: str | None = None
    if not full_url and not browser_parts:
        error_code = "HANDOFF_UNAVAILABLE"

    return MapsHandoff(
        full_route_url=full_url,
        full_route_universally_supported=universally_supported,
        browser_safe_parts=browser_parts,
        warning_code=warning_code,  # type: ignore[arg-type]
        error_code=error_code,  # type: ignore[arg-type]
    )
