"""Integration tests for DynamoDB rate limiter."""

from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from vialo.services.rate_limiter import RateLimiter


@pytest.fixture()
def dynamodb_table():
    """Create a mocked DynamoDB table for rate limiting."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-rate-limits",
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
        table.meta.client.get_waiter("table_exists").wait(TableName="test-rate-limits")
        yield table


@pytest.fixture()
def rate_limiter(dynamodb_table):
    """Create a RateLimiter with the mocked table."""
    with mock_aws():
        return RateLimiter(
            table_name="test-rate-limits",
            hmac_secret="test-secret-key",
            max_requests=5,
        )


class TestRateLimiter:
    def test_first_request_allowed(self, dynamodb_table) -> None:
        with mock_aws():
            limiter = RateLimiter("test-rate-limits", "test-secret", 5)
            allowed, retry_after = limiter.check_and_increment("192.168.1.1")
            assert allowed is True
            assert retry_after is None

    def test_five_requests_allowed(self, dynamodb_table) -> None:
        with mock_aws():
            limiter = RateLimiter("test-rate-limits", "test-secret", 5)
            for _i in range(5):
                allowed, _ = limiter.check_and_increment("10.0.0.1")
                assert allowed is True

    def test_sixth_request_rejected(self, dynamodb_table) -> None:
        with mock_aws():
            limiter = RateLimiter("test-rate-limits", "test-secret", 5)
            for _i in range(5):
                limiter.check_and_increment("10.0.0.2")
            allowed, retry_after = limiter.check_and_increment("10.0.0.2")
            assert allowed is False
            assert retry_after is not None
            assert retry_after > 0

    def test_different_ips_independent(self, dynamodb_table) -> None:
        with mock_aws():
            limiter = RateLimiter("test-rate-limits", "test-secret", 5)
            for _i in range(5):
                limiter.check_and_increment("10.0.0.3")
            # Different IP should still be allowed
            allowed, _ = limiter.check_and_increment("10.0.0.4")
            assert allowed is True

    def test_no_raw_ip_stored(self, dynamodb_table) -> None:
        """Verify that raw IP addresses are never stored in DynamoDB."""
        with mock_aws():
            limiter = RateLimiter("test-rate-limits", "test-secret", 5)
            test_ip = "192.168.100.200"
            limiter.check_and_increment(test_ip)

            # Scan the table and verify no raw IP
            dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
            table = dynamodb.Table("test-rate-limits")
            response = table.scan()
            items = response.get("Items", [])

            for item in items:
                # Check all string values in the item
                for key, value in item.items():
                    if isinstance(value, str):
                        assert test_ip not in value, f"Raw IP found in {key}"
