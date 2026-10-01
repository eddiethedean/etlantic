"""012 — bound event idempotency tombstone retention."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from etlantic.control_plane.event_retention import (
    DEFAULT_EVENT_IDEMPOTENCY_RETENTION_SECONDS,
    event_expiry,
    event_time,
)

_INDEX_NAME = "ix_cp_event_idem_scope_expires"


def upgrade(engine: Engine) -> None:
    """Add tombstone expiries and backfill existing event delivery keys."""
    inspector = inspect(engine)
    if not inspector.has_table("cp_event_idempotency"):
        raise RuntimeError("Cannot bound event tombstones before migration 009")
    columns = {
        column["name"] for column in inspector.get_columns("cp_event_idempotency")
    }
    if "expires_at" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE cp_event_idempotency ADD COLUMN expires_at VARCHAR(40)"
                )
            )

    with engine.begin() as connection:
        pending = (
            connection.execute(
                text(
                    "SELECT tenant_id, workspace_id, event_key, event_id "
                    "FROM cp_event_idempotency WHERE expires_at IS NULL"
                )
            )
            .mappings()
            .all()
        )
        for mapping in pending:
            event = (
                connection.execute(
                    text(
                        "SELECT created_at FROM cp_events "
                        "WHERE tenant_id = :tenant_id AND workspace_id = :workspace_id "
                        "AND event_id = :event_id"
                    ),
                    {
                        "tenant_id": mapping["tenant_id"],
                        "workspace_id": mapping["workspace_id"],
                        "event_id": mapping["event_id"],
                    },
                )
                .mappings()
                .first()
            )
            created = event_time(None if event is None else str(event["created_at"]))
            if created is None:
                # A missing event cannot be safely deduplicated indefinitely.
                created = datetime(1970, 1, 1, tzinfo=UTC)
            expiry = event_expiry(created, DEFAULT_EVENT_IDEMPOTENCY_RETENTION_SECONDS)
            connection.execute(
                text(
                    "UPDATE cp_event_idempotency SET expires_at = :expires_at "
                    "WHERE tenant_id = :tenant_id AND workspace_id = :workspace_id "
                    "AND event_key = :event_key"
                ),
                {
                    "tenant_id": mapping["tenant_id"],
                    "workspace_id": mapping["workspace_id"],
                    "event_key": mapping["event_key"],
                    "expires_at": expiry,
                },
            )
        connection.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS {_INDEX_NAME} "
                "ON cp_event_idempotency (tenant_id, workspace_id, expires_at)"
            )
        )


def downgrade(engine: Engine) -> None:
    """Remove expiry metadata while retaining event history and key mappings."""
    inspector = inspect(engine)
    if not inspector.has_table("cp_event_idempotency"):
        return
    with engine.begin() as connection:
        connection.execute(text(f"DROP INDEX IF EXISTS {_INDEX_NAME}"))
        columns = {
            column["name"]
            for column in inspect(connection).get_columns("cp_event_idempotency")
        }
        if "expires_at" in columns:
            connection.execute(
                text("ALTER TABLE cp_event_idempotency DROP COLUMN expires_at")
            )


__all__ = ["downgrade", "upgrade"]
