"""Shared test fixtures and helpers."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest

from vialo.models.itinerary import GroundedStop, OpenInterval
from vialo.models.providers import (
    GroundedPlace,
    Location,
    PhotoAttribution,
    PlacePhoto,
    StopCategory,
)

FIXTURES_DIR = Path(__file__).parent.parent.parent / "docs" / "api-samples"


def load_fixture(name: str) -> Any:
    """Load a JSON fixture from docs/api-samples/."""
    path = FIXTURES_DIR / name
    with open(path) as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def _set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set minimal environment variables for tests that might load config."""
    env_vars = {
        "BEDROCK_MODEL_ID": "us.anthropic.claude-sonnet-4-6",
        "BEDROCK_REGION": "us-east-1",
        "BEDROCK_MONTHLY_BUDGET_USD": "5.00",
        "BEDROCK_INPUT_USD_PER_MILLION_TOKENS": "4.00",
        "BEDROCK_OUTPUT_USD_PER_MILLION_TOKENS": "20.00",
        "GOOGLE_SERVER_KEY": "test-server-key",
        "DYNAMODB_TABLE_CACHE": "test-cache",
        "DYNAMODB_TABLE_SHARES": "test-shares",
        "DYNAMODB_TABLE_RATE_LIMITS": "test-limits",
        "RATE_LIMIT_HMAC_SECRET": "test-hmac-secret",
        "SHARE_SIGNING_SECRET": "test-signing-secret",
        "SHARE_DELETION_SECRET": "test-deletion-secret",
        "POWERTOOLS_SERVICE_NAME": "vialo-api-test",
        "LOG_LEVEL": "DEBUG",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SECURITY_TOKEN": "testing",
        "AWS_SESSION_TOKEN": "testing",
    }
    for k, v in env_vars.items():
        monkeypatch.setenv(k, v)


@pytest.fixture()
def places_san_marco_fixture() -> dict[str, Any]:
    """Load the canonical Places API response for San Marco."""
    if not (FIXTURES_DIR / "places-san-marco.json").exists():
        pytest.skip("Fixture file not found")
    result: dict[str, Any] = load_fixture("places-san-marco.json")
    return result


@pytest.fixture()
def routes_venice_walk_fixture() -> list[dict[str, Any]]:
    """Load the canonical Routes API matrix response."""
    if not (FIXTURES_DIR / "routes-venice-walk.json").exists():
        pytest.skip("Fixture file not found")
    result: list[dict[str, Any]] = load_fixture("routes-venice-walk.json")
    return result


@pytest.fixture()
def sample_location() -> Location:
    """A sample Venice location."""
    return Location(latitude=45.434560600000005, longitude=12.3397125)


@pytest.fixture()
def sample_grounded_place() -> GroundedPlace:
    """A sample grounded place (San Marco)."""
    return GroundedPlace(
        place_id="ChIJv2xSZNexfkcRBaKsgyfVEgo",
        display_name="Saint Mark's Basilica",
        formatted_address="P.za San Marco, 328, 30124 Venezia VE, Italy",
        location=Location(latitude=45.434560600000005, longitude=12.3397125),
        primary_type="church",
        time_zone_id="Europe/Rome",
        photos=[
            PlacePhoto(
                name="places/ChIJv2xSZNexfkcRBaKsgyfVEgo/photos/test",
                width_px=4800,
                height_px=3600,
                author_attributions=[
                    PhotoAttribution(
                        display_name="Test Author",
                        uri="https://example.com",
                        photo_uri=None,
                    )
                ],
            )
        ],
    )


@pytest.fixture()
def sample_grounded_stop(sample_grounded_place: GroundedPlace) -> GroundedStop:
    """A sample grounded stop."""
    tz = dt.timezone(dt.timedelta(hours=2))  # CEST
    return GroundedStop(
        candidate_index=0,
        name="Saint Mark's Basilica",
        category=StopCategory.HISTORIC_RELIGIOUS_SITE,
        priority=1,
        visit_duration_minutes=50,
        duration_source="model_estimate",
        place=sample_grounded_place,
        hours_source="current",
        open_intervals=[
            OpenInterval(
                start=dt.datetime(2026, 8, 15, 9, 30, tzinfo=tz),
                end=dt.datetime(2026, 8, 15, 17, 15, tzinfo=tz),
                local_start="09:30",
                local_end="17:15",
            )
        ],
    )


@pytest.fixture()
def venice_time_window() -> tuple[dt.datetime, dt.datetime]:
    """A sample 9:00-19:00 CEST time window."""
    tz = dt.timezone(dt.timedelta(hours=2))
    return (
        dt.datetime(2026, 8, 15, 9, 0, tzinfo=tz),
        dt.datetime(2026, 8, 15, 19, 0, tzinfo=tz),
    )
