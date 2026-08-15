"""DynamoDB-backed rate limiter using HMAC-keyed IP buckets."""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac as hmac_module
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class RateLimiter:
    """Per-IP rate limiter using DynamoDB atomic counters.

    Never stores raw IP addresses. Uses HMAC(secret, ip) as the partition key.
    """

    def __init__(
        self,
        table_name: str,
        hmac_secret: str,
        max_requests: int = 5,
        region_name: str = "us-east-1",
    ) -> None:
        self._table_name = table_name
        self._hmac_secret = hmac_secret.encode()
        self._max_requests = max_requests
        dynamodb = boto3.resource("dynamodb", region_name=region_name)
        self._table = dynamodb.Table(table_name)

    def _hash_ip(self, ip: str) -> str:
        """Create HMAC digest of IP. Never stores the raw IP."""
        return hmac_module.new(self._hmac_secret, ip.encode(), hashlib.sha256).hexdigest()[:32]

    def _current_bucket(self) -> str:
        """Get the current hour bucket key."""
        now = dt.datetime.now(dt.UTC)
        return now.strftime("%Y%m%d%H")

    def _bucket_expiry(self) -> int:
        """Get epoch seconds for bucket expiry (end of hour + 1 hour buffer)."""
        now = dt.datetime.now(dt.UTC)
        # End of current hour
        end_of_hour = now.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
        # Add 1 hour buffer for TTL
        return int((end_of_hour + dt.timedelta(hours=1)).timestamp())

    def check_and_increment(self, client_ip: str) -> tuple[bool, int | None]:
        """Check rate limit and increment counter atomically.

        Returns:
            Tuple of (allowed: bool, retry_after_epoch: int | None).
            If not allowed, retry_after_epoch is when the bucket resets.
        """
        ip_hash = self._hash_ip(client_ip)
        bucket = self._current_bucket()
        pk = f"LIMIT#{ip_hash}"
        sk = f"HOUR#{bucket}"

        try:
            # Attempt conditional update: increment if count < max
            self._table.update_item(
                Key={"pk": pk, "sk": sk},
                UpdateExpression="SET #count = if_not_exists(#count, :zero) + :one, #exp = :exp",
                ConditionExpression="attribute_not_exists(#count) OR #count < :max",
                ExpressionAttributeNames={
                    "#count": "count",
                    "#exp": "expiresAt",
                },
                ExpressionAttributeValues={
                    ":zero": 0,
                    ":one": 1,
                    ":max": self._max_requests,
                    ":exp": self._bucket_expiry(),
                },
                ReturnValues="ALL_NEW",
            )
            return (True, None)

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Rate limit exceeded
                now = dt.datetime.now(dt.UTC)
                retry_after = now.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
                return (False, int(retry_after.timestamp()))
            raise
