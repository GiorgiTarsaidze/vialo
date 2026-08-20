"""Vialo Journal API: read anonymously, write with a verified Cognito identity."""

from __future__ import annotations

import json
from typing import Any

from aws_lambda_powertools.event_handler import Response, content_types
from pydantic import ValidationError

from vialo.config import load_blog_config
from vialo.handler import app, logger, metrics
from vialo.models.blog import (
    BlogAuthor,
    CommentListResponse,
    CreateCommentRequest,
    CreatePostRequest,
    CreatePostResponse,
    PostListResponse,
    UploadUrlRequest,
    UploadUrlResponse,
    ViewerResponse,
)
from vialo.services.auth import AuthenticatedUser, AuthError, bearer_token, verify_id_token
from vialo.services.blog_repository import (
    MAX_COVER_KEY_LENGTH,
    BlogRepository,
    BlogRepositoryError,
    QuotaExceededError,
)
from vialo.services.media_store import MAX_COVER_BYTES, MediaStore, MediaStoreError

MAX_BODY_BYTES = 64 * 1024


def _json(status_code: int, payload: dict[str, Any]) -> Response:  # type: ignore[type-arg]
    return Response(
        status_code=status_code,
        content_type=content_types.APPLICATION_JSON,
        body=json.dumps(payload),
    )


def _error(status_code: int, code: str, message: str) -> Response:  # type: ignore[type-arg]
    return _json(status_code, {"error": {"code": code, "message": message}})


def _model(status_code: int, model: Any) -> Response:  # type: ignore[type-arg]
    return Response(
        status_code=status_code,
        content_type=content_types.APPLICATION_JSON,
        body=model.model_dump_json(by_alias=True),
    )


def _repository() -> BlogRepository:
    config = load_blog_config()
    return BlogRepository(
        table_name=config.dynamodb_table_blog,
        media_base_url=config.media_base_url,
    )


def _require_user() -> AuthenticatedUser:
    """Verify the caller's Cognito ID token.

    Raises:
        AuthError: If the token is absent or invalid.
    """
    config = load_blog_config()
    headers = dict(app.current_event.headers or {})
    return verify_id_token(
        bearer_token(headers),
        region=config.cognito_region,
        user_pool_id=config.cognito_user_pool_id,
        client_id=config.cognito_client_id,
    )


def _author(user: AuthenticatedUser) -> BlogAuthor:
    return BlogAuthor(user_id=user.user_id, display_name=user.display_name)


def _raw_body() -> str:
    """Return the request body, refusing anything implausibly large."""
    body = app.current_event.body or "{}"
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        raise ValueError("Request body too large")
    return body


@app.get("/api/blog/posts")
def list_posts() -> Response:  # type: ignore[type-arg]
    """Newest stories, optionally filtered to one city."""
    metrics.add_metric(name="JournalListRequest", unit="Count", value=1)
    params = app.current_event.query_string_parameters or {}
    city = (params.get("city") or "").strip()
    cursor = params.get("cursor") or None

    try:
        repo = _repository()
        if city:
            posts, next_cursor = repo.list_by_city(city, cursor)
        else:
            posts, next_cursor = repo.list_feed(cursor)
    except BlogRepositoryError:
        return _error(503, "JOURNAL_UNAVAILABLE", "The Journal is temporarily unavailable")
    except ValueError:
        return _error(400, "INVALID_INPUT", "Invalid pagination cursor")

    return _model(200, PostListResponse(posts=posts, next_cursor=next_cursor))


@app.get("/api/blog/posts/<post_id>")
def get_post(post_id: str) -> Response:  # type: ignore[type-arg]
    """One story, including its attached itinerary when present."""
    metrics.add_metric(name="JournalPostRequest", unit="Count", value=1)
    try:
        post = _repository().get_post(post_id)
    except BlogRepositoryError:
        return _error(503, "JOURNAL_UNAVAILABLE", "The Journal is temporarily unavailable")
    if post is None:
        return _error(404, "POST_NOT_FOUND", "That story is no longer available")
    return _model(200, post)


@app.post("/api/blog/posts")
def create_post() -> Response:  # type: ignore[type-arg]
    """Publish a story. Requires a verified account."""
    metrics.add_metric(name="JournalPostCreateRequest", unit="Count", value=1)
    try:
        user = _require_user()
    except AuthError as exc:
        return _error(401, "UNAUTHENTICATED", exc.message)

    try:
        request = CreatePostRequest.model_validate_json(_raw_body())
    except (ValidationError, ValueError):
        return _error(
            400,
            "INVALID_INPUT",
            "A story needs a title, a city, and at least 50 characters of text",
        )

    cover_key = request.cover_image_key or None
    if cover_key and (
        len(cover_key) > MAX_COVER_KEY_LENGTH or not MediaStore.is_own_key(cover_key, user.user_id)
    ):
        return _error(400, "INVALID_INPUT", "That cover image is not available")

    try:
        repo = _repository()
        repo.consume_quota(user.user_id, kind="post")
        post = repo.create_post(
            author=_author(user),
            title=request.title,
            city=request.city,
            body=request.body,
            cover_image_key=cover_key,
            itinerary=request.itinerary,
        )
    except QuotaExceededError as exc:
        return _error(429, "QUOTA_EXCEEDED", exc.message)
    except BlogRepositoryError:
        return _error(503, "JOURNAL_UNAVAILABLE", "The Journal is temporarily unavailable")

    metrics.add_metric(name="JournalPostCreated", unit="Count", value=1)
    logger.info(
        "Journal story published",
        extra={"city_key": post.city_key, "has_route": post.has_route},
    )
    return _model(201, CreatePostResponse(post=post))


@app.delete("/api/blog/posts/<post_id>")
def delete_post(post_id: str) -> Response:  # type: ignore[type-arg]
    """Delete your own story."""
    try:
        user = _require_user()
    except AuthError as exc:
        return _error(401, "UNAUTHENTICATED", exc.message)

    try:
        deleted = _repository().delete_post(post_id, user.user_id)
    except BlogRepositoryError:
        return _error(503, "JOURNAL_UNAVAILABLE", "The Journal is temporarily unavailable")
    if not deleted:
        return _error(404, "POST_NOT_FOUND", "That story is not yours or no longer exists")
    metrics.add_metric(name="JournalPostDeleted", unit="Count", value=1)
    return Response(status_code=204, content_type=content_types.APPLICATION_JSON, body="")


@app.get("/api/blog/posts/<post_id>/comments")
def list_comments(post_id: str) -> Response:  # type: ignore[type-arg]
    """Comments for one story, newest first.

    The story is resolved first so that a thread cannot outlive the story it
    belongs to: `get_post` already excludes reported stories, so hiding a story
    hides its discussion with it.
    """
    try:
        repo = _repository()
        if repo.get_post(post_id) is None:
            return _error(404, "POST_NOT_FOUND", "That story is no longer available")
        comments = repo.list_comments(post_id)
    except BlogRepositoryError:
        return _error(503, "JOURNAL_UNAVAILABLE", "The Journal is temporarily unavailable")
    return _model(200, CommentListResponse(comments=comments))


@app.post("/api/blog/posts/<post_id>/comments")
def create_comment(post_id: str) -> Response:  # type: ignore[type-arg]
    """Comment on a story. Requires a verified account."""
    try:
        user = _require_user()
    except AuthError as exc:
        return _error(401, "UNAUTHENTICATED", exc.message)

    try:
        request = CreateCommentRequest.model_validate_json(_raw_body())
    except (ValidationError, ValueError):
        return _error(400, "INVALID_INPUT", "A comment needs 1 to 500 characters")

    try:
        repo = _repository()
        if repo.get_post(post_id) is None:
            return _error(404, "POST_NOT_FOUND", "That story is no longer available")
        repo.consume_quota(user.user_id, kind="comment")
        comment = repo.add_comment(post_id, _author(user), request.body)
    except QuotaExceededError as exc:
        return _error(429, "QUOTA_EXCEEDED", exc.message)
    except BlogRepositoryError:
        return _error(503, "JOURNAL_UNAVAILABLE", "The Journal is temporarily unavailable")

    metrics.add_metric(name="JournalCommentCreated", unit="Count", value=1)
    return _model(201, comment)


@app.delete("/api/blog/posts/<post_id>/comments/<comment_id>")
def delete_comment(post_id: str, comment_id: str) -> Response:  # type: ignore[type-arg]
    """Delete your own comment."""
    try:
        user = _require_user()
    except AuthError as exc:
        return _error(401, "UNAUTHENTICATED", exc.message)

    try:
        deleted = _repository().delete_comment(post_id, comment_id, user.user_id)
    except BlogRepositoryError:
        return _error(503, "JOURNAL_UNAVAILABLE", "The Journal is temporarily unavailable")
    if not deleted:
        return _error(404, "COMMENT_NOT_FOUND", "That comment is not yours or no longer exists")
    return Response(status_code=204, content_type=content_types.APPLICATION_JSON, body="")


@app.post("/api/blog/posts/<post_id>/report")
def report_post(post_id: str) -> Response:  # type: ignore[type-arg]
    """Report a story. Three reports hide it from every listing."""
    try:
        user = _require_user()
    except AuthError as exc:
        return _error(401, "UNAUTHENTICATED", exc.message)
    del user  # the reporter's identity is not stored

    try:
        reported = _repository().report_post(post_id)
    except BlogRepositoryError:
        return _error(503, "JOURNAL_UNAVAILABLE", "The Journal is temporarily unavailable")
    if not reported:
        return _error(404, "POST_NOT_FOUND", "That story is no longer available")
    metrics.add_metric(name="JournalPostReported", unit="Count", value=1)
    return _json(202, {"status": "received"})


@app.post("/api/blog/uploads")
def create_upload_url() -> Response:  # type: ignore[type-arg]
    """Issue a short-lived, size-capped upload target for one cover image."""
    try:
        user = _require_user()
    except AuthError as exc:
        return _error(401, "UNAUTHENTICATED", exc.message)

    try:
        request = UploadUrlRequest.model_validate_json(_raw_body())
    except (ValidationError, ValueError):
        return _error(400, "INVALID_INPUT", "Cover images must be JPEG, PNG, or WebP")

    config = load_blog_config()
    try:
        upload = MediaStore(
            bucket=config.media_bucket, region=config.cognito_region
        ).presign_cover_upload(user_id=user.user_id, content_type=request.content_type)
    except MediaStoreError as exc:
        return _error(503, "UPLOAD_UNAVAILABLE", str(exc))

    return _model(
        200,
        UploadUrlResponse(
            upload_url=upload.url,
            fields=upload.fields,
            image_key=upload.image_key,
            max_bytes=MAX_COVER_BYTES,
            expires_in_seconds=300,
        ),
    )


@app.get("/api/blog/me")
def get_viewer() -> Response:  # type: ignore[type-arg]
    """The signed-in author, their stories, and today's remaining allowance."""
    try:
        user = _require_user()
    except AuthError as exc:
        return _error(401, "UNAUTHENTICATED", exc.message)

    try:
        repo = _repository()
        posts, _cursor = repo.list_by_author(user.user_id)
        quota = repo.quota_state(user.user_id)
    except BlogRepositoryError:
        return _error(503, "JOURNAL_UNAVAILABLE", "The Journal is temporarily unavailable")

    return _model(
        200,
        ViewerResponse(
            author=_author(user),
            posts=posts,
            posts_remaining_today=quota.posts_remaining,
        ),
    )
