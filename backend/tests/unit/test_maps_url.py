"""Tests for Google Maps URL builder with official parameter format."""

from __future__ import annotations

import datetime as dt

from vialo.domain.maps_url import (
    MAX_URL_LENGTH,
    build_browser_safe_parts,
    build_full_url,
    build_handoff,
)
from vialo.models.itinerary import GroundedStop, OpenInterval
from vialo.models.providers import GroundedPlace, Location, StopCategory


def _make_place(place_id: str, lat: float = 45.0, lng: float = 12.0) -> GroundedPlace:
    """Create a minimal GroundedPlace for testing."""
    return GroundedPlace(
        place_id=place_id,
        display_name=f"Place {place_id}",
        formatted_address=f"Address {place_id}",
        location=Location(latitude=lat, longitude=lng),
        time_zone_id="Europe/Rome",
    )


def _make_test_stop(index: int, place_id: str) -> GroundedStop:
    """Create a minimal test stop."""
    tz = dt.UTC
    return GroundedStop(
        candidate_index=index,
        name=f"Stop {index}",
        category=StopCategory.LANDMARK,
        priority=1,
        visit_duration_minutes=30,
        duration_source="model_estimate",
        place=_make_place(place_id),
        hours_source="current",
        open_intervals=[
            OpenInterval(
                start=dt.datetime(2026, 8, 15, 9, 0, tzinfo=tz),
                end=dt.datetime(2026, 8, 15, 17, 0, tzinfo=tz),
                local_start="09:00",
                local_end="17:00",
            )
        ],
    )


class TestBuildFullUrl:
    def test_single_stop_no_intermediates(self) -> None:
        origin = _make_place("origin_id")
        dest = _make_place("dest_id")
        url = build_full_url(origin, [], dest, "WALK")
        assert url is not None
        # Official format: origin=<coords>&origin_place_id=<id>
        assert "origin=" in url
        assert "origin_place_id=origin_id" in url
        assert "destination_place_id=dest_id" in url
        assert "travelmode=walking" in url
        assert len(url) <= MAX_URL_LENGTH
        # Must NOT use origin=place_id:... format
        assert "origin=place_id:" not in url

    def test_three_stops_with_waypoints(self) -> None:
        origin = _make_place("origin_id")
        dest = _make_place("dest_id")
        waypoints = [_make_place(f"stop_{i}") for i in range(3)]
        url = build_full_url(origin, waypoints, dest, "WALK")
        assert url is not None
        assert "waypoints=" in url
        assert "waypoint_place_ids=" in url
        # All three place IDs in waypoint_place_ids
        assert "stop_0" in url
        assert "stop_1" in url
        assert "stop_2" in url

    def test_returns_none_if_too_long(self) -> None:
        """URL with many long place IDs exceeds 2048 chars."""
        origin = _make_place("origin_id")
        dest = _make_place("dest_id")
        long_waypoints = [_make_place(f"ChIJ{'x' * 200}_{i}") for i in range(9)]
        url = build_full_url(origin, long_waypoints, dest, "WALK")
        assert url is None

    def test_driving_mode(self) -> None:
        origin = _make_place("origin_id")
        dest = _make_place("dest_id")
        url = build_full_url(origin, [], dest, "DRIVE")
        assert url is not None
        assert "travelmode=driving" in url

    def test_waypoints_and_waypoint_place_ids_aligned(self) -> None:
        """Waypoints text and waypoint_place_ids must have same count."""
        origin = _make_place("origin_id")
        dest = _make_place("dest_id")
        waypoints = [_make_place(f"wp_{i}") for i in range(5)]
        url = build_full_url(origin, waypoints, dest, "WALK")
        assert url is not None
        # Count pipe separators in waypoint_place_ids
        if "waypoint_place_ids=" in url:
            pid_part = url.split("waypoint_place_ids=")[1].split("&")[0]
            pid_count = pid_part.count("|") + 1
            assert pid_count == 5

    def test_special_chars_in_place_id(self) -> None:
        """Place IDs with special chars are properly encoded."""
        origin = _make_place("ChIJ_special+chars/test")
        dest = _make_place("dest_id")
        url = build_full_url(origin, [], dest, "WALK")
        assert url is not None
        assert "origin_place_id=" in url


class TestBuildBrowserSafeParts:
    def test_no_waypoints(self) -> None:
        origin = _make_place("origin")
        dest = _make_place("dest")
        parts = build_browser_safe_parts(origin, [], dest, "WALK")
        assert len(parts) == 1
        assert parts[0].part == 1
        assert parts[0].total_parts == 1

    def test_three_waypoints_no_split_needed(self) -> None:
        """3 intermediates fit in one segment."""
        origin = _make_place("origin")
        dest = _make_place("dest")
        waypoints = [_make_place(f"s{i}") for i in range(3)]
        parts = build_browser_safe_parts(origin, waypoints, dest, "WALK")
        assert len(parts) >= 1
        for p in parts:
            assert p.total_parts == len(parts)

    def test_nine_waypoints_produces_multiple_parts(self) -> None:
        """9 waypoints need multiple overlapping segments (max 3 per part)."""
        origin = _make_place("origin")
        dest = _make_place("dest")
        waypoints = [_make_place(f"stop_{i}") for i in range(9)]
        parts = build_browser_safe_parts(origin, waypoints, dest, "WALK")
        assert len(parts) > 1
        for p in parts:
            assert p.total_parts == len(parts)
            assert "https://www.google.com/maps/dir/" in p.url

    def test_max_three_intermediates_per_part(self) -> None:
        """Each part has at most 3 intermediate waypoints."""
        origin = _make_place("origin")
        dest = _make_place("dest")
        waypoints = [_make_place(f"stop_{i}") for i in range(7)]
        parts = build_browser_safe_parts(origin, waypoints, dest, "WALK")
        for p in parts:
            # Count waypoints in the URL (pipe separators in waypoints param)
            url = p.url
            if "waypoints=" in url and "waypoint_place_ids=" in url:
                pid_part = url.split("waypoint_place_ids=")[1].split("&")[0]
                count = pid_part.count("|") + 1
                assert count <= 3


class TestBuildHandoff:
    def test_complete_handoff(self) -> None:
        origin = _make_place("origin_place")
        stops = [_make_test_stop(i, f"stop_{i}") for i in range(3)]
        handoff = build_handoff(origin, stops, "WALK", False)
        assert handoff.full_route_url is not None
        assert handoff.full_route_universally_supported is True
        assert len(handoff.browser_safe_parts) >= 1
        assert handoff.error_code is None

    def test_many_stops_warns_mobile_limit(self) -> None:
        origin = _make_place("origin_place")
        stops = [_make_test_stop(i, f"stop_{i}") for i in range(6)]
        handoff = build_handoff(origin, stops, "WALK", False)
        # 5 intermediates (stops 0-4, stop 5 is destination)
        # > 3 intermediates -> MOBILE_WAYPOINT_LIMIT warning
        assert handoff.warning_code == "MOBILE_WAYPOINT_LIMIT"
        assert handoff.full_route_universally_supported is False

    def test_return_to_origin(self) -> None:
        """When return_to_origin is True, all stops are waypoints."""
        origin = _make_place("origin_place")
        stops = [_make_test_stop(i, f"stop_{i}") for i in range(2)]
        handoff = build_handoff(origin, stops, "WALK", True)
        assert handoff.full_route_url is not None
        # Destination should be the origin
        assert "destination_place_id=origin_place" in handoff.full_route_url

    def test_one_stop(self) -> None:
        """Single stop: it's the destination, no waypoints."""
        origin = _make_place("origin_place")
        stops = [_make_test_stop(0, "only_stop")]
        handoff = build_handoff(origin, stops, "WALK", False)
        assert handoff.full_route_url is not None
        assert "destination_place_id=only_stop" in handoff.full_route_url
        # No waypoints
        assert "waypoint_place_ids" not in handoff.full_route_url


class TestBrowserPartSequenceIntegrity:
    def test_parts_reconstruct_exact_route_without_duplicate_overlap_stop(self) -> None:
        from urllib.parse import parse_qs, urlparse

        origin = _make_place("origin")
        destination = _make_place("destination")
        waypoints = [_make_place(f"stop_{index}") for index in range(7)]
        parts = build_browser_safe_parts(origin, waypoints, destination, "WALK")

        reconstructed: list[str] = []
        for part in parts:
            params = parse_qs(urlparse(part.url).query)
            sequence = [params["origin_place_id"][0]]
            sequence.extend(
                params.get("waypoint_place_ids", [""])[0].split("|")
                if params.get("waypoint_place_ids")
                else []
            )
            sequence.append(params["destination_place_id"][0])
            if reconstructed:
                assert reconstructed[-1] == sequence[0]
                reconstructed.extend(sequence[1:])
            else:
                reconstructed.extend(sequence)

        assert reconstructed == ["origin", *[f"stop_{index}" for index in range(7)], "destination"]

    def test_oversized_part_returns_unavailable_instead_of_dropping_waypoints(self) -> None:
        origin = _make_place("origin-" + "x" * 2100)
        destination = _make_place("destination")
        waypoint = _make_place("waypoint")

        assert build_browser_safe_parts(origin, [waypoint], destination, "WALK") == []
