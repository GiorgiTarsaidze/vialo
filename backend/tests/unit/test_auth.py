"""Tests for Cognito ID-token verification and display-name derivation."""

from __future__ import annotations

import datetime as dt
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from vialo.services.auth import (
    AuthenticatedUser,
    AuthError,
    bearer_token,
    display_name_from_claims,
    verify_id_token,
)

REGION = "us-east-1"
POOL_ID = "us-east-1_TESTPOOL"
CLIENT_ID = "test-client-id"
ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{POOL_ID}"

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _token(**overrides: Any) -> str:
    now = dt.datetime.now(dt.UTC)
    claims: dict[str, Any] = {
        "sub": "cognito-subject-1",
        "aud": CLIENT_ID,
        "iss": ISSUER,
        "token_use": "id",
        "email": "traveller@example.com",
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(minutes=30)).timestamp()),
    }
    claims.update(overrides)
    return jwt.encode(claims, _KEY, algorithm="RS256")


class _FakeSigningKey:
    key = _KEY.public_key()


class _FakeJwksClient:
    def get_signing_key_from_jwt(self, token: str) -> _FakeSigningKey:
        del token
        return _FakeSigningKey()


@pytest.fixture(autouse=True)
def _patch_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "vialo.services.auth._jwks_client",
        lambda region, user_pool_id: _FakeJwksClient(),
    )


def _verify(token: str) -> AuthenticatedUser:
    return verify_id_token(token, region=REGION, user_pool_id=POOL_ID, client_id=CLIENT_ID)


class TestVerifyIdToken:
    def test_valid_token_returns_the_subject(self) -> None:
        user = _verify(_token())
        assert user.user_id == "cognito-subject-1"
        assert user.display_name == "traveller"

    def test_missing_token_is_refused(self) -> None:
        with pytest.raises(AuthError):
            _verify("")

    def test_expired_token_is_refused(self) -> None:
        past = dt.datetime.now(dt.UTC) - dt.timedelta(hours=2)
        with pytest.raises(AuthError):
            _verify(_token(exp=int(past.timestamp()), iat=int(past.timestamp())))

    def test_token_for_another_client_is_refused(self) -> None:
        with pytest.raises(AuthError):
            _verify(_token(aud="someone-elses-client"))

    def test_token_from_another_pool_is_refused(self) -> None:
        with pytest.raises(AuthError):
            _verify(_token(iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_OTHER"))

    def test_access_token_is_refused_for_write_routes(self) -> None:
        with pytest.raises(AuthError):
            _verify(_token(token_use="access"))

    def test_token_without_subject_is_refused(self) -> None:
        with pytest.raises(AuthError):
            _verify(_token(sub=""))

    def test_garbage_token_is_refused(self) -> None:
        with pytest.raises(AuthError):
            _verify("not-a-jwt")


class TestDisplayName:
    def test_nickname_wins(self) -> None:
        assert display_name_from_claims({"nickname": "Ana", "email": "x@y.z"}) == "Ana"

    def test_falls_back_through_profile_claims(self) -> None:
        assert display_name_from_claims({"given_name": "Bo"}) == "Bo"
        assert display_name_from_claims({"preferred_username": "cy"}) == "cy"

    def test_email_local_part_is_used_but_the_domain_is_dropped(self) -> None:
        name = display_name_from_claims({"email": "ana.traveller@example.com"})
        assert name == "ana.traveller"
        assert "example.com" not in name

    def test_unknown_identity_becomes_traveller(self) -> None:
        assert display_name_from_claims({}) == "Traveller"

    def test_display_name_is_bounded_and_single_line(self) -> None:
        name = display_name_from_claims({"nickname": "A" * 200})
        assert len(name) <= 40
        multiline = display_name_from_claims({"nickname": "Ana\n\nSmith"})
        assert multiline == "Ana Smith"

    def test_control_characters_are_stripped(self) -> None:
        assert display_name_from_claims({"nickname": "An\x07a"}) == "Ana"


class TestBearerToken:
    def test_extracts_case_insensitively(self) -> None:
        assert bearer_token({"Authorization": "Bearer abc"}) == "abc"
        assert bearer_token({"authorization": "bearer abc"}) == "abc"

    def test_missing_or_malformed_header_yields_empty(self) -> None:
        assert bearer_token(None) == ""
        assert bearer_token({}) == ""
        assert bearer_token({"Authorization": "abc"}) == ""
        assert bearer_token({"Authorization": "Basic abc"}) == ""
