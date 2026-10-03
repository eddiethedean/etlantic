"""011 — index managed result age and durable artifact cleanup state."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import Index, MetaData, Table, inspect, text
from sqlalchemy.engine import Engine

from etlantic.reports.retention import (
    RUN_ARTIFACT_RETENTION_STATE_KEY,
    TERMINAL_RUN_STATUSES,
)

_COLUMNS: tuple[tuple[str, str], ...] = (
    ("security_domain_id", "VARCHAR(255) NOT NULL DEFAULT ''"),
    ("run_status", "VARCHAR(32) NOT NULL DEFAULT ''"),
    ("ended_at", "VARCHAR(64)"),
    ("artifact_retention_state", "VARCHAR(16)"),
)
_INDEX = "ix_cp_run_reports_retention"


def upgrade(engine: Engine) -> None:
    """Backfill queryable terminal age/state without changing result JSON."""
    inspector = inspect(engine)
    if not inspector.has_table("cp_run_reports"):
        raise RuntimeError("Cannot add result retention before migration 007")

    columns = {column["name"] for column in inspector.get_columns("cp_run_reports")}
    with engine.begin() as connection:
        for name, definition in _COLUMNS:
            if name not in columns:
                connection.execute(
                    text(f"ALTER TABLE cp_run_reports ADD COLUMN {name} {definition}")
                )

        rows = list(
            connection.execute(
                text(
                    "SELECT tenant_id, workspace_id, run_id, report_json "
                    "FROM cp_run_reports"
                )
            ).mappings()
        )
        for row in rows:
            try:
                report = json.loads(row["report_json"])
            except (TypeError, ValueError):
                continue
            if not isinstance(report, dict):
                continue
            status = str(report.get("status") or "")
            ended_at = _normalize_timestamp(report.get("ended_at"))
            metadata = report.get("metadata")
            raw_state = (
                metadata.get(RUN_ARTIFACT_RETENTION_STATE_KEY)
                if isinstance(metadata, dict)
                else None
            )
            state = (
                raw_state
                if isinstance(raw_state, str)
                and raw_state in {"running", "failed", "complete"}
                else None
            )
            if status not in TERMINAL_RUN_STATUSES:
                status = status or "unknown"
            connection.execute(
                text(
                    "UPDATE cp_run_reports SET run_status = :run_status, "
                    "ended_at = :ended_at, artifact_retention_state = :state "
                    "WHERE tenant_id = :tenant_id AND workspace_id = :workspace_id "
                    "AND run_id = :run_id"
                ),
                {
                    "tenant_id": row["tenant_id"],
                    "workspace_id": row["workspace_id"],
                    "run_id": row["run_id"],
                    "run_status": status,
                    "ended_at": ended_at,
                    "state": state,
                },
            )
        # A report created before security-domain scoping has no provable
        # security domain. Keep its empty marker fail-closed; an operator must
        # establish the mapping before scoped reads or cleanup can resume.

    if _INDEX not in {
        index["name"] for index in inspect(engine).get_indexes("cp_run_reports")
    }:
        # The SQLModel metadata contains this index for clean installations;
        # reflect here so upgrades from migration 010 receive the same index.
        table = Table("cp_run_reports", MetaData(), autoload_with=engine)
        Index(
            _INDEX,
            table.c.tenant_id,
            table.c.workspace_id,
            table.c.security_domain_id,
            table.c.run_status,
            table.c.ended_at,
            table.c.artifact_retention_state,
        ).create(engine, checkfirst=True)


def downgrade(engine: Engine) -> None:
    """Remove retention query metadata while keeping durable run reports."""
    if not inspect(engine).has_table("cp_run_reports"):
        return
    columns = {
        column["name"] for column in inspect(engine).get_columns("cp_run_reports")
    }
    with engine.begin() as connection:
        connection.execute(text(f"DROP INDEX IF EXISTS {_INDEX}"))
        for name, _definition in reversed(_COLUMNS):
            if name in columns:
                connection.execute(
                    text(f"ALTER TABLE cp_run_reports DROP COLUMN {name}")
                )


def _normalize_timestamp(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    parsed = (
        parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    )
    return parsed.isoformat().replace("+00:00", "Z")


__all__ = ["downgrade", "upgrade"]
