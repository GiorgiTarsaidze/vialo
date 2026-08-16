"""Contract tests: JSON Schema export and stability."""

from __future__ import annotations

import json
from pathlib import Path

from vialo.models.itinerary import ItineraryResponse


class TestJsonSchema:
    def test_schema_export_succeeds(self) -> None:
        """ItineraryResponse can export a valid JSON Schema."""
        schema = ItineraryResponse.model_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema
        assert schema.get("title") == "ItineraryResponse"

    def test_schema_has_required_fields(self) -> None:
        """Schema includes all critical response fields."""
        schema = ItineraryResponse.model_json_schema()
        props = schema.get("properties", {})
        required_fields = [
            "schemaVersion",
            "requestId",
            "status",
            "locality",
            "travelMode",
            "window",
            "origin",
            "stops",
            "timeline",
            "droppedStops",
            "comparison",
            "mapsHandoff",
            "totals",
            "diagnostics",
            "shareProof",
        ]
        for field in required_fields:
            assert field in props, f"Missing field: {field}"

    def test_schema_is_json_serializable(self) -> None:
        """Schema can be serialized to JSON string."""
        schema = ItineraryResponse.model_json_schema()
        json_str = json.dumps(schema, indent=2)
        assert len(json_str) > 100
        # Verify it can be parsed back
        parsed = json.loads(json_str)
        assert parsed == schema

    def test_schema_version_is_literal_1(self) -> None:
        """schemaVersion is a literal 1."""
        schema = ItineraryResponse.model_json_schema()
        # Check that schemaVersion has a const or enum constraint
        props = schema.get("properties", {})
        version_schema = props.get("schemaVersion", {})
        assert version_schema.get("const") == 1 or version_schema.get("default") == 1

    def test_committed_frontend_schema_matches_pydantic(self) -> None:
        """The frontend contract artifact must be regenerated whenever Pydantic changes."""
        schema_path = (
            Path(__file__).resolve().parents[3]
            / "frontend"
            / "src"
            / "lib"
            / "itinerary-response.schema.json"
        )
        committed = json.loads(schema_path.read_text())
        assert committed == ItineraryResponse.model_json_schema(by_alias=True)
