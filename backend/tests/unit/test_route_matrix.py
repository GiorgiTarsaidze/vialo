"""Tests for directed route matrix building."""

from __future__ import annotations

from typing import Any

from vialo.domain.route_matrix import build_matrix


class TestBuildMatrix:
    def test_canonical_fixture(self, routes_venice_walk_fixture: list[dict[str, Any]]) -> None:
        """Test with the canonical Venice walking fixture.
        Must preserve 518s != 508s (directed, never mirrored).
        """
        matrix = build_matrix(routes_venice_walk_fixture, 2)
        assert len(matrix) == 2
        assert len(matrix[0]) == 2

        # Diagonal
        assert matrix[0][0].duration_seconds == 0
        assert matrix[0][0].reachable is True
        assert matrix[1][1].duration_seconds == 0

        # Forward: 0->1 = 518s, 592m
        assert matrix[0][1].duration_seconds == 518
        assert matrix[0][1].distance_meters == 592
        assert matrix[0][1].reachable is True

        # Reverse: 1->0 = 508s, 592m (different duration!)
        assert matrix[1][0].duration_seconds == 508
        assert matrix[1][0].distance_meters == 592
        assert matrix[1][0].reachable is True

        # Prove it's directed: 518 != 508
        assert matrix[0][1].duration_seconds != matrix[1][0].duration_seconds

    def test_missing_element_is_unreachable(self) -> None:
        """Points with no element data should be unreachable."""
        # Only diagonal elements
        elements = [
            {
                "originIndex": 0,
                "destinationIndex": 0,
                "condition": "ROUTE_EXISTS",
                "duration": "0s",
            },
            {
                "originIndex": 1,
                "destinationIndex": 1,
                "condition": "ROUTE_EXISTS",
                "duration": "0s",
            },
            {
                "originIndex": 2,
                "destinationIndex": 2,
                "condition": "ROUTE_EXISTS",
                "duration": "0s",
            },
        ]
        matrix = build_matrix(elements, 3)
        assert matrix[0][1].reachable is False
        assert matrix[0][1].duration_seconds is None
        assert matrix[1][2].reachable is False

    def test_never_mirrored(self) -> None:
        """Even with partial data, matrix never assumes symmetry."""
        elements = [
            {
                "originIndex": 0,
                "destinationIndex": 0,
                "condition": "ROUTE_EXISTS",
                "duration": "0s",
            },
            {
                "originIndex": 1,
                "destinationIndex": 1,
                "condition": "ROUTE_EXISTS",
                "duration": "0s",
            },
            {
                "originIndex": 0,
                "destinationIndex": 1,
                "condition": "ROUTE_EXISTS",
                "distanceMeters": 500,
                "duration": "300s",
            },
            # No 1->0 element
        ]
        matrix = build_matrix(elements, 2)
        assert matrix[0][1].reachable is True
        assert matrix[0][1].duration_seconds == 300
        assert matrix[1][0].reachable is False
        assert matrix[1][0].duration_seconds is None

    def test_route_not_found_condition(self) -> None:
        """ROUTE_NOT_FOUND condition marks edge as unreachable."""
        elements = [
            {
                "originIndex": 0,
                "destinationIndex": 0,
                "condition": "ROUTE_EXISTS",
                "duration": "0s",
            },
            {
                "originIndex": 1,
                "destinationIndex": 1,
                "condition": "ROUTE_EXISTS",
                "duration": "0s",
            },
            {"originIndex": 0, "destinationIndex": 1, "condition": "ROUTE_NOT_FOUND"},
        ]
        matrix = build_matrix(elements, 2)
        assert matrix[0][1].reachable is False

    def test_duration_parsing_with_s_suffix(self) -> None:
        """Duration strings like '518s' are parsed correctly."""
        elements = [
            {
                "originIndex": 0,
                "destinationIndex": 0,
                "condition": "ROUTE_EXISTS",
                "duration": "0s",
            },
            {
                "originIndex": 1,
                "destinationIndex": 1,
                "condition": "ROUTE_EXISTS",
                "duration": "0s",
            },
            {
                "originIndex": 0,
                "destinationIndex": 1,
                "condition": "ROUTE_EXISTS",
                "distanceMeters": 100,
                "duration": "518s",
            },
        ]
        matrix = build_matrix(elements, 2)
        assert matrix[0][1].duration_seconds == 518
