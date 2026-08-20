"""Vialo Journal models: posts, comments, authors, and media uploads.

The Journal is the second surface of Vialo: travellers publish what a day in a
city was actually like, optionally attaching the computed itinerary they walked.
Everything here is user-authored text, so every field is length-bounded, and the
frontend renders it through JSX escaping only — never as HTML.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from pydantic import Field

from vialo.models.base import ApiModel
from vialo.models.itinerary import ItineraryResponse

TITLE_MAX = 120
CITY_MAX = 80
BODY_MAX = 8000
BODY_MIN = 50
COMMENT_MAX = 500
EXCERPT_MAX = 240
DISPLAY_NAME_MAX = 40

CoverContentType = Literal["image/jpeg", "image/png", "image/webp"]


class BlogAuthor(ApiModel):
    """The public identity of a Journal author.

    Only an opaque Cognito subject and a display name are ever exposed. Email
    addresses stay inside the user pool and are never stored in the Journal table
    or returned by the API.
    """

    user_id: Annotated[str, Field(min_length=1, max_length=64)]
    display_name: Annotated[str, Field(min_length=1, max_length=DISPLAY_NAME_MAX)]


class BlogPostSummary(ApiModel):
    """A Journal entry as it appears in a listing."""

    post_id: Annotated[str, Field(min_length=1, max_length=40)]
    title: Annotated[str, Field(min_length=1, max_length=TITLE_MAX)]
    city: Annotated[str, Field(min_length=1, max_length=CITY_MAX)]
    city_key: Annotated[str, Field(min_length=1, max_length=CITY_MAX)]
    excerpt: Annotated[str, Field(max_length=EXCERPT_MAX)]
    cover_image_url: str | None = None
    author: BlogAuthor
    created_at: dt.datetime
    comment_count: int = Field(ge=0)
    has_route: bool = False
    stop_count: int = Field(default=0, ge=0)


class BlogPost(BlogPostSummary):
    """A full Journal entry, including its body and any attached itinerary."""

    body: Annotated[str, Field(min_length=1, max_length=BODY_MAX)]
    itinerary: ItineraryResponse | None = None


class BlogComment(ApiModel):
    """One flat comment on a Journal entry."""

    comment_id: Annotated[str, Field(min_length=1, max_length=40)]
    post_id: Annotated[str, Field(min_length=1, max_length=40)]
    author: BlogAuthor
    body: Annotated[str, Field(min_length=1, max_length=COMMENT_MAX)]
    created_at: dt.datetime


class CreatePostRequest(ApiModel):
    """Request body for POST /api/blog/posts."""

    title: Annotated[str, Field(min_length=3, max_length=TITLE_MAX)]
    city: Annotated[str, Field(min_length=2, max_length=CITY_MAX)]
    body: Annotated[str, Field(min_length=BODY_MIN, max_length=BODY_MAX)]
    cover_image_key: Annotated[str, Field(max_length=200)] | None = None
    itinerary: ItineraryResponse | None = None


class CreateCommentRequest(ApiModel):
    """Request body for POST /api/blog/posts/{postId}/comments."""

    body: Annotated[str, Field(min_length=1, max_length=COMMENT_MAX)]


class PostListResponse(ApiModel):
    """Response for GET /api/blog/posts."""

    posts: list[BlogPostSummary]
    next_cursor: str | None = None


class CommentListResponse(ApiModel):
    """Response for GET /api/blog/posts/{postId}/comments."""

    comments: list[BlogComment]


class CreatePostResponse(ApiModel):
    """Response for POST /api/blog/posts."""

    post: BlogPost


class UploadUrlRequest(ApiModel):
    """Request body for POST /api/blog/uploads."""

    content_type: CoverContentType


class UploadUrlResponse(ApiModel):
    """A short-lived presigned POST for exactly one cover image."""

    upload_url: str
    fields: dict[str, str]
    image_key: str
    max_bytes: int
    expires_in_seconds: int


class ViewerResponse(ApiModel):
    """Response for GET /api/blog/me."""

    author: BlogAuthor
    posts: list[BlogPostSummary]
    posts_remaining_today: int = Field(ge=0)
