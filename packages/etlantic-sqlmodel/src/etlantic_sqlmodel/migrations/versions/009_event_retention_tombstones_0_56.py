"""009 — retain event idempotency tombstones across history pruning."""

from __future__ import annotations

import hashlib

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

_COLUMNS: tuple[tuple[str, str], ...] = (
    ("event_kind", "VARCHAR(255)"),
    ("payload_sha256", "VARCHAR(64)"),
    ("sequence", "INTEGER"),
    ("cursor", "VARCHAR(64)"),
)


def upgrade(engine: Engine) -> None:
    """Add delivery tombstone metadata and backfill existing event keys."""
    inspector = inspect(engine)
    if not inspector.has_table("cp_event_idempotency"):
        raise RuntimeError("Cannot add event tombstones before migration 008")

    existing_columns = {column["name"] for column in inspector.get_columns("cp_event_idempotency")}
    with engine.begin() as connection:
        for name, sql_type in _COLUMNS:
            if name not in existing_columns:
                connection.execute(
                    text(f"ALTER TABLE cp_event_idempotency ADD COLUMN {name} {sql_type}")
                )

        mappings = connection.execute(
            text(
                "SELECT tenant_id, workspace_id, event_key, event_id "
                "FROM cp_event_idempotency"
            )
        ).mappings()
        for mapping in mappings:
            event = connection.execute(
                text(
                    "SELECT kind, payload_json, sequence, cursor FROM cp_events "
                    "WHERE tenant_id = :tenant_id AND workspace_id = :workspace_id "
                    "AND event_id = :event_id"
                ),
                {
                    "tenant_id": mapping["tenant_id"],
                    "workspace_id": mapping["workspace_id"],
                    "event_id": mapping["event_id"],
                },
            ).mappings().first()
            if event is None:
                raise RuntimeError(
                    "Event idempotency row references missing event history"
                )
            connection.execute(
                text(
                    "UPDATE cp_event_idempotency SET event_kind = :event_kind, "
                    "payload_sha256 = :payload_sha256, sequence = :sequence, "
                    "cursor = :cursor WHERE tenant_id = :tenant_id "
                    "AND workspace_id = :workspace_id AND event_key = :event_key"
                ),
                {
                    "tenant_id": mapping["tenant_id"],
                    "workspace_id": mapping["workspace_id"],
                    "event_key": mapping["event_key"],
                    "event_kind": event["kind"],
                    "payload_sha256": hashlib.sha256(
                        str(event["payload_json"]).encode("utf-8")
                    ).hexdigest(),
                    "sequence": event["sequence"],
                    "cursor": event["cursor"],
                },
            )


def downgrade(engine: Engine) -> None:
    """Remove only the tombstone metadata, leaving event history and keys."""
    if not inspect(engine).has_table("cp_event_idempotency"):
        return
    columns = {column["name"] for column in inspect(engine).get_columns("cp_event_idempotency")}
    with engine.begin() as connection:
        for name, _sql_type in reversed(_COLUMNS):
            if name in columns:
                connection.execute(
                    text(f"ALTER TABLE cp_event_idempotency DROP COLUMN {name}")
                )


__all__ = ["downgrade", "upgrade"]
