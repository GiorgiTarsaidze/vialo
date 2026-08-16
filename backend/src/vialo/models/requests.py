"""Request models for API endpoints."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, model_validator

from vialo.models.base import ApiModel
from vialo.models.itinerary import ItineraryResponse, ShareProof
from vialo.models.providers import Location


class PlaceReference(ApiModel):
    """A structured reference to a Google Place for origin/destination override.

    Server canonicalizes via PlacesClient.get_place(placeId).
    formattedAddress is accepted for frontend convenience but ignored server-side.
    """

    place_id: Annotated[str, Field(min_length=1, max_length=300)]
    display_name: Annotated[str, Field(min_length=1, max_length=200)]
    formatted_address: Annotated[str, Field(max_length=500)] | None = None  # ignored server-side


class PlanItineraryRequest(ApiModel):
    """Request body for POST /api/itineraries.

    prompt is always required. Optional structured origin/destination place
    references override model-parsed origin/return behavior when provided.
    Same start/end is supported by setting destination equal to origin.
    """

    prompt: Annotated[str, Field(min_length=1, max_length=500)]
    origin: PlaceReference | None = None
    destination: PlaceReference | None = None

    @model_validator(mode="after")
    def _validate_refs(self) -> PlanItineraryRequest:
        """Destination requires origin to be set."""
        if self.destination is not None and self.origin is None:
            raise ValueError("destination requires origin to be set")
        return self


class AutocompleteRequest(ApiModel):
    """Request body for POST /api/places/autocomplete.

    Accepts 'query' (canonical) or 'input' (frontend compat).
    """

    query: Annotated[str, Field(min_length=3, max_length=200)]


class AutocompleteSuggestion(ApiModel):
    """A single autocomplete suggestion."""

    place_id: str
    display_name: str
    formatted_address: str
    location: Location | None = None


class AutocompleteResponse(ApiModel):
    """Response for POST /api/places/autocomplete.

    Uses 'predictions' key for frontend compatibility.
    """

    predictions: list[AutocompleteSuggestion] = Field(max_length=5)


class PlaceLookupRequest(ApiModel):
    """Request body for POST /api/places/lookup."""

    place_id: Annotated[str, Field(min_length=1, max_length=300)]


class PlaceLookupResponse(ApiModel):
    """Canonical place details returned from server-side lookup."""

    place_id: str
    display_name: str
    formatted_address: str
    location: Location
    time_zone_id: str | None = None


class CreateShareRequest(ApiModel):
    """Request body for POST /api/shares."""

    itinerary: ItineraryResponse
    proof: ShareProof
