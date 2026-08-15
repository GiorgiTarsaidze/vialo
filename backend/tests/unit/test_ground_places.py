"""Tests for ground_places pipeline step: origin grounding and hours exclusion."""

from __future__ import annotations

import datetime as dt
from typing import Any
from unittest.mock import MagicMock

from vialo.models.diagnostics import DiagnosticCode
from vialo.models.providers import CandidateStop, StopCategory
from vialo.pipeline.ground_places import ground_origin, ground_places
from vialo.services.places_client import PlacesSearchResult


def _make_search_result(
    place_id: str = "test_place",
    display_name: str = "Test Place",
    tz_id: str | None = "Europe/Rome",
    current_hours: dict[str, Any] | None = None,
    regular_hours: dict[str, Any] | None = None,
) -> PlacesSearchResult:
    """Create a PlacesSearchResult for testing."""
    return PlacesSearchResult(
        place_id=place_id,
        display_name=display_name,
        formatted_address="Test Address",
        latitude=45.43,
        longitude=12.34,
        primary_type="landmark",
        time_zone_id=tz_id,
        current_opening_hours=current_hours,
        regular_opening_hours=regular_hours,
        photos=[],
    )


class TestGroundOrigin:
    """Origin grounding is separate from candidates."""

    def test_origin_grounded_separately(self) -> None:
        """ground_origin uses origin_query, not first candidate."""
        client = MagicMock()
        client.search_text.return_value = [
            _make_search_result(place_id="origin_hotel", display_name="Hotel Danieli")
        ]

        result = ground_origin("Hotel Danieli", "Venice", client)
        assert result is not None
        assert result.place_id == "origin_hotel"
        assert result.display_name == "Hotel Danieli"
        # Verify it was called with origin query
        client.search_text.assert_called_once_with("Hotel Danieli", "Venice")

    def test_origin_not_found_returns_none(self) -> None:
        """If origin query has no results, returns None."""
        client = MagicMock()
        client.search_text.return_value = []

        result = ground_origin("Nonexistent Hotel", "Venice", client)
        assert result is None

    def test_origin_without_timezone_returns_none(self) -> None:
        """Origin without timezone is rejected."""
        client = MagicMock()
        client.search_text.return_value = [_make_search_result(tz_id=None)]

        result = ground_origin("Some Place", "Venice", client)
        assert result is None


class TestGroundPlacesHoursExclusion:
    """Stops with missing/unusable hours are excluded with diagnostics."""

    def test_stop_with_valid_hours_included(self) -> None:
        """A stop with valid opening hours is included."""
        client = MagicMock()
        # Return a place with current hours that are open on the requested date
        current_hours = {
            "periods": [
                {
                    "open": {
                        "day": 6,
                        "hour": 9,
                        "minute": 0,
                        "date": {"year": 2026, "month": 8, "day": 15},
                    },
                    "close": {
                        "day": 6,
                        "hour": 18,
                        "minute": 0,
                        "date": {"year": 2026, "month": 8, "day": 15},
                    },
                }
            ]
        }
        client.search_text.return_value = [_make_search_result(current_hours=current_hours)]

        candidates = [
            CandidateStop(
                candidate_index=0,
                name="Test Place",
                category=StopCategory.LANDMARK,
                priority=1,
                visit_duration_minutes=60,
                duration_source="model_estimate",
            )
        ]

        stops, diagnostics = ground_places(
            candidates=candidates,
            locality="Venice",
            client=client,
            requested_date=dt.date(2026, 8, 15),
        )

        assert len(stops) == 1
        assert len(diagnostics) == 0
        assert stops[0].hours_source == "current"
        assert len(stops[0].open_intervals) == 1

    def test_stop_with_no_hours_excluded(self) -> None:
        """A stop with no opening hours data is excluded, NEVER synthesizes 00:00-24:00."""
        client = MagicMock()
        client.search_text.return_value = [
            _make_search_result(
                display_name="Mystery Place", current_hours=None, regular_hours=None
            )
        ]

        candidates = [
            CandidateStop(
                candidate_index=0,
                name="Mystery Place",
                category=StopCategory.LANDMARK,
                priority=1,
                visit_duration_minutes=60,
                duration_source="model_estimate",
            )
        ]

        stops, diagnostics = ground_places(
            candidates=candidates,
            locality="Venice",
            client=client,
            requested_date=dt.date(2026, 8, 15),
        )

        assert len(stops) == 0
        assert len(diagnostics) == 1
        assert diagnostics[0].code == DiagnosticCode.HOURS_UNAVAILABLE
        # Verify no synthesized interval exists
        for s in stops:
            for iv in s.open_intervals:
                assert iv.local_start != "00:00" or iv.local_end != "24:00"

    def test_stop_closed_on_date_excluded(self) -> None:
        """A stop explicitly closed on the requested date is excluded."""
        client = MagicMock()
        # currentOpeningHours with coverage but no periods for the requested date
        current_hours = {
            "periods": [
                {
                    "open": {
                        "day": 0,
                        "hour": 9,
                        "minute": 0,
                        "date": {"year": 2026, "month": 8, "day": 16},
                    },
                    "close": {
                        "day": 0,
                        "hour": 18,
                        "minute": 0,
                        "date": {"year": 2026, "month": 8, "day": 16},
                    },
                }
            ]
        }
        client.search_text.return_value = [_make_search_result(current_hours=current_hours)]

        candidates = [
            CandidateStop(
                candidate_index=0,
                name="Test Place",
                category=StopCategory.MUSEUM_GALLERY,
                priority=2,
                visit_duration_minutes=90,
                duration_source="model_estimate",
            )
        ]

        stops, diagnostics = ground_places(
            candidates=candidates,
            locality="Venice",
            client=client,
            requested_date=dt.date(2026, 8, 15),
        )

        assert len(stops) == 0
        assert len(diagnostics) == 1
        assert diagnostics[0].code == DiagnosticCode.CLOSED_ON_DATE


class TestGroundPlacesSplitFreshnessCache:
    @staticmethod
    def _profile(place_id: str = "cached-place"):
        from vialo.models.cache import CacheProfile
        from vialo.models.providers import Location

        now = dt.datetime.now(dt.UTC)
        return CacheProfile(
            place_id=place_id,
            display_name="Cached Museum",
            formatted_address="Venice, Italy",
            location=Location(latitude=45.43, longitude=12.34),
            primary_type="museum",
            time_zone_id="Europe/Rome",
            photos=[],
            fetched_at=now,
            expires_at=int(now.timestamp()) + 3600,
        )

    @staticmethod
    def _candidate() -> CandidateStop:
        return CandidateStop(
            candidate_index=0,
            name="Cached Museum",
            category=StopCategory.MUSEUM_GALLERY,
            priority=1,
            visit_duration_minutes=90,
            duration_source="model_estimate",
        )

    @staticmethod
    def _periods(date: dt.date) -> list[dict[str, Any]]:
        return [
            {
                "open": {
                    "date": {"year": date.year, "month": date.month, "day": date.day},
                    "hour": 9,
                    "minute": 0,
                },
                "close": {
                    "date": {"year": date.year, "month": date.month, "day": date.day},
                    "hour": 18,
                    "minute": 0,
                },
            }
        ]

    def test_fresh_profile_and_date_hours_avoid_places_call(self) -> None:
        from zoneinfo import ZoneInfo

        from vialo.models.cache import CacheDateHours

        requested = dt.datetime.now(ZoneInfo("Europe/Rome")).date()
        now = dt.datetime.now(dt.UTC)
        cache = MagicMock()
        cache.get_query_resolution.return_value = "cached-place"
        cache.get_profile.return_value = self._profile()
        cache.get_date_hours.return_value = CacheDateHours(
            place_id="cached-place",
            date=requested.isoformat(),
            periods=self._periods(requested),
            source="current",
            fetched_at=now,
            expires_at=int(now.timestamp()) + 3600,
        )
        cache.get_regular_hours.return_value = None
        client = MagicMock()

        stops, diagnostics = ground_places(
            [self._candidate()],
            "Venice",
            client,
            requested,
            cache=cache,
            origin_tz="Europe/Rome",
        )

        assert len(stops) == 1
        assert diagnostics == []
        client.search_text.assert_not_called()

    def test_missing_current_date_refreshes_even_with_fresh_regular_hours(self) -> None:
        from zoneinfo import ZoneInfo

        from vialo.models.cache import CacheRegularHours

        requested = dt.datetime.now(ZoneInfo("Europe/Rome")).date()
        now = dt.datetime.now(dt.UTC)
        cache = MagicMock()
        cache.get_query_resolution.return_value = "cached-place"
        cache.get_profile.return_value = self._profile()
        cache.get_date_hours.return_value = None
        cache.get_regular_hours.return_value = CacheRegularHours(
            place_id="cached-place",
            periods=[],
            fetched_at=now,
            expires_at=int(now.timestamp()) + 3600,
        )
        client = MagicMock()
        client.search_text.return_value = [
            _make_search_result(
                place_id="cached-place",
                display_name="Cached Museum",
                current_hours={"periods": self._periods(requested)},
                regular_hours={"periods": []},
            )
        ]

        stops, diagnostics = ground_places(
            [self._candidate()],
            "Venice",
            client,
            requested,
            cache=cache,
            origin_tz="Europe/Rome",
        )

        assert len(stops) == 1
        assert diagnostics == []
        client.search_text.assert_called_once_with("Cached Museum", "Venice")
        cache.put_date_hours.assert_called_once()

    def test_cached_empty_current_periods_remain_authoritatively_closed(self) -> None:
        from zoneinfo import ZoneInfo

        from vialo.models.cache import CacheDateHours

        requested = dt.datetime.now(ZoneInfo("Europe/Rome")).date()
        now = dt.datetime.now(dt.UTC)
        cache = MagicMock()
        cache.get_query_resolution.return_value = "cached-place"
        cache.get_profile.return_value = self._profile()
        cache.get_date_hours.return_value = CacheDateHours(
            place_id="cached-place",
            date=requested.isoformat(),
            periods=[],
            source="current",
            fetched_at=now,
            expires_at=int(now.timestamp()) + 3600,
        )
        cache.get_regular_hours.return_value = None
        client = MagicMock()

        stops, diagnostics = ground_places(
            [self._candidate()], "Venice", client, requested, cache=cache
        )

        assert stops == []
        assert diagnostics[0].code == DiagnosticCode.CLOSED_ON_DATE
        client.search_text.assert_not_called()

    def test_cache_read_failure_falls_back_to_valid_live_response(self) -> None:
        from zoneinfo import ZoneInfo

        requested = dt.datetime.now(ZoneInfo("Europe/Rome")).date()
        cache = MagicMock()
        cache.get_query_resolution.side_effect = RuntimeError("cache unavailable")
        client = MagicMock()
        client.search_text.return_value = [
            _make_search_result(
                place_id="cached-place",
                display_name="Cached Museum",
                current_hours={"periods": self._periods(requested)},
            )
        ]

        stops, diagnostics = ground_places(
            [self._candidate()], "Venice", client, requested, cache=cache
        )

        assert len(stops) == 1
        assert diagnostics == []
