"""DynamoDB repository for Vialo Journal posts, comments, and per-author quotas.

Single table, three global secondary indexes:

* `pk = POST#<postId>`, `sk = META` — the post itself.
* `pk = POST#<postId>`, `sk = COMMENT#<createdAt>#<commentId>` — flat comments.
* `pk = AUTHOR#<userId>`, `sk = QUOTA#<YYYY-MM-DD>` — daily write quotas with TTL.

Indexes project only listing attributes, so a feed query never reads a post body
or an attached itinerary. Journal data is deliberately separate from the place
cache, the rate-limit table, and anonymous shares: different lifecycle, different
retention, different access pattern.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.exceptions import ClientError

from vialo.models.blog import (
    EXCERPT_MAX,
    BlogAuthor,
    BlogComment,
    BlogPost,
    BlogPostSummary,
)
from vialo.models.itinerary import ItineraryResponse

logger = logging.getLogger(__name__)

FEED_PARTITION = "FEED"
GSI_FEED = "gsi1"
GSI_CITY = "gsi2"
GSI_AUTHOR = "gsi3"

MAX_POSTS_PER_DAY = 5
MAX_COMMENTS_PER_DAY = 20
QUOTA_TTL_SECONDS = 3 * 24 * 60 * 60
PAGE_SIZE = 12
MAX_COVER_KEY_LENGTH = 200
# A post is hidden from every listing and from direct reads at this many reports.
REPORT_HIDE_THRESHOLD = 3

_WHITESPACE_RUN = re.compile(r"[ \t]+")
_BLANK_RUN = re.compile(r"\n{3,}")


class BlogRepositoryError(Exception):
    """Raised when the Journal store cannot serve a request."""


class QuotaExceededError(Exception):
    """Raised when an author exceeds their daily write allowance."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True, slots=True)
class QuotaState:
    """Remaining daily allowance for one author."""

    posts_used: int
    comments_used: int

    @property
    def posts_remaining(self) -> int:
        return max(0, MAX_POSTS_PER_DAY - self.posts_used)


def _as_int(value: Any) -> int:
    """DynamoDB returns numbers as Decimal; treat anything unusable as zero."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def city_key(city: str) -> str:
    """Normalize a city label into a stable partition key."""
    lowered = " ".join(city.strip().lower().split())
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "elsewhere"


def clean_text(raw: str) -> str:
    """Keep user text printable and tidy without altering its meaning.

    Control characters are removed, runs of spaces collapse, and more than one
    blank line collapses to one. Nothing is HTML-escaped here: the frontend never
    renders this as markup.
    """
    without_controls = "".join(ch for ch in raw if ch == "\n" or ch.isprintable())
    normalized = _WHITESPACE_RUN.sub(" ", without_controls.replace("\r\n", "\n"))
    lines = [line.rstrip() for line in normalized.split("\n")]
    return _BLANK_RUN.sub("\n\n", "\n".join(lines)).strip()


def build_excerpt(body: str) -> str:
    """First sentence-ish slice of the body for listings."""
    flat = " ".join(body.split())
    if len(flat) <= EXCERPT_MAX:
        return flat
    cut = flat[:EXCERPT_MAX].rsplit(" ", 1)[0]
    return f"{cut}…"


class BlogRepository:
    """Journal persistence. All timestamps are UTC ISO-8601 strings in storage."""

    def __init__(self, table_name: str, media_base_url: str = "/media") -> None:
        self._table = boto3.resource("dynamodb").Table(table_name)
        self._media_base_url = media_base_url.rstrip("/")

    # --- helpers -----------------------------------------------------------

    def _cover_url(self, key: str | None) -> str | None:
        if not key:
            return None
        return f"{self._media_base_url}/{key.lstrip('/')}"

    def _summary_from_item(self, item: dict[str, Any]) -> BlogPostSummary:
        return BlogPostSummary(
            post_id=str(item["postId"]),
            title=str(item["title"]),
            city=str(item["city"]),
            city_key=str(item["cityKey"]),
            excerpt=str(item.get("excerpt", "")),
            cover_image_url=self._cover_url(item.get("coverImageKey")),
            author=BlogAuthor(
                user_id=str(item["authorId"]),
                display_name=str(item["authorName"]),
            ),
            created_at=dt.datetime.fromisoformat(str(item["createdAt"])),
            comment_count=int(item.get("commentCount", 0)),
            has_route=bool(item.get("hasRoute", False)),
            stop_count=int(item.get("stopCount", 0)),
        )

    def _post_from_item(self, item: dict[str, Any]) -> BlogPost:
        summary = self._summary_from_item(item)
        itinerary: ItineraryResponse | None = None
        raw_itinerary = item.get("itinerary")
        if isinstance(raw_itinerary, str) and raw_itinerary:
            try:
                itinerary = ItineraryResponse.model_validate_json(raw_itinerary)
            except Exception:
                # A stored itinerary that no longer validates is dropped rather
                # than rendered half-parsed. The story itself stays readable.
                logger.warning("Stored itinerary failed validation; omitting")
        return BlogPost(
            **summary.model_dump(),
            body=str(item["body"]),
            itinerary=itinerary,
        )

    # --- quotas ------------------------------------------------------------

    def _quota_key(self, user_id: str, today: dt.date) -> dict[str, str]:
        return {"pk": f"AUTHOR#{user_id}", "sk": f"QUOTA#{today.isoformat()}"}

    def consume_quota(self, user_id: str, *, kind: str) -> None:
        """Atomically consume one daily write allowance.

        Raises:
            QuotaExceededError: When the author has reached the daily limit.
        """
        attribute = "posts" if kind == "post" else "comments"
        limit = MAX_POSTS_PER_DAY if kind == "post" else MAX_COMMENTS_PER_DAY
        now = dt.datetime.now(dt.UTC)
        expires_at = int(now.timestamp()) + QUOTA_TTL_SECONDS
        try:
            self._table.update_item(
                Key=self._quota_key(user_id, now.date()),
                UpdateExpression=(f"SET expiresAt = :ttl ADD {attribute} :one"),
                ConditionExpression=(f"attribute_not_exists({attribute}) OR {attribute} < :limit"),
                ExpressionAttributeValues={":one": 1, ":limit": limit, ":ttl": expires_at},
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                unit = "stories" if kind == "post" else "comments"
                raise QuotaExceededError(
                    f"You have reached today's limit of {limit} {unit}. Try again tomorrow."
                ) from exc
            raise BlogRepositoryError("Journal store unavailable") from exc

    def quota_state(self, user_id: str) -> QuotaState:
        """Read today's allowance usage. Missing item means nothing used yet."""
        try:
            response = self._table.get_item(
                Key=self._quota_key(user_id, dt.datetime.now(dt.UTC).date())
            )
        except ClientError as exc:
            raise BlogRepositoryError("Journal store unavailable") from exc
        item = response.get("Item") or {}
        return QuotaState(
            posts_used=_as_int(item.get("posts")),
            comments_used=_as_int(item.get("comments")),
        )

    # --- posts -------------------------------------------------------------

    def create_post(
        self,
        *,
        author: BlogAuthor,
        title: str,
        city: str,
        body: str,
        cover_image_key: str | None,
        itinerary: ItineraryResponse | None,
    ) -> BlogPost:
        """Persist one Journal entry and return it."""
        post_id = uuid.uuid4().hex[:16]
        created_at = dt.datetime.now(dt.UTC)
        created_iso = created_at.isoformat()
        key = city_key(city)
        sort_value = f"{created_iso}#{post_id}"

        item: dict[str, Any] = {
            "pk": f"POST#{post_id}",
            "sk": "META",
            "postId": post_id,
            "title": clean_text(title),
            "city": clean_text(city),
            "cityKey": key,
            "body": clean_text(body),
            "excerpt": build_excerpt(clean_text(body)),
            "authorId": author.user_id,
            "authorName": author.display_name,
            "createdAt": created_iso,
            "commentCount": 0,
            "reportCount": 0,
            "hidden": False,
            "hasRoute": itinerary is not None,
            "stopCount": len(itinerary.stops) if itinerary is not None else 0,
            "gsi1pk": FEED_PARTITION,
            "gsi1sk": sort_value,
            "gsi2pk": f"CITY#{key}",
            "gsi2sk": sort_value,
            "gsi3pk": f"AUTHOR#{author.user_id}",
            "gsi3sk": sort_value,
        }
        if cover_image_key:
            item["coverImageKey"] = cover_image_key
        if itinerary is not None:
            item["itinerary"] = itinerary.model_dump_json(by_alias=True)

        try:
            self._table.put_item(Item=item, ConditionExpression="attribute_not_exists(pk)")
        except ClientError as exc:
            raise BlogRepositoryError("Could not publish the story") from exc

        return self._post_from_item(item)

    def get_post(self, post_id: str) -> BlogPost | None:
        """Read one post. Hidden (reported) posts read as missing."""
        try:
            response = self._table.get_item(Key={"pk": f"POST#{post_id}", "sk": "META"})
        except ClientError as exc:
            raise BlogRepositoryError("Journal store unavailable") from exc
        item = response.get("Item")
        if not item or bool(item.get("hidden", False)):
            return None
        return self._post_from_item(item)

    def delete_post(self, post_id: str, user_id: str) -> bool:
        """Delete a post and its comments. Only the author may do this."""
        try:
            self._table.delete_item(
                Key={"pk": f"POST#{post_id}", "sk": "META"},
                ConditionExpression="authorId = :author",
                ExpressionAttributeValues={":author": user_id},
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return False
            raise BlogRepositoryError("Could not delete the story") from exc

        # Best-effort comment cleanup; a missed comment is unreachable anyway.
        try:
            comments = self._table.query(
                KeyConditionExpression=(
                    boto3.dynamodb.conditions.Key("pk").eq(f"POST#{post_id}")
                    & boto3.dynamodb.conditions.Key("sk").begins_with("COMMENT#")
                ),
                ProjectionExpression="pk, sk",
            ).get("Items", [])
            with self._table.batch_writer() as batch:
                for comment in comments:
                    batch.delete_item(Key={"pk": comment["pk"], "sk": comment["sk"]})
        except ClientError:
            logger.warning("Comment cleanup incomplete for deleted post")
        return True

    def report_post(self, post_id: str) -> bool:
        """Increment the report counter and hide the post at the threshold."""
        try:
            response = self._table.update_item(
                Key={"pk": f"POST#{post_id}", "sk": "META"},
                UpdateExpression="ADD reportCount :one",
                ConditionExpression="attribute_exists(pk)",
                ExpressionAttributeValues={":one": 1},
                ReturnValues="UPDATED_NEW",
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return False
            raise BlogRepositoryError("Could not report the story") from exc

        count = _as_int(response.get("Attributes", {}).get("reportCount"))
        if count >= REPORT_HIDE_THRESHOLD:
            try:
                self._table.update_item(
                    Key={"pk": f"POST#{post_id}", "sk": "META"},
                    # "hidden" is a DynamoDB reserved word, hence the alias.
                    # Removing the index keys drops the post out of every listing.
                    UpdateExpression="SET #hidden = :true REMOVE gsi1pk, gsi2pk, gsi3pk",
                    ExpressionAttributeNames={"#hidden": "hidden"},
                    ExpressionAttributeValues={":true": True},
                )
            except ClientError:
                logger.warning("Could not hide reported post")
        return True

    def _list(
        self,
        *,
        index_name: str,
        partition_attr: str,
        partition_value: str,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[BlogPostSummary], str | None]:
        sort_attr = partition_attr.replace("pk", "sk")
        kwargs: dict[str, Any] = {
            "IndexName": index_name,
            "KeyConditionExpression": boto3.dynamodb.conditions.Key(partition_attr).eq(
                partition_value
            ),
            "ScanIndexForward": False,
            "Limit": limit,
        }
        if cursor:
            kwargs["ExclusiveStartKey"] = json.loads(cursor)
        try:
            response = self._table.query(**kwargs)
        except (ClientError, ValueError) as exc:
            raise BlogRepositoryError("Journal store unavailable") from exc

        posts: list[BlogPostSummary] = []
        for item in response.get("Items", []):
            if bool(item.get("hidden", False)):
                continue
            try:
                posts.append(self._summary_from_item(item))
            except Exception:
                logger.warning("Skipping unreadable Journal item")
        next_key = response.get("LastEvaluatedKey")
        del sort_attr
        return posts, json.dumps(next_key) if next_key else None

    def list_feed(
        self, cursor: str | None = None, limit: int = PAGE_SIZE
    ) -> tuple[list[BlogPostSummary], str | None]:
        """Newest stories across every city."""
        return self._list(
            index_name=GSI_FEED,
            partition_attr="gsi1pk",
            partition_value=FEED_PARTITION,
            cursor=cursor,
            limit=limit,
        )

    def list_by_city(
        self, city: str, cursor: str | None = None, limit: int = PAGE_SIZE
    ) -> tuple[list[BlogPostSummary], str | None]:
        """Newest stories for one city, keyed by the normalized city slug."""
        return self._list(
            index_name=GSI_CITY,
            partition_attr="gsi2pk",
            partition_value=f"CITY#{city_key(city)}",
            cursor=cursor,
            limit=limit,
        )

    def list_by_author(
        self, user_id: str, cursor: str | None = None, limit: int = PAGE_SIZE
    ) -> tuple[list[BlogPostSummary], str | None]:
        """Newest stories by one author."""
        return self._list(
            index_name=GSI_AUTHOR,
            partition_attr="gsi3pk",
            partition_value=f"AUTHOR#{user_id}",
            cursor=cursor,
            limit=limit,
        )

    # --- comments ----------------------------------------------------------

    def add_comment(self, post_id: str, author: BlogAuthor, body: str) -> BlogComment:
        """Append one comment and keep the post's counter in step."""
        comment_id = uuid.uuid4().hex[:16]
        created_at = dt.datetime.now(dt.UTC)
        cleaned = clean_text(body)
        item = {
            "pk": f"POST#{post_id}",
            "sk": f"COMMENT#{created_at.isoformat()}#{comment_id}",
            "commentId": comment_id,
            "postId": post_id,
            "authorId": author.user_id,
            "authorName": author.display_name,
            "body": cleaned,
            "createdAt": created_at.isoformat(),
        }
        try:
            self._table.put_item(Item=item)
            self._table.update_item(
                Key={"pk": f"POST#{post_id}", "sk": "META"},
                UpdateExpression="ADD commentCount :one",
                ConditionExpression="attribute_exists(pk)",
                ExpressionAttributeValues={":one": 1},
            )
        except ClientError as exc:
            raise BlogRepositoryError("Could not add the comment") from exc

        return BlogComment(
            comment_id=comment_id,
            post_id=post_id,
            author=author,
            body=cleaned,
            created_at=created_at,
        )

    def list_comments(self, post_id: str, limit: int = 100) -> list[BlogComment]:
        """Comments for a post, newest first."""
        try:
            response = self._table.query(
                KeyConditionExpression=(
                    boto3.dynamodb.conditions.Key("pk").eq(f"POST#{post_id}")
                    & boto3.dynamodb.conditions.Key("sk").begins_with("COMMENT#")
                ),
                ScanIndexForward=False,
                Limit=limit,
            )
        except ClientError as exc:
            raise BlogRepositoryError("Journal store unavailable") from exc

        comments: list[BlogComment] = []
        for item in response.get("Items", []):
            try:
                comments.append(
                    BlogComment(
                        comment_id=str(item["commentId"]),
                        post_id=post_id,
                        author=BlogAuthor(
                            user_id=str(item["authorId"]),
                            display_name=str(item["authorName"]),
                        ),
                        body=str(item["body"]),
                        created_at=dt.datetime.fromisoformat(str(item["createdAt"])),
                    )
                )
            except Exception:
                logger.warning("Skipping unreadable comment")
        return comments

    def delete_comment(self, post_id: str, comment_id: str, user_id: str) -> bool:
        """Delete one comment, author only. Requires a lookup for the sort key."""
        try:
            response = self._table.query(
                KeyConditionExpression=(
                    boto3.dynamodb.conditions.Key("pk").eq(f"POST#{post_id}")
                    & boto3.dynamodb.conditions.Key("sk").begins_with("COMMENT#")
                ),
                FilterExpression=boto3.dynamodb.conditions.Attr("commentId").eq(comment_id),
                Limit=100,
            )
            items = response.get("Items", [])
            if not items:
                return False
            target = items[0]
            if str(target.get("authorId")) != user_id:
                return False
            self._table.delete_item(Key={"pk": target["pk"], "sk": target["sk"]})
            self._table.update_item(
                Key={"pk": f"POST#{post_id}", "sk": "META"},
                UpdateExpression="ADD commentCount :minus",
                ConditionExpression="attribute_exists(pk) AND commentCount > :zero",
                ExpressionAttributeValues={":minus": -1, ":zero": 0},
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return True
            raise BlogRepositoryError("Could not delete the comment") from exc
        return True
