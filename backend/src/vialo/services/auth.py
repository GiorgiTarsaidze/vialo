"""Cognito ID-token verification for Vialo Journal writes.

Reading the Journal is anonymous. Publishing, commenting, reporting, and
requesting an upload URL require a Cognito ID token, verified here against the
user pool's published JWKS. Tokens are never logged, and no email address is
copied out of the token into storage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import jwt
from jwt import PyJWKClient

from vialo.models.blog import DISPLAY_NAME_MAX

logger = logging.getLogger(__name__)

# One JWKS client per pool, cached for the life of the execution environment.
_jwks_clients: dict[str, PyJWKClient] = {}


class AuthError(Exception):
    """Raised when a request is not authenticated."""

    def __init__(self, message: str = "Sign in to continue") -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """The verified caller. `user_id` is the opaque Cognito subject."""

    user_id: str
    display_name: str


def _issuer(region: str, user_pool_id: str) -> str:
    return f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"


def _jwks_client(region: str, user_pool_id: str) -> PyJWKClient:
    url = f"{_issuer(region, user_pool_id)}/.well-known/jwks.json"
    client = _jwks_clients.get(url)
    if client is None:
        client = PyJWKClient(url, cache_keys=True, lifespan=3600)
        _jwks_clients[url] = client
    return client


def _clean_display_name(raw: str) -> str:
    """Keep a display name printable, single-line, and bounded."""
    collapsed = " ".join(raw.split())
    safe = "".join(ch for ch in collapsed if ch.isprintable())
    return safe[:DISPLAY_NAME_MAX].strip()


def display_name_from_claims(claims: dict[str, Any]) -> str:
    """Derive a display name without storing the email address itself."""
    for key in ("nickname", "preferred_username", "name", "given_name"):
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            cleaned = _clean_display_name(value)
            if cleaned:
                return cleaned
    email = claims.get("email")
    if isinstance(email, str) and "@" in email:
        cleaned = _clean_display_name(email.split("@", 1)[0])
        if cleaned:
            return cleaned
    return "Traveller"


def verify_id_token(
    token: str,
    *,
    region: str,
    user_pool_id: str,
    client_id: str,
) -> AuthenticatedUser:
    """Verify a Cognito ID token and return the caller.

    Raises:
        AuthError: If the token is missing, malformed, expired, or not issued by
            this user pool for this application client.
    """
    if not token:
        raise AuthError()

    try:
        signing_key = _jwks_client(region, user_pool_id).get_signing_key_from_jwt(token)
        claims: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=_issuer(region, user_pool_id),
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except Exception as exc:  # PyJWT raises many subclasses; none may leak upward
        logger.info("Token verification failed: %s", type(exc).__name__)
        raise AuthError("Your session has expired. Sign in again.") from exc

    if claims.get("token_use") != "id":
        raise AuthError("Wrong token type")

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise AuthError()

    return AuthenticatedUser(user_id=subject, display_name=display_name_from_claims(claims))


def bearer_token(headers: dict[str, str] | None) -> str:
    """Extract a bearer token from request headers, case-insensitively."""
    if not headers:
        return ""
    for key, value in headers.items():
        if key.lower() != "authorization":
            continue
        parts = value.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
    return ""
