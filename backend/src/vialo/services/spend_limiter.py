"""Fail-closed, concurrency-safe Bedrock spend limiter using DynamoDB.

Uses the existing request-limits table with a separate monthly key prefix
(BEDROCK_SPEND#YYYY-MM) distinct from IP rate-limit records (LIMIT#...).

All monetary amounts are tracked in micro-USD (1 USD = 1,000,000 micro-USD)
to avoid floating-point arithmetic in DynamoDB atomic operations.
"""

from __future__ import annotations

import calendar
import datetime as dt
import logging
from decimal import Decimal

import boto3
from aws_lambda_powertools import Metrics
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

# Default pricing (conservative overestimates)
DEFAULT_INPUT_USD_PER_MILLION = Decimal("4.00")
DEFAULT_OUTPUT_USD_PER_MILLION = Decimal("20.00")
DEFAULT_MONTHLY_CAP_MICRO_USD = 5_000_000  # $5.00


class BudgetExceededError(Exception):
    """Raised when the monthly Bedrock spend budget would be exceeded."""

    pass


class SpendLimiterUnavailableError(Exception):
    """Raised when the spend limiter cannot verify budget state (DynamoDB unreachable).

    Callers must fail closed: no model call should proceed.
    """

    pass


class BedrockSpendLimiter:
    """Atomic DynamoDB-backed spend limiter for Bedrock inference calls.

    Guarantees:
    - No Bedrock call can happen if the reservation would exceed the monthly cap.
    - Failed/uncertain calls retain their full reservation (fail closed).
    - Settlement refunds only the unused portion after confirmed usage.
    - If actual cost exceeds reservation (should not happen with conservative bounds),
      the overage is added to reserved spend and a warning is logged.
    - Concurrent reservations never exceed the cap due to DynamoDB conditional updates.
    - DynamoDB errors on reserve raise SpendLimiterUnavailableError (fail closed).
    """

    def __init__(
        self,
        table_name: str,
        region_name: str = "us-east-1",
        monthly_cap_micro_usd: int = DEFAULT_MONTHLY_CAP_MICRO_USD,
        input_usd_per_million: Decimal = DEFAULT_INPUT_USD_PER_MILLION,
        output_usd_per_million: Decimal = DEFAULT_OUTPUT_USD_PER_MILLION,
        metrics: Metrics | None = None,
    ) -> None:
        self._table_name = table_name
        self._monthly_cap = monthly_cap_micro_usd
        self._input_rate = input_usd_per_million
        self._output_rate = output_usd_per_million
        self._metrics = metrics
        dynamodb = boto3.resource("dynamodb", region_name=region_name)
        self._table = dynamodb.Table(table_name)

    def _month_key(self, now: dt.datetime | None = None) -> str:
        """Generate the monthly partition key."""
        if now is None:
            now = dt.datetime.now(dt.UTC)
        return f"BEDROCK_SPEND#{now.strftime('%Y-%m')}"

    def _month_sort_key(self) -> str:
        """Sort key for the monthly spend record."""
        return "MONTHLY_TOTAL"

    def _month_expiry(self, now: dt.datetime | None = None) -> int:
        """TTL: end of the month plus 7 days buffer."""
        if now is None:
            now = dt.datetime.now(dt.UTC)
        _, last_day = calendar.monthrange(now.year, now.month)
        end_of_month = now.replace(day=last_day, hour=23, minute=59, second=59, microsecond=0)
        return int((end_of_month + dt.timedelta(days=7)).timestamp())

    def estimate_reservation_micro_usd(
        self, estimated_input_tokens: int, max_output_tokens: int
    ) -> int:
        """Calculate the conservative micro-USD reservation for a call.

        Uses estimated input tokens and the full max_output_tokens as the
        worst-case output cost.
        """
        input_cost = Decimal(estimated_input_tokens) * self._input_rate / Decimal("1000000")
        output_cost = Decimal(max_output_tokens) * self._output_rate / Decimal("1000000")
        # Convert to micro-USD (multiply by 1,000,000) and round up
        total_micro = int((input_cost + output_cost) * Decimal("1000000")) + 1
        return total_micro

    def estimate_actual_micro_usd(self, input_tokens: int, output_tokens: int) -> int:
        """Calculate actual micro-USD cost from real token counts."""
        input_cost = Decimal(input_tokens) * self._input_rate / Decimal("1000000")
        output_cost = Decimal(output_tokens) * self._output_rate / Decimal("1000000")
        total_micro = int((input_cost + output_cost) * Decimal("1000000")) + 1
        return total_micro

    def reserve(self, estimated_input_tokens: int, max_output_tokens: int) -> int:
        """Atomically reserve spend budget before a Bedrock call.

        Returns the reservation amount in micro-USD.
        Raises BudgetExceededError if the cap would be exceeded.
        Raises SpendLimiterUnavailableError on non-conditional DynamoDB errors
        (fail closed — no call should proceed).
        """
        reservation = self.estimate_reservation_micro_usd(estimated_input_tokens, max_output_tokens)

        pk = self._month_key()
        sk = self._month_sort_key()

        # Use a conditional update that checks remaining capacity.
        max_allowed = self._monthly_cap - reservation
        if max_allowed < 0:
            # Reservation alone exceeds cap — impossible to fit
            if self._metrics:
                self._metrics.add_metric(name="BedrockBudgetBlocked", unit="Count", value=1)
            raise BudgetExceededError(
                f"Monthly Bedrock budget cap ({self._monthly_cap} micro-USD) would be exceeded"
            )

        try:
            self._table.update_item(
                Key={"pk": pk, "sk": sk},
                UpdateExpression=(
                    "SET reservedMicroUsd = if_not_exists(reservedMicroUsd, :zero) + :amount, "
                    "expiresAt = :exp"
                ),
                ConditionExpression=(
                    "attribute_not_exists(reservedMicroUsd) OR reservedMicroUsd <= :max_allowed"
                ),
                ExpressionAttributeValues={
                    ":zero": 0,
                    ":amount": reservation,
                    ":max_allowed": max_allowed,
                    ":exp": self._month_expiry(),
                },
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                if self._metrics:
                    self._metrics.add_metric(name="BedrockBudgetBlocked", unit="Count", value=1)
                raise BudgetExceededError(
                    f"Monthly Bedrock budget cap ({self._monthly_cap} micro-USD) would be exceeded"
                ) from e
            # Any other DynamoDB error: fail closed
            raise SpendLimiterUnavailableError(
                f"DynamoDB error during budget reservation: {e}"
            ) from e
        except BotoCoreError as e:
            # Network/SDK error: fail closed — cannot verify budget state
            raise SpendLimiterUnavailableError(
                f"DynamoDB unavailable during budget reservation: {e}"
            ) from e

        return reservation

    def settle(
        self,
        reservation_micro_usd: int,
        actual_input_tokens: int,
        actual_output_tokens: int,
    ) -> None:
        """Settle a successful call: refund unused reservation, record actuals.

        If actual cost exceeds reservation (should not happen with conservative bounds),
        the overage is ADDED to reserved spend so it is never under-accounted, and a
        warning is logged.

        If settlement fails, the full reservation remains (fail closed).
        This is safe because it overestimates spend rather than underestimating.
        """
        actual_cost = self.estimate_actual_micro_usd(actual_input_tokens, actual_output_tokens)

        # If actual exceeds reservation, we must ADD the overage to not under-account
        if actual_cost > reservation_micro_usd:
            overage = actual_cost - reservation_micro_usd
            logger.warning(
                "Actual cost exceeds reservation; adding overage to reserved spend",
                extra={
                    "reservation_micro_usd": reservation_micro_usd,
                    "actual_cost_micro_usd": actual_cost,
                    "overage_micro_usd": overage,
                },
            )
            refund = 0
            # We need to ADD overage instead of subtracting a refund
            adjustment = overage
        else:
            refund = reservation_micro_usd - actual_cost
            adjustment = -refund  # negative means we decrease reservedMicroUsd

        pk = self._month_key()
        sk = self._month_sort_key()

        try:
            if adjustment >= 0:
                # Overage case: add to reserved (never under-account)
                self._table.update_item(
                    Key={"pk": pk, "sk": sk},
                    UpdateExpression=(
                        "SET reservedMicroUsd = reservedMicroUsd + :adj, "
                        "actualMicroUsd = if_not_exists(actualMicroUsd, :zero) + :actual, "
                        "callCount = if_not_exists(callCount, :zero) + :one, "
                        "totalInputTokens = if_not_exists(totalInputTokens, :zero) + :input_t, "
                        "totalOutputTokens = if_not_exists(totalOutputTokens, :zero) + :output_t"
                    ),
                    ExpressionAttributeValues={
                        ":adj": adjustment,
                        ":actual": actual_cost,
                        ":zero": 0,
                        ":one": 1,
                        ":input_t": actual_input_tokens,
                        ":output_t": actual_output_tokens,
                    },
                )
            else:
                # Normal case: refund unused reservation
                self._table.update_item(
                    Key={"pk": pk, "sk": sk},
                    UpdateExpression=(
                        "SET reservedMicroUsd = reservedMicroUsd - :refund, "
                        "actualMicroUsd = if_not_exists(actualMicroUsd, :zero) + :actual, "
                        "callCount = if_not_exists(callCount, :zero) + :one, "
                        "totalInputTokens = if_not_exists(totalInputTokens, :zero) + :input_t, "
                        "totalOutputTokens = if_not_exists(totalOutputTokens, :zero) + :output_t"
                    ),
                    ExpressionAttributeValues={
                        ":refund": refund,
                        ":actual": actual_cost,
                        ":zero": 0,
                        ":one": 1,
                        ":input_t": actual_input_tokens,
                        ":output_t": actual_output_tokens,
                    },
                )
        except (ClientError, BotoCoreError):
            # Settlement failure: reservation stays in place (fail closed).
            # This overestimates spend, which is safe.
            logger.warning(
                "Bedrock spend settlement failed; reservation retained",
                extra={"reservation_micro_usd": reservation_micro_usd},
            )

        # Emit metrics for successful settlement
        if self._metrics:
            self._metrics.add_metric(
                name="BedrockInputTokens", unit="Count", value=actual_input_tokens
            )
            self._metrics.add_metric(
                name="BedrockOutputTokens", unit="Count", value=actual_output_tokens
            )
            self._metrics.add_metric(name="BedrockCostMicroUsd", unit="Count", value=actual_cost)
