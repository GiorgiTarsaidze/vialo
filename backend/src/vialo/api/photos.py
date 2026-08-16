"""GET /api/photos — secure bounded photo proxy.

Proxies Google Places photo requests through the server to avoid exposing
the server API key. Uses query parameters for resource name to avoid
slash-path complexity with API Gateway/Powertools routing.

Frontend constructs: /api/photos?name=<encoded resource>&maxWidth=<n>
Server validates the resource name matches Google photo resource pattern,
returns a 307 redirect to Google's signed photoUri. Never exposes key.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import quote

import httpx
from aws_lambda_powertools.event_handler import Response, content_types

from vialo.config import load_config
from vialo.handler import app, metrics
from vialo.services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# Google Places photo resource name pattern:
# places/{placeId}/photos/{photoReference}
_PHOTO_RESOURCE_PATTERN = re.compile(r"^places/[A-Za-z0-9_-]+/photos/[A-Za-z0-9_-]+$")

# Max dimensions (bounded to avoid abuse)
_MAX_WIDTH = 800
_MAX_HEIGHT = 600

# Photo proxy timeout and per-IP hourly cap
_PHOTO_TIMEOUT = 8.0
_PHOTO_RATE_LIMIT = 60


def build_photo_url(resource_name: str, max_width: int = 400) -> str | None:
    """Build a same-origin photo proxy URL from a Places photo resource name.

    Returns None if the resource name is invalid.
    """
    if not _PHOTO_RESOURCE_PATTERN.match(resource_name):
        return None
    width = min(max(1, max_width), _MAX_WIDTH)
    return f"/api/photos?name={quote(resource_name, safe='')}&maxWidth={width}"


@app.get("/api/photos")
def get_photo() -> Response:  # type: ignore[type-arg]
    """Proxy a Google Places photo with bounded dimensions.

    Query params:
      name: Google photo resource (places/{placeId}/photos/{photoRef})
      maxWidth: optional, capped at 800
      maxHeight: optional, capped at 600
    """
    metrics.add_metric(name="PhotoProxyRequest", unit="Count", value=1)

    params: dict[str, Any] = app.current_event.query_string_parameters or {}
    photo_resource = params.get("name", "")

    # Validate resource name strictly
    if not photo_resource or not _PHOTO_RESOURCE_PATTERN.match(photo_resource):
        return _error(400, "INVALID_PHOTO_RESOURCE", "Invalid photo resource name")

    # Get optional dimension params
    try:
        max_width = min(int(params.get("maxWidth", str(_MAX_WIDTH))), _MAX_WIDTH)
        max_height = min(int(params.get("maxHeight", str(_MAX_HEIGHT))), _MAX_HEIGHT)
    except (ValueError, TypeError):
        return _error(400, "INVALID_DIMENSIONS", "Invalid dimension parameters")

    if max_width < 1 or max_height < 1:
        return _error(400, "INVALID_DIMENSIONS", "Dimensions must be positive")

    try:
        config = load_config()
    except ValueError:
        return _error(500, "INTERNAL_ERROR", "Server configuration error")

    try:
        rate_limiter = RateLimiter(
            table_name=config.dynamodb_table_rate_limits,
            hmac_secret=config.rate_limit_hmac_secret,
            max_requests=_PHOTO_RATE_LIMIT,
            bucket_prefix="PLACES_PHOTO",
        )
        try:
            client_ip = app.current_event.request_context.http.source_ip
        except (AttributeError, TypeError):
            client_ip = "unknown"
        allowed, retry_after = rate_limiter.check_and_increment(client_ip)
    except Exception:
        logger.exception("Rate-limit check failed for photo proxy")
        return _error(500, "INTERNAL_ERROR", "Server error")

    if not allowed:
        rate_response = _error(429, "RATE_LIMITED", "Photo request limit exceeded")
        if retry_after:
            rate_response.headers = {"Retry-After": str(retry_after)}
        return rate_response

    # Fetch photo URI from Google Places API (skipHttpRedirect=true returns JSON)
    url = f"https://places.googleapis.com/v1/{photo_resource}/media"
    headers = {
        "X-Goog-Api-Key": config.google_server_key,
    }
    query_params = {
        "maxWidthPx": str(max_width),
        "maxHeightPx": str(max_height),
        "skipHttpRedirect": "true",
    }

    try:
        client = httpx.Client(timeout=_PHOTO_TIMEOUT)
        try:
            response = client.get(url, headers=headers, params=query_params)
        finally:
            client.close()
    except httpx.RequestError:
        return _error(502, "PHOTO_SERVICE_UNAVAILABLE", "Photo service unavailable")

    if response.status_code != 200:
        if response.status_code == 404:
            return _error(404, "PHOTO_NOT_FOUND", "Photo not found")
        return _error(502, "PHOTO_SERVICE_ERROR", "Photo service error")

    # The skipHttpRedirect=true response returns JSON with photoUri
    try:
        data = response.json()
        photo_uri = data.get("photoUri")
        if not photo_uri:
            return _error(502, "NO_PHOTO_URI", "No photo URI returned")
    except Exception:
        return _error(502, "INVALID_PHOTO_RESPONSE", "Invalid photo response")

    # Return 307 redirect to Google's time-limited signed URL (no key exposure)
    return Response(
        status_code=307,
        content_type=content_types.APPLICATION_JSON,
        body="",
        headers={
            "Location": photo_uri,
            "Cache-Control": "public, max-age=3600, s-maxage=86400",
            "X-Photo-Width": str(max_width),
            "X-Photo-Height": str(max_height),
        },
    )


def _error(status_code: int, code: str, message: str) -> Response:  # type: ignore[type-arg]
    """Build typed error response with code+message."""
    return Response(
        status_code=status_code,
        content_type=content_types.APPLICATION_JSON,
        body=json.dumps({"error": {"code": code, "message": message}}),
    )
