"""Pipeline step 5b: Build Google Maps handoff URLs."""

from __future__ import annotations

from vialo.domain.maps_url import build_handoff
from vialo.models.itinerary import GroundedStop, MapsHandoff
from vialo.models.providers import GroundedPlace, TravelMode


def build_maps_handoff_step(
    origin: GroundedPlace,
    ordered_stops: list[GroundedStop],
    travel_mode: TravelMode,
    return_to_origin: bool,
) -> MapsHandoff:
    """Build the Maps handoff with full URL and browser-safe parts."""
    return build_handoff(
        origin=origin,
        ordered_stops=ordered_stops,
        travel_mode=travel_mode,
        return_to_origin=return_to_origin,
    )
