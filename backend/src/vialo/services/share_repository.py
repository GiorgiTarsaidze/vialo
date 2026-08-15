"""DynamoDB repository for explicit anonymous itinerary shares."""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import secrets
import time
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError

from vialo.models.itinerary import ItineraryResponse, ShareProof
from vialo.models.shares import CreateShareResponse

SHARE_TTL_DAYS = 30
PROOF_TTL_SECONDS = 300


def _decimal_to_native(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, dict):
        return {key: _decimal_to_native(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decimal_to_native(item) for item in value]
    return value


def _item_int(item: dict[str, Any], key: str) -> int:
    value = item.get(key, 0)
    if isinstance(value, int | Decimal | str):
        return int(value)
    return 0


class ShareRepository:
    """Store computed itineraries only after verifying a short-lived signed proof."""

    def __init__(
        self,
        table_name: str,
        signing_secret: str,
        deletion_secret: str,
        region_name: str = "us-east-1",
    ) -> None:
        self._table_name = table_name
        self._signing_secret = signing_secret.encode()
        self._deletion_secret = deletion_secret.encode()
        self._table = boto3.resource("dynamodb", region_name=region_name).Table(table_name)
        self._client = boto3.client("dynamodb", region_name=region_name)

    def _canonical_itinerary_json(self, itinerary: ItineraryResponse) -> str:
        data = itinerary.model_dump(by_alias=True, mode="json", exclude={"share_proof"})
        return json.dumps(data, sort_keys=True, separators=(",", ":"))

    def _compute_itinerary_hmac(self, itinerary: ItineraryResponse, expires_at: dt.datetime) -> str:
        canonical = self._canonical_itinerary_json(itinerary)
        payload = f"v{itinerary.schema_version}:{expires_at.isoformat()}:{canonical}"
        return hmac.new(self._signing_secret, payload.encode(), hashlib.sha256).hexdigest()

    def _verify_proof(self, proof: ShareProof, itinerary: ItineraryResponse) -> bool:
        if proof.expires_at <= dt.datetime.now(dt.UTC):
            return False
        expected = self._compute_itinerary_hmac(itinerary, proof.expires_at)
        return hmac.compare_digest(proof.hmac, expected)

    def _proof_digest(self, proof: ShareProof) -> str:
        value = f"{proof.expires_at.isoformat()}:{proof.hmac}"
        return hashlib.sha256(value.encode()).hexdigest()

    def _delete_digest(self, token: str) -> str:
        return hmac.new(self._deletion_secret, token.encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def _serialize_item(item: dict[str, Any]) -> dict[str, Any]:
        from boto3.dynamodb.types import TypeSerializer

        serializer = TypeSerializer()
        return {key: serializer.serialize(value) for key, value in item.items()}

    def generate_proof(self, itinerary: ItineraryResponse) -> ShareProof:
        expires_at = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=PROOF_TTL_SECONDS)
        return ShareProof(
            expires_at=expires_at,
            hmac=self._compute_itinerary_hmac(itinerary, expires_at),
        )

    def create(self, itinerary: ItineraryResponse, proof: ShareProof) -> CreateShareResponse:
        """Atomically claim a proof and create its single share item."""
        if not self._verify_proof(proof, itinerary):
            raise ValueError("Invalid or expired share proof")

        proof_digest = self._proof_digest(proof)
        proof_key = f"PROOF#{proof_digest}"
        existing = self._table.get_item(Key={"pk": proof_key}, ConsistentRead=True).get("Item")
        if existing and _item_int(existing, "expiresAt") > int(time.time()):
            share_id = str(existing.get("shareId", ""))
            if share_id:
                return CreateShareResponse(
                    share_id=share_id,
                    share_url=f"https://vialo.place/r/{share_id}",
                    deletion_token="",
                )

        deletion_token = secrets.token_urlsafe(24)
        delete_digest = self._delete_digest(deletion_token)
        now = dt.datetime.now(dt.UTC)
        share_expires_at = int((now + dt.timedelta(days=SHARE_TTL_DAYS)).timestamp())
        proof_expires_at = int(proof.expires_at.timestamp())
        response_data = json.loads(
            json.dumps(itinerary.model_dump(by_alias=True, mode="json", exclude={"share_proof"})),
            parse_float=Decimal,
        )

        for _attempt in range(3):
            share_id = secrets.token_urlsafe(12)
            try:
                self._client.transact_write_items(
                    TransactItems=[
                        {
                            "Put": {
                                "TableName": self._table_name,
                                "Item": self._serialize_item(
                                    {
                                        "pk": proof_key,
                                        "shareId": share_id,
                                        "createdAt": now.isoformat(),
                                        "expiresAt": proof_expires_at,
                                    }
                                ),
                                "ConditionExpression": "attribute_not_exists(pk)",
                            }
                        },
                        {
                            "Put": {
                                "TableName": self._table_name,
                                "Item": self._serialize_item(
                                    {
                                        "pk": f"SHARE#{share_id}",
                                        "response": response_data,
                                        "proofDigest": proof_digest,
                                        "deleteTokenDigest": delete_digest,
                                        "createdAt": now.isoformat(),
                                        "expiresAt": share_expires_at,
                                    }
                                ),
                                "ConditionExpression": "attribute_not_exists(pk)",
                            }
                        },
                    ]
                )
                return CreateShareResponse(
                    share_id=share_id,
                    share_url=f"https://vialo.place/r/{share_id}",
                    deletion_token=deletion_token,
                )
            except ClientError as exc:
                if exc.response["Error"]["Code"] != "TransactionCanceledException":
                    raise
                claim = self._table.get_item(Key={"pk": proof_key}, ConsistentRead=True).get("Item")
                if claim and _item_int(claim, "expiresAt") > int(time.time()):
                    existing_share_id = str(claim.get("shareId", ""))
                    if existing_share_id:
                        return CreateShareResponse(
                            share_id=existing_share_id,
                            share_url=f"https://vialo.place/r/{existing_share_id}",
                            deletion_token="",
                        )
                # No proof claim means the generated share ID collided; retry the
                # entire atomic transaction with a new ID.

        raise RuntimeError("Could not allocate a unique share ID")

    def get(self, share_id: str) -> ItineraryResponse | None:
        item = self._table.get_item(Key={"pk": f"SHARE#{share_id}"}).get("Item")
        if not item or _item_int(item, "expiresAt") <= int(time.time()):
            return None
        response = item.get("response")
        if not response:
            return None
        return ItineraryResponse.model_validate_json(json.dumps(_decimal_to_native(response)))

    def delete(self, share_id: str, deletion_token: str) -> bool:
        item = self._table.get_item(Key={"pk": f"SHARE#{share_id}"}).get("Item")
        if not item:
            return False
        expected = str(item.get("deleteTokenDigest", ""))
        if not hmac.compare_digest(expected, self._delete_digest(deletion_token)):
            return False
        try:
            self._table.delete_item(
                Key={"pk": f"SHARE#{share_id}"},
                ConditionExpression="attribute_exists(pk)",
            )
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise
