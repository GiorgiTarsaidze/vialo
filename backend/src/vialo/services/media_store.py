"""Presigned cover-image uploads for Vialo Journal.

Only one image per story, uploaded straight from the browser to a private S3
bucket and served back through CloudFront. A presigned POST is used rather than a
presigned PUT because only POST can enforce a maximum object size and an exact
content type as part of the signed policy — the browser cannot raise either.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

MAX_COVER_BYTES = 2 * 1024 * 1024
PRESIGN_EXPIRY_SECONDS = 300

_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


class MediaStoreError(Exception):
    """Raised when an upload URL cannot be issued."""


@dataclass(frozen=True, slots=True)
class PresignedUpload:
    """A single-use browser upload target."""

    url: str
    fields: dict[str, str]
    image_key: str


class MediaStore:
    """Issues bounded presigned uploads for Journal cover images."""

    def __init__(self, bucket: str, region: str = "us-east-1") -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            region_name=region,
            config=BotoConfig(signature_version="s3v4"),
        )

    def presign_cover_upload(self, *, user_id: str, content_type: str) -> PresignedUpload:
        """Create a presigned POST for exactly one cover image.

        The key is server-generated and namespaced by the author's opaque user
        ID, so a caller cannot choose a path or overwrite someone else's image.
        """
        extension = _EXTENSIONS.get(content_type)
        if extension is None:
            raise MediaStoreError("Unsupported image type")

        key = f"covers/{user_id}/{uuid.uuid4().hex}.{extension}"
        try:
            presigned: dict[str, Any] = self._client.generate_presigned_post(
                Bucket=self._bucket,
                Key=key,
                Fields={"Content-Type": content_type, "success_action_status": "201"},
                Conditions=[
                    {"Content-Type": content_type},
                    {"success_action_status": "201"},
                    ["content-length-range", 1, MAX_COVER_BYTES],
                ],
                ExpiresIn=PRESIGN_EXPIRY_SECONDS,
            )
        except (BotoCoreError, ClientError) as exc:
            logger.warning("Presign failed: %s", type(exc).__name__)
            raise MediaStoreError("Could not prepare the image upload") from exc

        return PresignedUpload(
            url=str(presigned["url"]),
            fields={str(k): str(v) for k, v in presigned["fields"].items()},
            image_key=key,
        )

    @staticmethod
    def is_own_key(key: str, user_id: str) -> bool:
        """Whether a submitted cover key was issued to this author."""
        return key.startswith(f"covers/{user_id}/") and ".." not in key
