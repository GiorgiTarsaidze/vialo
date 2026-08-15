"""Tests for ShareRepository: idempotency, HMAC verification, tamper, replay, expiry."""

from __future__ import annotations

import datetime as dt
import time
from typing import Any
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

from vialo.models.itinerary import (
    ComparisonUnavailable,
    GroundedStop,
    ItineraryResponse,
    Locality,
    MapsHandoff,
    OpenInterval,
    ShareProof,
    TimeWindow,
    Totals,
)
from vialo.models.providers import GroundedPlace, Location, StopCategory
from vialo.services.share_repository import ShareRepository


def _make_itinerary() -> ItineraryResponse:
    """Create a minimal valid ItineraryResponse for testing."""
    tz = dt.timezone(dt.timedelta(hours=2))
    origin = GroundedPlace(
        place_id="origin_place",
        display_name="Origin",
        formatted_address="Somewhere",
        location=Location(latitude=45.0, longitude=12.0),
        time_zone_id="Europe/Rome",
    )
    stop = GroundedStop(
        candidate_index=0,
        name="Stop A",
        category=StopCategory.LANDMARK,
        priority=1,
        visit_duration_minutes=30,
        duration_source="model_estimate",
        place=GroundedPlace(
            place_id="stop_a_place",
            display_name="Stop A",
            formatted_address="Address A",
            location=Location(latitude=45.01, longitude=12.01),
            time_zone_id="Europe/Rome",
        ),
        hours_source="current",
        open_intervals=[
            OpenInterval(
                start=dt.datetime(2026, 8, 15, 9, 0, tzinfo=tz),
                end=dt.datetime(2026, 8, 15, 18, 0, tzinfo=tz),
                local_start="09:00",
                local_end="18:00",
            )
        ],
    )

    return ItineraryResponse(
        schema_version=1,
        request_id="test-req-id",
        status="complete",
        locality=Locality(name="Venice", time_zone_id="Europe/Rome"),
        travel_mode="WALK",
        window=TimeWindow(
            start=dt.datetime(2026, 8, 15, 9, 0, tzinfo=tz),
            end=dt.datetime(2026, 8, 15, 18, 0, tzinfo=tz),
            local_start="09:00",
            local_end="18:00",
            date=dt.date(2026, 8, 15),
        ),
        origin=origin,
        stops=[stop],
        timeline=[],
        dropped_stops=[],
        comparison=ComparisonUnavailable(status="unavailable", reason_code="TEST"),
        maps_handoff=MapsHandoff(
            full_route_url="https://maps.google.com",
            full_route_universally_supported=True,
            browser_safe_parts=[],
        ),
        totals=Totals(visit_seconds=1800, travel_seconds=300, wait_seconds=0, elapsed_seconds=2100),
        diagnostics=[],
        share_proof=ShareProof(
            expires_at=dt.datetime(2026, 8, 15, 10, 0, tzinfo=dt.UTC),
            hmac="placeholder",
        ),
    )


@pytest.fixture()
def share_table():
    """Create a moto DynamoDB table for shares."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-shares",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield


@pytest.fixture()
def repo(share_table: Any) -> ShareRepository:
    """Create a ShareRepository pointing at the moto table."""
    return ShareRepository(
        table_name="test-shares",
        signing_secret="test-signing-secret",
        deletion_secret="test-deletion-secret",
    )


class TestProofVerification:
    """Proof HMAC must be verified using the signing secret."""

    def test_valid_proof_accepted(self, repo: ShareRepository) -> None:
        """A correctly signed proof is accepted."""
        itinerary = _make_itinerary()
        proof = repo.generate_proof(itinerary)
        result = repo.create(itinerary, proof)
        assert result.share_id
        assert result.share_url.startswith("https://vialo.place/r/")
        assert result.deletion_token  # first create returns a token

    def test_tampered_hmac_rejected(self, repo: ShareRepository) -> None:
        """A proof with a tampered HMAC is rejected."""
        itinerary = _make_itinerary()
        proof = repo.generate_proof(itinerary)
        tampered_proof = ShareProof(
            expires_at=proof.expires_at,
            hmac="tampered_hmac_value_that_does_not_match",
        )
        with pytest.raises(ValueError, match="Invalid or expired"):
            repo.create(itinerary, tampered_proof)

    def test_expired_proof_rejected(self, repo: ShareRepository) -> None:
        """An expired proof is rejected."""
        itinerary = _make_itinerary()
        # Generate proof but set expiry in the past
        past_expiry = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1)
        expired_proof = ShareProof(
            expires_at=past_expiry,
            hmac=repo._compute_itinerary_hmac(itinerary, past_expiry),
        )
        with pytest.raises(ValueError, match="Invalid or expired"):
            repo.create(itinerary, expired_proof)

    def test_proof_for_different_itinerary_rejected(self, repo: ShareRepository) -> None:
        """A proof generated for a different itinerary is rejected (replay attack)."""
        itinerary_a = _make_itinerary()
        itinerary_b = _make_itinerary()
        # Modify itinerary_b so its HMAC differs
        itinerary_b.request_id = "different-request-id"

        proof_for_a = repo.generate_proof(itinerary_a)
        # Try to use proof_for_a with itinerary_b
        with pytest.raises(ValueError, match="Invalid or expired"):
            repo.create(itinerary_b, proof_for_a)


class TestIdempotency:
    """Repeated create must not lose creator deletion capability."""

    def test_idempotent_create(self, repo: ShareRepository) -> None:
        """Creating the same share twice returns the same share_id."""
        itinerary = _make_itinerary()
        proof = repo.generate_proof(itinerary)

        result1 = repo.create(itinerary, proof)
        result2 = repo.create(itinerary, proof)

        assert result1.share_id == result2.share_id
        assert result1.share_url == result2.share_url
        # Second call cannot recover the deletion token (by design)
        assert result2.deletion_token == ""

    def test_idempotent_share_still_retrievable(self, repo: ShareRepository) -> None:
        """After idempotent create, the share is still retrievable."""
        itinerary = _make_itinerary()
        proof = repo.generate_proof(itinerary)

        result = repo.create(itinerary, proof)
        retrieved = repo.get(result.share_id)
        assert retrieved is not None
        assert retrieved.request_id == itinerary.request_id

    def test_first_creator_can_still_delete(self, repo: ShareRepository) -> None:
        """The deletion token from the first create still works after idempotent retry."""
        itinerary = _make_itinerary()
        proof = repo.generate_proof(itinerary)

        result1 = repo.create(itinerary, proof)
        _result2 = repo.create(itinerary, proof)  # idempotent

        # First creator's token still works
        assert repo.delete(result1.share_id, result1.deletion_token)


class TestDeletion:
    """Deletion token verification."""

    def test_wrong_token_rejected(self, repo: ShareRepository) -> None:
        """Wrong deletion token does not delete."""
        itinerary = _make_itinerary()
        proof = repo.generate_proof(itinerary)
        result = repo.create(itinerary, proof)

        assert not repo.delete(result.share_id, "wrong-token")
        # Share still exists
        assert repo.get(result.share_id) is not None

    def test_correct_token_deletes(self, repo: ShareRepository) -> None:
        """Correct deletion token deletes the share."""
        itinerary = _make_itinerary()
        proof = repo.generate_proof(itinerary)
        result = repo.create(itinerary, proof)

        assert repo.delete(result.share_id, result.deletion_token)
        assert repo.get(result.share_id) is None


class TestExpiry:
    """Application-level expiry checks."""

    def test_expired_share_returns_none(self, repo: ShareRepository) -> None:
        """Expired shares return None on get."""
        itinerary = _make_itinerary()
        proof = repo.generate_proof(itinerary)
        result = repo.create(itinerary, proof)

        # Manually expire the item
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.Table("test-shares")
        table.update_item(
            Key={"pk": f"SHARE#{result.share_id}"},
            UpdateExpression="SET expiresAt = :exp",
            ExpressionAttributeValues={":exp": int(time.time()) - 100},
        )

        assert repo.get(result.share_id) is None


class TestProductionProofRoundTrip:
    def test_attached_proof_survives_json_round_trip_and_verifies(
        self, repo: ShareRepository
    ) -> None:
        itinerary = _make_itinerary()
        itinerary.share_proof = None
        proof = repo.generate_proof(itinerary)
        itinerary.share_proof = proof

        deserialized = ItineraryResponse.model_validate_json(
            itinerary.model_dump_json(by_alias=True)
        )
        assert deserialized.share_proof is not None
        created = repo.create(deserialized, deserialized.share_proof)

        assert created.share_id
        assert repo.get(created.share_id) is not None

    def test_extending_proof_expiry_without_resigning_is_rejected(
        self, repo: ShareRepository
    ) -> None:
        itinerary = _make_itinerary()
        itinerary.share_proof = None
        proof = repo.generate_proof(itinerary)
        extended = ShareProof(
            expires_at=proof.expires_at + dt.timedelta(minutes=1),
            hmac=proof.hmac,
        )

        with pytest.raises(ValueError, match="Invalid or expired"):
            repo.create(itinerary, extended)

    def test_transaction_failure_leaves_no_claim_or_share(self, repo: ShareRepository) -> None:
        from botocore.exceptions import ClientError

        itinerary = _make_itinerary()
        itinerary.share_proof = None
        proof = repo.generate_proof(itinerary)
        transaction_error = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "failed"}},
            "TransactWriteItems",
        )

        with (
            patch.object(repo._client, "transact_write_items", side_effect=transaction_error),
            pytest.raises(ClientError),
        ):
            repo.create(itinerary, proof)

        table = boto3.resource("dynamodb", region_name="us-east-1").Table("test-shares")
        assert table.scan()["Items"] == []
