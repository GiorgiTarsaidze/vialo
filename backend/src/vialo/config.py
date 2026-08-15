"""Environment configuration loading and validation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class Config:
    """Application configuration loaded from environment variables."""

    bedrock_model_id: str
    bedrock_region: str
    bedrock_monthly_budget_micro_usd: int
    bedrock_input_usd_per_million: Decimal
    bedrock_output_usd_per_million: Decimal
    google_server_key: str
    dynamodb_table_cache: str
    dynamodb_table_shares: str
    dynamodb_table_rate_limits: str
    rate_limit_hmac_secret: str
    share_signing_secret: str
    share_deletion_secret: str
    powertools_service_name: str
    log_level: str


def load_config() -> Config:
    """Load configuration from environment variables.

    All variables are required; raises ValueError if any are missing.
    Monetary values are parsed with Decimal for exactness; the budget cap
    is converted to integer micro-USD (1 USD = 1,000,000 micro-USD).

    Budget and rate values must be strictly positive (> 0).
    """

    def _get(name: str) -> str:
        val = os.environ.get(name)
        if not val:
            raise ValueError(f"Missing required environment variable: {name}")
        return val

    def _get_decimal(name: str) -> Decimal:
        raw = _get(name)
        try:
            return Decimal(raw)
        except InvalidOperation as e:
            raise ValueError(
                f"Environment variable {name} must be a valid decimal number, got: {raw!r}"
            ) from e

    def _get_positive_decimal(name: str) -> Decimal:
        val = _get_decimal(name)
        if not val.is_finite():
            raise ValueError(f"Environment variable {name} must be a finite number, got: {val}")
        if val <= Decimal("0"):
            raise ValueError(
                f"Environment variable {name} must be strictly positive (> 0), got: {val}"
            )
        return val

    # Parse budget as Decimal USD, convert to integer micro-USD
    budget_usd = _get_positive_decimal("BEDROCK_MONTHLY_BUDGET_USD")
    budget_micro_usd = int(budget_usd * Decimal("1000000"))

    input_rate = _get_positive_decimal("BEDROCK_INPUT_USD_PER_MILLION_TOKENS")
    output_rate = _get_positive_decimal("BEDROCK_OUTPUT_USD_PER_MILLION_TOKENS")

    return Config(
        bedrock_model_id=os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6"),
        bedrock_region=os.environ.get("BEDROCK_REGION", os.environ.get("AWS_REGION", "us-east-1")),
        bedrock_monthly_budget_micro_usd=budget_micro_usd,
        bedrock_input_usd_per_million=input_rate,
        bedrock_output_usd_per_million=output_rate,
        google_server_key=_get("GOOGLE_SERVER_KEY"),
        dynamodb_table_cache=_get("DYNAMODB_TABLE_CACHE"),
        dynamodb_table_shares=_get("DYNAMODB_TABLE_SHARES"),
        dynamodb_table_rate_limits=_get("DYNAMODB_TABLE_RATE_LIMITS"),
        rate_limit_hmac_secret=_get("RATE_LIMIT_HMAC_SECRET"),
        share_signing_secret=_get("SHARE_SIGNING_SECRET"),
        share_deletion_secret=_get("SHARE_DELETION_SECRET"),
        powertools_service_name=os.environ.get("POWERTOOLS_SERVICE_NAME", "vialo-api"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
