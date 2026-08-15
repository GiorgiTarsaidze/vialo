"""Environment configuration loading and validation."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Application configuration loaded from environment variables."""

    anthropic_api_key: str
    anthropic_model_id: str
    google_places_key: str
    google_routes_key: str
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
    """

    def _get(name: str) -> str:
        val = os.environ.get(name)
        if not val:
            raise ValueError(f"Missing required environment variable: {name}")
        return val

    return Config(
        anthropic_api_key=_get("ANTHROPIC_API_KEY"),
        anthropic_model_id=_get("ANTHROPIC_MODEL_ID"),
        google_places_key=_get("GOOGLE_PLACES_KEY"),
        google_routes_key=_get("GOOGLE_ROUTES_KEY"),
        dynamodb_table_cache=_get("DYNAMODB_TABLE_CACHE"),
        dynamodb_table_shares=_get("DYNAMODB_TABLE_SHARES"),
        dynamodb_table_rate_limits=_get("DYNAMODB_TABLE_RATE_LIMITS"),
        rate_limit_hmac_secret=_get("RATE_LIMIT_HMAC_SECRET"),
        share_signing_secret=_get("SHARE_SIGNING_SECRET"),
        share_deletion_secret=_get("SHARE_DELETION_SECRET"),
        powertools_service_name=os.environ.get("POWERTOOLS_SERVICE_NAME", "vialo-api"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
