"""Request models for API endpoints."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from vialo.models.base import ApiModel
from vialo.models.itinerary import ItineraryResponse, ShareProof


class PlanItineraryRequest(ApiModel):
    """Request body for POST /api/itineraries."""

    prompt: Annotated[str, Field(min_length=1, max_length=500)]


class CreateShareRequest(ApiModel):
    """Request body for POST /api/shares."""

    itinerary: ItineraryResponse
    proof: ShareProof
