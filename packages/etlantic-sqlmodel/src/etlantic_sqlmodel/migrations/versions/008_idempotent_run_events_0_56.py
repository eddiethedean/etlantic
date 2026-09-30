"""008 — scoped idempotency for managed runtime lifecycle events."""

from __future__ import annotations

from sqlalchemy import (
    Column,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    inspect,
)
from sqlalchemy.engine import Engine


def _event_idempotency_table() -> Table:
    """Return the original 008 schema independent of later ORM additions."""
    return Table(
        "cp_event_idempotency",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("tenant_id", String(), nullable=False),
        Column("workspace_id", String(), nullable=False),
        Column("event_key", String(), nullable=False),
        Column("event_id", String(), nullable=False),
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "event_key",
            name="uq_cp_event_scope_idem",
        ),
        Index("ix_cp_event_idempotency_tenant_id", "tenant_id"),
        Index("ix_cp_event_idempotency_workspace_id", "workspace_id"),
        Index("ix_cp_event_idempotency_event_id", "event_id"),
    )


def upgrade(engine: Engine) -> None:
    """Create the event-key mapping without rewriting retained event history."""
    inspector = inspect(engine)
    if not inspector.has_table("cp_events"):
        raise RuntimeError("Cannot add event idempotency before cp_events exists")
    _event_idempotency_table().create(engine, checkfirst=True)


def downgrade(engine: Engine) -> None:
    """Remove key mappings; retained event rows remain available."""
    if inspect(engine).has_table("cp_event_idempotency"):
        _event_idempotency_table().drop(engine, checkfirst=True)


__all__ = ["downgrade", "upgrade"]
