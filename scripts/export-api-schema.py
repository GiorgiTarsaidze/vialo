#!/usr/bin/env python3
"""Export the authoritative frontend itinerary contract from Pydantic."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from vialo.models.itinerary import ItineraryResponse  # noqa: E402

OUTPUT = ROOT / "frontend" / "src" / "lib" / "itinerary-response.schema.json"
OUTPUT.write_text(
    json.dumps(ItineraryResponse.model_json_schema(by_alias=True), indent=2, sort_keys=True)
    + "\n"
)
print(f"exported {OUTPUT.relative_to(ROOT)}")
