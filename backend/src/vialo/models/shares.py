"""Share-related models."""

from __future__ import annotations

from vialo.models.base import ApiModel


class CreateShareResponse(ApiModel):
    """Response for POST /api/shares."""

    share_id: str
    share_url: str
    deletion_token: str
