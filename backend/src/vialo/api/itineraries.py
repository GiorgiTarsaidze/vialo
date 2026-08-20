"""POST /api/itineraries — itinerary planning route.

Integrated features:
- Structured origin/destination canonicalization via PlacesClient.get_place(placeId)
- Fixed destination support through matrix/solver/geometry/handoff
- One bounded repair pass between grounding and matrix
- Honest comparison with same origin/stops/destination parity
"""

from __future__ import annotations

import datetime as dt
import json
import re
import time
import uuid
from typing import Any
from zoneinfo import ZoneInfo

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
    OpenInterval,
    RouteMetrics,
    TimeWindow,
)
from vialo.models.providers import GroundedPlace, HoursSource
from vialo.models.requests import PlanItineraryRequest
from vialo.pipeline.compute_matrix import compute_matrix
from vialo.pipeline.compute_route_geometry import RouteGeometry, compute_route_geometry
from vialo.pipeline.ground_places import GroundingDiagnostic, ground_origin, ground_places
from vialo.pipeline.repair_candidates import (
    build_repair_context,
    collect_alternatives,
    parse_repair_decisions,
)
from vialo.pipeline.solve_route import solve_route
from vialo.services.bedrock_selector import BedrockCandidateSelector
from vialo.services.candidate_selector import SelectorError
from vialo.services.place_cache import PlaceCacheRepository
from vialo.services.places_client import PlacesClient, PlacesClientError
from vialo.services.rate_limiter import RateLimiter
from vialo.services.routes_client import RoutesClient, RoutesClientError
from vialo.services.share_repository import ShareRepository
from vialo.services.spend_limiter import (
    BedrockSpendLimiter,
    BudgetExceededError,
    SpendLimiterUnavailableError,
)

MAX_PROMPT_LENGTH = 500
MAX_REPAIR_CANDIDATES = 5

# Scope guard: reject obvious non-itinerary input
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

# Two signal families combined: travel-activity terms and place-type terms.
# At least one match from either family satisfies the place/travel requirement.
# Uses optional plural suffixes and multi-word phrases to cover common morphology
# without admitting arbitrary non-travel requests.
_PLACE_INTENT_PATTERNS = re.compile(
    r"|".join(
        [
            # --- Travel activity signals ---
            r"\bvisit(?:ing|s)?\b",
            r"\bsee(?:ing)?\b",
            r"\bsights(?:eeing)?s?\b",
            r"\bexplor(?:e|ing)\b",
            r"\bwalk(?:ing|s)?\b",
            r"\b(?:on|by)\s+foot\b",
            r"\bdriv(?:e|ing)\b",
            r"\btour(?:ing|s)?\b",
            r"\bitinerar(?:y|ies)\b",
            r"\battraction(?:s)?\b",
            r"\blandmark(?:s)?\b",
            r"\bstart(?:ing)?\s+(?:at|from)\b",
            # --- Place-type signals ---
            r"\bcit(?:y|ies)\b",
            r"\btown(?:s)?\b",
            r"\bmuseum(?:s)?\b",
            r"\bchurch(?:es)?\b",
            r"\bcathedral(?:s)?\b",
            r"\btemple(?:s)?\b",
            r"\bpark(?:s)?\b",
            r"\brestaurant(?:s)?\b",
            r"\bsquare(?:s)?\b",
            r"\bpalace(?:s)?\b",
            r"\bcastle(?:s)?\b",
            r"\bhotel(?:s)?\b",
            r"\bstation(?:s)?\b",
            r"\bairport(?:s)?\b",
            r"\bmarket(?:s)?\b",
            r"\bgarden(?:s)?\b",
            r"\bbridge(?:s)?\b",
            r"\bmonument(?:s)?\b",
        ]
    ),
    re.IGNORECASE,
)
_TIME_INTENT_PATTERNS = re.compile(
    r"\b(today|tomorrow|morning|afternoon|evening|day|start|end|from|until|between)\b|"
    r"\d{1,2}:\d{2}|\d{1,2}\s*(?:am|pm)\b|\d+\s*(?:hours?|hrs?|minutes?|mins?|h|m)\b",
    re.IGNORECASE,
)


def _record_latency(name: str, started_at: float) -> None:
    metrics.add_metric(
        name=name,
        unit="Milliseconds",
        value=(time.perf_counter() - started_at) * 1000,
    )


def _repair_hours_with_unverified_fallback(
    hours: list[OpenInterval] | DiagnosticCode,
    *,
    window_start: dt.datetime,
    window_end: dt.datetime,
    time_zone_id: str,
) -> tuple[HoursSource, list[OpenInterval]] | DiagnosticCode:
    """Apply the same missing-hours policy to repaired candidates as initial grounding."""
    if not isinstance(hours, DiagnosticCode):
        return "current", hours
    if hours != DiagnosticCode.HOURS_UNAVAILABLE:
        return hours

    zone = ZoneInfo(time_zone_id)
    return (
        "unverified",
        [
            OpenInterval(
                start=window_start,
                end=window_end,
                local_start=window_start.astimezone(zone).strftime("%H:%M"),
                local_end=window_end.astimezone(zone).strftime("%H:%M"),
            )
        ],
    )


def _is_off_topic(prompt: str, *, has_structured_origin: bool = False) -> bool:
    if _ABUSE_PATTERNS.search(prompt):
        return True
    if has_structured_origin:
        # Structured origin satisfies the place/city requirement;
        # only require a time/day signal in the prompt.
        return not _TIME_INTENT_PATTERNS.search(prompt)
    return not (_PLACE_INTENT_PATTERNS.search(prompt) and _TIME_INTENT_PATTERNS.search(prompt))


def _error_response(code: DiagnosticCode, message: str, status_code: int = 400) -> Response:  # type: ignore[type-arg]
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
    try:
        rc = app.current_event.request_context
        source_ip: str = rc.http.source_ip
        return source_ip
    except (AttributeError, TypeError):
        return "unknown"


def _canonicalize_place(
    place_ref: Any,
    client: PlacesClient,
    cache: PlaceCacheRepository,
) -> GroundedPlace | None:
    """Canonicalize a PlaceReference via get_place. Returns None if not found."""
    result = client.get_place(place_ref.place_id)
    if result is None:
        return None
    from vialo.pipeline.ground_places import _result_to_grounded_place

    place = _result_to_grounded_place(result)
    return place


def _resolve_requested_date(
    requested_date: dt.date | None,
    local_start_time: dt.time,
    origin_tz: str,
    *,
    now_utc: dt.datetime | None = None,
) -> dt.date:
    """Resolve an omitted date to the next upcoming local start.

    Explicit model-parsed dates are preserved. For date-less prompts, use today
    when the requested start is still ahead in the origin timezone; otherwise
    roll to tomorrow instead of creating a schedule that begins in the past.
    """
    if requested_date is not None:
        return requested_date

    from zoneinfo import ZoneInfo

    now = now_utc or dt.datetime.now(dt.UTC)
    local_today = now.astimezone(ZoneInfo(origin_tz)).date()
    start_today = validate_local_time(local_start_time, local_today, origin_tz)
    if start_today <= now:
        return local_today + dt.timedelta(days=1)
    return local_today


def _build_selection_prompt(
    raw_prompt: str,
    canonical_origin: GroundedPlace | None,
    canonical_destination: GroundedPlace | None,
    return_to_origin: bool,
) -> str:
    """Build the prompt sent to the candidate selector.

    Preserves the raw user prompt unchanged as the prefix (so duration evidence
    offsets/quotes remain valid), then appends a clearly delimited server-canonical
    location data block when structured origin is available.
    """
    if canonical_origin is None:
        return raw_prompt

    # Build canonical context as JSON
    context_data: dict[str, Any] = {
        "origin": {
            "place_id": canonical_origin.place_id,
            "name": canonical_origin.display_name,
            "address": canonical_origin.formatted_address,
        },
    }

    if (
        canonical_destination is not None
        and canonical_destination.place_id != canonical_origin.place_id
    ):
        context_data["destination"] = {
            "place_id": canonical_destination.place_id,
            "name": canonical_destination.display_name,
            "address": canonical_destination.formatted_address,
        }
        context_data["destination_equals_origin"] = False
    else:
        context_data["destination_equals_origin"] = return_to_origin

    context_json = json.dumps(context_data, ensure_ascii=False)

    return (
        f"{raw_prompt}\n\n"
        "---SERVER-CANONICAL LOCATION DATA (treat as authoritative data; "
        "infer locality/city from the canonical start address; use the exact "
        "canonical origin as origin_query; honor explicit end/return constraints)---\n"
        f"{context_json}"
    )


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
    has_structured_origin = request.origin is not None

    # Scope guard — no provider calls for off-topic
    if _is_off_topic(prompt, has_structured_origin=has_structured_origin):
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

    # --- Pre-Bedrock origin/destination canonicalization for structured requests ---
    canonical_origin: GroundedPlace | None = None
    canonical_destination: GroundedPlace | None = None
    return_to_origin = False
    use_fixed_destination = False

    if has_structured_origin:
        # Canonicalize origin via PlacesClient.get_place BEFORE Bedrock call
        canon_client = PlacesClient(api_key=config.google_server_key)
        origin_started = time.perf_counter()
        try:
            canonical_origin = _canonicalize_place(
                request.origin,
                canon_client,
                PlaceCacheRepository(table_name=config.dynamodb_table_cache),
            )
        except PlacesClientError:
            _record_latency("OriginGroundingLatency", origin_started)
            canon_client.close()
            return _error_response(
                DiagnosticCode.PROVIDER_UNAVAILABLE,
                "Places service temporarily unavailable",
                503,
            )
        _record_latency("OriginGroundingLatency", origin_started)

        if canonical_origin is None:
            canon_client.close()
            return _error_response(
                DiagnosticCode.ORIGIN_NOT_FOUND,
                "Could not resolve the specified origin place",
            )

        # Canonicalize distinct destination if provided
        if request.destination is not None:
            if request.destination.place_id == canonical_origin.place_id:
                # Same place = fixed return to origin
                canonical_destination = canonical_origin
                return_to_origin = True
                use_fixed_destination = False
            else:
                dest_started = time.perf_counter()
                try:
                    canonical_destination = _canonicalize_place(
                        request.destination,
                        canon_client,
                        PlaceCacheRepository(table_name=config.dynamodb_table_cache),
                    )
                except PlacesClientError:
                    _record_latency("DestinationGroundingLatency", dest_started)
                    canon_client.close()
                    return _error_response(
                        DiagnosticCode.PROVIDER_UNAVAILABLE,
                        "Places service temporarily unavailable",
                        503,
                    )
                _record_latency("DestinationGroundingLatency", dest_started)

                if canonical_destination is None:
                    canon_client.close()
                    return _error_response(
                        DiagnosticCode.DESTINATION_NOT_FOUND,
                        "Could not resolve the specified destination place",
                    )

                # Validate timezone compatibility
                from vialo.domain.timezones import is_same_timezone

                if not is_same_timezone(
                    canonical_destination.time_zone_id, canonical_origin.time_zone_id
                ):
                    canon_client.close()
                    return _error_response(
                        DiagnosticCode.DESTINATION_NOT_FOUND,
                        "Destination is in a different timezone than the origin",
                    )

                use_fixed_destination = True
                return_to_origin = False

        canon_client.close()

    # Build the selection prompt: raw user prompt + optional canonical context
    selection_prompt = _build_selection_prompt(
        prompt, canonical_origin, canonical_destination, return_to_origin
    )

    # Step 1: Select candidate stops via Bedrock Claude
    spend_limiter = BedrockSpendLimiter(
        table_name=config.dynamodb_table_rate_limits,
        monthly_cap_micro_usd=config.bedrock_monthly_budget_micro_usd,
        input_usd_per_million=config.bedrock_input_usd_per_million,
        output_usd_per_million=config.bedrock_output_usd_per_million,
        metrics=metrics,
    )

    selector = BedrockCandidateSelector(
        spend_limiter=spend_limiter,
        model_id=config.bedrock_model_id,
        region_name=config.bedrock_region,
    )

    selection_started = time.perf_counter()
    try:
        intent = selector.select(selection_prompt)
    except BudgetExceededError:
        _record_latency("CandidateSelectionLatency", selection_started)
        return _error_response(
            DiagnosticCode.AI_BUDGET_EXCEEDED,
            "Service temporarily unavailable due to usage limits",
            429,
        )
    except SpendLimiterUnavailableError:
        _record_latency("CandidateSelectionLatency", selection_started)
        logger.exception("Spend limiter unavailable")
        return _error_response(DiagnosticCode.INTERNAL_ERROR, "Server error", 503)
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

    # Override intent return_to_origin with structured constraint
    if has_structured_origin:
        intent.return_to_origin = return_to_origin

    # Instantiate cache and places client for grounding candidates
    place_cache = PlaceCacheRepository(table_name=config.dynamodb_table_cache)
    places_client = PlacesClient(api_key=config.google_server_key)

    # --- Ground origin for non-structured requests (legacy flow) ---
    if not has_structured_origin:
        origin_started = time.perf_counter()
        try:
            canonical_origin = ground_origin(
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

        if canonical_origin is None:
            places_client.close()
            return _error_response(
                DiagnosticCode.ORIGIN_NOT_FOUND,
                "Could not resolve the requested starting point unambiguously",
            )
        return_to_origin = intent.return_to_origin

    # Handle structured destination for non-structured requests (not applicable,
    # destination requires origin) — destination already handled above for structured.
    # For legacy flow, no destination override exists.

    # At this point canonical_origin is guaranteed non-None (early returns above).
    assert canonical_origin is not None

    # Origin timezone controls date/window validation
    origin_tz = canonical_origin.time_zone_id

    # Resolve an omitted date to the next upcoming local start.
    requested_date = _resolve_requested_date(
        intent.requested_date,
        intent.local_start_time,
        origin_tz,
    )

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

    # Step 2b: Ground candidate stops
    grounding_started = time.perf_counter()
    try:
        grounded_stops, grounding_diagnostics = ground_places(
            candidates=intent.candidates,
            locality=intent.locality_query,
            client=places_client,
            requested_date=requested_date,
            cache=place_cache,
            origin_tz=origin_tz,
            window_start=window_start,
            window_end=window_end,
        )
    except PlacesClientError:
        places_client.close()
        return _error_response(
            DiagnosticCode.PROVIDER_UNAVAILABLE,
            "Places service temporarily unavailable",
            503,
        )
    finally:
        _record_latency("CandidateGroundingLatency", grounding_started)

    # --- Criterion F: One repair pass for failed candidates ---
    repairable_codes = {
        DiagnosticCode.PLACE_NOT_FOUND,
        DiagnosticCode.CLOSED_ON_DATE,
    }
    failed_for_repair = [d for d in grounding_diagnostics if d.code in repairable_codes][
        :MAX_REPAIR_CANDIDATES
    ]

    if failed_for_repair:
        repair_started = time.perf_counter()
        try:
            # Collect Google alternatives for failed candidates
            alternatives_by_index = collect_alternatives(
                failed_diagnostics=failed_for_repair,
                candidates=intent.candidates,
                locality=intent.locality_query,
                client=places_client,
            )

            # Only proceed if there are actual alternatives to offer
            if any(alts for alts in alternatives_by_index.values()):
                accepted_names = [s.name for s in grounded_stops]
                repair_context = build_repair_context(
                    failed=failed_for_repair,
                    candidates=intent.candidates,
                    accepted_names=accepted_names,
                    locality=intent.locality_query,
                    alternatives_by_index=alternatives_by_index,
                    original_prompt=prompt,
                )

                # Call repair through the selector's spend limiter (exactly once)
                try:
                    repair_response_text = selector.repair(repair_context)
                    decisions = parse_repair_decisions(repair_response_text)
                except (BudgetExceededError, SpendLimiterUnavailableError):
                    decisions = []
                except SelectorError:
                    decisions = []

                # Validate and apply decisions
                failed_indices = {d.candidate_index for d in failed_for_repair}
                candidate_by_index = {c.candidate_index: c for c in intent.candidates}

                for decision in decisions:
                    if decision.candidate_index not in failed_indices:
                        continue  # reject decisions for non-failed indices

                    if decision.action == "select_alternative":
                        # Validate selected place_id is in supplied alternatives
                        alts = alternatives_by_index.get(decision.candidate_index, [])
                        valid_pids = {a["place_id"] for a in alts}
                        if (
                            not decision.selected_place_id
                            or decision.selected_place_id not in valid_pids
                        ):
                            # Reject: arbitrary place_id
                            grounding_diagnostics.append(
                                GroundingDiagnostic(
                                    candidate_index=decision.candidate_index,
                                    name=candidate_by_index[decision.candidate_index].name,
                                    code=DiagnosticCode.CANDIDATE_REPAIR_FAILED,
                                    detail="Selected place ID not in supplied alternatives",
                                )
                            )
                            continue

                        # Re-ground the selected alternative
                        try:
                            result = places_client.get_place(decision.selected_place_id)
                        except PlacesClientError:
                            result = None

                        if result is not None and result.time_zone_id:
                            from vialo.domain.opening_hours import normalize_opening_hours
                            from vialo.domain.timezones import is_same_timezone
                            from vialo.pipeline.ground_places import (
                                _result_to_grounded_place,
                            )

                            place = _result_to_grounded_place(result)

                            # Must be same timezone
                            if not is_same_timezone(place.time_zone_id, origin_tz):
                                grounding_diagnostics.append(
                                    GroundingDiagnostic(
                                        candidate_index=decision.candidate_index,
                                        name=place.display_name,
                                        code=DiagnosticCode.CANDIDATE_REPAIR_FAILED,
                                        detail="Replacement is outside origin timezone",
                                    )
                                )
                                continue

                            # Check hours
                            hours = normalize_opening_hours(
                                current_hours=result.current_opening_hours,
                                regular_hours=result.regular_opening_hours,
                                requested_date=requested_date,
                                tz_id=place.time_zone_id,
                                fetch_instant=dt.datetime.now(dt.UTC),
                            )
                            resolved_hours = _repair_hours_with_unverified_fallback(
                                hours,
                                window_start=window_start,
                                window_end=window_end,
                                time_zone_id=place.time_zone_id,
                            )
                            if isinstance(resolved_hours, DiagnosticCode):
                                grounding_diagnostics.append(
                                    GroundingDiagnostic(
                                        candidate_index=decision.candidate_index,
                                        name=place.display_name,
                                        code=DiagnosticCode.CANDIDATE_REPAIR_FAILED,
                                        detail=(
                                            f"Replacement has hours issue: {resolved_hours.value}"
                                        ),
                                    )
                                )
                                continue
                            hours_source, open_intervals = resolved_hours

                            # Success - add repaired stop
                            orig_candidate = candidate_by_index[decision.candidate_index]
                            from vialo.models.itinerary import GroundedStop

                            repaired_stop = GroundedStop(
                                candidate_index=decision.candidate_index,
                                name=place.display_name,
                                category=orig_candidate.category,
                                priority=orig_candidate.priority,
                                visit_duration_minutes=orig_candidate.visit_duration_minutes,
                                duration_source=orig_candidate.duration_source,
                                place=place,
                                hours_source=hours_source,
                                open_intervals=open_intervals,
                            )
                            grounded_stops.append(repaired_stop)

                            # Remove superseded failure diagnostic
                            grounding_diagnostics = [
                                d
                                for d in grounding_diagnostics
                                if d.candidate_index != decision.candidate_index
                                or d.code not in repairable_codes
                            ]
                            # Add repaired diagnostic
                            grounding_diagnostics.append(
                                GroundingDiagnostic(
                                    candidate_index=decision.candidate_index,
                                    name=place.display_name,
                                    code=DiagnosticCode.CANDIDATE_REPAIRED,
                                    detail=f"Replaced with {place.display_name}",
                                )
                            )
                        else:
                            grounding_diagnostics.append(
                                GroundingDiagnostic(
                                    candidate_index=decision.candidate_index,
                                    name=candidate_by_index[decision.candidate_index].name,
                                    code=DiagnosticCode.CANDIDATE_REPAIR_FAILED,
                                    detail="Could not resolve selected alternative",
                                )
                            )

                    elif decision.action == "replace_query":
                        # Validate query is bounded and concrete
                        query = decision.replacement_query or ""
                        if not query or len(query) > 100 or len(query) < 3:
                            grounding_diagnostics.append(
                                GroundingDiagnostic(
                                    candidate_index=decision.candidate_index,
                                    name=candidate_by_index[decision.candidate_index].name,
                                    code=DiagnosticCode.CANDIDATE_REPAIR_FAILED,
                                    detail="Replacement query invalid",
                                )
                            )
                            continue

                        # Re-ground with replacement query (once, no recursion)
                        try:
                            from vialo.domain.opening_hours import normalize_opening_hours
                            from vialo.domain.timezones import is_same_timezone
                            from vialo.pipeline.ground_places import (
                                _result_to_grounded_place,
                                _select_unambiguous_result,
                            )

                            results = places_client.search_text(query, intent.locality_query)
                            selected = _select_unambiguous_result(
                                query, intent.locality_query, results
                            )
                        except PlacesClientError:
                            selected = None

                        if (
                            selected is not None
                            and selected.time_zone_id
                            and is_same_timezone(selected.time_zone_id, origin_tz)
                        ):
                            place = _result_to_grounded_place(selected)
                            hours = normalize_opening_hours(
                                current_hours=selected.current_opening_hours,
                                regular_hours=selected.regular_opening_hours,
                                requested_date=requested_date,
                                tz_id=place.time_zone_id,
                                fetch_instant=dt.datetime.now(dt.UTC),
                            )
                            resolved_hours = _repair_hours_with_unverified_fallback(
                                hours,
                                window_start=window_start,
                                window_end=window_end,
                                time_zone_id=place.time_zone_id,
                            )
                            if isinstance(resolved_hours, DiagnosticCode):
                                grounding_diagnostics.append(
                                    GroundingDiagnostic(
                                        candidate_index=decision.candidate_index,
                                        name=query,
                                        code=DiagnosticCode.CANDIDATE_REPAIR_FAILED,
                                        detail=(
                                            f"Replacement has hours issue: {resolved_hours.value}"
                                        ),
                                    )
                                )
                                continue
                            hours_source, open_intervals = resolved_hours

                            orig_candidate = candidate_by_index[decision.candidate_index]
                            from vialo.models.itinerary import GroundedStop

                            repaired_stop = GroundedStop(
                                candidate_index=decision.candidate_index,
                                name=place.display_name,
                                category=orig_candidate.category,
                                priority=orig_candidate.priority,
                                visit_duration_minutes=orig_candidate.visit_duration_minutes,
                                duration_source=orig_candidate.duration_source,
                                place=place,
                                hours_source=hours_source,
                                open_intervals=open_intervals,
                            )
                            grounded_stops.append(repaired_stop)

                            grounding_diagnostics = [
                                d
                                for d in grounding_diagnostics
                                if d.candidate_index != decision.candidate_index
                                or d.code not in repairable_codes
                            ]
                            grounding_diagnostics.append(
                                GroundingDiagnostic(
                                    candidate_index=decision.candidate_index,
                                    name=place.display_name,
                                    code=DiagnosticCode.CANDIDATE_REPAIRED,
                                    detail=f"Replaced with {place.display_name} via query",
                                )
                            )
                        else:
                            grounding_diagnostics.append(
                                GroundingDiagnostic(
                                    candidate_index=decision.candidate_index,
                                    name=candidate_by_index[decision.candidate_index].name,
                                    code=DiagnosticCode.CANDIDATE_REPAIR_FAILED,
                                    detail="Replacement query did not resolve",
                                )
                            )
                    # action == "skip" — leave existing failure diagnostic
        except Exception:
            logger.exception("Repair pass failed")
        finally:
            _record_latency("RepairLatency", repair_started)

        # Re-sort grounded stops after repair
        grounded_stops.sort(key=lambda stop: stop.candidate_index)

    # Close places client after all grounding/repair
    places_client.close()

    for metric_name, attribute in (
        ("PlaceCacheHit", "hits"),
        ("PlaceCacheMiss", "misses"),
        ("PlaceCacheError", "errors"),
    ):
        metric_value = getattr(place_cache, attribute, None)
        if isinstance(metric_value, int):
            metrics.add_metric(name=metric_name, unit="Count", value=metric_value)

    # Populate photoUrl on grounded places
    from vialo.api.photos import build_photo_url

    for stop in grounded_stops:
        if stop.place.photos and not stop.place.photo_url:
            first_photo = stop.place.photos[0]
            if first_photo.name:
                stop.place.photo_url = build_photo_url(first_photo.name, 400)
    if canonical_origin.photos and not canonical_origin.photo_url:
        first_photo = canonical_origin.photos[0]
        if first_photo.name:
            canonical_origin.photo_url = build_photo_url(first_photo.name, 400)
    if (
        canonical_destination
        and canonical_destination.photos
        and not canonical_destination.photo_url
    ):
        first_photo = canonical_destination.photos[0]
        if first_photo.name:
            canonical_destination.photo_url = build_photo_url(first_photo.name, 400)

    # If all stops excluded, return NO_FEASIBLE_ITINERARY with diagnostics
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

    # Step 3: Compute travel-time matrix (with optional destination sink)
    routes_client = RoutesClient(api_key=config.google_server_key)
    matrix_started = time.perf_counter()
    try:
        matrix = compute_matrix(
            origin=canonical_origin,
            stops=grounded_stops,
            travel_mode=intent.travel_mode,
            client=routes_client,
            destination=canonical_destination if use_fixed_destination else None,
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

    # Destination index in matrix (if used): last position
    destination_matrix_index: int | None = None
    if use_fixed_destination:
        destination_matrix_index = len(grounded_stops) + 1

    # Step 4: Solve the route
    solver_started = time.perf_counter()
    solve_result = solve_route(
        stops=grounded_stops,
        matrix=matrix,
        window_start=window_start,
        window_end=window_end,
        return_to_origin=return_to_origin,
        travel_mode=intent.travel_mode,
        destination_index=destination_matrix_index,
    )
    _record_latency("ExactSolverLatency", solver_started)

    if solve_result is None:
        routes_client.close()
        return _error_response(
            DiagnosticCode.NO_FEASIBLE_ITINERARY,
            "Cannot fit any stops in the given time window",
            422,
        )

    schedule, dropped = solve_result

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
            origin=canonical_origin,
            ordered_stops=ordered_stops,
            travel_mode=intent.travel_mode,
            client=routes_client,
            return_to_origin=return_to_origin,
            destination=canonical_destination if use_fixed_destination else None,
        )

        # Naive geometry: stops in original candidate order
        naive_order_indices = [
            s.candidate_index
            for s in grounded_stops
            if s.candidate_index in retained_candidate_indices
        ]
        naive_ordered_stops = [stop_by_ci[ci] for ci in naive_order_indices if ci in stop_by_ci]
        naive_geometry = compute_route_geometry(
            origin=canonical_origin,
            ordered_stops=naive_ordered_stops,
            travel_mode=intent.travel_mode,
            client=routes_client,
            return_to_origin=return_to_origin,
            destination=canonical_destination if use_fixed_destination else None,
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

    # Simulate naive order with ORIGINAL matrix indices
    naive_candidate_order = [s.candidate_index for s in grounded_stops]
    _naive_timeline, naive_feasible, naive_codes = simulate_naive_order(
        retained_stops=retained_stops,
        candidate_order=naive_candidate_order,
        origin_index=0,
        matrix=matrix,
        window_start=window_start,
        window_end=window_end,
        return_to_origin=return_to_origin,
        travel_mode=intent.travel_mode,
        original_matrix_indices=original_matrix_indices,
        destination_index=destination_matrix_index,
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
        origin=canonical_origin,
        ordered_stops=ordered_stops,
        travel_mode=intent.travel_mode,
        return_to_origin=return_to_origin,
        destination=canonical_destination if use_fixed_destination else None,
    )

    # Build response
    request_id = str(uuid.uuid4())

    # Status is "partial" when ANY grounding exclusion OR solver drop exists
    has_drops = len(dropped) > 0
    # Simpler: partial if there are failure diagnostics or drops
    failure_diags = [
        d for d in grounding_diagnostics if d.code != DiagnosticCode.CANDIDATE_REPAIRED
    ]
    itinerary_status: str = "partial" if (failure_diags or has_drops) else "complete"

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

    # Walking beta warning
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

    dropped_by_candidate: dict[int, DroppedStop] = {}
    for diag in grounding_diagnostics:
        if diag.code not in {
            DiagnosticCode.PLACE_NOT_FOUND,
            DiagnosticCode.CLOSED_ON_DATE,
            DiagnosticCode.OUTSIDE_LOCALITY,
            DiagnosticCode.DUPLICATE_PLACE,
            DiagnosticCode.CANDIDATE_REPAIR_FAILED,
        }:
            continue
        # A failed repair follows the original grounding failure for the same
        # candidate. Keep the final diagnosis without counting that stop twice.
        dropped_by_candidate[diag.candidate_index] = DroppedStop(
            candidate_index=diag.candidate_index,
            name=diag.name,
            reason_code=diag.code,
            reason_detail=diag.detail,
        )
    all_dropped = list(dropped_by_candidate.values()) + dropped

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

    # Determine response destination field
    # Only set when explicitly supplied (including same as origin)
    response_destination: GroundedPlace | None = None
    if request.destination is not None:
        response_destination = canonical_destination

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
        origin=canonical_origin,
        destination=response_destination,
        stops=ordered_stops,
        timeline=schedule.timeline,
        dropped_stops=all_dropped,
        comparison=comparison,
        maps_handoff=handoff,
        totals=schedule.totals,
        diagnostics=response_diagnostics_list,
        share_proof=None,
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
