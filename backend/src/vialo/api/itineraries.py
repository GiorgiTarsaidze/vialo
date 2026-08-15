"""POST /api/itineraries — itinerary planning route.

Key fixes (H):
- Validate PlanItineraryRequest with Pydantic
- Map selector codes correctly
- Do not return raw provider errors
- Improved scope guard: reject input lacking time/day AND place/travel intent
- All provider clients close exactly once
- Return typed diagnostics for no-feasible/excluded cases
- Walking beta warning diagnostic (I)
- Cache integration (B)
- Partial status on grounding exclusion OR solver drop (C)
"""

from __future__ import annotations

import datetime as dt
import json
import re
import time
import uuid
from typing import Any

from aws_lambda_powertools.event_handler import Response, content_types
from pydantic import ValidationError

from vialo.config import load_config
from vialo.domain.comparison import build_comparison
from vialo.domain.maps_url import build_handoff
from vialo.domain.naive_simulation import simulate_naive_order
from vialo.domain.timezones import LocalTimeAmbiguousError, validate_local_time
from vialo.handler import app, logger, metrics
from vialo.models.diagnostics import Diagnostic, DiagnosticCode, DroppedStop
from vialo.models.itinerary import (
    ItineraryResponse,
    Locality,
    RouteMetrics,
    TimeWindow,
)
from vialo.models.requests import PlanItineraryRequest
from vialo.pipeline.compute_matrix import compute_matrix
from vialo.pipeline.compute_route_geometry import RouteGeometry, compute_route_geometry
from vialo.pipeline.ground_places import ground_origin, ground_places
from vialo.pipeline.select_stops import select_stops
from vialo.pipeline.solve_route import solve_route
from vialo.services.anthropic_selector import AnthropicCandidateSelector
from vialo.services.candidate_selector import SelectorError
from vialo.services.place_cache import PlaceCacheRepository
from vialo.services.places_client import PlacesClient, PlacesClientError
from vialo.services.rate_limiter import RateLimiter
from vialo.services.routes_client import RoutesClient, RoutesClientError
from vialo.services.share_repository import ShareRepository

MAX_PROMPT_LENGTH = 500

# Scope guard: reject obvious non-itinerary input
# Must have BOTH:
#   1) Some place/location/travel intent
#   2) No injection/abuse patterns
_ABUSE_PATTERNS = re.compile(
    r"|".join(
        [
            r"\b(write|code|program|script|hack|sql|inject)\b",
            r"\b(ignore|forget|disregard)\s+(previous|above|all)\b",
            r"\b(you are|act as|pretend|roleplay)\b",
            r"\b(password|credit.?card|ssn|social.?security)\b",
        ]
    ),
    re.IGNORECASE,
)

_PLACE_INTENT_PATTERNS = re.compile(
    r"\b(visit|see|explore|walk|drive|tour|sightseeing|itinerary|city|town|museum|"
    r"church|park|restaurant|hotel|station|airport|rome|venice|paris|london|tokyo|"
    r"barcelona|florence|naples|milan)\b",
    re.IGNORECASE,
)
_TIME_INTENT_PATTERNS = re.compile(
    r"\b(today|tomorrow|morning|afternoon|evening|day|start|end|from|until|between)\b|"
    r"\d{1,2}:\d{2}|\d{1,2}\s*(?:am|pm)\b|\d+\s*(?:hours?|hrs?|minutes?|mins?|h|m)\b",
    re.IGNORECASE,
)


def _record_latency(name: str, started_at: float) -> None:
    """Emit a fixed-name pipeline latency metric."""
    metrics.add_metric(
        name=name,
        unit="Milliseconds",
        value=(time.perf_counter() - started_at) * 1000,
    )


def _is_off_topic(prompt: str) -> bool:
    """Reject abuse or prompts without both place and time intent."""
    if _ABUSE_PATTERNS.search(prompt):
        return True
    return not (_PLACE_INTENT_PATTERNS.search(prompt) and _TIME_INTENT_PATTERNS.search(prompt))


def _error_response(code: DiagnosticCode, message: str, status_code: int = 400) -> Response:  # type: ignore[type-arg]
    """Build a JSON error response with typed diagnostic."""
    body = json.dumps(
        {
            "error": {"code": code.value, "message": message},
            "diagnostics": [{"code": code.value, "message": message}],
        }
    )
    return Response(
        status_code=status_code,
        content_type=content_types.APPLICATION_JSON,
        body=body,
    )


def _get_client_ip() -> str:
    """Extract client IP from the event, with privacy-safe fallback."""
    try:
        rc = app.current_event.request_context
        source_ip: str = rc.http.source_ip
        return source_ip
    except (AttributeError, TypeError):
        return "unknown"


@app.post("/api/itineraries")
def plan_itinerary() -> Response:  # type: ignore[type-arg]
    """Plan an itinerary from a natural-language prompt."""
    metrics.add_metric(name="ItineraryRequest", unit="Count", value=1)
    body: dict[str, Any] = app.current_event.json_body or {}

    # Validate with Pydantic model
    try:
        request = PlanItineraryRequest.model_validate(body)
    except ValidationError:
        return _error_response(
            DiagnosticCode.INVALID_INPUT,
            "Invalid request: prompt is required (1-500 characters)",
        )

    prompt = request.prompt

    # Scope guard — no provider calls for off-topic
    if _is_off_topic(prompt):
        return _error_response(
            DiagnosticCode.OFF_TOPIC,
            "Please describe a day of sightseeing in a city",
        )

    # Load config
    try:
        config = load_config()
    except ValueError as e:
        logger.error("Configuration error: %s", str(e))
        return _error_response(DiagnosticCode.INTERNAL_ERROR, "Server configuration error", 500)

    # Rate limiting
    try:
        rate_limiter = RateLimiter(
            table_name=config.dynamodb_table_rate_limits,
            hmac_secret=config.rate_limit_hmac_secret,
        )
        client_ip = _get_client_ip()
        allowed, retry_after = rate_limiter.check_and_increment(client_ip)
    except Exception:
        logger.exception("Rate-limit check failed")
        return _error_response(DiagnosticCode.INTERNAL_ERROR, "Server error", 500)
    if not allowed:
        resp = _error_response(DiagnosticCode.RATE_LIMITED, "Rate limit exceeded", 429)
        if retry_after:
            resp.headers = {"Retry-After": str(retry_after)}
        return resp

    # Step 1: Select candidate stops via Claude
    selector = AnthropicCandidateSelector(
        api_key=config.anthropic_api_key,
        model_id=config.anthropic_model_id,
    )
    selection_started = time.perf_counter()
    try:
        intent = select_stops(selector, prompt)
    except SelectorError as error:
        _record_latency("CandidateSelectionLatency", selection_started)
        try:
            error_code = DiagnosticCode(error.code)
        except ValueError:
            error_code = DiagnosticCode.MODEL_OUTPUT_INVALID
        if error_code == DiagnosticCode.PROVIDER_UNAVAILABLE:
            return _error_response(
                error_code,
                "Service temporarily unavailable, please try again",
                503,
            )
        return _error_response(
            DiagnosticCode.MODEL_OUTPUT_INVALID,
            "Could not understand the request. Please describe your day in a city.",
        )
    _record_latency("CandidateSelectionLatency", selection_started)

    # Instantiate cache
    place_cache = PlaceCacheRepository(
        table_name=config.dynamodb_table_cache,
    )

    # Step 2a: Ground origin separately via Places API
    places_client = PlacesClient(api_key=config.google_places_key)
    origin_started = time.perf_counter()
    try:
        origin = ground_origin(
            origin_query=intent.origin_query,
            locality=intent.locality_query,
            client=places_client,
            cache=place_cache,
        )
    except PlacesClientError:
        _record_latency("OriginGroundingLatency", origin_started)
        places_client.close()
        return _error_response(
            DiagnosticCode.PROVIDER_UNAVAILABLE,
            "Places service temporarily unavailable",
            503,
        )
    _record_latency("OriginGroundingLatency", origin_started)

    if origin is None:
        places_client.close()
        return _error_response(
            DiagnosticCode.ORIGIN_NOT_FOUND,
            "Could not resolve the requested starting point unambiguously",
        )

    # Origin timezone controls date/window validation
    origin_tz = origin.time_zone_id

    # Resolve the requested date
    requested_date = intent.requested_date
    if requested_date is None:
        from vialo.domain.timezones import local_today

        requested_date = local_today(origin_tz)

    # Reject past dates
    from vialo.domain.timezones import local_today as _local_today

    today_local = _local_today(origin_tz)
    if requested_date < today_local:
        places_client.close()
        return _error_response(
            DiagnosticCode.INVALID_DATE,
            f"Requested date {requested_date} is in the past"
            f" (today is {today_local} in {origin_tz})",
        )

    # Validate local times using origin timezone
    try:
        window_start = validate_local_time(intent.local_start_time, requested_date, origin_tz)
        window_end = validate_local_time(intent.local_end_time, requested_date, origin_tz)
    except LocalTimeAmbiguousError:
        places_client.close()
        return _error_response(
            DiagnosticCode.LOCAL_TIME_AMBIGUOUS,
            "The specified time is ambiguous due to DST transition",
        )

    if window_end <= window_start:
        places_client.close()
        return _error_response(
            DiagnosticCode.INVALID_TIME_WINDOW,
            "End time must be after start time",
        )

    # Reject time windows that are entirely in the past
    now_in_tz = dt.datetime.now(dt.UTC)
    if window_end <= now_in_tz:
        places_client.close()
        return _error_response(
            DiagnosticCode.INVALID_TIME_WINDOW,
            "Time window is entirely in the past",
        )

    # Step 2b: Ground candidate stops — with cache and origin timezone enforcement
    grounding_started = time.perf_counter()
    try:
        grounded_stops, grounding_diagnostics = ground_places(
            candidates=intent.candidates,
            locality=intent.locality_query,
            client=places_client,
            requested_date=requested_date,
            cache=place_cache,
            origin_tz=origin_tz,
        )
    except PlacesClientError:
        return _error_response(
            DiagnosticCode.PROVIDER_UNAVAILABLE,
            "Places service temporarily unavailable",
            503,
        )
    finally:
        _record_latency("CandidateGroundingLatency", grounding_started)
        places_client.close()

    for metric_name, attribute in (
        ("PlaceCacheHit", "hits"),
        ("PlaceCacheMiss", "misses"),
        ("PlaceCacheError", "errors"),
    ):
        metric_value = getattr(place_cache, attribute, None)
        if isinstance(metric_value, int):
            metrics.add_metric(name=metric_name, unit="Count", value=metric_value)

    # If all stops excluded, return NO_FEASIBLE_ITINERARY with diagnostics (C)
    if not grounded_stops:
        response_diagnostics: list[Diagnostic] = []
        for diag in grounding_diagnostics:
            response_diagnostics.append(
                Diagnostic(
                    code=diag.code,
                    message=diag.detail,
                    stop_name=diag.name,
                    candidate_index=diag.candidate_index,
                )
            )
        body_data = json.dumps(
            {
                "error": {
                    "code": DiagnosticCode.NO_FEASIBLE_ITINERARY.value,
                    "message": "All candidate stops were excluded during grounding",
                },
                "diagnostics": [
                    d.model_dump(by_alias=True, mode="json") for d in response_diagnostics
                ],
            }
        )
        return Response(
            status_code=422,
            content_type=content_types.APPLICATION_JSON,
            body=body_data,
        )

    # Step 3: Compute travel-time matrix
    routes_client = RoutesClient(api_key=config.google_routes_key)
    matrix_started = time.perf_counter()
    try:
        matrix = compute_matrix(
            origin=origin,
            stops=grounded_stops,
            travel_mode=intent.travel_mode,
            client=routes_client,
        )
    except RoutesClientError:
        _record_latency("RouteMatrixLatency", matrix_started)
        routes_client.close()
        return _error_response(
            DiagnosticCode.PROVIDER_UNAVAILABLE,
            "Routes service temporarily unavailable",
            503,
        )
    _record_latency("RouteMatrixLatency", matrix_started)

    # Build original matrix indices BEFORE any drops
    original_matrix_indices = {s.candidate_index: i + 1 for i, s in enumerate(grounded_stops)}

    # Step 4: Solve the route
    solver_started = time.perf_counter()
    result = solve_route(
        stops=grounded_stops,
        matrix=matrix,
        window_start=window_start,
        window_end=window_end,
        return_to_origin=intent.return_to_origin,
        travel_mode=intent.travel_mode,
    )
    _record_latency("ExactSolverLatency", solver_started)

    if result is None:
        routes_client.close()
        return _error_response(
            DiagnosticCode.NO_FEASIBLE_ITINERARY,
            "Cannot fit any stops in the given time window",
            422,
        )

    schedule, dropped = result

    # Determine which stops are in the final schedule
    retained_candidate_indices = set(schedule.order)
    retained_stops = [s for s in grounded_stops if s.candidate_index in retained_candidate_indices]

    # Reorder retained stops to match the solved order
    stop_by_ci = {s.candidate_index: s for s in retained_stops}
    ordered_stops = [stop_by_ci[ci] for ci in schedule.order]

    # Step 5: Compute route geometry for comparison
    naive_geometry: RouteGeometry | None = None
    optimized_geometry: RouteGeometry | None = None
    geometry_started = time.perf_counter()

    try:
        optimized_geometry = compute_route_geometry(
            origin=origin,
            ordered_stops=ordered_stops,
            travel_mode=intent.travel_mode,
            client=routes_client,
            return_to_origin=intent.return_to_origin,
        )

        # Naive geometry: stops in original candidate order
        naive_order_indices = [
            s.candidate_index
            for s in grounded_stops
            if s.candidate_index in retained_candidate_indices
        ]
        naive_ordered_stops = [stop_by_ci[ci] for ci in naive_order_indices if ci in stop_by_ci]
        naive_geometry = compute_route_geometry(
            origin=origin,
            ordered_stops=naive_ordered_stops,
            travel_mode=intent.travel_mode,
            client=routes_client,
            return_to_origin=intent.return_to_origin,
        )
    except RoutesClientError:
        pass  # Comparison will be unavailable
    finally:
        _record_latency("RouteGeometryLatency", geometry_started)
        routes_client.close()

    # Build comparison
    naive_metrics: RouteMetrics | None = None
    optimized_metrics: RouteMetrics | None = None

    if naive_geometry:
        naive_metrics = RouteMetrics(
            total_distance_meters=naive_geometry.total_distance_meters,
            total_duration_seconds=naive_geometry.total_duration_seconds,
            stop_order=naive_geometry.stop_order,
        )
    if optimized_geometry:
        optimized_metrics = RouteMetrics(
            total_distance_meters=optimized_geometry.total_distance_meters,
            total_duration_seconds=optimized_geometry.total_duration_seconds,
            stop_order=optimized_geometry.stop_order,
        )

    # Simulate naive order with ORIGINAL matrix indices preserved (F)
    naive_candidate_order = [s.candidate_index for s in grounded_stops]
    _naive_timeline, naive_feasible, naive_codes = simulate_naive_order(
        retained_stops=retained_stops,
        candidate_order=naive_candidate_order,
        origin_index=0,
        matrix=matrix,
        window_start=window_start,
        window_end=window_end,
        return_to_origin=intent.return_to_origin,
        travel_mode=intent.travel_mode,
        original_matrix_indices=original_matrix_indices,
    )

    comparison = build_comparison(
        naive_metrics=naive_metrics,
        optimized_metrics=optimized_metrics,
        naive_polyline=naive_geometry.polyline if naive_geometry else None,
        optimized_polyline=(optimized_geometry.polyline if optimized_geometry else None),
        naive_feasible=naive_feasible,
        naive_infeasibility_codes=naive_codes,
        num_stops=len(ordered_stops),
    )

    # Build Maps handoff
    handoff = build_handoff(
        origin=origin,
        ordered_stops=ordered_stops,
        travel_mode=intent.travel_mode,
        return_to_origin=intent.return_to_origin,
    )

    # Build response
    request_id = str(uuid.uuid4())

    # Status is "partial" when ANY grounding exclusion OR solver drop exists (C)
    has_exclusions = len(grounding_diagnostics) > 0
    has_drops = len(dropped) > 0
    itinerary_status: str = "partial" if (has_exclusions or has_drops) else "complete"

    # Build diagnostics
    response_diagnostics_list: list[Diagnostic] = []
    for diag in grounding_diagnostics:
        response_diagnostics_list.append(
            Diagnostic(
                code=diag.code,
                message=diag.detail,
                stop_name=diag.name,
                candidate_index=diag.candidate_index,
            )
        )

    # Walking beta warning (I) — required by Google docs for walking routes
    if intent.travel_mode == "WALK":
        response_diagnostics_list.append(
            Diagnostic(
                code=DiagnosticCode.WALKING_ROUTES_BETA,
                message=(
                    "Walking directions are in beta. Use caution – "
                    "This route may be missing sidewalks or pedestrian paths."
                ),
            )
        )

    grounding_dropped = [
        DroppedStop(
            candidate_index=diag.candidate_index,
            name=diag.name,
            reason_code=diag.code,
            reason_detail=diag.detail,
        )
        for diag in grounding_diagnostics
    ]
    all_dropped = grounding_dropped + dropped

    if comparison.status == "unavailable":
        response_diagnostics_list.append(
            Diagnostic(
                code=DiagnosticCode.COMPARISON_UNAVAILABLE,
                message="Route comparison geometry is unavailable",
            )
        )
    if handoff.error_code is not None:
        response_diagnostics_list.append(
            Diagnostic(
                code=DiagnosticCode.HANDOFF_UNAVAILABLE,
                message="Google Maps handoff is unavailable",
            )
        )

    # Generate share proof
    share_repo = ShareRepository(
        table_name=config.dynamodb_table_shares,
        signing_secret=config.share_signing_secret,
        deletion_secret=config.share_deletion_secret,
    )

    # Build response WITHOUT proof first, then sign and attach
    response_obj = ItineraryResponse(
        schema_version=1,
        request_id=request_id,
        status=itinerary_status,  # type: ignore[arg-type]
        locality=Locality(name=intent.locality_query, time_zone_id=origin_tz),
        travel_mode=intent.travel_mode,
        window=TimeWindow(
            start=window_start,
            end=window_end,
            local_start=intent.local_start_time.strftime("%H:%M"),
            local_end=intent.local_end_time.strftime("%H:%M"),
            date=requested_date,
        ),
        origin=origin,
        stops=ordered_stops,
        timeline=schedule.timeline,
        dropped_stops=all_dropped,
        comparison=comparison,
        maps_handoff=handoff,
        totals=schedule.totals,
        diagnostics=response_diagnostics_list,
        share_proof=None,  # Excluded from HMAC computation
    )

    # Generate proof over response WITHOUT proof (canonical)
    real_proof = share_repo.generate_proof(response_obj)
    response_obj.share_proof = real_proof
    metrics.add_metric(
        name="ItineraryPartial" if itinerary_status == "partial" else "ItineraryComplete",
        unit="Count",
        value=1,
    )
    logger.info(
        "Itinerary completed",
        extra={
            "status": itinerary_status,
            "stop_count": len(ordered_stops),
            "dropped_count": len(all_dropped),
            "comparison_status": comparison.status,
        },
    )

    return Response(
        status_code=200,
        content_type=content_types.APPLICATION_JSON,
        body=response_obj.model_dump_json(by_alias=True),
    )
