"""Integration tests for the Vialo Journal repository and media store."""

from __future__ import annotations

import datetime as dt
from typing import Any

import boto3
import pytest
from moto import mock_aws

from vialo.models.blog import BlogAuthor
from vialo.models.itinerary import (
    ComparisonUnavailable,
    GroundedStop,
    ItineraryResponse,
    Locality,
    MapsHandoff,
    OpenInterval,
    TimeWindow,
    Totals,
)
from vialo.models.providers import GroundedPlace, Location, StopCategory
from vialo.services.blog_repository import (
    MAX_COMMENTS_PER_DAY,
    MAX_POSTS_PER_DAY,
    REPORT_HIDE_THRESHOLD,
    BlogRepository,
    QuotaExceededError,
    build_excerpt,
    city_key,
    clean_text,
)
from vialo.services.media_store import MAX_COVER_BYTES, MediaStore, MediaStoreError

TABLE = "vialo-journal-test"
BUCKET = "vialo-journal-media-test"

AUTHOR = BlogAuthor(user_id="user-1", display_name="Ana")
OTHER = BlogAuthor(user_id="user-2", display_name="Bo")

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


def _index_attribute_definitions(index_names: tuple[str, ...]) -> list[Any]:
    """Key attribute definitions for each secondary index, in table order."""
    return [
        {"AttributeName": f"{name}{part}", "AttributeType": "S"}
        for name in index_names
        for part in ("pk", "sk")
    ]


def _create_table() -> None:
    client = boto3.client("dynamodb", region_name="us-east-1")
    index_names = ("gsi1", "gsi2", "gsi3")
    client.create_table(
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


def _itinerary() -> ItineraryResponse:
    now = dt.datetime.now(dt.UTC)
    origin = GroundedPlace(
        place_id="origin",
        display_name="Piazza",
        formatted_address="Piazza 1",
        location=Location(latitude=40.8, longitude=14.2),
        time_zone_id="Europe/Rome",
    )
    stop = GroundedStop(
        candidate_index=0,
        name="Castel Nuovo",
        category=StopCategory.LANDMARK,
        priority=1,
        visit_duration_minutes=60,
        duration_source="model_estimate",
        place=GroundedPlace(
            place_id="stop-1",
            display_name="Castel Nuovo",
            formatted_address="Via 1",
            location=Location(latitude=40.84, longitude=14.25),
            time_zone_id="Europe/Rome",
        ),
        hours_source="current",
        open_intervals=[
            OpenInterval(
                start=now,
                end=now + dt.timedelta(hours=8),
                local_start="09:00",
                local_end="17:00",
            )
        ],
    )
    return ItineraryResponse(
        request_id="req-1",
        status="complete",
        locality=Locality(name="Naples", time_zone_id="Europe/Rome"),
        travel_mode="WALK",
        window=TimeWindow(
            start=now,
            end=now + dt.timedelta(hours=8),
            local_start="09:00",
            local_end="17:00",
            date=now.date(),
        ),
        origin=origin,
        stops=[stop],
        timeline=[],
        dropped_stops=[],
        comparison=ComparisonUnavailable(reason_code="SINGLE_STOP"),
        maps_handoff=MapsHandoff(full_route_universally_supported=True, browser_safe_parts=[]),
        totals=Totals(visit_seconds=3600, travel_seconds=0, wait_seconds=0, elapsed_seconds=3600),
        diagnostics=[],
    )


class TestTextHelpers:
    def test_city_key_is_a_stable_slug(self) -> None:
        assert city_key(" Naples ") == "naples"
        assert city_key("Tbilisi, Georgia") == "tbilisi-georgia"
        assert city_key("São Paulo") == "s-o-paulo"
        assert city_key("???") == "elsewhere"

    def test_clean_text_removes_control_characters_and_collapses_blank_lines(self) -> None:
        cleaned = clean_text("Hello\x07  world\r\n\n\n\nSecond   paragraph  ")
        assert "\x07" not in cleaned
        assert cleaned == "Hello world\n\nSecond paragraph"

    def test_excerpt_is_bounded_and_word_safe(self) -> None:
        excerpt = build_excerpt("word " * 200)
        assert len(excerpt) <= 241
        assert excerpt.endswith("…")


@mock_aws
class TestJournalRepository:
    def _repo(self) -> BlogRepository:
        _create_table()
        return BlogRepository(table_name=TABLE, media_base_url="/media")

    def _post(self, repo: BlogRepository, **overrides: object) -> object:
        payload: dict[str, object] = {
            "author": AUTHOR,
            "title": "A day in Naples",
            "city": "Naples",
            "body": "We started early and walked the historic centre. " * 3,
            "cover_image_key": None,
            "itinerary": None,
        }
        payload.update(overrides)
        return repo.create_post(**payload)  # type: ignore[arg-type]

    def test_create_and_read_round_trip(self) -> None:
        repo = self._repo()
        created = self._post(repo)
        fetched = repo.get_post(created.post_id)  # type: ignore[attr-defined]
        assert fetched is not None
        assert fetched.title == "A day in Naples"
        assert fetched.city_key == "naples"
        assert fetched.author.display_name == "Ana"
        assert fetched.comment_count == 0
        assert fetched.has_route is False

    def test_cover_key_becomes_a_same_origin_media_url(self) -> None:
        repo = self._repo()
        created = self._post(repo, cover_image_key="covers/user-1/abc.jpg")
        assert created.cover_image_url == "/media/covers/user-1/abc.jpg"  # type: ignore[attr-defined]

    def test_attached_itinerary_round_trips_and_sets_route_flags(self) -> None:
        repo = self._repo()
        created = self._post(repo, itinerary=_itinerary())
        fetched = repo.get_post(created.post_id)  # type: ignore[attr-defined]
        assert fetched is not None
        assert fetched.has_route is True
        assert fetched.stop_count == 1
        assert fetched.itinerary is not None
        assert fetched.itinerary.locality.name == "Naples"

    def test_feed_city_and_author_listings(self) -> None:
        repo = self._repo()
        self._post(repo, title="Naples one")
        self._post(repo, title="Tbilisi one", city="Tbilisi")
        self._post(repo, title="Other author", city="Lisbon", author=OTHER)

        feed, cursor = repo.list_feed()
        assert len(feed) == 3
        assert cursor is None

        naples, _ = repo.list_by_city("naples")
        assert [p.title for p in naples] == ["Naples one"]

        mine, _ = repo.list_by_author("user-1")
        assert {p.title for p in mine} == {"Naples one", "Tbilisi one"}

    def test_listings_are_newest_first(self) -> None:
        repo = self._repo()
        first = self._post(repo, title="Older")
        second = self._post(repo, title="Newer")
        feed, _ = repo.list_feed()
        assert [p.post_id for p in feed] == [
            second.post_id,  # type: ignore[attr-defined]
            first.post_id,  # type: ignore[attr-defined]
        ]

    def test_pagination_returns_a_cursor_and_does_not_repeat_items(self) -> None:
        repo = self._repo()
        for index in range(3):
            self._post(repo, title=f"Story {index}")
        page_one, cursor = repo.list_feed(limit=2)
        assert len(page_one) == 2
        assert cursor is not None
        page_two, _ = repo.list_feed(cursor=cursor, limit=2)
        assert len(page_two) == 1
        assert not {p.post_id for p in page_one} & {p.post_id for p in page_two}

    def test_author_can_delete_and_others_cannot(self) -> None:
        repo = self._repo()
        created = self._post(repo)
        assert repo.delete_post(created.post_id, OTHER.user_id) is False  # type: ignore[attr-defined]
        assert repo.get_post(created.post_id) is not None  # type: ignore[attr-defined]
        assert repo.delete_post(created.post_id, AUTHOR.user_id) is True  # type: ignore[attr-defined]
        assert repo.get_post(created.post_id) is None  # type: ignore[attr-defined]

    def test_comments_round_trip_and_update_the_counter(self) -> None:
        repo = self._repo()
        created = self._post(repo)
        comment = repo.add_comment(created.post_id, OTHER, "Loved this route!")  # type: ignore[attr-defined]
        assert comment.author.display_name == "Bo"

        comments = repo.list_comments(created.post_id)  # type: ignore[attr-defined]
        assert [c.body for c in comments] == ["Loved this route!"]
        refreshed = repo.get_post(created.post_id)  # type: ignore[attr-defined]
        assert refreshed is not None
        assert refreshed.comment_count == 1

    def test_only_the_comment_author_can_delete_it(self) -> None:
        repo = self._repo()
        created = self._post(repo)
        comment = repo.add_comment(created.post_id, OTHER, "Mine")  # type: ignore[attr-defined]
        assert (
            repo.delete_comment(created.post_id, comment.comment_id, AUTHOR.user_id)  # type: ignore[attr-defined]
            is False
        )
        assert (
            repo.delete_comment(created.post_id, comment.comment_id, OTHER.user_id)  # type: ignore[attr-defined]
            is True
        )
        assert repo.list_comments(created.post_id) == []  # type: ignore[attr-defined]

    def test_deleting_a_post_removes_its_comments(self) -> None:
        repo = self._repo()
        created = self._post(repo)
        repo.add_comment(created.post_id, OTHER, "One")  # type: ignore[attr-defined]
        repo.delete_post(created.post_id, AUTHOR.user_id)  # type: ignore[attr-defined]
        assert repo.list_comments(created.post_id) == []  # type: ignore[attr-defined]

    def test_reports_hide_the_post_at_the_threshold(self) -> None:
        repo = self._repo()
        created = self._post(repo)
        for _ in range(REPORT_HIDE_THRESHOLD - 1):
            assert repo.report_post(created.post_id) is True  # type: ignore[attr-defined]
        assert repo.get_post(created.post_id) is not None  # type: ignore[attr-defined]

        assert repo.report_post(created.post_id) is True  # type: ignore[attr-defined]
        assert repo.get_post(created.post_id) is None  # type: ignore[attr-defined]
        feed, _ = repo.list_feed()
        assert feed == []

    def test_reporting_a_missing_post_is_reported_as_missing(self) -> None:
        repo = self._repo()
        assert repo.report_post("does-not-exist") is False

    def test_daily_post_quota_is_enforced_atomically(self) -> None:
        repo = self._repo()
        for _ in range(MAX_POSTS_PER_DAY):
            repo.consume_quota(AUTHOR.user_id, kind="post")
        with pytest.raises(QuotaExceededError):
            repo.consume_quota(AUTHOR.user_id, kind="post")
        # A different author is unaffected.
        repo.consume_quota(OTHER.user_id, kind="post")

    def test_comment_quota_is_separate_from_the_post_quota(self) -> None:
        repo = self._repo()
        for _ in range(MAX_POSTS_PER_DAY):
            repo.consume_quota(AUTHOR.user_id, kind="post")
        repo.consume_quota(AUTHOR.user_id, kind="comment")
        state = repo.quota_state(AUTHOR.user_id)
        assert state.posts_used == MAX_POSTS_PER_DAY
        assert state.posts_remaining == 0
        assert state.comments_used == 1

    def test_comment_quota_limit(self) -> None:
        repo = self._repo()
        for _ in range(MAX_COMMENTS_PER_DAY):
            repo.consume_quota(AUTHOR.user_id, kind="comment")
        with pytest.raises(QuotaExceededError):
            repo.consume_quota(AUTHOR.user_id, kind="comment")

    def test_quota_state_defaults_to_unused(self) -> None:
        repo = self._repo()
        state = repo.quota_state("nobody")
        assert state.posts_used == 0
        assert state.posts_remaining == MAX_POSTS_PER_DAY

    def test_stored_body_is_cleaned(self) -> None:
        repo = self._repo()
        created = self._post(repo, body="Line one\x00\n\n\n\nLine two. " + "padding " * 10)
        fetched = repo.get_post(created.post_id)  # type: ignore[attr-defined]
        assert fetched is not None
        assert "\x00" not in fetched.body
        assert "\n\n\n" not in fetched.body


@mock_aws
class TestMediaStore:
    def _store(self) -> MediaStore:
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
        return MediaStore(bucket=BUCKET, region="us-east-1")

    def test_presigned_post_enforces_type_and_size(self) -> None:
        store = self._store()
        upload = store.presign_cover_upload(user_id="user-1", content_type="image/jpeg")
        assert upload.image_key.startswith("covers/user-1/")
        assert upload.image_key.endswith(".jpg")
        assert upload.fields["Content-Type"] == "image/jpeg"
        policy = upload.fields["policy"]
        assert policy  # signed policy carries the content-length-range condition
        assert MAX_COVER_BYTES == 2 * 1024 * 1024

    def test_unsupported_type_is_refused(self) -> None:
        store = self._store()
        with pytest.raises(MediaStoreError):
            store.presign_cover_upload(user_id="user-1", content_type="image/gif")

    def test_keys_are_namespaced_per_author(self) -> None:
        assert MediaStore.is_own_key("covers/user-1/a.jpg", "user-1") is True
        assert MediaStore.is_own_key("covers/user-2/a.jpg", "user-1") is False
        assert MediaStore.is_own_key("covers/user-1/../../secret", "user-1") is False
        assert MediaStore.is_own_key("other/user-1/a.jpg", "user-1") is False
