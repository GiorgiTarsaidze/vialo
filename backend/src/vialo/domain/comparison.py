"""Route comparison logic: naive vs optimized.

Key fixes:
- One-stop comparison outcome: no_reordering_needed (only one possible order)
- Signed delta: negative means optimized is shorter/faster (improved)
- Keep request option parity
"""

from __future__ import annotations

from typing import Literal

from vialo.models.itinerary import ComparisonUnavailable, RouteComparison, RouteMetrics

OutcomeType = Literal["improved", "same_order", "no_reordering_needed", "metrics_diverged"]


def build_comparison(
    naive_metrics: RouteMetrics | None,
    optimized_metrics: RouteMetrics | None,
    naive_polyline: str | None,
    optimized_polyline: str | None,
    naive_feasible: bool,
    naive_infeasibility_codes: list[str],
    num_stops: int = 0,
) -> RouteComparison | ComparisonUnavailable:
    """Build the comparison result from naive and optimized route data.

    Returns ComparisonUnavailable if either route's geometry is missing.

    Args:
        naive_metrics: Route metrics for the naive (original) order.
        optimized_metrics: Route metrics for the optimized order.
        naive_polyline: Encoded polyline for naive route.
        optimized_polyline: Encoded polyline for optimized route.
        naive_feasible: Whether the naive order is feasible.
        naive_infeasibility_codes: Reasons the naive order is infeasible.
        num_stops: Number of stops in the comparison. Used for single-stop detection.
    """
    if (
        naive_metrics is None
        or optimized_metrics is None
        or naive_polyline is None
        or optimized_polyline is None
    ):
        return ComparisonUnavailable(
            status="unavailable",
            reason_code="GEOMETRY_UNAVAILABLE",
        )

    # Signed delta: negative means optimized is better
    distance_delta = optimized_metrics.total_distance_meters - naive_metrics.total_distance_meters
    duration_delta = optimized_metrics.total_duration_seconds - naive_metrics.total_duration_seconds

    # Determine outcome
    outcome: OutcomeType
    if num_stops <= 1:
        # Single stop: only one possible order, no reordering possible
        outcome = "no_reordering_needed"
    elif naive_metrics.stop_order == optimized_metrics.stop_order:
        outcome = "same_order"
    elif distance_delta < 0 or duration_delta < 0:
        outcome = "improved"
    elif distance_delta == 0 and duration_delta == 0:
        outcome = "same_order"
    else:
        outcome = "metrics_diverged"

    return RouteComparison(
        status="available",
        naive=naive_metrics,
        optimized=optimized_metrics,
        naive_polyline=naive_polyline,
        optimized_polyline=optimized_polyline,
        distance_delta_meters=distance_delta,
        duration_delta_seconds=duration_delta,
        naive_feasible=naive_feasible,
        naive_infeasibility_codes=naive_infeasibility_codes,
        outcome=outcome,
    )
