"""Integration tests for Routes client with mocked HTTP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from vialo.models.providers import Location
from vialo.services.routes_client import RoutesClient, RoutesClientError

FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "docs" / "api-samples"


def _load_matrix_fixture() -> list[dict[str, Any]]:
    with open(FIXTURES_DIR / "routes-venice-walk.json") as f:
        result: list[dict[str, Any]] = json.load(f)
        return result


class TestRoutesClientMatrix:
    @respx.mock
    def test_compute_route_matrix(self) -> None:
        """Test matrix computation with canonical fixture."""
        fixture = _load_matrix_fixture()
        respx.post("https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix").respond(
            200, json=fixture
        )

        client = RoutesClient(api_key="test-key")
        origins = [
            Location(latitude=45.4340, longitude=12.3388),
            Location(latitude=45.4345, longitude=12.3397),
        ]
        result = client.compute_route_matrix(origins, origins, "WALK")

        assert len(result) == 4
        # Verify the canonical 518s/508s asymmetry
        forward = next(
            e for e in result if e.get("originIndex") == 0 and e.get("destinationIndex") == 1
        )
        reverse = next(
            e for e in result if e.get("originIndex") == 1 and e.get("destinationIndex") == 0
        )
        assert forward["duration"] == "518s"
        assert reverse["duration"] == "508s"

    @respx.mock
    def test_retry_on_server_error(self) -> None:
        """Client retries on 500."""
        fixture = _load_matrix_fixture()
        route = respx.post("https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix")
        route.side_effect = [
            httpx.Response(500, text="Server Error"),
            httpx.Response(200, json=fixture),
        ]

        client = RoutesClient(api_key="test-key", timeout=2.0)
        result = client.compute_route_matrix(
            [Location(latitude=45.0, longitude=12.0)],
            [Location(latitude=45.0, longitude=12.0)],
            "WALK",
        )
        assert len(result) == 4


class TestRoutesClientRoutes:
    @respx.mock
    def test_compute_routes(self) -> None:
        """Test route computation with polyline."""
        mock_response = {
            "routes": [
                {
                    "distanceMeters": 1500,
                    "duration": "1200s",
                    "polyline": {"encodedPolyline": "abc123"},
                    "legs": [
                        {"distanceMeters": 800, "duration": "600s"},
                        {"distanceMeters": 700, "duration": "600s"},
                    ],
                }
            ]
        }
        respx.post("https://routes.googleapis.com/directions/v2:computeRoutes").respond(
            200, json=mock_response
        )

        client = RoutesClient(api_key="test-key")
        result = client.compute_routes(
            origin=Location(latitude=45.0, longitude=12.0),
            intermediates=[Location(latitude=45.01, longitude=12.01)],
            destination=Location(latitude=45.02, longitude=12.02),
            travel_mode="WALK",
        )

        assert "routes" in result
        assert result["routes"][0]["polyline"]["encodedPolyline"] == "abc123"
        assert result["routes"][0]["distanceMeters"] == 1500

    @respx.mock
    def test_geometry_failure_raises(self) -> None:
        """Non-retryable error in computeRoutes raises."""
        respx.post("https://routes.googleapis.com/directions/v2:computeRoutes").respond(
            400, text="Bad Request"
        )

        client = RoutesClient(api_key="test-key")
        with pytest.raises(RoutesClientError) as exc_info:
            client.compute_routes(
                origin=Location(latitude=45.0, longitude=12.0),
                intermediates=[],
                destination=Location(latitude=45.01, longitude=12.01),
                travel_mode="WALK",
            )
        assert exc_info.value.status_code == 400

    @respx.mock
    def test_retry_on_connection_error(self) -> None:
        """Connection failures are sanitized, retried, and can recover."""
        fixture = _load_matrix_fixture()
        url = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
        request = httpx.Request("POST", url)
        route = respx.post(url)
        route.side_effect = [
            httpx.ConnectError("sensitive transport detail", request=request),
            httpx.Response(200, json=fixture),
        ]

        client = RoutesClient(api_key="test-key", timeout=2.0)
        result = client.compute_route_matrix(
            [Location(latitude=45.0, longitude=12.0)],
            [Location(latitude=45.0, longitude=12.0)],
            "WALK",
        )

        assert len(result) == 4
