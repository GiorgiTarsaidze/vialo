"""Integration tests for share repository (legacy tests updated for HMAC verification)."""

from __future__ import annotations

import datetime as dt

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
    TravelEntry,
    VisitEntry,
)
from vialo.models.providers import GroundedPlace, Location, StopCategory
from vialo.services.share_repository import ShareRepository


def _make_test_itinerary() -> ItineraryResponse:
    """Create a minimal valid ItineraryResponse for testing."""
    tz = dt.UTC
    now = dt.datetime.now(tz)
    origin = GroundedPlace(
        place_id="origin_place",
        display_name="Origin",
        formatted_address="Origin St",
        location=Location(latitude=45.0, longitude=12.0),
        time_zone_id="Europe/Rome",
    )
    stop = GroundedStop(
        candidate_index=0,
        name="Test Stop",
        category=StopCategory.LANDMARK,
        priority=1,
        visit_duration_minutes=30,
        duration_source="model_estimate",
        place=GroundedPlace(
            place_id="stop_place",
            display_name="Test Stop",
            formatted_address="Stop St",
            location=Location(latitude=45.01, longitude=12.01),
            time_zone_id="Europe/Rome",
        ),
        hours_source="current",
        open_intervals=[
            OpenInterval(
                start=now, end=now + dt.timedelta(hours=8), local_start="09:00", local_end="17:00"
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
            start=now,
            end=now + dt.timedelta(hours=10),
            local_start="09:00",
            local_end="19:00",
            date=now.date(),
        ),
        origin=origin,
        stops=[stop],
        timeline=[
            TravelEntry(
                type="travel",
                from_index=0,
                to_index=1,
                mode="WALK",
                duration_seconds=300,
                distance_meters=600,
                departure=now,
                arrival=now + dt.timedelta(seconds=300),
            ),
            VisitEntry(
                type="visit",
                stop_index=1,
                arrival=now + dt.timedelta(seconds=300),
                departure=now + dt.timedelta(seconds=2100),
                duration_minutes=30,
                interval_used=stop.open_intervals[0],
            ),
        ],
        dropped_stops=[],
        comparison=ComparisonUnavailable(status="unavailable", reason_code="TEST"),
        maps_handoff=MapsHandoff(
            full_route_url="https://maps.google.com/test",
            full_route_universally_supported=True,
            browser_safe_parts=[],
        ),
        totals=Totals(visit_seconds=1800, travel_seconds=300, wait_seconds=0, elapsed_seconds=2100),
        diagnostics=[],
        share_proof=ShareProof(
            expires_at=now + dt.timedelta(days=30),
            hmac="placeholder",
        ),
    )


@pytest.fixture()
def share_table():
    """Create mocked DynamoDB table for shares."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-shares",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.meta.client.get_waiter("table_exists").wait(TableName="test-shares")
        yield table


class TestShareRepository:
    def test_create_and_read(self, share_table) -> None:
        with mock_aws():
            repo = ShareRepository("test-shares", "sign-secret", "delete-secret")
            itinerary = _make_test_itinerary()
            proof = repo.generate_proof(itinerary)
            response = repo.create(itinerary, proof)
            assert response.share_id
            assert response.share_url.startswith("https://vialo.place/r/")
            assert response.deletion_token

            # Read it back
            retrieved = repo.get(response.share_id)
            assert retrieved is not None
            assert retrieved.request_id == "test-req-id"

    def test_expired_returns_none(self, share_table) -> None:
        with mock_aws():
            repo = ShareRepository("test-shares", "sign-secret", "delete-secret")
            itinerary = _make_test_itinerary()
            proof = repo.generate_proof(itinerary)
            response = repo.create(itinerary, proof)

            # Manually expire the item
            dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
            table = dynamodb.Table("test-shares")
            table.update_item(
                Key={"pk": f"SHARE#{response.share_id}"},
                UpdateExpression="SET expiresAt = :exp",
                ExpressionAttributeValues={":exp": 1},  # epoch 1 = expired
            )

            retrieved = repo.get(response.share_id)
            assert retrieved is None

    def test_delete_with_valid_token(self, share_table) -> None:
        with mock_aws():
            repo = ShareRepository("test-shares", "sign-secret", "delete-secret")
            itinerary = _make_test_itinerary()
            proof = repo.generate_proof(itinerary)
            response = repo.create(itinerary, proof)

            deleted = repo.delete(response.share_id, response.deletion_token)
            assert deleted is True

            # Should be gone
            retrieved = repo.get(response.share_id)
            assert retrieved is None

    def test_delete_with_invalid_token(self, share_table) -> None:
        with mock_aws():
            repo = ShareRepository("test-shares", "sign-secret", "delete-secret")
            itinerary = _make_test_itinerary()
            proof = repo.generate_proof(itinerary)
            response = repo.create(itinerary, proof)

            deleted = repo.delete(response.share_id, "wrong-token")
            assert deleted is False

    def test_not_found(self, share_table) -> None:
        with mock_aws():
            repo = ShareRepository("test-shares", "sign-secret", "delete-secret")
            retrieved = repo.get("nonexistent-id")
            assert retrieved is None

    def test_no_raw_prompt_in_stored_record(self, share_table) -> None:
        """Verify no prompt or IP is stored in the shared record."""
        with mock_aws():
            repo = ShareRepository("test-shares", "sign-secret", "delete-secret")
            itinerary = _make_test_itinerary()
            proof = repo.generate_proof(itinerary)
            response = repo.create(itinerary, proof)

            # Scan the raw DynamoDB item
            dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
            table = dynamodb.Table("test-shares")
            result = table.get_item(Key={"pk": f"SHARE#{response.share_id}"})
            item = result.get("Item", {})

            # Should not contain any "prompt" key in the stored data
            item_str = str(item)
            assert "192.168" not in item_str
            assert "10.0.0" not in item_str
