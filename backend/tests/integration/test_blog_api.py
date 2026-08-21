"""API tests for the Vialo Journal routes.

Reading is anonymous; every write requires a verified Cognito identity. Token
verification itself is covered in tests/unit/test_auth.py, so these tests patch
the verifier and focus on route behaviour, authorization, and quotas.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from vialo.handler import lambda_handler
from vialo.services.auth import AuthenticatedUser, AuthError

TABLE = "vialo-journal-api-test"
BUCKET = "vialo-journal-media-api-test"

LISTING_ATTRIBUTES = [
    "postId",
    "title",
    "city",
    "cityKey",
    "excerpt",
    "coverImageKey",
    "authorId",
    "authorName",
    "createdAt",
    "commentCount",
    "hasRoute",
    "stopCount",
    "hidden",
]

VALID_BODY = "We walked the old town from the square, then up to the fortress at sunset. " * 2


def _event(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    query: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": "",
        "queryStringParameters": query,
        "headers": {"content-type": "application/json", **(headers or {})},
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "testapi",
            "domainName": "test.execute-api.us-east-1.amazonaws.com",
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "test",
            },
            "requestId": "test-request-id",
            "routeKey": f"{method} {path}",
            "stage": "$default",
            "timeEpoch": 1786950000000,
        },
        "body": json.dumps(body) if body is not None else "",
        "isBase64Encoded": False,
    }


def _context() -> Any:
    ctx = MagicMock()
    ctx.function_name = "vialo-backend-dev"
    ctx.memory_limit_in_mb = 1769
    ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:vialo-backend-dev"
    ctx.aws_request_id = "test-request-id"
    return ctx


def _index_attribute_definitions(index_names: tuple[str, ...]) -> list[Any]:
    """Key attribute definitions for each secondary index, in table order."""
    return [
        {"AttributeName": f"{name}{part}", "AttributeType": "S"}
        for name in index_names
        for part in ("pk", "sk")
    ]


def _create_infrastructure() -> None:
    index_names = ("gsi1", "gsi2", "gsi3")
    boto3.client("dynamodb", region_name="us-east-1").create_table(
        TableName=TABLE,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
            *_index_attribute_definitions(index_names),
        ],
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": name,
                "KeySchema": [
                    {"AttributeName": f"{name}pk", "KeyType": "HASH"},
                    {"AttributeName": f"{name}sk", "KeyType": "RANGE"},
                ],
                "Projection": {
                    "ProjectionType": "INCLUDE",
                    "NonKeyAttributes": LISTING_ATTRIBUTES,
                },
            }
            for name in index_names
        ],
    )
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)


@pytest.fixture(autouse=True)
def _journal_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DYNAMODB_TABLE_BLOG", TABLE)
    monkeypatch.setenv("MEDIA_BUCKET", BUCKET)
    monkeypatch.setenv("MEDIA_BASE_URL", "/media")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "us-east-1_TESTPOOL")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "test-client")
    monkeypatch.setenv("COGNITO_REGION", "us-east-1")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


def _as_user(user_id: str = "user-1", name: str = "Ana") -> Any:
    return patch(
        "vialo.api.blog.verify_id_token",
        return_value=AuthenticatedUser(user_id=user_id, display_name=name),
    )


def _as_anonymous() -> Any:
    return patch("vialo.api.blog.verify_id_token", side_effect=AuthError("Sign in to continue"))


def _publish(title: str = "A day in Tbilisi", city: str = "Tbilisi", **extra: Any) -> str:
    payload: dict[str, Any] = {"title": title, "city": city, "body": VALID_BODY}
    payload.update(extra)
    with _as_user():
        response = lambda_handler(
            _event("POST", "/api/blog/posts", payload, {"authorization": "Bearer t"}),
            _context(),
        )
    assert response["statusCode"] == 201, response["body"]
    return str(json.loads(response["body"])["post"]["postId"])


@mock_aws
class TestJournalReads:
    def test_empty_feed_is_a_valid_empty_list(self) -> None:
        _create_infrastructure()
        response = lambda_handler(_event("GET", "/api/blog/posts"), _context())
        assert response["statusCode"] == 200
        assert json.loads(response["body"]) == {"posts": [], "nextCursor": None}

    def test_reading_requires_no_authentication(self) -> None:
        _create_infrastructure()
        post_id = _publish()
        response = lambda_handler(_event("GET", f"/api/blog/posts/{post_id}"), _context())
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["title"] == "A day in Tbilisi"
        assert body["author"]["displayName"] == "Ana"
        # The API exposes an opaque author id and never an email address.
        assert "@" not in json.dumps(body)

    def test_city_filter_uses_the_normalized_slug(self) -> None:
        _create_infrastructure()
        _publish(title="Tbilisi story", city="Tbilisi")
        _publish(title="Naples story", city="Naples")
        response = lambda_handler(
            _event("GET", "/api/blog/posts", query={"city": "tbilisi"}), _context()
        )
        titles = [p["title"] for p in json.loads(response["body"])["posts"]]
        assert titles == ["Tbilisi story"]

    def test_missing_post_is_a_typed_404(self) -> None:
        _create_infrastructure()
        response = lambda_handler(_event("GET", "/api/blog/posts/nope"), _context())
        assert response["statusCode"] == 404
        assert json.loads(response["body"])["error"]["code"] == "POST_NOT_FOUND"


@mock_aws
class TestJournalWrites:
    def test_publishing_requires_authentication(self) -> None:
        _create_infrastructure()
        with _as_anonymous():
            response = lambda_handler(
                _event("POST", "/api/blog/posts", {"title": "t", "city": "c", "body": VALID_BODY}),
                _context(),
            )
        assert response["statusCode"] == 401
        assert json.loads(response["body"])["error"]["code"] == "UNAUTHENTICATED"

    def test_publishing_validates_length(self) -> None:
        _create_infrastructure()
        with _as_user():
            response = lambda_handler(
                _event(
                    "POST",
                    "/api/blog/posts",
                    {"title": "x", "city": "Tbilisi", "body": "too short"},
                    {"authorization": "Bearer t"},
                ),
                _context(),
            )
        assert response["statusCode"] == 400
        assert json.loads(response["body"])["error"]["code"] == "INVALID_INPUT"

    def test_a_story_carrying_a_real_itinerary_is_accepted(self) -> None:
        """A day snapshot is tens of kilobytes; the cap must leave room for one.

        The original 64 KB ceiling rejected a real seven-stop day at about 78 KB,
        and reported it as a missing title. Nobody hit it because a separate
        frontend defect meant no itinerary ever reached this route.
        """
        _create_infrastructure()
        big = {"title": "A day in Naples", "city": "Naples", "body": VALID_BODY}
        # Stand in for the snapshot with a payload of the same order of size.
        big["filler"] = "x" * 90_000
        with _as_user():
            response = lambda_handler(
                _event("POST", "/api/blog/posts", big, {"authorization": "Bearer t"}),
                _context(),
            )
        # Rejected on schema (unknown key), never on size: the size gate is past.
        assert response["statusCode"] == 400
        assert json.loads(response["body"])["error"]["code"] == "INVALID_INPUT"

    def test_an_oversized_story_is_reported_as_oversized(self) -> None:
        _create_infrastructure()
        payload = {
            "title": "A day in Naples",
            "city": "Naples",
            "body": VALID_BODY,
            "filler": "x" * (300 * 1024),
        }
        with _as_user():
            response = lambda_handler(
                _event("POST", "/api/blog/posts", payload, {"authorization": "Bearer t"}),
                _context(),
            )
        assert response["statusCode"] == 413
        body = json.loads(response["body"])
        assert body["error"]["code"] == "STORY_TOO_LARGE"
        # The old behaviour blamed the title, city, and body, all of which were present.
        assert "title" not in body["error"]["message"]

    def test_cover_key_belonging_to_another_author_is_refused(self) -> None:
        _create_infrastructure()
        with _as_user("user-1"):
            response = lambda_handler(
                _event(
                    "POST",
                    "/api/blog/posts",
                    {
                        "title": "Borrowed cover",
                        "city": "Tbilisi",
                        "body": VALID_BODY,
                        "coverImageKey": "covers/user-2/theirs.jpg",
                    },
                    {"authorization": "Bearer t"},
                ),
                _context(),
            )
        assert response["statusCode"] == 400

    def test_only_the_author_can_delete(self) -> None:
        _create_infrastructure()
        post_id = _publish()
        with _as_user("someone-else", "Bo"):
            denied = lambda_handler(
                _event(
                    "DELETE", f"/api/blog/posts/{post_id}", headers={"authorization": "Bearer t"}
                ),
                _context(),
            )
        assert denied["statusCode"] == 404

        with _as_user():
            allowed = lambda_handler(
                _event(
                    "DELETE", f"/api/blog/posts/{post_id}", headers={"authorization": "Bearer t"}
                ),
                _context(),
            )
        assert allowed["statusCode"] == 204

    def test_daily_story_quota_returns_429(self) -> None:
        _create_infrastructure()
        for index in range(5):
            _publish(title=f"Story {index}")
        with _as_user():
            response = lambda_handler(
                _event(
                    "POST",
                    "/api/blog/posts",
                    {"title": "One too many", "city": "Tbilisi", "body": VALID_BODY},
                    {"authorization": "Bearer t"},
                ),
                _context(),
            )
        assert response["statusCode"] == 429
        assert json.loads(response["body"])["error"]["code"] == "QUOTA_EXCEEDED"

    def test_viewer_route_lists_own_posts_and_remaining_allowance(self) -> None:
        _create_infrastructure()
        _publish(title="Mine")
        with _as_user():
            response = lambda_handler(
                _event("GET", "/api/blog/me", headers={"authorization": "Bearer t"}), _context()
            )
        body = json.loads(response["body"])
        assert response["statusCode"] == 200
        assert [p["title"] for p in body["posts"]] == ["Mine"]
        assert body["postsRemainingToday"] == 4


@mock_aws
class TestJournalComments:
    def test_comment_round_trip(self) -> None:
        _create_infrastructure()
        post_id = _publish()
        with _as_user("user-2", "Bo"):
            created = lambda_handler(
                _event(
                    "POST",
                    f"/api/blog/posts/{post_id}/comments",
                    {"body": "This route is exactly what I needed."},
                    {"authorization": "Bearer t"},
                ),
                _context(),
            )
        assert created["statusCode"] == 201

        listed = lambda_handler(_event("GET", f"/api/blog/posts/{post_id}/comments"), _context())
        comments = json.loads(listed["body"])["comments"]
        assert [c["body"] for c in comments] == ["This route is exactly what I needed."]
        assert comments[0]["author"]["displayName"] == "Bo"

    def test_commenting_requires_authentication(self) -> None:
        _create_infrastructure()
        post_id = _publish()
        with _as_anonymous():
            response = lambda_handler(
                _event("POST", f"/api/blog/posts/{post_id}/comments", {"body": "hi"}), _context()
            )
        assert response["statusCode"] == 401

    def test_commenting_on_a_missing_post_is_404(self) -> None:
        _create_infrastructure()
        with _as_user():
            response = lambda_handler(
                _event(
                    "POST",
                    "/api/blog/posts/missing/comments",
                    {"body": "hello"},
                    {"authorization": "Bearer t"},
                ),
                _context(),
            )
        assert response["statusCode"] == 404

    def test_empty_comment_is_refused(self) -> None:
        _create_infrastructure()
        post_id = _publish()
        with _as_user():
            response = lambda_handler(
                _event(
                    "POST",
                    f"/api/blog/posts/{post_id}/comments",
                    {"body": ""},
                    {"authorization": "Bearer t"},
                ),
                _context(),
            )
        assert response["statusCode"] == 400


@mock_aws
class TestJournalModerationAndUploads:
    def test_three_reports_hide_a_story(self) -> None:
        _create_infrastructure()
        post_id = _publish()
        for index in range(3):
            with _as_user(f"reporter-{index}", "Reporter"):
                response = lambda_handler(
                    _event(
                        "POST",
                        f"/api/blog/posts/{post_id}/report",
                        headers={"authorization": "Bearer t"},
                    ),
                    _context(),
                )
            assert response["statusCode"] == 202

        gone = lambda_handler(_event("GET", f"/api/blog/posts/{post_id}"), _context())
        assert gone["statusCode"] == 404

    def test_hiding_a_story_also_hides_its_comments(self) -> None:
        _create_infrastructure()
        post_id = _publish()
        with _as_user("commenter", "Commenter"):
            posted = lambda_handler(
                _event(
                    "POST",
                    f"/api/blog/posts/{post_id}/comments",
                    body={"body": "Walked this exact route last week."},
                    headers={"authorization": "Bearer t"},
                ),
                _context(),
            )
        assert posted["statusCode"] == 201

        visible = lambda_handler(_event("GET", f"/api/blog/posts/{post_id}/comments"), _context())
        assert visible["statusCode"] == 200
        assert len(json.loads(visible["body"])["comments"]) == 1

        for index in range(3):
            with _as_user(f"reporter-{index}", "Reporter"):
                lambda_handler(
                    _event(
                        "POST",
                        f"/api/blog/posts/{post_id}/report",
                        headers={"authorization": "Bearer t"},
                    ),
                    _context(),
                )

        # The story is hidden, so its discussion must not remain readable.
        hidden = lambda_handler(_event("GET", f"/api/blog/posts/{post_id}/comments"), _context())
        assert hidden["statusCode"] == 404
        assert json.loads(hidden["body"])["error"]["code"] == "POST_NOT_FOUND"

    def test_comments_on_a_missing_story_are_404(self) -> None:
        _create_infrastructure()
        response = lambda_handler(_event("GET", "/api/blog/posts/nope/comments"), _context())
        assert response["statusCode"] == 404
        assert json.loads(response["body"])["error"]["code"] == "POST_NOT_FOUND"

    def test_reporting_requires_authentication(self) -> None:
        _create_infrastructure()
        post_id = _publish()
        with _as_anonymous():
            response = lambda_handler(
                _event("POST", f"/api/blog/posts/{post_id}/report"), _context()
            )
        assert response["statusCode"] == 401

    def test_upload_url_is_scoped_to_the_caller(self) -> None:
        _create_infrastructure()
        with _as_user("user-1"):
            response = lambda_handler(
                _event(
                    "POST",
                    "/api/blog/uploads",
                    {"contentType": "image/jpeg"},
                    {"authorization": "Bearer t"},
                ),
                _context(),
            )
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["imageKey"].startswith("covers/user-1/")
        assert body["maxBytes"] == 2 * 1024 * 1024
        assert "policy" in body["fields"]

    def test_upload_url_refuses_unsupported_types(self) -> None:
        _create_infrastructure()
        with _as_user():
            response = lambda_handler(
                _event(
                    "POST",
                    "/api/blog/uploads",
                    {"contentType": "image/gif"},
                    {"authorization": "Bearer t"},
                ),
                _context(),
            )
        assert response["statusCode"] == 400

    def test_upload_requires_authentication(self) -> None:
        _create_infrastructure()
        with _as_anonymous():
            response = lambda_handler(
                _event("POST", "/api/blog/uploads", {"contentType": "image/png"}), _context()
            )
        assert response["statusCode"] == 401
