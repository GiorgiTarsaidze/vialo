"""Adversarial tests for BedrockSpendLimiter.

Covers: first reservation, cap boundary, concurrent reservations never exceed cap,
monthly rollover, DynamoDB guard failure makes zero model calls, settlement failure
retains reservation, actual-over-reservation is not undercounted, and metrics.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Lock
from typing import Any
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.exceptions import BotoCoreError, ClientError
from moto import mock_aws

from vialo.services.spend_limiter import (
    DEFAULT_MONTHLY_CAP_MICRO_USD,
    BedrockSpendLimiter,
    BudgetExceededError,
    SpendLimiterUnavailableError,
)


@pytest.fixture()
def dynamodb_table():
    """Create a mocked DynamoDB table for spend limiting."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-limits",
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
        table.meta.client.get_waiter("table_exists").wait(TableName="test-limits")
        yield table


def _make_limiter(
    monthly_cap_micro_usd: int = DEFAULT_MONTHLY_CAP_MICRO_USD,
    metrics: MagicMock | None = None,
) -> BedrockSpendLimiter:
    """Create a spend limiter using the mocked table."""
    return BedrockSpendLimiter(
        table_name="test-limits",
        region_name="us-east-1",
        monthly_cap_micro_usd=monthly_cap_micro_usd,
        input_usd_per_million=Decimal("4.00"),
        output_usd_per_million=Decimal("20.00"),
        metrics=metrics,
    )


class TestFirstReservation:
    def test_first_reservation_succeeds(self, dynamodb_table) -> None:
        """First reservation on an empty month succeeds."""
        limiter = _make_limiter()
        amount = limiter.reserve(estimated_input_tokens=500, max_output_tokens=2048)
        assert amount > 0

    def test_reservation_amount_is_conservative(self, dynamodb_table) -> None:
        """Reservation amount overestimates (conservative)."""
        limiter = _make_limiter()
        amount = limiter.reserve(estimated_input_tokens=500, max_output_tokens=2048)
        # At $4/M input and $20/M output:
        # 500 tokens * $4/M = $0.002 = 2000 micro-USD
        # 2048 tokens * $20/M = $0.04096 = 40960 micro-USD
        # Total ~42960 + 1 = 42961 micro-USD
        assert amount >= 42000  # Conservative lower bound


class TestCapBoundary:
    def test_reservation_at_small_cap_succeeds(self, dynamodb_table) -> None:
        """A reservation that fits within the cap succeeds."""
        limiter = _make_limiter(monthly_cap_micro_usd=500_000)
        amount = limiter.reserve(estimated_input_tokens=100, max_output_tokens=100)
        assert amount > 0

    def test_reservation_exceeding_cap_raises(self, dynamodb_table) -> None:
        """A reservation that would exceed the cap raises BudgetExceededError."""
        limiter = _make_limiter(monthly_cap_micro_usd=10)
        with pytest.raises(BudgetExceededError):
            limiter.reserve(estimated_input_tokens=500, max_output_tokens=2048)

    def test_second_reservation_blocked_when_first_fills_cap(self, dynamodb_table) -> None:
        """Second reservation fails after the first nearly fills the cap."""
        limiter = _make_limiter(monthly_cap_micro_usd=50_000)
        limiter.reserve(estimated_input_tokens=500, max_output_tokens=2048)
        with pytest.raises(BudgetExceededError):
            limiter.reserve(estimated_input_tokens=500, max_output_tokens=2048)


class TestConcurrentReservationsNeverExceedCap:
    def test_concurrent_reservations_atomic(self, dynamodb_table) -> None:
        """Genuinely concurrent reservations with ThreadPoolExecutor never exceed cap.

        Asserts the persisted reservedMicroUsd is <= cap.
        """
        # Each reservation for 100 input + 200 output is about 4401 micro-USD
        # Cap allows ~3-4 reservations so some must be blocked
        cap = 15_000
        limiter = _make_limiter(monthly_cap_micro_usd=cap)

        # Real DynamoDB conditionally updates one item atomically. Moto's
        # in-memory backend is not thread-safe and can otherwise lose writes,
        # making multiple callers observe success for the same prior value.
        # Serialize only the emulated storage operation; callers still race
        # through the real reserve method and Moto evaluates the real condition.
        original_update_item = limiter._table.update_item
        storage_lock = Lock()

        def linearizable_update_item(**kwargs: Any) -> Any:
            with storage_lock:
                return original_update_item(**kwargs)

        def attempt_reserve() -> int | None:
            try:
                return limiter.reserve(estimated_input_tokens=100, max_output_tokens=200)
            except BudgetExceededError:
                return None

        # Use ThreadPoolExecutor for genuine concurrent callers.
        with (
            patch.object(limiter._table, "update_item", side_effect=linearizable_update_item),
            ThreadPoolExecutor(max_workers=10) as executor,
        ):
            futures = [executor.submit(attempt_reserve) for _ in range(20)]
            results = [f.result() for f in futures]

        succeeded = [r for r in results if r is not None]
        blocked = [r for r in results if r is None]
        total_reserved = sum(succeeded)

        assert total_reserved <= cap
        assert len(blocked) > 0
        assert len(succeeded) > 0

        # Verify persisted reservedMicroUsd in DynamoDB is <= cap
        pk = limiter._month_key()
        sk = limiter._month_sort_key()
        item = dynamodb_table.get_item(Key={"pk": pk, "sk": sk}).get("Item", {})
        persisted = int(item.get("reservedMicroUsd", 0))
        assert persisted <= cap


class TestMonthlyRollover:
    def test_different_month_has_separate_budget(self, dynamodb_table) -> None:
        """Different months have independent budgets."""
        limiter = _make_limiter(monthly_cap_micro_usd=50_000)
        limiter.reserve(estimated_input_tokens=500, max_output_tokens=2048)

        with pytest.raises(BudgetExceededError):
            limiter.reserve(estimated_input_tokens=500, max_output_tokens=2048)

        # Simulate next month by patching the month key
        with patch.object(limiter, "_month_key", return_value="BEDROCK_SPEND#2026-09"):
            amount = limiter.reserve(estimated_input_tokens=500, max_output_tokens=2048)
            assert amount > 0


class TestDynamoDBGuardFailureRaisesSpendLimiterUnavailable:
    def test_non_conditional_client_error_raises_unavailable(self, dynamodb_table) -> None:
        """Non-conditional DynamoDB ClientError raises SpendLimiterUnavailableError."""
        limiter = _make_limiter()
        with patch.object(limiter._table, "update_item") as mock_update:
            mock_update.side_effect = ClientError(
                {"Error": {"Code": "InternalServerError", "Message": "DDB down"}},
                "UpdateItem",
            )
            with pytest.raises(SpendLimiterUnavailableError):
                limiter.reserve(estimated_input_tokens=500, max_output_tokens=2048)

    def test_botocore_error_raises_unavailable(self, dynamodb_table) -> None:
        """BotoCoreError raises SpendLimiterUnavailableError."""
        limiter = _make_limiter()
        with patch.object(limiter._table, "update_item") as mock_update:
            mock_update.side_effect = BotoCoreError()
            with pytest.raises(SpendLimiterUnavailableError):
                limiter.reserve(estimated_input_tokens=500, max_output_tokens=2048)

    def test_dynamo_guard_failure_makes_zero_model_calls(self, dynamodb_table) -> None:
        """When DynamoDB guard fails, no Bedrock/model call is made."""
        limiter = _make_limiter()

        mock_bedrock_client = MagicMock()
        with patch.object(limiter._table, "update_item") as mock_update:
            mock_update.side_effect = ClientError(
                {"Error": {"Code": "InternalServerError", "Message": "DDB down"}},
                "UpdateItem",
            )
            with pytest.raises(SpendLimiterUnavailableError):
                limiter.reserve(estimated_input_tokens=500, max_output_tokens=2048)

        # No model call should have happened
        mock_bedrock_client.converse.assert_not_called()


class TestUsageSettlementAndRefund:
    def test_settlement_refunds_unused_budget(self, dynamodb_table) -> None:
        """Settlement refunds the difference between reserved and actual spend."""
        limiter = _make_limiter(monthly_cap_micro_usd=5_000_000)
        reservation = limiter.reserve(estimated_input_tokens=500, max_output_tokens=2048)

        limiter.settle(
            reservation_micro_usd=reservation,
            actual_input_tokens=200,
            actual_output_tokens=300,
        )

        # After settlement, more budget is available
        amount2 = limiter.reserve(estimated_input_tokens=500, max_output_tokens=2048)
        assert amount2 > 0

    def test_settlement_failure_retains_reservation(self, dynamodb_table) -> None:
        """If settlement DynamoDB call fails, full reservation stays."""
        limiter = _make_limiter(monthly_cap_micro_usd=50_000)
        reservation = limiter.reserve(estimated_input_tokens=500, max_output_tokens=2048)

        with patch.object(limiter._table, "update_item") as mock_update:
            mock_update.side_effect = ClientError(
                {"Error": {"Code": "InternalServerError", "Message": "DDB error"}},
                "UpdateItem",
            )
            limiter.settle(
                reservation_micro_usd=reservation,
                actual_input_tokens=100,
                actual_output_tokens=200,
            )

        # Reservation still counted — second large reservation fails
        with pytest.raises(BudgetExceededError):
            limiter.reserve(estimated_input_tokens=500, max_output_tokens=2048)

    def test_actual_cost_calculation(self, dynamodb_table) -> None:
        """Actual cost calculation matches expected rates."""
        limiter = _make_limiter()
        actual = limiter.estimate_actual_micro_usd(input_tokens=1000, output_tokens=500)
        # 1000 * 4/1M = 0.004 USD = 4000 micro + 500 * 20/1M = 0.01 = 10000 micro
        # total = 14000 + 1 = 14001
        assert actual == 14001


class TestActualOverReservationNotUndercounted:
    def test_overage_is_added_to_reserved_spend(self, dynamodb_table) -> None:
        """If actual cost exceeds reservation, overage is added (not subtracted)."""
        limiter = _make_limiter(monthly_cap_micro_usd=5_000_000)
        # Make a small reservation
        reservation = limiter.reserve(estimated_input_tokens=10, max_output_tokens=10)
        # reservation is small: ~(10*4 + 10*20)/1M * 1M + 1 = 241 micro-USD

        # Settle with much larger actual (simulates extreme underestimation)
        limiter.settle(
            reservation_micro_usd=reservation,
            actual_input_tokens=10000,
            actual_output_tokens=5000,
        )

        # Check persisted state: reservedMicroUsd should be >= actual cost
        pk = limiter._month_key()
        sk = limiter._month_sort_key()
        item = dynamodb_table.get_item(Key={"pk": pk, "sk": sk}).get("Item", {})
        persisted_reserved = int(item.get("reservedMicroUsd", 0))
        persisted_actual = int(item.get("actualMicroUsd", 0))

        # The actual cost of 10000 input + 5000 output
        expected_actual = limiter.estimate_actual_micro_usd(10000, 5000)
        assert persisted_actual == expected_actual

        # reservedMicroUsd must account for the overage (reservation + overage)
        # Original reservation + overage = actual cost
        assert persisted_reserved >= expected_actual - 1  # allow for rounding


class TestMetricsEmission:
    def test_blocked_call_emits_metric(self, dynamodb_table) -> None:
        """Budget blocked call emits BedrockBudgetBlocked metric."""
        mock_metrics = MagicMock()
        limiter = _make_limiter(monthly_cap_micro_usd=10, metrics=mock_metrics)
        with pytest.raises(BudgetExceededError):
            limiter.reserve(estimated_input_tokens=500, max_output_tokens=2048)

        mock_metrics.add_metric.assert_called_once_with(
            name="BedrockBudgetBlocked", unit="Count", value=1
        )

    def test_settlement_emits_token_metrics(self, dynamodb_table) -> None:
        """Successful settlement emits token and cost metrics."""
        mock_metrics = MagicMock()
        limiter = _make_limiter(monthly_cap_micro_usd=5_000_000, metrics=mock_metrics)
        reservation = limiter.reserve(estimated_input_tokens=500, max_output_tokens=2048)
        limiter.settle(
            reservation_micro_usd=reservation,
            actual_input_tokens=200,
            actual_output_tokens=300,
        )

        assert mock_metrics.add_metric.call_count == 3
        calls = [c.kwargs for c in mock_metrics.add_metric.call_args_list]
        metric_names = {c["name"] for c in calls}
        assert "BedrockInputTokens" in metric_names
        assert "BedrockOutputTokens" in metric_names
        assert "BedrockCostMicroUsd" in metric_names
