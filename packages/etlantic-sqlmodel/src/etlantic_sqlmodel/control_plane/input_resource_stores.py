"""SQLModel-package persistence for immutable scoped input resources."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import (
    Column,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    delete,
    exists,
    func,
    select,
    update,
)
from sqlalchemy.engine import Engine

from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.input_resources import (
    SUPPORTED_INPUT_FORMATS,
    SUPPORTED_INPUT_MEDIA_TYPES,
    InputResourceCleanupResult,
    InputResourceReference,
    InputUploadReceipt,
)
from etlantic.control_plane.models import ControlPlaneContext


def _tables() -> tuple[Table, Table]:
    metadata = MetaData()
    uploads = Table(
        "cp_input_uploads",
        metadata,
        Column("upload_id", String(64), primary_key=True),
        Column("tenant_id", String(), nullable=False, index=True),
        Column("workspace_id", String(), nullable=False, index=True),
        Column("owner_id", String(), nullable=False, index=True),
        Column("status", String(16), nullable=False),
        Column("media_type", String(255), nullable=False),
        Column("format", String(32), nullable=False),
        Column("content", LargeBinary(), nullable=False),
        Column("byte_length", Integer(), nullable=False),
        Column("sha256", String(64), nullable=True),
        Column("version", String(72), nullable=True),
        Column("reference_json", Text(), nullable=True),
        Column("created_at", String(40), nullable=False),
        Column("expires_at", String(40), nullable=False),
        Column("finalized_at", String(40), nullable=True),
    )
    leases = Table(
        "cp_input_resource_leases",
        metadata,
        Column("id", Integer(), primary_key=True),
        Column("tenant_id", String(), nullable=False, index=True),
        Column("workspace_id", String(), nullable=False, index=True),
        Column("owner_id", String(), nullable=False, index=True),
        Column("upload_id", String(64), nullable=False, index=True),
        Column("lease_id", String(255), nullable=False),
        Column("retain_until", String(40), nullable=False),
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "owner_id",
            "upload_id",
            "lease_id",
            name="uq_cp_input_resource_lease",
        ),
    )
    return uploads, leases


# The provider exposes its table metadata so schema inspection can remain
# provider-owned without depending on an internal helper.
INPUT_RESOURCE_TABLES = _tables()


def _iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _owner(ctx: ControlPlaneContext) -> str:
    return ctx.resource_owner_id or ctx.principal.identity_key


class SqlModelInputResourceStore:
    """Durable upload bytes and run leases scoped by tenant/workspace/owner.

    The table stores bytes in the configured relational database. A deployment
    that uses object storage can implement the same core ``InputResourceStore``
    contract without changing accepted resource references.
    """

    def __init__(self, engine: Engine, *, max_upload_bytes: int = 64 * 1024 * 1024):
        if type(max_upload_bytes) is not int or max_upload_bytes < 1:
            raise ValueError("max_upload_bytes must be a positive integer")
        self.engine = engine
        self.max_upload_bytes = max_upload_bytes
        self.uploads, self.leases = INPUT_RESOURCE_TABLES

    def stage(
        self,
        ctx: ControlPlaneContext,
        content: bytes,
        *,
        media_type: str,
        format: str,
        expires_at: datetime,
    ) -> InputUploadReceipt:
        if not isinstance(content, bytes) or len(content) > self.max_upload_bytes:
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
        now = datetime.now(UTC)
        expiry = _iso(expires_at)
        if datetime.fromisoformat(expiry.replace("Z", "+00:00")) <= now:
            raise ControlPlaneError.conflict(
                "Input upload expiry must be in the future"
            )
        upload_id = uuid.uuid4().hex
        created_at = _iso(now)
        with self.engine.begin() as connection:
            connection.execute(
                self.uploads.insert().values(
                    upload_id=upload_id,
                    tenant_id=ctx.tenant.tenant_id,
                    workspace_id=ctx.workspace.workspace_id,
                    owner_id=_owner(ctx),
                    status="staged",
                    media_type=media_type,
                    format=format,
                    content=content,
                    byte_length=len(content),
                    created_at=created_at,
                    expires_at=expiry,
                )
            )
        return InputUploadReceipt(upload_id, "staged", len(content), expiry)

    def abort(self, ctx: ControlPlaneContext, upload_id: str) -> None:
        with self.engine.begin() as connection:
            row = connection.execute(
                select(self.uploads.c.status)
                .where(
                    self.uploads.c.upload_id == upload_id,
                    self.uploads.c.tenant_id == ctx.tenant.tenant_id,
                    self.uploads.c.workspace_id == ctx.workspace.workspace_id,
                    self.uploads.c.owner_id == _owner(ctx),
                )
                .with_for_update()
            ).first()
            if row is None:
                raise ControlPlaneError.not_found("Input resource not found")
            if row[0] != "staged":
                raise ControlPlaneError.conflict(
                    "Finalized input resources cannot be aborted"
                )
            connection.execute(
                delete(self.uploads).where(
                    self.uploads.c.upload_id == upload_id,
                    self.uploads.c.tenant_id == ctx.tenant.tenant_id,
                    self.uploads.c.workspace_id == ctx.workspace.workspace_id,
                    self.uploads.c.owner_id == _owner(ctx),
                )
            )

    def finalize(
        self,
        ctx: ControlPlaneContext,
        upload_id: str,
        *,
        expected_sha256: str,
        expected_byte_length: int,
        now: datetime | None = None,
    ) -> InputResourceReference:
        current = _iso(now or datetime.now(UTC))
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    select(self.uploads)
                    .where(
                        self.uploads.c.upload_id == upload_id,
                        self.uploads.c.tenant_id == ctx.tenant.tenant_id,
                        self.uploads.c.workspace_id == ctx.workspace.workspace_id,
                        self.uploads.c.owner_id == _owner(ctx),
                    )
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ControlPlaneError.not_found("Input resource not found")
            if row["status"] == "finalized":
                stored = InputResourceReference.from_dict(
                    json.loads(str(row["reference_json"]))
                )
                if (
                    type(expected_byte_length) is not int
                    or expected_byte_length != stored.byte_length
                    or not _valid_digest(expected_sha256)
                    or not hmac.compare_digest(expected_sha256.lower(), stored.sha256)
                ):
                    raise ControlPlaneError.conflict(
                        "Finalized input resource cannot be changed"
                    )
                return stored
            if row["status"] != "staged":
                raise ControlPlaneError.conflict("Input upload is not staged")
            if str(row["expires_at"]) <= current:
                raise _expired_upload()
            content = bytes(row["content"])
            digest = hashlib.sha256(content).hexdigest()
            if (
                type(expected_byte_length) is not int
                or expected_byte_length != len(content)
                or not _valid_digest(expected_sha256)
                or not hmac.compare_digest(digest, expected_sha256.lower())
            ):
                raise ControlPlaneError.conflict(
                    "Input upload checksum or length verification failed"
                )
            reference = InputResourceReference(
                resource_id=upload_id,
                version=f"sha256:{digest}",
                sha256=digest,
                byte_length=len(content),
                tenant_id=ctx.tenant.tenant_id,
                workspace_id=ctx.workspace.workspace_id,
                owner_id=_owner(ctx),
                media_type=str(row["media_type"]),
                format=str(row["format"]),
                finalized_at=current,
            )
            connection.execute(
                update(self.uploads)
                .where(self.uploads.c.upload_id == upload_id)
                .values(
                    status="finalized",
                    sha256=digest,
                    version=reference.version,
                    reference_json=json.dumps(
                        reference.to_dict(),
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    finalized_at=current,
                )
            )
            return reference

    def read(
        self,
        ctx: ControlPlaneContext,
        reference: InputResourceReference,
        *,
        now: datetime | None = None,
    ) -> bytes:
        current = _iso(now or datetime.now(UTC))
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    select(self.uploads).where(
                        self.uploads.c.upload_id == reference.resource_id,
                        self.uploads.c.tenant_id == ctx.tenant.tenant_id,
                        self.uploads.c.workspace_id == ctx.workspace.workspace_id,
                        self.uploads.c.owner_id == _owner(ctx),
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ControlPlaneError.not_found("Input resource not found")
            self._verify_row_reference(ctx, row, reference)
            active_lease = connection.execute(
                select(self.leases.c.id)
                .where(
                    self.leases.c.tenant_id == ctx.tenant.tenant_id,
                    self.leases.c.workspace_id == ctx.workspace.workspace_id,
                    self.leases.c.owner_id == _owner(ctx),
                    self.leases.c.upload_id == reference.resource_id,
                    self.leases.c.retain_until > current,
                )
                .limit(1)
            ).first()
            if str(row["expires_at"]) <= current and active_lease is None:
                raise _expired_upload()
            content = bytes(row["content"])
            digest = hashlib.sha256(content).hexdigest()
            if len(content) != reference.byte_length or not hmac.compare_digest(
                digest, reference.sha256
            ):
                raise ControlPlaneError.conflict(
                    "Stored input resource failed integrity verification"
                )
            return content

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
        current = _iso(now or datetime.now(UTC))
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    select(self.uploads).where(
                        self.uploads.c.upload_id == reference.resource_id,
                        self.uploads.c.tenant_id == ctx.tenant.tenant_id,
                        self.uploads.c.workspace_id == ctx.workspace.workspace_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ControlPlaneError.not_found("Input resource not found")
            self._verify_row_reference(
                ctx,
                cast(Mapping[str, Any], row),
                reference,
                allow_different_owner=True,
            )
            active_lease = connection.execute(
                select(self.leases.c.id)
                .where(
                    self.leases.c.tenant_id == ctx.tenant.tenant_id,
                    self.leases.c.workspace_id == ctx.workspace.workspace_id,
                    self.leases.c.owner_id == reference.owner_id,
                    self.leases.c.upload_id == reference.resource_id,
                    self.leases.c.lease_id == lease_id,
                    self.leases.c.retain_until > current,
                )
                .limit(1)
            ).first()
            if active_lease is None:
                raise _expired_upload()
            content = bytes(row["content"])
            digest = hashlib.sha256(content).hexdigest()
            if len(content) != reference.byte_length or not hmac.compare_digest(
                digest, reference.sha256
            ):
                raise ControlPlaneError.conflict(
                    "Stored input resource failed integrity verification"
                )
            return content

    def verify_reference(
        self,
        ctx: ControlPlaneContext,
        reference: InputResourceReference,
        *,
        now: datetime | None = None,
    ) -> None:
        current = _iso(now or datetime.now(UTC))
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    select(self.uploads).where(
                        self.uploads.c.upload_id == reference.resource_id,
                        self.uploads.c.tenant_id == ctx.tenant.tenant_id,
                        self.uploads.c.workspace_id == ctx.workspace.workspace_id,
                        self.uploads.c.owner_id == _owner(ctx),
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ControlPlaneError.not_found("Input resource not found")
            self._verify_row_reference(ctx, row, reference)
            if str(row["expires_at"]) <= current:
                active = connection.execute(
                    select(self.leases.c.id)
                    .where(
                        self.leases.c.tenant_id == ctx.tenant.tenant_id,
                        self.leases.c.workspace_id == ctx.workspace.workspace_id,
                        self.leases.c.owner_id == _owner(ctx),
                        self.leases.c.upload_id == reference.resource_id,
                        self.leases.c.retain_until > current,
                    )
                    .limit(1)
                ).first()
                if active is None:
                    raise _expired_upload()

    def acquire_lease(
        self,
        ctx: ControlPlaneContext,
        reference: InputResourceReference,
        *,
        lease_id: str,
        retain_until: datetime,
    ) -> None:
        self.acquire_leases(
            ctx, (reference,), lease_id=lease_id, retain_until=retain_until
        )

    def acquire_leases(
        self,
        ctx: ControlPlaneContext,
        references: Sequence[InputResourceReference],
        *,
        lease_id: str,
        retain_until: datetime,
    ) -> None:
        if not lease_id.strip():
            raise ValueError("lease_id must be non-empty")
        if not references:
            return
        retain = _iso(retain_until)
        current = _iso(datetime.now(UTC))
        if retain <= current:
            raise ValueError("retain_until must be in the future")
        owner_id = _owner(ctx)
        with self.engine.begin() as connection:
            prepared: list[tuple[InputResourceReference, Any | None]] = []
            for reference in references:
                row = (
                    connection.execute(
                        select(self.uploads)
                        .where(
                            self.uploads.c.upload_id == reference.resource_id,
                            self.uploads.c.tenant_id == ctx.tenant.tenant_id,
                            self.uploads.c.workspace_id == ctx.workspace.workspace_id,
                            self.uploads.c.owner_id == owner_id,
                        )
                        .with_for_update()
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise ControlPlaneError.not_found("Input resource not found")
                self._verify_row_reference(ctx, row, reference)
                existing = (
                    connection.execute(
                        select(self.leases)
                        .where(
                            self.leases.c.tenant_id == ctx.tenant.tenant_id,
                            self.leases.c.workspace_id == ctx.workspace.workspace_id,
                            self.leases.c.owner_id == owner_id,
                            self.leases.c.upload_id == reference.resource_id,
                            self.leases.c.lease_id == lease_id,
                        )
                        .with_for_update()
                    )
                    .mappings()
                    .one_or_none()
                )
                active_lease = connection.execute(
                    select(self.leases.c.id)
                    .where(
                        self.leases.c.tenant_id == ctx.tenant.tenant_id,
                        self.leases.c.workspace_id == ctx.workspace.workspace_id,
                        self.leases.c.owner_id == owner_id,
                        self.leases.c.upload_id == reference.resource_id,
                        self.leases.c.retain_until > current,
                    )
                    .limit(1)
                ).first()
                if str(row["expires_at"]) <= current and active_lease is None:
                    raise _expired_upload()
                prepared.append((reference, existing))
            for reference, existing in prepared:
                if existing is not None:
                    lease_retain = max(retain, str(existing["retain_until"]))
                    connection.execute(
                        update(self.leases)
                        .where(self.leases.c.id == existing["id"])
                        .values(retain_until=lease_retain)
                    )
                else:
                    connection.execute(
                        self.leases.insert().values(
                            tenant_id=ctx.tenant.tenant_id,
                            workspace_id=ctx.workspace.workspace_id,
                            owner_id=owner_id,
                            upload_id=reference.resource_id,
                            lease_id=lease_id,
                            retain_until=retain,
                        )
                    )

    def release_lease(self, ctx: ControlPlaneContext, *, lease_id: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                delete(self.leases).where(
                    self.leases.c.tenant_id == ctx.tenant.tenant_id,
                    self.leases.c.workspace_id == ctx.workspace.workspace_id,
                    self.leases.c.owner_id == _owner(ctx),
                    self.leases.c.lease_id == lease_id,
                )
            )

    def cleanup(
        self,
        ctx: ControlPlaneContext,
        *,
        now: datetime,
        limit: int,
    ) -> InputResourceCleanupResult:
        if type(limit) is not int or limit < 1 or limit > 10_000:
            raise ValueError("cleanup limit must be between 1 and 10000")
        current = _iso(now)
        active_lease = exists(
            select(self.leases.c.id).where(
                self.leases.c.tenant_id == self.uploads.c.tenant_id,
                self.leases.c.workspace_id == self.uploads.c.workspace_id,
                self.leases.c.owner_id == self.uploads.c.owner_id,
                self.leases.c.upload_id == self.uploads.c.upload_id,
                self.leases.c.retain_until > current,
            )
        )
        candidate = (
            select(self.uploads.c.upload_id)
            .where(
                self.uploads.c.tenant_id == ctx.tenant.tenant_id,
                self.uploads.c.workspace_id == ctx.workspace.workspace_id,
                self.uploads.c.owner_id == _owner(ctx),
                self.uploads.c.expires_at <= current,
                ~active_lease,
            )
            .order_by(self.uploads.c.expires_at, self.uploads.c.upload_id)
            .with_for_update(skip_locked=True)
        )
        with self.engine.begin() as connection:
            ids = [
                str(row[0]) for row in connection.execute(candidate.limit(limit)).all()
            ]
            deleted: list[str] = []
            for upload_id in ids:
                result = connection.execute(
                    delete(self.uploads).where(
                        self.uploads.c.upload_id == upload_id,
                        self.uploads.c.tenant_id == ctx.tenant.tenant_id,
                        self.uploads.c.workspace_id == ctx.workspace.workspace_id,
                        self.uploads.c.owner_id == _owner(ctx),
                        self.uploads.c.expires_at <= current,
                        ~active_lease,
                    )
                )
                if result.rowcount:
                    deleted.append(upload_id)
                    connection.execute(
                        delete(self.leases).where(
                            self.leases.c.tenant_id == ctx.tenant.tenant_id,
                            self.leases.c.workspace_id == ctx.workspace.workspace_id,
                            self.leases.c.owner_id == _owner(ctx),
                            self.leases.c.upload_id == upload_id,
                        )
                    )
            remaining = connection.execute(
                select(func.count()).where(
                    self.uploads.c.tenant_id == ctx.tenant.tenant_id,
                    self.uploads.c.workspace_id == ctx.workspace.workspace_id,
                    self.uploads.c.owner_id == _owner(ctx),
                    self.uploads.c.expires_at <= current,
                    ~active_lease,
                )
            ).scalar_one()
        return InputResourceCleanupResult(
            deleted_upload_ids=tuple(deleted),
            remaining_candidates=int(remaining),
        )

    @staticmethod
    def _verify_row_reference(
        ctx: ControlPlaneContext,
        row: Mapping[str, Any],
        reference: InputResourceReference,
        *,
        allow_different_owner: bool = False,
    ) -> None:
        if row["status"] != "finalized" or not row["reference_json"]:
            raise ControlPlaneError.conflict("Input resource is not finalized")
        try:
            stored = InputResourceReference.from_dict(
                json.loads(str(row["reference_json"]))
            )
        except Exception as exc:
            raise ControlPlaneError.conflict(
                "Stored input resource reference is invalid"
            ) from exc
        expected_owner = reference.owner_id if allow_different_owner else _owner(ctx)
        if (
            stored != reference
            or stored.tenant_id != ctx.tenant.tenant_id
            or stored.workspace_id != ctx.workspace.workspace_id
            or stored.owner_id != expected_owner
            or row["owner_id"] != expected_owner
            or row["sha256"] != reference.sha256
            or row["version"] != reference.version
            or row["byte_length"] != reference.byte_length
        ):
            raise ControlPlaneError.conflict(
                "Input resource reference does not match its finalized owner-bound version"
            )


def _expired_upload() -> ControlPlaneError:
    return ControlPlaneError(
        "Input resource retention has expired",
        code="PMRES410",
        status=410,
        title="Gone",
        type="etlantic.control_plane/input_expired",
    )


def _valid_digest(value: str) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


__all__ = ["SqlModelInputResourceStore"]
