"""Integration tests for Places client with mocked HTTP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from vialo.services.places_client import PlacesClient, PlacesClientError

FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "docs" / "api-samples"


def _load_fixture() -> dict[str, Any]:
    with open(FIXTURES_DIR / "places-san-marco.json") as f:
        result: dict[str, Any] = json.load(f)
        return result


class TestPlacesClient:
    @respx.mock
    def test_parse_canonical_fixture(self) -> None:
        """Test parsing the canonical San Marco fixture."""
        fixture = _load_fixture()
        respx.post("https://places.googleapis.com/v1/places:searchText").respond(200, json=fixture)

        client = PlacesClient(api_key="test-key")
        results = client.search_text("Saint Mark's Basilica", "Venice")

        assert len(results) == 1
        result = results[0]
        assert result.place_id == "ChIJv2xSZNexfkcRBaKsgyfVEgo"
        assert result.display_name == "Saint Mark's Basilica"
        assert result.latitude == pytest.approx(45.4345606, abs=0.001)
        assert result.longitude == pytest.approx(12.3397125, abs=0.001)
        assert result.current_opening_hours is not None
        assert result.regular_opening_hours is not None
        assert len(result.photos) == 10

    @respx.mock
    def test_empty_response(self) -> None:
        """Empty results return empty list."""
        respx.post("https://places.googleapis.com/v1/places:searchText").respond(
            200, json={"places": []}
        )

        client = PlacesClient(api_key="test-key")
        results = client.search_text("Nonexistent Place", "Venice")
        assert results == []

    @respx.mock
    def test_retry_on_429(self) -> None:
        """Client retries on 429 status."""
        fixture = _load_fixture()
        route = respx.post("https://places.googleapis.com/v1/places:searchText")
        route.side_effect = [
            httpx.Response(429, text="Rate limited"),
            httpx.Response(200, json=fixture),
        ]

        client = PlacesClient(api_key="test-key", timeout=2.0)
        results = client.search_text("San Marco", "Venice")
        assert len(results) == 1

    @respx.mock
    def test_non_retryable_error_raises(self) -> None:
        """Non-retryable errors raise immediately."""
        respx.post("https://places.googleapis.com/v1/places:searchText").respond(
            403, text="Forbidden"
        )

        client = PlacesClient(api_key="test-key")
        with pytest.raises(PlacesClientError) as exc_info:
            client.search_text("Test", "Venice")
        assert exc_info.value.status_code == 403

    @respx.mock
    def test_retry_on_connection_error(self) -> None:
        """Connection failures are sanitized, retried, and can recover."""
        fixture = _load_fixture()
        request = httpx.Request("POST", "https://places.googleapis.com/v1/places:searchText")
        route = respx.post("https://places.googleapis.com/v1/places:searchText")
        route.side_effect = [
            httpx.ConnectError("sensitive transport detail", request=request),
            httpx.Response(200, json=fixture),
        ]

        client = PlacesClient(api_key="test-key", timeout=2.0)
        results = client.search_text("San Marco", "Venice")

        assert len(results) == 1
