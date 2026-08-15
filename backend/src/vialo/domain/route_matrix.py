"""Directed travel-time matrix building from Routes API response."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Regex for protobuf Duration format: optional digits, optional decimal, followed by 's'
_DURATION_RE = re.compile(r"^(-?\d+(?:\.\d+)?)s$")


@dataclass(frozen=True, slots=True)
class MatrixEdge:
    """A directed edge in the travel-time matrix."""

    origin_index: int
    destination_index: int
    distance_meters: int | None
    duration_seconds: int | None
    reachable: bool


def parse_protobuf_duration(value: str | int | float | None) -> int | None:
    """Parse a protobuf Duration string (e.g. '518s', '517.5s') to integer seconds.

    Handles:
    - None → None
    - int/float → round to int
    - str like '518s', '517.5s' → integer seconds (rounded)
    - str with just digits → integer seconds
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value)
    s = str(value).strip()
    if not s:
        return None
    m = _DURATION_RE.match(s)
    if m:
        return round(float(m.group(1)))
    # Try bare numeric string
    try:
        return round(float(s))
    except ValueError:
        return None


def build_matrix(elements: list[dict[str, Any]], point_count: int) -> list[list[MatrixEdge]]:
    """Build a directed NxN matrix from Routes API response elements.

    The matrix is DIRECTED — never mirrored. Diagonal entries are
    distance=0, duration=0, reachable=True.

    Args:
        elements: List of element dicts from computeRouteMatrix response.
        point_count: Number of points (origin + stops). Matrix is point_count x point_count.

    Returns:
        NxN list of lists where matrix[i][j] is the edge from point i to point j.
    """
    # Initialize with unreachable defaults
    matrix: list[list[MatrixEdge]] = []
    for i in range(point_count):
        row: list[MatrixEdge] = []
        for j in range(point_count):
            if i == j:
                row.append(
                    MatrixEdge(
                        origin_index=i,
                        destination_index=j,
                        distance_meters=0,
                        duration_seconds=0,
                        reachable=True,
                    )
                )
            else:
                row.append(
                    MatrixEdge(
                        origin_index=i,
                        destination_index=j,
                        distance_meters=None,
                        duration_seconds=None,
                        reachable=False,
                    )
                )
        matrix.append(row)

    # Populate from elements
    for elem in elements:
        origin_idx = elem.get("originIndex")
        dest_idx = elem.get("destinationIndex")
        if origin_idx is None or dest_idx is None:
            continue
        if origin_idx == dest_idx:
            continue  # diagonal already set

        condition = elem.get("condition", "")
        is_reachable = condition == "ROUTE_EXISTS"
        distance = elem.get("distanceMeters")
        duration = parse_protobuf_duration(elem.get("duration"))

        matrix[origin_idx][dest_idx] = MatrixEdge(
            origin_index=origin_idx,
            destination_index=dest_idx,
            distance_meters=distance if is_reachable else None,
            duration_seconds=duration if is_reachable else None,
            reachable=is_reachable,
        )

    return matrix
