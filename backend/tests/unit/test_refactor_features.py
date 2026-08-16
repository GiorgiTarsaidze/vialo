"""Tests for the new backend refactor features."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from vialo.domain.hours_category_policy import requires_verified_hours
from vialo.models.diagnostics import DiagnosticCode
from vialo.models.itinerary import ItineraryResponse
from vialo.models.providers import (
    GroundedPlace,
    Location,
    StopCategory,
)
from vialo.models.requests import (
    AutocompleteRequest,
    AutocompleteResponse,
    AutocompleteSuggestion,
    PlaceLookupRequest,
    PlaceLookupResponse,
    PlaceReference,
    PlanItineraryRequest,
)
from vialo.pipeline.repair_candidates import (
    build_repair_context,
    parse_repair_decisions,
)


class TestPlanItineraryRequestBackwardCompat:
    """Req 1: Backward-compatible PlanItineraryRequest."""

    def test_prompt_only_still_works(self) -> None:
        """Existing requests with only prompt continue to work."""
        req = PlanItineraryRequest(prompt="Visit Venice 9am-5pm")
        assert req.prompt == "Visit Venice 9am-5pm"
        assert req.origin is None
        assert req.destination is None

    def test_with_structured_origin(self) -> None:
        """Origin place reference can be provided."""
        req = PlanItineraryRequest(
            prompt="Visit Venice",
            origin=PlaceReference(
                place_id="ChIJRcbZaklYwkcR8MrN5s_OP6Q",
                display_name="Piazzale Roma",
            ),
        )
        assert req.origin is not None
        assert req.origin.place_id == "ChIJRcbZaklYwkcR8MrN5s_OP6Q"

    def test_with_origin_and_destination(self) -> None:
        """Both origin and destination can be provided."""
        req = PlanItineraryRequest(
            prompt="Visit Venice",
            origin=PlaceReference(
                place_id="ChIJRcbZaklYwkcR8MrN5s_OP6Q",
                display_name="Piazzale Roma",
            ),
            destination=PlaceReference(
                place_id="ChIJ7_v7WNKxfkcR23whg6ggFd0",
                display_name="Venice Santa Lucia Station",
            ),
        )
        assert req.destination is not None
        assert req.destination.place_id == "ChIJ7_v7WNKxfkcR23whg6ggFd0"

    def test_same_start_end_supported(self) -> None:
        """Same place for origin and destination is valid (return-to-origin)."""
        ref = PlaceReference(
            place_id="ChIJRcbZaklYwkcR8MrN5s_OP6Q",
            display_name="Piazzale Roma",
        )
        req = PlanItineraryRequest(prompt="Visit Venice", origin=ref, destination=ref)
        assert req.origin == req.destination

    def test_destination_without_origin_rejected(self) -> None:
        """Destination requires origin to be set."""
        with pytest.raises(ValidationError):
            PlanItineraryRequest(
                prompt="Visit Venice",
                destination=PlaceReference(
                    place_id="ChIJ7_v7WNKxfkcR23whg6ggFd0",
                    display_name="Station",
                ),
            )

    def test_prompt_too_short_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PlanItineraryRequest(prompt="")

    def test_prompt_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PlanItineraryRequest(prompt="x" * 501)

    def test_camel_case_json_deserialization(self) -> None:
        """JSON with camelCase aliases works."""
        data = {
            "prompt": "Visit Venice",
            "origin": {
                "placeId": "ChIJRcbZaklYwkcR8MrN5s_OP6Q",
                "displayName": "Piazzale Roma",
            },
        }
        req = PlanItineraryRequest.model_validate(data)
        assert req.origin is not None
        assert req.origin.place_id == "ChIJRcbZaklYwkcR8MrN5s_OP6Q"


class TestAutocompleteRequest:
    """Req 2: Autocomplete request/response models."""

    def test_valid_query(self) -> None:
        req = AutocompleteRequest(query="San Marco Venice")
        assert req.query == "San Marco Venice"

    def test_query_too_short(self) -> None:
        with pytest.raises(ValidationError):
            AutocompleteRequest(query="ab")

    def test_query_too_long(self) -> None:
        with pytest.raises(ValidationError):
            AutocompleteRequest(query="x" * 201)

    def test_response_max_5_suggestions(self) -> None:
        suggestions = [
            AutocompleteSuggestion(
                place_id=f"place_{i}",
                display_name=f"Place {i}",
                formatted_address=f"Addr {i}",
            )
            for i in range(5)
        ]
        resp = AutocompleteResponse(predictions=suggestions)
        assert len(resp.predictions) == 5

    def test_response_rejects_more_than_5(self) -> None:
        suggestions = [
            AutocompleteSuggestion(
                place_id=f"place_{i}",
                display_name=f"Place {i}",
                formatted_address=f"Addr {i}",
            )
            for i in range(6)
        ]
        with pytest.raises(ValidationError):
            AutocompleteResponse(predictions=suggestions)


class TestPlaceLookupRequest:
    """Req 3: Place lookup request/response models."""

    def test_valid_lookup(self) -> None:
        req = PlaceLookupRequest(place_id="ChIJRcbZaklYwkcR8MrN5s_OP6Q")
        assert req.place_id == "ChIJRcbZaklYwkcR8MrN5s_OP6Q"

    def test_empty_place_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PlaceLookupRequest(place_id="")

    def test_response_model(self) -> None:
        resp = PlaceLookupResponse(
            place_id="ChIJRcbZaklYwkcR8MrN5s_OP6Q",
            display_name="Piazzale Roma",
            formatted_address="Piazzale Roma, 30135 Venice VE",
            location=Location(latitude=45.437, longitude=12.318),
            time_zone_id="Europe/Rome",
        )
        data = json.loads(resp.model_dump_json(by_alias=True))
        assert data["placeId"] == "ChIJRcbZaklYwkcR8MrN5s_OP6Q"
        assert data["timeZoneId"] == "Europe/Rome"


class TestHoursCategoryPolicy:
    """Req 6: every category requires provider-backed opening hours."""

    def test_all_categories_require_verified_hours(self) -> None:
        for category in StopCategory:
            assert requires_verified_hours(category) is True


class TestPlaceEvidence:
    """Req 7: Place rating and user_rating_count in models."""

    def test_grounded_place_has_rating(self) -> None:
        place = GroundedPlace(
            place_id="test",
            display_name="Test Place",
            formatted_address="Test Addr",
            location=Location(latitude=45.0, longitude=12.0),
            time_zone_id="Europe/Rome",
            rating=4.5,
            user_rating_count=1234,
        )
        assert place.rating == 4.5
        assert place.user_rating_count == 1234

    def test_grounded_place_rating_optional(self) -> None:
        place = GroundedPlace(
            place_id="test",
            display_name="Test Place",
            formatted_address="Test Addr",
            location=Location(latitude=45.0, longitude=12.0),
            time_zone_id="Europe/Rome",
        )
        assert place.rating is None
        assert place.user_rating_count is None

    def test_rating_in_json_response(self) -> None:
        place = GroundedPlace(
            place_id="test",
            display_name="Test",
            formatted_address="Addr",
            location=Location(latitude=45.0, longitude=12.0),
            time_zone_id="Europe/Rome",
            rating=4.2,
            user_rating_count=567,
        )
        data = json.loads(place.model_dump_json(by_alias=True))
        assert data["rating"] == 4.2
        assert data["userRatingCount"] == 567


class TestItineraryResponseDestination:
    """Req 4: Destination field in response model."""

    def test_destination_is_optional(self) -> None:
        """Existing responses without destination still valid."""
        schema = ItineraryResponse.model_json_schema(by_alias=True)
        required = schema.get("required", [])
        # destination is NOT required
        assert "destination" not in required

    def test_destination_in_schema(self) -> None:
        """Schema includes destination field."""
        schema = ItineraryResponse.model_json_schema(by_alias=True)
        props = schema.get("properties", {})
        assert "destination" in props


class TestRepairCandidatesParsing:
    """Req 5: Repair pipeline parsing."""

    def test_parse_valid_decisions(self) -> None:
        response = json.dumps(
            [
                {
                    "candidate_index": 0,
                    "action": "select_alternative",
                    "selected_place_id": "ChIJ123",
                },
                {
                    "candidate_index": 1,
                    "action": "replace_query",
                    "replacement_query": "Trattoria al Gatto Nero",
                },
                {"candidate_index": 2, "action": "skip"},
            ]
        )
        decisions = parse_repair_decisions(response)
        assert len(decisions) == 3
        assert decisions[0].action == "select_alternative"
        assert decisions[0].selected_place_id == "ChIJ123"
        assert decisions[1].action == "replace_query"
        assert decisions[1].replacement_query == "Trattoria al Gatto Nero"
        assert decisions[2].action == "skip"

    def test_parse_with_markdown_fences(self) -> None:
        response = '```json\n[{"candidate_index": 0, "action": "skip"}]\n```'
        decisions = parse_repair_decisions(response)
        assert len(decisions) == 1
        assert decisions[0].action == "skip"

    def test_parse_invalid_json_returns_empty(self) -> None:
        decisions = parse_repair_decisions("not json at all")
        assert decisions == []

    def test_parse_invalid_action_skipped(self) -> None:
        response = json.dumps([{"candidate_index": 0, "action": "invalid_action"}])
        decisions = parse_repair_decisions(response)
        assert decisions == []

    def test_build_repair_context_structure(self) -> None:
        from vialo.pipeline.ground_places import GroundingDiagnostic

        failed = [
            GroundingDiagnostic(
                candidate_index=2,
                name="Local Restaurant",
                code=DiagnosticCode.PLACE_NOT_FOUND,
                detail="Could not resolve",
            )
        ]
        alternatives = {
            2: [
                {
                    "place_id": "ChIJ_alt1",
                    "display_name": "Trattoria XYZ",
                    "formatted_address": "Venice",
                    "primary_type": "restaurant",
                }
            ]
        }
        from vialo.models.providers import CandidateStop

        candidates = [
            CandidateStop(
                candidate_index=2,
                name="Local Restaurant",
                category=StopCategory.FOOD_BREAK,
                priority=2,
                visit_duration_minutes=60,
                duration_source="model_estimate",
            )
        ]

        context_json = build_repair_context(
            failed=failed,
            candidates=candidates,
            accepted_names=["San Marco", "Rialto Bridge"],
            locality="Venice",
            alternatives_by_index=alternatives,
            original_prompt="Visit Venice restaurants",
        )
        context = json.loads(context_json)
        assert context["task"] == "repair_failed_candidates"
        assert context["locality"] == "Venice"
        assert len(context["failed_candidates"]) == 1
        assert context["failed_candidates"][0]["candidate_index"] == 2
        assert len(context["failed_candidates"][0]["google_alternatives"]) == 1


class TestNewDiagnosticCodes:
    """Verify new diagnostic codes exist."""

    def test_candidate_repaired_code(self) -> None:
        assert DiagnosticCode.CANDIDATE_REPAIRED == "CANDIDATE_REPAIRED"

    def test_candidate_repair_failed_code(self) -> None:
        assert DiagnosticCode.CANDIDATE_REPAIR_FAILED == "CANDIDATE_REPAIR_FAILED"

    def test_destination_not_found_code(self) -> None:
        assert DiagnosticCode.DESTINATION_NOT_FOUND == "DESTINATION_NOT_FOUND"
