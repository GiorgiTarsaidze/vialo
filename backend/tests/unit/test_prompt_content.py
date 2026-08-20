"""Unit tests for Bedrock candidate selector prompt content and behavior.

Proves:
- System prompt contains required geographic coherence guidance
- System prompt contains time-budget-aware candidate count instructions
- System prompt distinguishes WALK vs DRIVE candidate character
- System prompt preserves solver authority over ordering
- System prompt does NOT claim route-level scenic guarantees
- Valid responses with fewer than 9 candidates pass validation
- Candidate count range 1-9 is validated by ParsedIntent schema
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from vialo.models.providers import ParsedIntent
from vialo.services.bedrock_selector import (
    SYSTEM_PROMPT,
    BedrockCandidateSelector,
)


class TestSystemPromptTimeBudgetGuidance:
    """The prompt must instruct the model to scale candidate count to time budget."""

    def test_prompt_mentions_time_budget(self) -> None:
        """Prompt explicitly references fitting candidates to the time budget."""
        assert "time budget" in SYSTEM_PROMPT.lower()

    def test_prompt_discourages_always_9(self) -> None:
        """Prompt tells model NOT to default to 9 candidates."""
        assert "NOT" in SYSTEM_PROMPT
        # Should say not to default to 9 or always fill to maximum
        assert "9" in SYSTEM_PROMPT
        lower = SYSTEM_PROMPT.lower()
        assert "never pad" in lower or "do not default to 9" in lower

    def test_prompt_provides_time_to_count_heuristics(self) -> None:
        """Prompt provides guidance on candidate count for different time windows."""
        lower = SYSTEM_PROMPT.lower()
        # Should mention short windows get fewer candidates
        assert "3-hour" in lower or "3 hour" in lower
        assert "8" in SYSTEM_PROMPT or "10 hour" in lower

    def test_prompt_mentions_transit_overhead(self) -> None:
        """Prompt mentions transit/walking time between stops in the calculation."""
        lower = SYSTEM_PROMPT.lower()
        assert "transit" in lower or "walking" in lower or "overhead" in lower

    def test_prompt_instructs_sum_of_durations_plus_transit(self) -> None:
        """Prompt instructs model to sum visit durations plus transit."""
        lower = SYSTEM_PROMPT.lower()
        assert "sum" in lower or "total" in lower
        assert "duration" in lower


class TestSystemPromptTravelModeCharacter:
    """The prompt must clearly distinguish WALK and DRIVE candidate requirements."""

    def test_prompt_defines_walk_as_pedestrian(self) -> None:
        """WALK is explicitly defined as pedestrian travel."""
        assert "PEDESTRIAN" in SYSTEM_PROMPT or "pedestrian" in SYSTEM_PROMPT

    def test_prompt_walk_requires_pedestrian_appropriate_candidates(self) -> None:
        """WALK candidates must be pedestrian-appropriate and foot-reachable."""
        lower = SYSTEM_PROMPT.lower()
        assert "pedestrian-appropriate" in lower or "reachable on foot" in lower

    def test_prompt_walk_mentions_walkable_radius(self) -> None:
        """WALK guidance mentions walkable distance constraints."""
        lower = SYSTEM_PROMPT.lower()
        assert "walkable" in lower or "km" in lower

    def test_prompt_drive_allows_wider_geographic_area(self) -> None:
        """DRIVE candidates may be geographically spread out."""
        lower = SYSTEM_PROMPT.lower()
        assert "wider" in lower or "spread" in lower

    def test_prompt_drive_mentions_vehicle_appropriate(self) -> None:
        """DRIVE candidates must be vehicle-appropriate."""
        lower = SYSTEM_PROMPT.lower()
        assert "vehicle" in lower or "driving" in lower

    def test_prompt_has_separate_walk_and_drive_sections(self) -> None:
        """Prompt has distinct WALK and DRIVE guidance blocks."""
        assert "WALK" in SYSTEM_PROMPT
        assert "DRIVE" in SYSTEM_PROMPT
        # Both appear in candidate character guidance
        walk_idx = SYSTEM_PROMPT.index("WALK means")
        drive_idx = SYSTEM_PROMPT.index("DRIVE means")
        assert walk_idx < drive_idx


class TestSystemPromptGeographicCoherence:
    """The prompt must require geographic coherence for candidate selection."""

    def test_prompt_mentions_geographic_coherence(self) -> None:
        """Geographic coherence is explicitly mentioned."""
        lower = SYSTEM_PROMPT.lower()
        assert "geographically coherent" in lower or "geographic" in lower

    def test_prompt_forward_corridor_for_distinct_endpoints(self) -> None:
        """When return_to_origin is FALSE, prefer forward corridor."""
        lower = SYSTEM_PROMPT.lower()
        assert "forward corridor" in lower
        assert "backtracking" in lower

    def test_prompt_compact_loop_for_return_to_origin(self) -> None:
        """When return_to_origin is TRUE, prefer compact loop."""
        lower = SYSTEM_PROMPT.lower()
        assert "compact loop" in lower

    def test_prompt_varied_neighborhoods(self) -> None:
        """For return-to-origin, suggest varied neighborhoods."""
        lower = SYSTEM_PROMPT.lower()
        assert "varied" in lower
        assert "neighborhood" in lower

    def test_prompt_no_route_level_scenic_guarantees(self) -> None:
        """Prompt never claims route-level scenic guarantees."""
        lower = SYSTEM_PROMPT.lower()
        # Must say it does NOT claim/guarantee scenic quality or route geometry
        assert "do not claim" in lower or "never claim" in lower
        assert "scenery" in lower or "scenic" in lower or "route-level" in lower

    def test_prompt_geographic_clustering_good(self) -> None:
        """Prompt mentions that geographic clustering reduces transit waste."""
        lower = SYSTEM_PROMPT.lower()
        assert "clustering" in lower or "cluster" in lower


class TestSystemPromptSolverAuthority:
    """The prompt must preserve that the deterministic solver, not AI, chooses order."""

    def test_prompt_states_solver_chooses_order(self) -> None:
        """Prompt explicitly states a solver determines the final order."""
        lower = SYSTEM_PROMPT.lower()
        assert "solver" in lower
        assert "order" in lower

    def test_prompt_tells_model_not_to_choose_order(self) -> None:
        """Prompt tells the model NOT to choose the visit order."""
        # Should have an explicit instruction like "Do NOT choose the order"
        assert "NOT choose the order" in SYSTEM_PROMPT or "not you" in SYSTEM_PROMPT.lower()

    def test_prompt_mentions_deterministic(self) -> None:
        """Prompt mentions the solver is deterministic."""
        lower = SYSTEM_PROMPT.lower()
        assert "deterministic" in lower

    def test_prompt_mentions_real_travel_time_data(self) -> None:
        """Prompt mentions the solver uses real travel-time data."""
        lower = SYSTEM_PROMPT.lower()
        assert "travel-time" in lower or "travel time" in lower


class TestSystemPromptCategoryBoundsPresent:
    """The prompt must still contain all category bounds."""

    @pytest.mark.parametrize(
        "category",
        [
            "quick_viewpoint",
            "landmark",
            "museum_gallery",
            "historic_religious_site",
            "neighborhood_market_park",
            "food_break",
            "experience_tour",
            "other",
        ],
    )
    def test_category_present_in_prompt(self, category: str) -> None:
        """Each category appears in the system prompt."""
        assert category in SYSTEM_PROMPT

    def test_category_bounds_values_present(self) -> None:
        """Specific bounds values are present."""
        assert "15/20/30" in SYSTEM_PROMPT
        assert "30/45/75" in SYSTEM_PROMPT
        assert "60/90/180" in SYSTEM_PROMPT
        assert "60/120/240" in SYSTEM_PROMPT


class TestSystemPromptDurationEvidenceRules:
    """Duration evidence rules are preserved."""

    def test_user_duration_source_rules(self) -> None:
        """user duration_source rules are in the prompt."""
        assert "duration_source" in SYSTEM_PROMPT
        assert '"user"' in SYSTEM_PROMPT
        assert "duration_evidence" in SYSTEM_PROMPT

    def test_model_estimate_rules(self) -> None:
        """model_estimate rules with null evidence are in the prompt."""
        assert '"model_estimate"' in SYSTEM_PROMPT
        assert "null" in SYSTEM_PROMPT


class TestSystemPromptNoCandidateCountHardcode:
    """The prompt must NOT hardcode '1-9 candidates' as a fixed instruction."""

    def test_no_fixed_1_9_candidates_instruction(self) -> None:
        """The old '1-9 candidates' phrase is replaced with budget-aware logic."""
        # The old prompt said "and 1-9 candidates" — this should not appear as a
        # simple instruction without context
        assert "and 1-9 candidates" not in SYSTEM_PROMPT


class TestParsedIntentAcceptsFewCandidates:
    """ParsedIntent validation must accept 1-9 candidates, including low counts."""

    @pytest.mark.parametrize("count", [1, 2, 3, 4, 5, 6, 7, 8, 9])
    def test_valid_candidate_count(self, count: int) -> None:
        """ParsedIntent accepts any count from 1 to 9."""
        candidates = [
            {
                "candidate_index": i,
                "name": f"Place {i}",
                "category": "landmark",
                "priority": 1,
                "visit_duration_minutes": 45,
                "duration_source": "model_estimate",
            }
            for i in range(count)
        ]
        data = {
            "locality_query": "Venice",
            "origin_query": "Hotel Danieli",
            "requested_date": "2026-08-15",
            "local_start_time": "09:00",
            "local_end_time": "12:00",
            "travel_mode": "WALK",
            "return_to_origin": True,
            "candidates": candidates,
        }
        intent = ParsedIntent.model_validate_json(json.dumps(data))
        assert len(intent.candidates) == count

    def test_zero_candidates_rejected(self) -> None:
        """ParsedIntent rejects zero candidates."""
        data = {
            "locality_query": "Venice",
            "origin_query": "Hotel Danieli",
            "requested_date": "2026-08-15",
            "local_start_time": "09:00",
            "local_end_time": "12:00",
            "travel_mode": "WALK",
            "return_to_origin": True,
            "candidates": [],
        }
        with pytest.raises(ValidationError):
            ParsedIntent.model_validate_json(json.dumps(data))

    def test_ten_candidates_rejected(self) -> None:
        """ParsedIntent rejects more than 9 candidates."""
        candidates = [
            {
                "candidate_index": i,
                "name": f"Place {i}",
                "category": "landmark",
                "priority": 1,
                "visit_duration_minutes": 45,
                "duration_source": "model_estimate",
            }
            for i in range(10)
        ]
        data = {
            "locality_query": "Venice",
            "origin_query": "Hotel Danieli",
            "requested_date": "2026-08-15",
            "local_start_time": "09:00",
            "local_end_time": "19:00",
            "travel_mode": "WALK",
            "return_to_origin": True,
            "candidates": candidates,
        }
        with pytest.raises(ValidationError):
            ParsedIntent.model_validate_json(json.dumps(data))


class TestBedrockSelectorValidatesFewerCandidates:
    """BedrockCandidateSelector correctly validates responses with <9 candidates."""

    def _make_response(self, text: str, input_tokens: int = 100, output_tokens: int = 200):
        return {
            "output": {"message": {"role": "assistant", "content": [{"text": text}]}},
            "usage": {"inputTokens": input_tokens, "outputTokens": output_tokens},
            "stopReason": "end_turn",
        }

    def _make_selector(self, mock_bedrock: MagicMock) -> BedrockCandidateSelector:
        mock_limiter = MagicMock()
        mock_limiter.reserve.return_value = 50000
        with patch("vialo.services.bedrock_selector.boto3.client") as mock_client:
            mock_client.return_value = mock_bedrock
            selector = BedrockCandidateSelector(
                spend_limiter=mock_limiter,
                model_id="us.anthropic.claude-sonnet-4-6",
                region_name="us-east-1",
            )
        return selector

    def test_two_candidate_response_valid(self) -> None:
        """A response with only 2 candidates is accepted for a short time window."""
        response_json = json.dumps(
            {
                "locality_query": "Paris",
                "origin_query": "Eiffel Tower",
                "requested_date": "2026-06-10",
                "local_start_time": "14:00",
                "local_end_time": "16:30",
                "travel_mode": "WALK",
                "return_to_origin": True,
                "candidates": [
                    {
                        "candidate_index": 0,
                        "name": "Musée du Quai Branly",
                        "category": "museum_gallery",
                        "priority": 1,
                        "visit_duration_minutes": 60,
                        "duration_source": "model_estimate",
                    },
                    {
                        "candidate_index": 1,
                        "name": "Champ de Mars",
                        "category": "neighborhood_market_park",
                        "priority": 2,
                        "visit_duration_minutes": 30,
                        "duration_source": "model_estimate",
                    },
                ],
            }
        )
        mock_bedrock = MagicMock()
        mock_bedrock.converse.return_value = self._make_response(response_json)
        selector = self._make_selector(mock_bedrock)
        intent = selector.select("Walk around Paris for 2.5 hours from the Eiffel Tower")
        assert len(intent.candidates) == 2

    def test_five_candidate_response_valid(self) -> None:
        """A response with 5 candidates is accepted for a medium time window."""
        candidates = [
            {
                "candidate_index": i,
                "name": f"Stop {i}",
                "category": "landmark",
                "priority": min(i + 1, 3),
                "visit_duration_minutes": 45,
                "duration_source": "model_estimate",
            }
            for i in range(5)
        ]
        response_json = json.dumps(
            {
                "locality_query": "Rome",
                "origin_query": "Colosseum",
                "requested_date": None,
                "local_start_time": "09:00",
                "local_end_time": "14:00",
                "travel_mode": "WALK",
                "return_to_origin": False,
                "candidates": candidates,
            }
        )
        mock_bedrock = MagicMock()
        mock_bedrock.converse.return_value = self._make_response(response_json)
        selector = self._make_selector(mock_bedrock)
        intent = selector.select("Walk Rome 5 hours from Colosseum to Piazza Navona")
        assert len(intent.candidates) == 5

    def test_drive_mode_response_valid(self) -> None:
        """A DRIVE mode response is accepted."""
        response_json = json.dumps(
            {
                "locality_query": "Amalfi Coast",
                "origin_query": "Naples",
                "requested_date": "2026-07-01",
                "local_start_time": "08:00",
                "local_end_time": "18:00",
                "travel_mode": "DRIVE",
                "return_to_origin": True,
                "candidates": [
                    {
                        "candidate_index": 0,
                        "name": "Positano",
                        "category": "neighborhood_market_park",
                        "priority": 1,
                        "visit_duration_minutes": 90,
                        "duration_source": "model_estimate",
                    },
                    {
                        "candidate_index": 1,
                        "name": "Ravello",
                        "category": "quick_viewpoint",
                        "priority": 2,
                        "visit_duration_minutes": 30,
                        "duration_source": "model_estimate",
                    },
                    {
                        "candidate_index": 2,
                        "name": "Amalfi Cathedral",
                        "category": "historic_religious_site",
                        "priority": 1,
                        "visit_duration_minutes": 45,
                        "duration_source": "model_estimate",
                    },
                ],
            }
        )
        mock_bedrock = MagicMock()
        mock_bedrock.converse.return_value = self._make_response(response_json)
        selector = self._make_selector(mock_bedrock)
        intent = selector.select("Drive the Amalfi Coast from Naples, full day")
        assert intent.travel_mode == "DRIVE"
        assert len(intent.candidates) == 3


class TestPromptStructureIntegrity:
    """Verify the prompt structure is well-formed and complete."""

    def test_prompt_starts_with_extraction_instruction(self) -> None:
        """Prompt begins with clear extraction instruction."""
        assert SYSTEM_PROMPT.startswith("Extract a typed one-day city itinerary request")

    def test_prompt_ends_with_no_prose_instruction(self) -> None:
        """Prompt ends with the no-prose instruction."""
        assert SYSTEM_PROMPT.strip().endswith("Do not emit prose or markdown.")

    def test_prompt_contains_candidate_index_instruction(self) -> None:
        """Prompt still requires candidate_index key."""
        assert "candidate_index" in SYSTEM_PROMPT
        assert "not index" in SYSTEM_PROMPT

    def test_prompt_mentions_json_only(self) -> None:
        """Prompt requires JSON only output."""
        assert "JSON only" in SYSTEM_PROMPT

    def test_prompt_specifies_return_to_origin_field(self) -> None:
        """return_to_origin field is mentioned."""
        assert "return_to_origin" in SYSTEM_PROMPT

    def test_prompt_specifies_travel_mode_values(self) -> None:
        """WALK and DRIVE are the travel_mode values."""
        assert "WALK or DRIVE" in SYSTEM_PROMPT
