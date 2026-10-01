"""Owner isolation, immutable finalization and retention for input resources."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text

from etlantic.control_plane import (
    ControlPlaneContext,
    CorrelationKey,
    EnvironmentRef,
    IdempotencyKey,
    MemoryInputResourceStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.input_resources import InputResourceReference
from etlantic_sqlmodel.control_plane import SqlModelInputResourceStore
from etlantic_sqlmodel.migrations import current_version, upgrade


def _context(
    *,
    tenant: str = "uploads-tenant",
    workspace: str = "uploads-workspace",
    owner: str = "uploads-owner",
) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject=owner, kind="workload"),
        tenant=TenantRef(tenant),
        workspace=WorkspaceRef(tenant, workspace),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("uploads-domain"),
        correlation_key=CorrelationKey("upload-test"),
        idempotency_key=IdempotencyKey("upload-test"),
        resource_owner_id=owner,
    )


def _finalize(
    store: Any, ctx: ControlPlaneContext, content: bytes
) -> InputResourceReference:
    staged = store.stage(
        ctx,
        content,
        media_type="text/csv",
        format="csv",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    return store.finalize(
        ctx,
        staged.upload_id,
        expected_sha256=hashlib.sha256(content).hexdigest(),
        expected_byte_length=len(content),
    )


@pytest.mark.parametrize("store_factory", [MemoryInputResourceStore])
def test_finalized_reference_is_owner_bound_and_checksum_verified(
    store_factory: Any,
) -> None:
    store = store_factory()
    ctx = _context()
    content = b"id,name\n1,Ada\n"
    staged = store.stage(
        ctx,
        content,
        media_type="text/csv",
        format="csv",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    with pytest.raises(ControlPlaneError, match="checksum or length"):
        store.finalize(
            ctx,
            staged.upload_id,
            expected_sha256="0" * 64,
            expected_byte_length=len(content),
        )
    reference = store.finalize(
        ctx,
        staged.upload_id,
        expected_sha256=hashlib.sha256(content).hexdigest(),
        expected_byte_length=len(content),
    )

    assert InputResourceReference.from_dict(reference.to_dict()) == reference
    with pytest.raises(ValueError, match="unsupported fields"):
        InputResourceReference.from_dict({**reference.to_dict(), "path": "/etc/passwd"})
    assert store.read(ctx, reference) == content
    other_owner = _context(owner="different-owner")
    with pytest.raises(ControlPlaneError) as denied:
        store.read(other_owner, reference)
    assert denied.value.status == 404
    with pytest.raises(ControlPlaneError, match="owner-bound"):
        store.read(
            ctx,
            InputResourceReference.from_dict(
                {**reference.to_dict(), "owner_id": "forged"}
            ),
        )
    with pytest.raises(ControlPlaneError, match="byte limit"):
        MemoryInputResourceStore(max_upload_bytes=2).stage(
            ctx,
            content,
            media_type="text/csv",
            format="csv",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )


def test_upload_cleanup_is_bounded_and_respects_live_leases() -> None:
    store = MemoryInputResourceStore()
    ctx = _context()
    content = b"id\n1\n"
    reference = _finalize(store, ctx, content)
    lease_until = datetime.now(UTC) + timedelta(days=4)
    store.acquire_lease(
        ctx, reference, lease_id="submission-1", retain_until=lease_until
    )
    expired = datetime.now(UTC) + timedelta(days=3)

    held = store.cleanup(ctx, now=expired, limit=1)
    assert held.deleted_upload_ids == ()
    assert store.read(ctx, reference, now=expired) == content

    store.release_lease(ctx, lease_id="submission-1")
    deleted = store.cleanup(ctx, now=expired, limit=1)
    assert deleted.deleted_upload_ids == (reference.resource_id,)
    assert store.cleanup(ctx, now=expired, limit=1).deleted_upload_ids == ()
    with pytest.raises(ControlPlaneError) as missing:
        store.read(ctx, reference, now=expired)
    assert missing.value.status == 404


def test_expired_orphan_upload_is_removed_by_bounded_cleanup() -> None:
    store = MemoryInputResourceStore()
    ctx = _context()
    expires_at = datetime.now(UTC) + timedelta(seconds=1)
    staged = store.stage(
        ctx,
        b"id\n1\n",
        media_type="text/csv",
        format="csv",
        expires_at=expires_at,
    )

    result = store.cleanup(ctx, now=expires_at + timedelta(seconds=1), limit=1)

    assert result.deleted_upload_ids == (staged.upload_id,)
    assert result.remaining_candidates == 0
    with pytest.raises(ControlPlaneError) as gone:
        store.abort(ctx, staged.upload_id)
    assert gone.value.status == 404


@pytest.mark.parametrize(
    ("media_type", "format"),
    [("text/plain", "csv"), ("text/csv", "json")],
)
def test_upload_rejects_unsupported_media_and_format(
    media_type: str, format: str
) -> None:
    with pytest.raises(ControlPlaneError) as unsupported:
        MemoryInputResourceStore().stage(
            _context(),
            b"id\n1\n",
            media_type=media_type,
            format=format,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    assert unsupported.value.status == 415


def test_sqlmodel_upload_bytes_and_leases_survive_backend_restart(
    tmp_path: Path,
) -> None:
    database = tmp_path / "input-resources.sqlite"
    engine = create_engine(
        f"sqlite:///{database}", connect_args={"check_same_thread": False}
    )
    try:
        assert upgrade(engine) == "012_bounded_event_tombstone_retention_0_56"
        first = SqlModelInputResourceStore(engine)
        ctx = _context()
        content = b"id,name\n2,Grace\n"
        reference = _finalize(first, ctx, content)
        retain_until = datetime.now(UTC) + timedelta(days=4)
        first.acquire_lease(
            ctx, reference, lease_id="accepted-run", retain_until=retain_until
        )
        restarted = SqlModelInputResourceStore(engine)
        assert restarted.read(ctx, reference) == content

        expired = datetime.now(UTC) + timedelta(days=3)
        assert restarted.cleanup(ctx, now=expired, limit=1).deleted_upload_ids == ()
        restarted.release_lease(ctx, lease_id="accepted-run")
        assert restarted.cleanup(ctx, now=expired, limit=1).deleted_upload_ids == (
            reference.resource_id,
        )
        with pytest.raises(ControlPlaneError) as missing:
            restarted.read(ctx, reference, now=expired)
        assert missing.value.status == 404
        assert current_version(engine) == "012_bounded_event_tombstone_retention_0_56"
    finally:
        engine.dispose()


def test_sqlmodel_read_rejects_cross_owner_and_changed_blob_bytes(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'tampered-input.db'}")
    try:
        assert upgrade(engine) == "012_bounded_event_tombstone_retention_0_56"
        store = SqlModelInputResourceStore(engine)
        ctx = _context()
        content = b"id,name\n7,Lin\n"
        reference = _finalize(store, ctx, content)
        with pytest.raises(ControlPlaneError) as cross_owner:
            store.read(_context(owner="other-owner"), reference)
        assert cross_owner.value.status == 404

        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE cp_input_uploads SET content = :content "
                    "WHERE upload_id = :upload_id"
                ),
                {"content": b"id,name\n8,Lin\n", "upload_id": reference.resource_id},
            )
        with pytest.raises(ControlPlaneError, match="integrity verification"):
            store.read(ctx, reference)
    finally:
        engine.dispose()
