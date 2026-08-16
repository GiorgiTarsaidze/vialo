"""POST /api/places/autocomplete and /api/places/lookup — server-side place search.

Uses existing GOOGLE_SERVER_KEY for Places API calls. Separate rate limit
bucket (PLACES prefix) avoids consuming the 5/hour planning quota.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from aws_lambda_powertools.event_handler import Response, content_types
from pydantic import ValidationError

from vialo.config import load_config
from vialo.handler import app, metrics
from vialo.models.diagnostics import DiagnosticCode
from vialo.models.providers import Location
from vialo.models.requests import (
    AutocompleteRequest,
    AutocompleteResponse,
    AutocompleteSuggestion,
    PlaceLookupRequest,
    PlaceLookupResponse,
)
from vialo.services.places_client import (
    AUTOCOMPLETE_FIELD_MASK,
    PlacesClient,
    PlacesClientError,
)
from vialo.services.rate_limiter import RateLimiter

_logger = logging.getLogger(__name__)

# Separate rate limit: 30 autocomplete requests/hour per IP (does not consume planning quota)
_AUTOCOMPLETE_RATE_LIMIT = 30


def _error_response(code: DiagnosticCode, message: str, status_code: int = 400) -> Response:  # type: ignore[type-arg]
    body = json.dumps({"error": {"code": code.value, "message": message}})
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


@app.post("/api/places/autocomplete")
def places_autocomplete() -> Response:  # type: ignore[type-arg]
    """Return up to 5 place suggestions for a query (min 3 chars)."""
    metrics.add_metric(name="PlacesAutocompleteRequest", unit="Count", value=1)
    body: dict[str, Any] = app.current_event.json_body or {}

    # Frontend sends {input: query}, backend canonical is {query: ...}
    # Accept either for compatibility
    if "input" in body and "query" not in body:
        body["query"] = body.pop("input")

    try:
        request = AutocompleteRequest.model_validate(body)
    except ValidationError:
        return _error_response(
            DiagnosticCode.INVALID_INPUT,
            "Invalid request: query is required (3-200 characters)",
        )

    try:
        config = load_config()
    except ValueError:
        return _error_response(DiagnosticCode.INTERNAL_ERROR, "Server configuration error", 500)

    # Separate rate limit bucket for autocomplete (prefix: PLACES_AC)
    try:
        rate_limiter = RateLimiter(
            table_name=config.dynamodb_table_rate_limits,
            hmac_secret=config.rate_limit_hmac_secret,
            max_requests=_AUTOCOMPLETE_RATE_LIMIT,
            bucket_prefix="PLACES_AC",
        )
        client_ip = _get_client_ip()
        allowed, retry_after = rate_limiter.check_and_increment(client_ip)
    except Exception:
        _logger.exception("Rate-limit check failed for autocomplete")
        return _error_response(DiagnosticCode.INTERNAL_ERROR, "Server error", 500)

    if not allowed:
        resp = _error_response(DiagnosticCode.RATE_LIMITED, "Rate limit exceeded", 429)
        if retry_after:
            resp.headers = {"Retry-After": str(retry_after)}
        return resp

    # Call Places API searchText (reusing existing client)
    places_client = PlacesClient(api_key=config.google_server_key)
    try:
        results = places_client.search_text(
            request.query,
            "",
            field_mask=AUTOCOMPLETE_FIELD_MASK,
        )
    except PlacesClientError:
        return _error_response(
            DiagnosticCode.PROVIDER_UNAVAILABLE,
            "Places service temporarily unavailable",
            503,
        )
    finally:
        places_client.close()

    # Build suggestions (max 5)
    suggestions: list[AutocompleteSuggestion] = []
    for result in results[:5]:
        if not result.place_id or not result.display_name:
            continue
        loc = (
            Location(latitude=result.latitude, longitude=result.longitude)
            if result.latitude != 0.0 or result.longitude != 0.0
            else None
        )
        suggestions.append(
            AutocompleteSuggestion(
                place_id=result.place_id,
                display_name=result.display_name,
                formatted_address=result.formatted_address,
                location=loc,
            )
        )

    response = AutocompleteResponse(predictions=suggestions)
    return Response(
        status_code=200,
        content_type=content_types.APPLICATION_JSON,
        body=response.model_dump_json(by_alias=True),
    )


@app.post("/api/places/lookup")
def places_lookup() -> Response:  # type: ignore[type-arg]
    """Canonical server-side place lookup by ID. Never trust browser display name/coords."""
    metrics.add_metric(name="PlacesLookupRequest", unit="Count", value=1)
    body: dict[str, Any] = app.current_event.json_body or {}

    try:
        request = PlaceLookupRequest.model_validate(body)
    except ValidationError:
        return _error_response(
            DiagnosticCode.INVALID_INPUT,
            "Invalid request: placeId is required",
        )

    try:
        config = load_config()
    except ValueError:
        return _error_response(DiagnosticCode.INTERNAL_ERROR, "Server configuration error", 500)

    # Separate rate limit bucket for lookups (prefix: PLACES_LK)
    try:
        rate_limiter = RateLimiter(
            table_name=config.dynamodb_table_rate_limits,
            hmac_secret=config.rate_limit_hmac_secret,
            max_requests=_AUTOCOMPLETE_RATE_LIMIT,
            bucket_prefix="PLACES_LK",
        )
        client_ip = _get_client_ip()
        allowed, retry_after = rate_limiter.check_and_increment(client_ip)
    except Exception:
        _logger.exception("Rate-limit check failed for lookup")
        return _error_response(DiagnosticCode.INTERNAL_ERROR, "Server error", 500)

    if not allowed:
        resp = _error_response(DiagnosticCode.RATE_LIMITED, "Rate limit exceeded", 429)
        if retry_after:
            resp.headers = {"Retry-After": str(retry_after)}
        return resp

    # Call Places API get-by-ID
    places_client = PlacesClient(api_key=config.google_server_key)
    try:
        result = places_client.get_place(request.place_id)
    except PlacesClientError:
        return _error_response(
            DiagnosticCode.PROVIDER_UNAVAILABLE,
            "Places service temporarily unavailable",
            503,
        )
    finally:
        places_client.close()

    if result is None:
        return _error_response(
            DiagnosticCode.PLACE_NOT_FOUND,
            "Place not found",
            404,
        )

    response = PlaceLookupResponse(
        place_id=result.place_id,
        display_name=result.display_name,
        formatted_address=result.formatted_address,
        location=Location(latitude=result.latitude, longitude=result.longitude),
        time_zone_id=result.time_zone_id,
    )
    return Response(
        status_code=200,
        content_type=content_types.APPLICATION_JSON,
        body=response.model_dump_json(by_alias=True),
    )
