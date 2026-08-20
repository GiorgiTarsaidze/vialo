"""Repeatable exact-solver benchmark.

Runs the production `vialo.domain.solver.solve_exact` implementation over
synthetic-but-realistic inputs so the 8!/9! latency claim rests on measurement
instead of estimation. The same module runs locally and inside a temporary
512 MB ARM64 Lambda so deployed numbers are comparable to host numbers.

Three cases are measured per stop count:

* `unconstrained` — a wide window and short visits, so every permutation stays
  feasible to the final leg. This is the true upper bound of the exhaustive
  search because no permutation exits early.
* `realistic` — a 10-hour window, hour-long visits, and staggered opening
  hours, which is what an actual request looks like. Infeasible permutations
  abort early, so this is faster than the upper bound.
* `dropping` — the production `solve_route` entry point on a day that cannot
  fit, so the exhaustive search runs once per progressive drop. This is the
  worst case an API request can actually reach.

Local usage:

    uv run --project backend python scripts/solver_benchmark.py --stops 8 9 --repeats 5

Lambda usage: deploy this file with the `vialo` package and invoke
`solver_benchmark.lambda_handler` with `{"stops": [8, 9], "repeats": 3}`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Literal

_REPO_BACKEND_SRC = Path(__file__).resolve().parent.parent / "backend" / "src"
if _REPO_BACKEND_SRC.is_dir() and str(_REPO_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_REPO_BACKEND_SRC))

from vialo.domain.route_matrix import MatrixEdge  # noqa: E402
from vialo.domain.solver import solve_exact  # noqa: E402
from vialo.models.itinerary import GroundedStop, OpenInterval  # noqa: E402
from vialo.models.providers import GroundedPlace, Location, StopCategory  # noqa: E402
from vialo.pipeline.solve_route import solve_route  # noqa: E402

CaseName = Literal["unconstrained", "realistic", "dropping"]

# Fixed seed: the matrix must be identical on every host and in every run.
MATRIX_SEED = 20260820
# Walking-scale directed travel times, in seconds, for a dense old-town cluster.
MIN_TRAVEL_SECONDS = 240
MAX_TRAVEL_SECONDS = 1_500


def _build_matrix(point_count: int) -> list[list[MatrixEdge]]:
    """Build a fully reachable, deliberately asymmetric directed matrix."""
    rng = random.Random(MATRIX_SEED)
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
                continue
            duration = rng.randint(MIN_TRAVEL_SECONDS, MAX_TRAVEL_SECONDS)
            row.append(
                MatrixEdge(
                    origin_index=i,
                    destination_index=j,
                    # Directed on purpose: the reverse edge is drawn separately.
                    distance_meters=int(duration * 1.25),
                    duration_seconds=duration,
                    reachable=True,
                )
            )
        matrix.append(row)
    return matrix


def _place(index: int) -> GroundedPlace:
    return GroundedPlace(
        place_id=f"benchmark-place-{index}",
        display_name=f"Benchmark Stop {index}",
        formatted_address=f"{index} Benchmark Street",
        location=Location(latitude=45.4 + index / 1000, longitude=12.3 + index / 1000),
        time_zone_id="UTC",
    )


def build_case(
    stop_count: int, case: CaseName
) -> tuple[list[GroundedStop], list[list[MatrixEdge]], dt.datetime, dt.datetime]:
    """Build one benchmark case: stops, directed matrix, and the time window."""
    day = dt.datetime(2026, 9, 15, tzinfo=dt.UTC)
    window_start = day.replace(hour=9)

    if case == "unconstrained":
        window_end = day.replace(hour=23)
        visit_minutes = 20
    elif case == "dropping":
        # Nine 100-minute visits cannot fit a 10-hour day, so `solve_route`
        # runs the exhaustive search once per progressive drop.
        window_end = day.replace(hour=19)
        visit_minutes = 100
    else:
        window_end = day.replace(hour=19)
        visit_minutes = 60

    stops: list[GroundedStop] = []
    for index in range(stop_count):
        if case == "realistic":
            # Staggered real-world hours: some stops open late, some close early.
            open_start = window_start + dt.timedelta(minutes=30 * (index % 3))
            open_end = window_end - dt.timedelta(minutes=45 * (index % 4))
        else:
            open_start, open_end = window_start, window_end
        stops.append(
            GroundedStop(
                candidate_index=index,
                name=f"Benchmark Stop {index}",
                category=StopCategory.LANDMARK,
                priority=1 + (index % 3),
                visit_duration_minutes=visit_minutes,
                duration_source="model_estimate",
                place=_place(index),
                hours_source="current",
                open_intervals=[
                    OpenInterval(
                        start=open_start,
                        end=open_end,
                        local_start=open_start.strftime("%H:%M"),
                        local_end=open_end.strftime("%H:%M"),
                    )
                ],
            )
        )

    matrix = _build_matrix(stop_count + 1)
    return stops, matrix, window_start, window_end


def _factorial(value: int) -> int:
    result = 1
    for i in range(2, value + 1):
        result *= i
    return result


def measure(stop_count: int, case: CaseName, repeats: int) -> dict[str, Any]:
    """Time the solver for one case, discarding a single warm-up run."""
    stops, matrix, window_start, window_end = build_case(stop_count, case)

    def run() -> tuple[bool, int]:
        if case == "dropping":
            # Production entry point: exhaustive search plus progressive dropping.
            outcome = solve_route(
                stops=stops,
                matrix=matrix,
                window_start=window_start,
                window_end=window_end,
                return_to_origin=True,
                travel_mode="WALK",
            )
            if outcome is None:
                return False, 0
            schedule, dropped = outcome
            return True, len(dropped)
        schedule_only = solve_exact(
            stops=stops,
            origin_index=0,
            matrix=matrix,
            window_start=window_start,
            window_end=window_end,
            return_to_origin=True,
            travel_mode="WALK",
        )
        return schedule_only is not None, 0

    warmup_started = time.perf_counter()
    feasible, dropped_count = run()
    warmup_seconds = time.perf_counter() - warmup_started

    samples: list[float] = []
    for _ in range(repeats):
        started = time.perf_counter()
        run()
        samples.append(time.perf_counter() - started)

    ordered = sorted(samples)
    # Nearest-rank p95, the same definition used for the earlier host numbers.
    p95_index = max(0, min(len(ordered) - 1, -(-95 * len(ordered) // 100) - 1))
    return {
        "stops": stop_count,
        "case": case,
        "permutations": _factorial(stop_count),
        "solutionFound": feasible,
        "droppedStops": dropped_count,
        "samples": len(samples),
        "warmupSeconds": round(warmup_seconds, 4),
        "minSeconds": round(ordered[0], 4),
        "medianSeconds": round(statistics.median(ordered), 4),
        "p95Seconds": round(ordered[p95_index], 4),
        "maxSeconds": round(ordered[-1], 4),
    }


def run_benchmark(stop_counts: list[int], repeats: int) -> dict[str, Any]:
    """Run every case for every requested stop count and describe the environment."""
    cases: list[CaseName] = ["unconstrained", "realistic", "dropping"]
    results = [measure(stop_count, case, repeats) for stop_count in stop_counts for case in cases]
    return {
        "environment": {
            "python": platform.python_version(),
            "machine": platform.machine(),
            "platform": platform.platform(),
            "lambdaFunction": os.environ.get("AWS_LAMBDA_FUNCTION_NAME"),
            "lambdaMemoryMb": os.environ.get("AWS_LAMBDA_FUNCTION_MEMORY_SIZE"),
            "measuredAt": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        },
        "matrixSeed": MATRIX_SEED,
        "repeats": repeats,
        "results": results,
    }


def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    """Lambda entry point for the deployed 512 MB ARM64 measurement."""
    stop_counts = [int(value) for value in event.get("stops", [8, 9])]
    repeats = int(event.get("repeats", 3))
    return run_benchmark(stop_counts, repeats)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the exact itinerary solver.")
    parser.add_argument("--stops", type=int, nargs="+", default=[8, 9])
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(run_benchmark(args.stops, args.repeats), indent=2))


if __name__ == "__main__":
    main()
