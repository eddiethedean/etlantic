"""In-memory S3 fake: multipart abort + conditional commit pointers."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Any


def boto3_available() -> bool:
    """Return True when boto3 can be imported (live path opt-in)."""
    try:
        import boto3  # noqa: F401
    except ImportError:
        return False
    return True


@dataclass
class _MultipartUpload:
    upload_id: str
    bucket: str
    key: str
    parts: dict[int, bytes] = field(default_factory=dict)
    aborted: bool = False
    completed: bool = False


@dataclass
class InMemoryS3Fake:
    """Deterministic S3 stub for unit tests (no network).

    Semantics mirrored for CI:

    - Multipart uploads stage parts until complete or abort.
    - Abort discards parts and marks the upload aborted (orphan cleanup).
    - Commit pointers use conditional put (If-None-Match ``*`` by default):
      only one winner; losers see a precondition failure for reconciliation.
    - Readers resolve only the committed pointer, never incomplete multipart
      staging keys.
    """

    objects: dict[tuple[str, str], bytes] = field(default_factory=dict)
    etags: dict[tuple[str, str], str] = field(default_factory=dict)
    multiparts: dict[str, _MultipartUpload] = field(default_factory=dict)
    commit_pointers: dict[tuple[str, str], str] = field(default_factory=dict)
    _ops: list[dict[str, Any]] = field(default_factory=list, repr=False)

    def create_multipart_upload(self, *, bucket: str, key: str) -> str:
        upload_id = f"mpu-{uuid.uuid4().hex[:12]}"
        self.multiparts[upload_id] = _MultipartUpload(
            upload_id=upload_id, bucket=bucket, key=key
        )
        self._ops.append(
            {"op": "create_multipart_upload", "bucket": bucket, "key": key}
        )
        return upload_id

    def upload_part(
        self,
        *,
        upload_id: str,
        part_number: int,
        body: bytes,
    ) -> str:
        upload = self._require_open_multipart(upload_id)
        upload.parts[int(part_number)] = bytes(body)
        etag = _etag(body)
        self._ops.append(
            {
                "op": "upload_part",
                "upload_id": upload_id,
                "part_number": part_number,
                "bytes": len(body),
            }
        )
        return etag

    def complete_multipart_upload(self, *, upload_id: str) -> str:
        upload = self._require_open_multipart(upload_id)
        ordered = [upload.parts[n] for n in sorted(upload.parts)]
        payload = b"".join(ordered)
        key = (upload.bucket, upload.key)
        self.objects[key] = payload
        etag = _etag(payload)
        self.etags[key] = etag
        upload.completed = True
        self._ops.append(
            {
                "op": "complete_multipart_upload",
                "upload_id": upload_id,
                "etag": etag,
                "bytes": len(payload),
            }
        )
        return etag

    def abort_multipart_upload(self, *, upload_id: str) -> None:
        upload = self.multiparts.get(upload_id)
        if upload is None:
            return
        upload.parts.clear()
        upload.aborted = True
        self._ops.append({"op": "abort_multipart_upload", "upload_id": upload_id})

    def put_object(self, *, bucket: str, key: str, body: bytes) -> str:
        loc = (bucket, key)
        payload = bytes(body)
        etag = _etag(payload)
        self.objects[loc] = payload
        self.etags[loc] = etag
        self._ops.append(
            {"op": "put_object", "bucket": bucket, "key": key, "bytes": len(payload)}
        )
        return etag

    def put_commit_pointer(
        self,
        *,
        bucket: str,
        pointer_key: str,
        data_key: str,
        if_none_match: bool = True,
    ) -> dict[str, Any]:
        """Conditionally publish a commit pointer to an immutable data object.

        When ``if_none_match`` is True (default), succeeds only if the pointer
        does not already exist — concurrent losers get ``precondition_failed``.
        """
        ptr = (bucket, pointer_key)
        if if_none_match and ptr in self.commit_pointers:
            self._ops.append(
                {
                    "op": "put_commit_pointer",
                    "status": "precondition_failed",
                    "bucket": bucket,
                    "pointer_key": pointer_key,
                }
            )
            return {
                "ok": False,
                "status": "precondition_failed",
                "existing": self.commit_pointers[ptr],
            }
        data_loc = (bucket, data_key)
        if data_loc not in self.objects:
            raise KeyError(f"data object missing: s3://{bucket}/{data_key}")
        self.commit_pointers[ptr] = data_key
        # Pointer object itself is a small marker for inspect/list symmetry.
        marker = data_key.encode("utf-8")
        self.objects[ptr] = marker
        self.etags[ptr] = _etag(marker)
        self._ops.append(
            {
                "op": "put_commit_pointer",
                "status": "ok",
                "bucket": bucket,
                "pointer_key": pointer_key,
                "data_key": data_key,
            }
        )
        return {
            "ok": True,
            "status": "ok",
            "data_key": data_key,
            "etag": self.etags[ptr],
        }

    def get_committed_object(
        self, *, bucket: str, pointer_key: str
    ) -> tuple[str, bytes] | None:
        """Resolve pointer → immutable object; ignore incomplete multipart keys."""
        data_key = self.commit_pointers.get((bucket, pointer_key))
        if data_key is None:
            return None
        payload = self.objects.get((bucket, data_key))
        if payload is None:
            return None
        return data_key, payload

    def get_object(self, *, bucket: str, key: str) -> bytes | None:
        return self.objects.get((bucket, key))

    def delete_object(self, *, bucket: str, key: str) -> None:
        self.objects.pop((bucket, key), None)
        self.etags.pop((bucket, key), None)
        self.commit_pointers.pop((bucket, key), None)
        self._ops.append({"op": "delete_object", "bucket": bucket, "key": key})

    def list_operations(self) -> list[dict[str, Any]]:
        return list(self._ops)

    def _require_open_multipart(self, upload_id: str) -> _MultipartUpload:
        upload = self.multiparts.get(upload_id)
        if upload is None:
            raise KeyError(f"unknown multipart upload_id={upload_id!r}")
        if upload.aborted:
            raise RuntimeError(f"multipart upload aborted: {upload_id}")
        if upload.completed:
            raise RuntimeError(f"multipart upload already completed: {upload_id}")
        return upload


def _etag(body: bytes) -> str:
    return hashlib.md5(body, usedforsecurity=False).hexdigest()


__all__ = ["InMemoryS3Fake", "boto3_available"]
