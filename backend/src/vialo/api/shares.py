"""Share routes: POST/GET/DELETE /api/shares.

Fix (A): Require POST proof to match itinerary.share_proof when present.
"""

from __future__ import annotations

import json
from typing import Any

from aws_lambda_powertools.event_handler import Response, content_types
from pydantic import ValidationError

from vialo.config import load_config
from vialo.handler import app, logger, metrics
from vialo.models.diagnostics import DiagnosticCode
from vialo.models.requests import CreateShareRequest
from vialo.services.share_repository import ShareRepository


def _error_response(code: str, message: str, status_code: int = 400) -> Response:  # type: ignore[type-arg]
    """Build a JSON error response."""
    body = json.dumps({"error": {"code": code, "message": message}})
    return Response(
        status_code=status_code,
        content_type=content_types.APPLICATION_JSON,
        body=body,
    )


def _get_share_repo() -> ShareRepository:
    """Create a ShareRepository from config."""
    config = load_config()
    return ShareRepository(
        table_name=config.dynamodb_table_shares,
        signing_secret=config.share_signing_secret,
        deletion_secret=config.share_deletion_secret,
    )


@app.post("/api/shares")
def create_share() -> Response:  # type: ignore[type-arg]
    """Create a shared itinerary permalink.

    Requires proof to match itinerary.share_proof when present in the itinerary.
    """
    metrics.add_metric(name="ShareCreateRequest", unit="Count", value=1)
    body: dict[str, Any] = app.current_event.json_body or {}
    if not body:
        return _error_response(
            DiagnosticCode.INVALID_INPUT.value,
            "Body required",
        )

    # Validate with Pydantic model
    try:
        request = CreateShareRequest.model_validate_json(json.dumps(body))
    except ValidationError:
        return _error_response(
            DiagnosticCode.INVALID_INPUT.value,
            "Invalid request body: itinerary and proof fields required",
        )

    itinerary = request.itinerary
    proof = request.proof

    # If the itinerary has a share_proof attached, the POST proof must match
    if itinerary.share_proof is not None and (
        proof.hmac != itinerary.share_proof.hmac
        or proof.expires_at != itinerary.share_proof.expires_at
    ):
        return _error_response(
            DiagnosticCode.INVALID_INPUT.value,
            "Proof does not match itinerary.share_proof",
        )

    # Create the share — proof verification happens inside repository
    try:
        repo = _get_share_repo()
        result = repo.create(itinerary, proof)
    except ValueError:
        return _error_response(
            DiagnosticCode.INVALID_INPUT.value,
            "Invalid or expired share proof",
        )
    except Exception:
        logger.exception("Share creation failed")
        return _error_response(DiagnosticCode.INTERNAL_ERROR.value, "Server error", 500)

    metrics.add_metric(name="ShareCreated", unit="Count", value=1)
    return Response(
        status_code=201,
        content_type=content_types.APPLICATION_JSON,
        body=result.model_dump_json(by_alias=True),
    )


@app.get("/api/shares/<share_id>")
def get_share(share_id: str) -> Response:  # type: ignore[type-arg]
    """Retrieve a shared itinerary."""
    metrics.add_metric(name="ShareGetRequest", unit="Count", value=1)
    if not share_id:
        return _error_response(
            DiagnosticCode.SHARE_NOT_FOUND.value,
            "Share ID required",
            404,
        )

    try:
        repo = _get_share_repo()
        itinerary = repo.get(share_id)
    except ValueError:
        return _error_response(DiagnosticCode.INTERNAL_ERROR.value, "Server error", 500)
    except Exception:
        logger.exception("Share retrieval failed")
        return _error_response(DiagnosticCode.INTERNAL_ERROR.value, "Server error", 500)

    if itinerary is None:
        return _error_response(
            DiagnosticCode.SHARE_NOT_FOUND.value,
            "Share not found or expired",
            404,
        )

    metrics.add_metric(name="ShareRetrieved", unit="Count", value=1)
    return Response(
        status_code=200,
        content_type=content_types.APPLICATION_JSON,
        body=itinerary.model_dump_json(by_alias=True),
    )


@app.delete("/api/shares/<share_id>")
def delete_share(share_id: str) -> Response:  # type: ignore[type-arg]
    """Delete a shared itinerary using a deletion token."""
    metrics.add_metric(name="ShareDeleteRequest", unit="Count", value=1)
    if not share_id:
        return _error_response(
            DiagnosticCode.SHARE_NOT_FOUND.value,
            "Share ID required",
            404,
        )

    # Deletion token from header
    token = app.current_event.headers.get("x-share-delete-token")
    if not token:
        return _error_response(
            DiagnosticCode.INVALID_INPUT.value,
            "X-Share-Delete-Token header required",
            401,
        )

    try:
        repo = _get_share_repo()
        deleted = repo.delete(share_id, token)
    except ValueError:
        return _error_response(DiagnosticCode.INTERNAL_ERROR.value, "Server error", 500)
    except Exception:
        logger.exception("Share deletion failed")
        return _error_response(DiagnosticCode.INTERNAL_ERROR.value, "Server error", 500)

    if not deleted:
        return _error_response(
            DiagnosticCode.SHARE_NOT_FOUND.value,
            "Share not found or invalid deletion token",
            404,
        )

    metrics.add_metric(name="ShareDeleted", unit="Count", value=1)
    return Response(
        status_code=204,
        content_type=content_types.APPLICATION_JSON,
        body="",
    )
