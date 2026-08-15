"""Tests for Pydantic models: strict validation, aliases, rejection."""

from __future__ import annotations

import datetime as dt
import json

import pytest
from pydantic import ValidationError

from vialo.models.diagnostics import Diagnostic, DiagnosticCode, DroppedStop
from vialo.models.providers import CandidateStop, Location, ParsedIntent, StopCategory
from vialo.models.requests import PlanItineraryRequest


class TestStrictValidation:
    """Test that extra fields are rejected and types are enforced."""

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            Location(latitude=1.0, longitude=2.0, extra_field="bad")  # type: ignore[call-arg]

    def test_wrong_type_rejected_in_python_mode(self) -> None:
        """Strict mode rejects string-to-float coercion in Python dict validation."""
        with pytest.raises(ValidationError):
            Location.model_validate({"latitude": "45.0", "longitude": "12.0"})

    def test_correct_types_accepted(self) -> None:
        loc = Location(latitude=45.0, longitude=12.0)
        assert loc.latitude == 45.0

    def test_out_of_range_candidate_priority(self) -> None:
        with pytest.raises(ValidationError):
            CandidateStop(
                candidate_index=0,
                name="Test",
                category=StopCategory.LANDMARK,
                priority=5,  # out of range
                visit_duration_minutes=30,
                duration_source="model_estimate",
            )

    def test_out_of_range_duration(self) -> None:
        with pytest.raises(ValidationError):
            CandidateStop(
                candidate_index=0,
                name="Test",
                category=StopCategory.LANDMARK,
                priority=1,
                visit_duration_minutes=300,  # > 240
                duration_source="model_estimate",
            )

    def test_prompt_too_short(self) -> None:
        with pytest.raises(ValidationError):
            PlanItineraryRequest(prompt="")

    def test_prompt_too_long(self) -> None:
        with pytest.raises(ValidationError):
            PlanItineraryRequest(prompt="x" * 501)

    def test_valid_prompt(self) -> None:
        req = PlanItineraryRequest(prompt="Walk Venice for 6 hours")
        assert req.prompt == "Walk Venice for 6 hours"


class TestCamelCaseAliases:
    """Test that camelCase aliases work for serialization."""

    def test_serialize_to_camel(self) -> None:
        loc = Location(latitude=45.4, longitude=12.3)
        data = loc.model_dump(by_alias=True)
        assert "latitude" in data
        assert "longitude" in data

    def test_candidate_stop_aliases(self) -> None:
        stop = CandidateStop(
            candidate_index=0,
            name="Test",
            category=StopCategory.LANDMARK,
            priority=1,
            visit_duration_minutes=30,
            duration_source="model_estimate",
        )
        data = stop.model_dump(by_alias=True)
        assert "candidateIndex" in data
        assert "visitDurationMinutes" in data
        assert "durationSource" in data

    def test_deserialize_from_camel_json(self) -> None:
        """Deserialization from JSON string (as arrives from API Gateway)."""
        data = {
            "candidateIndex": 0,
            "name": "Test",
            "category": "landmark",
            "priority": 1,
            "visitDurationMinutes": 30,
            "durationSource": "model_estimate",
        }
        # Use model_validate_json since data originates from JSON
        stop = CandidateStop.model_validate_json(json.dumps(data))
        assert stop.candidate_index == 0
        assert stop.visit_duration_minutes == 30
        assert stop.category == StopCategory.LANDMARK

    def test_plan_request_from_json(self) -> None:
        data = {"prompt": "Walk Venice 6 hours"}
        req = PlanItineraryRequest.model_validate_json(json.dumps(data))
        assert req.prompt == "Walk Venice 6 hours"


class TestDiagnostics:
    """Test diagnostic model creation."""

    def test_diagnostic_creation(self) -> None:
        d = Diagnostic(
            code=DiagnosticCode.PLACE_NOT_FOUND,
            message="Could not find this place",
            stop_name="Mystery Place",
            candidate_index=2,
        )
        assert d.code == DiagnosticCode.PLACE_NOT_FOUND
        assert d.stop_name == "Mystery Place"

    def test_dropped_stop_creation(self) -> None:
        ds = DroppedStop(
            candidate_index=3,
            name="Arsenale",
            reason_code=DiagnosticCode.CLOSED_ON_DATE,
            reason_detail="Arsenale closes at 17:00",
        )
        assert ds.candidate_index == 3
        data = ds.model_dump(by_alias=True)
        assert "reasonCode" in data


class TestParsedIntent:
    """Test ParsedIntent validation."""

    def test_valid_intent(self) -> None:
        intent = ParsedIntent(
            locality_query="Venice",
            origin_query="Hotel Danieli",
            requested_date=dt.date(2026, 8, 15),
            local_start_time=dt.time(9, 0),
            local_end_time=dt.time(19, 0),
            travel_mode="WALK",
            return_to_origin=True,
            candidates=[
                CandidateStop(
                    candidate_index=0,
                    name="San Marco",
                    category=StopCategory.HISTORIC_RELIGIOUS_SITE,
                    priority=1,
                    visit_duration_minutes=50,
                    duration_source="model_estimate",
                )
            ],
        )
        assert intent.locality_query == "Venice"
        assert len(intent.candidates) == 1

    def test_empty_candidates_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ParsedIntent(
                locality_query="Venice",
                origin_query="Hotel",
                local_start_time=dt.time(9, 0),
                local_end_time=dt.time(19, 0),
                travel_mode="WALK",
                return_to_origin=False,
                candidates=[],
            )

    def test_too_many_candidates_rejected(self) -> None:
        candidates = [
            CandidateStop(
                candidate_index=i,
                name=f"Stop {i}",
                category=StopCategory.LANDMARK,
                priority=1,
                visit_duration_minutes=30,
                duration_source="model_estimate",
            )
            for i in range(10)
        ]
        with pytest.raises(ValidationError):
            ParsedIntent(
                locality_query="Venice",
                origin_query="Hotel",
                local_start_time=dt.time(9, 0),
                local_end_time=dt.time(19, 0),
                travel_mode="WALK",
                return_to_origin=False,
                candidates=candidates,
            )

    def test_json_round_trip(self) -> None:
        """ParsedIntent round-trips through JSON correctly."""
        intent = ParsedIntent(
            locality_query="Venice",
            origin_query="Hotel Danieli",
            requested_date=dt.date(2026, 8, 15),
            local_start_time=dt.time(9, 0),
            local_end_time=dt.time(19, 0),
            travel_mode="WALK",
            return_to_origin=True,
            candidates=[
                CandidateStop(
                    candidate_index=0,
                    name="San Marco",
                    category=StopCategory.HISTORIC_RELIGIOUS_SITE,
                    priority=1,
                    visit_duration_minutes=50,
                    duration_source="model_estimate",
                )
            ],
        )
        json_str = intent.model_dump_json(by_alias=True)
        reconstructed = ParsedIntent.model_validate_json(json_str)
        assert reconstructed.locality_query == "Venice"
        assert reconstructed.candidates[0].category == StopCategory.HISTORIC_RELIGIOUS_SITE
