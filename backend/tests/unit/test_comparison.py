"""Tests for route comparison logic."""

from __future__ import annotations

from vialo.domain.comparison import build_comparison
from vialo.models.itinerary import ComparisonUnavailable, RouteComparison, RouteMetrics


class TestBuildComparison:
    def test_unavailable_when_geometry_missing(self) -> None:
        result = build_comparison(
            naive_metrics=None,
            optimized_metrics=None,
            naive_polyline=None,
            optimized_polyline=None,
            naive_feasible=True,
            naive_infeasibility_codes=[],
        )
        assert isinstance(result, ComparisonUnavailable)
        assert result.reason_code == "GEOMETRY_UNAVAILABLE"

    def test_unavailable_when_one_polyline_missing(self) -> None:
        naive = RouteMetrics(
            total_distance_meters=1000, total_duration_seconds=600, stop_order=[0, 1]
        )
        optimized = RouteMetrics(
            total_distance_meters=800, total_duration_seconds=500, stop_order=[1, 0]
        )
        result = build_comparison(
            naive_metrics=naive,
            optimized_metrics=optimized,
            naive_polyline="abc",
            optimized_polyline=None,
            naive_feasible=True,
            naive_infeasibility_codes=[],
        )
        assert isinstance(result, ComparisonUnavailable)

    def test_improved_outcome(self) -> None:
        naive = RouteMetrics(
            total_distance_meters=8400, total_duration_seconds=6120, stop_order=[0, 1, 2]
        )
        optimized = RouteMetrics(
            total_distance_meters=5100, total_duration_seconds=3840, stop_order=[2, 0, 1]
        )
        result = build_comparison(
            naive_metrics=naive,
            optimized_metrics=optimized,
            naive_polyline="naive_poly",
            optimized_polyline="opt_poly",
            naive_feasible=True,
            naive_infeasibility_codes=[],
            num_stops=3,
        )
        assert isinstance(result, RouteComparison)
        assert result.outcome == "improved"
        assert result.distance_delta_meters < 0  # savings
        assert result.duration_delta_seconds < 0

    def test_same_order(self) -> None:
        naive = RouteMetrics(
            total_distance_meters=5000, total_duration_seconds=3000, stop_order=[0, 1]
        )
        optimized = RouteMetrics(
            total_distance_meters=5000, total_duration_seconds=3000, stop_order=[0, 1]
        )
        result = build_comparison(
            naive_metrics=naive,
            optimized_metrics=optimized,
            naive_polyline="poly1",
            optimized_polyline="poly2",
            naive_feasible=True,
            naive_infeasibility_codes=[],
            num_stops=2,
        )
        assert isinstance(result, RouteComparison)
        assert result.outcome == "same_order"
        assert result.distance_delta_meters == 0
        assert result.duration_delta_seconds == 0

    def test_metrics_diverged(self) -> None:
        """Optimized is actually worse (shouldn't normally happen)."""
        naive = RouteMetrics(
            total_distance_meters=5000, total_duration_seconds=3000, stop_order=[0, 1]
        )
        optimized = RouteMetrics(
            total_distance_meters=6000, total_duration_seconds=4000, stop_order=[1, 0]
        )
        result = build_comparison(
            naive_metrics=naive,
            optimized_metrics=optimized,
            naive_polyline="poly1",
            optimized_polyline="poly2",
            naive_feasible=True,
            naive_infeasibility_codes=[],
            num_stops=2,
        )
        assert isinstance(result, RouteComparison)
        assert result.outcome == "metrics_diverged"

    def test_naive_not_feasible(self) -> None:
        naive = RouteMetrics(
            total_distance_meters=8000, total_duration_seconds=6000, stop_order=[0, 1]
        )
        optimized = RouteMetrics(
            total_distance_meters=5000, total_duration_seconds=3000, stop_order=[1, 0]
        )
        result = build_comparison(
            naive_metrics=naive,
            optimized_metrics=optimized,
            naive_polyline="poly1",
            optimized_polyline="poly2",
            naive_feasible=False,
            naive_infeasibility_codes=["EXCEEDS_WINDOW:Stop 1"],
            num_stops=2,
        )
        assert isinstance(result, RouteComparison)
        assert result.naive_feasible is False
        assert "EXCEEDS_WINDOW:Stop 1" in result.naive_infeasibility_codes

    def test_one_stop_comparison(self) -> None:
        """With one stop, only one possible order: no_reordering_needed."""
        naive = RouteMetrics(total_distance_meters=500, total_duration_seconds=300, stop_order=[0])
        optimized = RouteMetrics(
            total_distance_meters=500, total_duration_seconds=300, stop_order=[0]
        )
        result = build_comparison(
            naive_metrics=naive,
            optimized_metrics=optimized,
            naive_polyline="p1",
            optimized_polyline="p2",
            naive_feasible=True,
            naive_infeasibility_codes=[],
            num_stops=1,
        )
        assert isinstance(result, RouteComparison)
        assert result.outcome == "no_reordering_needed"
