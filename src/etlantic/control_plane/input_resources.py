"""Immutable, owner-scoped input uploads and retention leases.

Upload metadata is safe to persist in accepted envelopes. Input bytes remain
behind the resource-store boundary and are returned only after scope, owner,
version, length and digest validation.
"""

from __future__ import annotations

import hashlib
import hmac
import threading
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext

INPUT_RESOURCE_REFERENCE_SCHEMA = "etlantic.control_plane.input_resource_ref/1"
SUPPORTED_INPUT_FORMATS = frozenset({"csv"})
SUPPORTED_INPUT_MEDIA_TYPES = frozenset({"text/csv", "application/csv"})


def _time(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return value.astimezone(UTC)


def _iso(value: datetime) -> str:
    return _time(value).isoformat().replace("+00:00", "Z")


def _parse_time(value: str) -> datetime:
    return _time(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _owner(ctx: ControlPlaneContext) -> str:
    owner = ctx.resource_owner_id or ctx.principal.subject
    if not owner.strip():
        raise ControlPlaneError(
            "Authenticated resource owner is required",
            code="PMRES403",
            status=403,
            title="Forbidden",
            type="etlantic.control_plane/forbidden",
        )
    return owner


@dataclass(frozen=True, slots=True)
class InputResourceReference:
    """A finalized immutable input identity with no physical storage locator."""

    resource_id: str
    version: str
    sha256: str
    byte_length: int
    tenant_id: str
    workspace_id: str
    owner_id: str
    media_type: str
    format: str
    finalized_at: str
    schema: str = INPUT_RESOURCE_REFERENCE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != INPUT_RESOURCE_REFERENCE_SCHEMA:
            raise ValueError("unsupported input resource reference schema")
        if len(self.resource_id) != 32:
            raise ValueError("resource_id must be an opaque 128-bit identifier")
        try:
            int(self.resource_id, 16)
        except ValueError as exc:
            raise ValueError(
                "resource_id must be an opaque 128-bit identifier"
            ) from exc
        if not self.owner_id:
            raise ValueError("owner_id must be non-empty")
        if self.version != f"sha256:{self.sha256}" or len(self.sha256) != 64:
            raise ValueError("input resource version must bind its SHA-256 digest")
        try:
            int(self.sha256, 16)
        except ValueError as exc:
            raise ValueError("input resource digest must be hexadecimal") from exc
        if type(self.byte_length) is not int or self.byte_length < 0:
            raise ValueError("input resource byte_length must be non-negative")
        if not self.tenant_id or not self.workspace_id:
            raise ValueError("input resource scope must be non-empty")
        if self.format not in SUPPORTED_INPUT_FORMATS:
            raise ValueError("unsupported input resource format")
        if self.media_type not in SUPPORTED_INPUT_MEDIA_TYPES:
            raise ValueError("unsupported input resource media type")
        _parse_time(self.finalized_at)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "resource_id": self.resource_id,
            "version": self.version,
            "sha256": self.sha256,
            "byte_length": self.byte_length,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "owner_id": self.owner_id,
            "media_type": self.media_type,
            "format": self.format,
            "finalized_at": self.finalized_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> InputResourceReference:
        expected_fields = {
            "schema",
            "resource_id",
            "version",
            "sha256",
            "byte_length",
            "tenant_id",
            "workspace_id",
            "owner_id",
            "media_type",
            "format",
            "finalized_at",
        }
        if set(data) != expected_fields:
            raise ValueError("input resource reference has unsupported fields")
        text_fields = (
            "schema",
            "resource_id",
            "version",
            "sha256",
            "tenant_id",
            "workspace_id",
            "owner_id",
            "media_type",
            "format",
            "finalized_at",
        )
        if any(not isinstance(data.get(key), str) for key in text_fields):
            raise ValueError("input resource reference has invalid field types")
        length = data.get("byte_length")
        if type(length) is not int:
            raise ValueError("input resource byte_length must be an integer")
        return cls(
            schema=str(data["schema"]),
            resource_id=str(data["resource_id"]),
            version=str(data["version"]),
            sha256=str(data["sha256"]),
            byte_length=length,
            tenant_id=str(data["tenant_id"]),
            workspace_id=str(data["workspace_id"]),
            owner_id=str(data["owner_id"]),
            media_type=str(data["media_type"]),
            format=str(data["format"]),
            finalized_at=str(data["finalized_at"]),
        )


@dataclass(frozen=True, slots=True)
class InputUploadReceipt:
    """Safe upload status returned by staging/finalization operations."""

    upload_id: str
    status: str
    byte_length: int
    expires_at: str
    reference: InputResourceReference | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "upload_id": self.upload_id,
            "status": self.status,
            "byte_length": self.byte_length,
            "expires_at": self.expires_at,
            "reference": self.reference.to_dict() if self.reference else None,
        }


@dataclass(frozen=True, slots=True)
class InputResourceCleanupResult:
    deleted_upload_ids: tuple[str, ...] = ()
    remaining_candidates: int = 0


@runtime_checkable
class InputResourceStore(Protocol):
    """Owner-scoped staged/finalized input store with durable run leases."""

    def stage(
        self,
        ctx: ControlPlaneContext,
        content: bytes,
        *,
        media_type: str,
        format: str,
        expires_at: datetime,
    ) -> InputUploadReceipt:
        """Persist bounded staged bytes under the authenticated owner scope."""
        ...

    def abort(self, ctx: ControlPlaneContext, upload_id: str) -> None:
        """Discard staged bytes without permitting mutation of finalized data."""
        ...

    def finalize(
        self,
        ctx: ControlPlaneContext,
        upload_id: str,
        *,
        expected_sha256: str,
        expected_byte_length: int,
        now: datetime | None = None,
    ) -> InputResourceReference:
        """Verify staged bytes and return their immutable owner-bound identity."""
        ...

    def read(
        self,
        ctx: ControlPlaneContext,
        reference: InputResourceReference,
        *,
        now: datetime | None = None,
    ) -> bytes:
        """Read one finalized version after exact scope/owner/digest checks."""
        ...

    def read_leased(
        self,
        ctx: ControlPlaneContext,
        reference: InputResourceReference,
        *,
        lease_id: str,
        now: datetime | None = None,
    ) -> bytes:
        """Read a worker-owned immutable version under its exact live run lease."""
        ...

    def verify_reference(
        self,
        ctx: ControlPlaneContext,
        reference: InputResourceReference,
        *,
        now: datetime | None = None,
    ) -> None:
        """Verify owner, scope, finalization and live retention before acceptance."""
        ...

    def acquire_lease(
        self,
        ctx: ControlPlaneContext,
        reference: InputResourceReference,
        *,
        lease_id: str,
        retain_until: datetime,
    ) -> None:
        """Protect an accepted, retryable or replayable input reference."""
        ...

    def release_lease(self, ctx: ControlPlaneContext, *, lease_id: str) -> None:
        """Release every input associated with one terminal retention lease."""
        ...

    def cleanup(
        self,
        ctx: ControlPlaneContext,
        *,
        now: datetime,
        limit: int,
    ) -> InputResourceCleanupResult:
        """Delete expired staged or unleased finalized inputs in a bounded batch."""
        ...


@dataclass(slots=True)
class _MemoryUpload:
    upload_id: str
    tenant_id: str
    workspace_id: str
    owner_id: str
    content: bytes
    media_type: str
    format: str
    expires_at: str
    reference: InputResourceReference | None = None


def _new_memory_uploads() -> dict[str, _MemoryUpload]:
    return {}


def _new_memory_leases() -> dict[tuple[str, str, str], dict[str, str]]:
    return {}


@dataclass
class MemoryInputResourceStore:
    """Thread-safe reference implementation for tests and small deployments."""

    max_upload_bytes: int = 64 * 1024 * 1024
    _uploads: dict[str, _MemoryUpload] = field(
        default_factory=_new_memory_uploads, repr=False
    )
    _leases: dict[tuple[str, str, str], dict[str, str]] = field(
        default_factory=_new_memory_leases, repr=False
    )
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def __post_init__(self) -> None:
        if type(self.max_upload_bytes) is not int or self.max_upload_bytes < 1:
            raise ValueError("max_upload_bytes must be a positive integer")

    def stage(
        self,
        ctx: ControlPlaneContext,
        content: bytes,
        *,
        media_type: str,
        format: str,
        expires_at: datetime,
    ) -> InputUploadReceipt:
        owner_id = _owner(ctx)
        if len(content) > self.max_upload_bytes:
            raise ControlPlaneError(
                "Input upload exceeds the configured byte limit",
                code="PMRES413",
                status=413,
                title="Payload Too Large",
                type="etlantic.control_plane/payload_too_large",
            )
        if (
            media_type not in SUPPORTED_INPUT_MEDIA_TYPES
            or format not in SUPPORTED_INPUT_FORMATS
        ):
            raise ControlPlaneError(
                "Unsupported input resource media type or format",
                code="PMRES415",
                status=415,
                title="Unsupported Media Type",
                type="etlantic.control_plane/unsupported_media_type",
            )
        expiry = _time(expires_at)
        if expiry <= datetime.now(UTC):
            raise ControlPlaneError.conflict(
                "Input upload expiry must be in the future"
            )
        upload_id = uuid.uuid4().hex
        upload = _MemoryUpload(
            upload_id=upload_id,
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            owner_id=owner_id,
            content=bytes(content),
            media_type=media_type,
            format=format,
            expires_at=_iso(expiry),
        )
        with self._lock:
            self._uploads[upload_id] = upload
        return InputUploadReceipt(upload_id, "staged", len(content), upload.expires_at)

    def finalize(
        self,
        ctx: ControlPlaneContext,
        upload_id: str,
        *,
        expected_sha256: str,
        expected_byte_length: int,
        now: datetime | None = None,
    ) -> InputResourceReference:
        with self._lock:
            upload = self._get_upload(ctx, upload_id)
            current = _time(now or datetime.now(UTC))
            if type(expected_byte_length) is not int or not _valid_digest(
                expected_sha256
            ):
                raise _checksum_error()
            if _parse_time(upload.expires_at) <= current:
                if upload.reference is not None:
                    digest = hashlib.sha256(upload.content).hexdigest()
                    if (
                        expected_byte_length == upload.reference.byte_length
                        and _valid_digest(expected_sha256)
                        and hmac.compare_digest(digest, expected_sha256.lower())
                        and digest == upload.reference.sha256
                    ):
                        return upload.reference
                raise ControlPlaneError(
                    "Staged input upload has expired",
                    code="PMRES410",
                    status=410,
                    title="Gone",
                    type="etlantic.control_plane/input_expired",
                )
            digest = hashlib.sha256(upload.content).hexdigest()
            if (
                expected_byte_length != len(upload.content)
                or not _valid_digest(expected_sha256)
                or not hmac.compare_digest(digest, expected_sha256.lower())
            ):
                raise _checksum_error()
            reference = InputResourceReference(
                resource_id=upload.upload_id,
                version=f"sha256:{digest}",
                sha256=digest,
                byte_length=len(upload.content),
                tenant_id=upload.tenant_id,
                workspace_id=upload.workspace_id,
                owner_id=upload.owner_id,
                media_type=upload.media_type,
                format=upload.format,
                finalized_at=_iso(current),
            )
            if upload.reference is not None and upload.reference != reference:
                if (
                    upload.reference.sha256 != digest
                    or upload.reference.byte_length != len(upload.content)
                ):
                    raise ControlPlaneError.conflict(
                        "Finalized input resource cannot be changed"
                    )
                return upload.reference
            upload.reference = reference
            return reference

    def read(
        self,
        ctx: ControlPlaneContext,
        reference: InputResourceReference,
        *,
        now: datetime | None = None,
    ) -> bytes:
        with self._lock:
            upload = self._get_upload(ctx, reference.resource_id)
            self._verify_reference(ctx, upload, reference)
            expiry = _parse_time(upload.expires_at)
            if expiry <= _time(now or datetime.now(UTC)) and not self._has_live_lease(
                upload, now or datetime.now(UTC)
            ):
                raise _expired_input()
            if len(upload.content) != reference.byte_length or not hmac.compare_digest(
                hashlib.sha256(upload.content).hexdigest(), reference.sha256
            ):
                raise ControlPlaneError.conflict(
                    "Stored input resource failed integrity verification"
                )
            return bytes(upload.content)

    def read_leased(
        self,
        ctx: ControlPlaneContext,
        reference: InputResourceReference,
        *,
        lease_id: str,
        now: datetime | None = None,
    ) -> bytes:
        if not lease_id.strip():
            raise ValueError("lease_id must be non-empty")
        current = _time(now or datetime.now(UTC))
        with self._lock:
            upload = self._uploads.get(reference.resource_id)
            if (
                upload is None
                or (upload.tenant_id, upload.workspace_id) != ctx.scope_key
            ):
                raise ControlPlaneError.not_found("Input resource not found")
            self._verify_reference(ctx, upload, reference, allow_different_owner=True)
            key = (upload.tenant_id, upload.workspace_id, upload.upload_id)
            expiry = self._leases.get(key, {}).get(lease_id)
            if expiry is None or _parse_time(expiry) <= current:
                self._has_live_lease(upload, current)
                raise _expired_input()
            if len(upload.content) != reference.byte_length or not hmac.compare_digest(
                hashlib.sha256(upload.content).hexdigest(), reference.sha256
            ):
                raise ControlPlaneError.conflict(
                    "Stored input resource failed integrity verification"
                )
            return bytes(upload.content)

    def abort(self, ctx: ControlPlaneContext, upload_id: str) -> None:
        with self._lock:
            upload = self._get_upload(ctx, upload_id)
            if upload.reference is not None:
                raise ControlPlaneError.conflict(
                    "Finalized input resources cannot be aborted"
                )
            self._uploads.pop(upload_id, None)

    def verify_reference(
        self,
        ctx: ControlPlaneContext,
        reference: InputResourceReference,
        *,
        now: datetime | None = None,
    ) -> None:
        current = now or datetime.now(UTC)
        with self._lock:
            upload = self._get_upload(ctx, reference.resource_id)
            self._verify_reference(ctx, upload, reference)
            if _parse_time(upload.expires_at) <= _time(
                current
            ) and not self._has_live_lease(upload, current):
                raise _expired_input()

    def acquire_lease(
        self,
        ctx: ControlPlaneContext,
        reference: InputResourceReference,
        *,
        lease_id: str,
        retain_until: datetime,
    ) -> None:
        if not lease_id.strip():
            raise ValueError("lease_id must be non-empty")
        expiry = _time(retain_until)
        if expiry <= datetime.now(UTC):
            raise ValueError("retain_until must be in the future")
        with self._lock:
            upload = self._get_upload(ctx, reference.resource_id)
            self._verify_reference(ctx, upload, reference)
            current = datetime.now(UTC)
            if _parse_time(upload.expires_at) <= current and not self._has_live_lease(
                upload, current
            ):
                raise _expired_input()
            key = (upload.tenant_id, upload.workspace_id, upload.upload_id)
            leases = self._leases.setdefault(key, {})
            prior = leases.get(lease_id)
            encoded = _iso(expiry)
            if prior is not None and prior != encoded:
                leases[lease_id] = max(prior, encoded)
            else:
                leases[lease_id] = encoded

    def release_lease(self, ctx: ControlPlaneContext, *, lease_id: str) -> None:
        owner = _owner(ctx)
        with self._lock:
            keys = [
                key
                for key, leases in self._leases.items()
                if key[:2] == ctx.scope_key
                and lease_id in leases
                and self._uploads.get(key[2], None) is not None
                and self._uploads[key[2]].owner_id == owner
            ]
            for key in keys:
                self._leases[key].pop(lease_id, None)
                if not self._leases[key]:
                    self._leases.pop(key, None)

    def cleanup(
        self,
        ctx: ControlPlaneContext,
        *,
        now: datetime,
        limit: int,
    ) -> InputResourceCleanupResult:
        if type(limit) is not int or limit < 1 or limit > 10_000:
            raise ValueError("cleanup limit must be between 1 and 10000")
        current = _time(now)
        with self._lock:
            candidates = [
                upload
                for upload in self._uploads.values()
                if (upload.tenant_id, upload.workspace_id) == ctx.scope_key
                and upload.owner_id == _owner(ctx)
                and _parse_time(upload.expires_at) <= current
                and not self._has_live_lease(upload, current)
            ]
            candidates.sort(key=lambda item: (item.expires_at, item.upload_id))
            selected = candidates[:limit]
            for upload in selected:
                self._uploads.pop(upload.upload_id, None)
                self._leases.pop(
                    (upload.tenant_id, upload.workspace_id, upload.upload_id), None
                )
            return InputResourceCleanupResult(
                deleted_upload_ids=tuple(item.upload_id for item in selected),
                remaining_candidates=max(0, len(candidates) - len(selected)),
            )

    def _get_upload(self, ctx: ControlPlaneContext, upload_id: str) -> _MemoryUpload:
        upload = self._uploads.get(upload_id)
        if (
            upload is None
            or (upload.tenant_id, upload.workspace_id) != ctx.scope_key
            or upload.owner_id != _owner(ctx)
        ):
            raise ControlPlaneError.not_found("Input resource not found")
        return upload

    @staticmethod
    def _verify_reference(
        ctx: ControlPlaneContext,
        upload: _MemoryUpload,
        reference: InputResourceReference,
        *,
        allow_different_owner: bool = False,
    ) -> None:
        expected_owner = reference.owner_id if allow_different_owner else _owner(ctx)
        if (
            upload.reference is None
            or upload.reference != reference
            or reference.tenant_id != ctx.tenant.tenant_id
            or reference.workspace_id != ctx.workspace.workspace_id
            or reference.owner_id != expected_owner
            or upload.owner_id != expected_owner
        ):
            raise ControlPlaneError.conflict(
                "Input resource reference does not match its finalized owner-bound version"
            )

    def _has_live_lease(self, upload: _MemoryUpload, now: datetime) -> bool:
        key = (upload.tenant_id, upload.workspace_id, upload.upload_id)
        leases = self._leases.get(key, {})
        current = _time(now)
        live = {
            lease: expiry
            for lease, expiry in leases.items()
            if _parse_time(expiry) > current
        }
        if live:
            self._leases[key] = live
        else:
            self._leases.pop(key, None)
        return bool(live)


def _valid_digest(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _checksum_error() -> ControlPlaneError:
    return ControlPlaneError.conflict(
        "Input upload checksum or length verification failed"
    )


def _expired_input() -> ControlPlaneError:
    return ControlPlaneError(
        "Input resource retention has expired",
        code="PMRES410",
        status=410,
        title="Gone",
        type="etlantic.control_plane/input_expired",
    )


__all__ = [
    "INPUT_RESOURCE_REFERENCE_SCHEMA",
    "SUPPORTED_INPUT_FORMATS",
    "SUPPORTED_INPUT_MEDIA_TYPES",
    "InputResourceCleanupResult",
    "InputResourceReference",
    "InputResourceStore",
    "InputUploadReceipt",
    "MemoryInputResourceStore",
]
