"""Contract tests: camelCase alias round-trip compatibility."""

from __future__ import annotations

import datetime as dt

from vialo.models.itinerary import (
    ComparisonUnavailable,
    GroundedStop,
    ItineraryResponse,
    Locality,
    MapsHandoff,
    OpenInterval,
    ShareProof,
    TimeWindow,
    Totals,
    TravelEntry,
    VisitEntry,
)
from vialo.models.providers import GroundedPlace, Location, StopCategory


def _build_minimal_response() -> ItineraryResponse:
    """Build a minimal valid ItineraryResponse."""
    tz = dt.UTC
    now = dt.datetime(2026, 8, 15, 7, 0, tzinfo=tz)
    origin = GroundedPlace(
        place_id="origin_id",
        display_name="Hotel",
        formatted_address="Hotel St 1",
        location=Location(latitude=45.43, longitude=12.34),
        time_zone_id="Europe/Rome",
    )
    stop = GroundedStop(
        candidate_index=0,
        name="San Marco",
        category=StopCategory.HISTORIC_RELIGIOUS_SITE,
        priority=1,
        visit_duration_minutes=50,
        duration_source="model_estimate",
        place=GroundedPlace(
            place_id="san_marco_id",
            display_name="San Marco",
            formatted_address="P.za San Marco",
            location=Location(latitude=45.434, longitude=12.339),
            time_zone_id="Europe/Rome",
        ),
        hours_source="current",
        open_intervals=[
            OpenInterval(
                start=now + dt.timedelta(hours=2, minutes=30),
                end=now + dt.timedelta(hours=10, minutes=15),
                local_start="09:30",
                local_end="17:15",
            )
        ],
    )
    return ItineraryResponse(
        schema_version=1,
        request_id="test-123",
        status="complete",
        locality=Locality(name="Venice", time_zone_id="Europe/Rome"),
        travel_mode="WALK",
        window=TimeWindow(
            start=now + dt.timedelta(hours=2),
            end=now + dt.timedelta(hours=12),
            local_start="09:00",
            local_end="19:00",
            date=dt.date(2026, 8, 15),
        ),
        origin=origin,
        stops=[stop],
        timeline=[
            TravelEntry(
                type="travel",
                from_index=0,
                to_index=1,
                mode="WALK",
                duration_seconds=300,
                distance_meters=500,
                departure=now + dt.timedelta(hours=2),
                arrival=now + dt.timedelta(hours=2, minutes=5),
            ),
            VisitEntry(
                type="visit",
                stop_index=1,
                arrival=now + dt.timedelta(hours=2, minutes=30),
                departure=now + dt.timedelta(hours=3, minutes=20),
                duration_minutes=50,
                interval_used=stop.open_intervals[0],
            ),
        ],
        dropped_stops=[],
        comparison=ComparisonUnavailable(status="unavailable", reason_code="TEST"),
        maps_handoff=MapsHandoff(
            full_route_url="https://maps.google.com/test",
            full_route_universally_supported=True,
            browser_safe_parts=[],
        ),
        totals=Totals(visit_seconds=3000, travel_seconds=300, wait_seconds=0, elapsed_seconds=3300),
        diagnostics=[],
        share_proof=ShareProof(
            expires_at=now + dt.timedelta(days=30),
            hmac="test_hmac",
        ),
    )


class TestCamelCaseRoundTrip:
    def test_serialize_uses_camel_case(self) -> None:
        """Serialized JSON uses camelCase keys."""
        resp = _build_minimal_response()
        data = resp.model_dump(mode="json", by_alias=True)
        # Top-level keys should be camelCase
        assert "schemaVersion" in data
        assert "requestId" in data
        assert "travelMode" in data
        assert "mapsHandoff" in data
        assert "shareProof" in data
        assert "droppedStops" in data
        # Should NOT have snake_case versions at top level
        assert "schema_version" not in data
        assert "request_id" not in data

    def test_round_trip_json(self) -> None:
        """Serialize to JSON and deserialize back produces equivalent model.

        Uses model_validate_json which correctly handles strict mode with
        JSON-native datetime string parsing.
        """
        resp = _build_minimal_response()
        json_str = resp.model_dump_json(by_alias=True)
        # model_validate_json handles string→datetime in JSON mode even with strict=True
        reconstructed = ItineraryResponse.model_validate_json(json_str)
        assert reconstructed.request_id == resp.request_id
        assert reconstructed.schema_version == 1
        assert reconstructed.locality.name == "Venice"
        assert len(reconstructed.stops) == 1
        assert reconstructed.stops[0].name == "San Marco"

    def test_nested_camel_case(self) -> None:
        """Nested objects also use camelCase."""
        resp = _build_minimal_response()
        data = resp.model_dump(mode="json", by_alias=True)
        # Check nested stop
        stop = data["stops"][0]
        assert "candidateIndex" in stop
        assert "visitDurationMinutes" in stop
        assert "durationSource" in stop
        assert "openIntervals" in stop
        # Check nested place
        place = stop["place"]
        assert "placeId" in place
        assert "displayName" in place
        assert "formattedAddress" in place
        assert "timeZoneId" in place

    def test_timeline_discriminator(self) -> None:
        """Timeline entries have type discriminator in JSON."""
        resp = _build_minimal_response()
        data = resp.model_dump(mode="json", by_alias=True)
        timeline = data["timeline"]
        assert timeline[0]["type"] == "travel"
        assert timeline[1]["type"] == "visit"
