"""Integration tests for DynamoDB place cache."""

from __future__ import annotations

import datetime as dt
import time

import boto3
import pytest
from moto import mock_aws

from vialo.models.cache import CacheDateHours, CacheProfile
from vialo.models.providers import Location
from vialo.services.place_cache import PlaceCacheRepository


@pytest.fixture()
def cache_table():
    """Create a mocked DynamoDB table for place cache."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-place-cache",
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.meta.client.get_waiter("table_exists").wait(TableName="test-place-cache")
        yield table


class TestPlaceCache:
    def test_fresh_profile_hit(self, cache_table) -> None:
        """Fresh profile is returned."""
        with mock_aws():
            repo = PlaceCacheRepository("test-place-cache")
            profile = CacheProfile(
                place_id="test_place_1",
                display_name="Test Place",
                formatted_address="123 Test St",
                location=Location(latitude=45.0, longitude=12.0),
                primary_type="restaurant",
                time_zone_id="Europe/Rome",
                photos=[],
                fetched_at=dt.datetime.now(dt.UTC),
                expires_at=int(time.time()) + 3600,  # 1 hour from now
            )
            repo.put_profile(profile)
            result = repo.get_profile("test_place_1")
            assert result is not None
            assert result.display_name == "Test Place"

    def test_expired_profile_miss(self, cache_table) -> None:
        """Expired profile returns None."""
        with mock_aws():
            repo = PlaceCacheRepository("test-place-cache")
            profile = CacheProfile(
                place_id="test_place_2",
                display_name="Old Place",
                formatted_address="456 Old St",
                location=Location(latitude=45.0, longitude=12.0),
                time_zone_id="Europe/Rome",
                photos=[],
                fetched_at=dt.datetime.now(dt.UTC) - dt.timedelta(hours=25),
                expires_at=int(time.time()) - 100,  # Already expired
            )
            repo.put_profile(profile)
            result = repo.get_profile("test_place_2")
            assert result is None

    def test_date_hours_write_read(self, cache_table) -> None:
        """Date-specific hours can be written and read."""
        with mock_aws():
            repo = PlaceCacheRepository("test-place-cache")
            hours = CacheDateHours(
                place_id="test_place_3",
                date="2026-08-15",
                periods=[{"open": {"hour": 9, "minute": 30}, "close": {"hour": 17, "minute": 15}}],
                source="current",
                fetched_at=dt.datetime.now(dt.UTC),
                expires_at=int(time.time()) + 3600,
            )
            repo.put_date_hours(hours)
            result = repo.get_date_hours("test_place_3", "2026-08-15")
            assert result is not None
            assert result.source == "current"
            assert len(result.periods) == 1

    def test_missing_item_returns_none(self, cache_table) -> None:
        """Non-existent items return None."""
        with mock_aws():
            repo = PlaceCacheRepository("test-place-cache")
            assert repo.get_profile("nonexistent") is None
            assert repo.get_regular_hours("nonexistent") is None
            assert repo.get_date_hours("nonexistent", "2026-08-15") is None
