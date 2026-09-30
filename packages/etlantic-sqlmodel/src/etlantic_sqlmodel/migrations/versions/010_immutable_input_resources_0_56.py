"""010 — immutable owner-scoped input bytes and accepted-run leases."""

from __future__ import annotations

from sqlalchemy import (
    Column,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    inspect,
    select,
)
from sqlalchemy.engine import Engine


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


def upgrade(engine: Engine) -> None:
    """Create upload metadata/blob and lease tables after event tombstones."""
    inspector = inspect(engine)
    if not inspector.has_table("cp_event_idempotency"):
        raise RuntimeError("Cannot add input resources before migration 009")
    uploads, leases = _tables()
    uploads.create(engine, checkfirst=True)
    leases.create(engine, checkfirst=True)


def downgrade(engine: Engine) -> None:
    """Refuse data loss while any staged/finalized upload remains."""
    inspector = inspect(engine)
    if not inspector.has_table("cp_input_uploads"):
        return
    uploads, leases = _tables()
    with engine.connect() as connection:
        has_upload = connection.execute(select(uploads.c.upload_id).limit(1)).first()
    if has_upload is not None:
        raise RuntimeError(
            "Cannot downgrade input-resource migration while uploads remain; "
            "expire and clean them before rollback"
        )
    leases.drop(engine, checkfirst=True)
    uploads.drop(engine, checkfirst=True)


__all__ = ["downgrade", "upgrade"]
