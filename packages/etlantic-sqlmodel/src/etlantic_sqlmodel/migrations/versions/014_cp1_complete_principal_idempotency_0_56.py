"""014 — qualify CP1 idempotency by complete principal identity."""

from __future__ import annotations

import json
from typing import cast

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

_OLD_COLUMNS = (
    "id, tenant_id, workspace_id, principal_subject, operation, idempotency_key, "
    "acceptance_id, submission_id, created_at, status, resource_type, resource_id, "
    "payload_json, run_status, updated_at, definition_id"
)
_UNRESOLVED_PRINCIPAL_KIND = "legacy_unresolved"


def _cp3_principal_identities(
    engine: Engine,
) -> dict[tuple[str, str, str, str, str], set[tuple[str, str, str]]]:
    """Find principal identities that CP3 can verify for legacy CP1 rows."""
    if not inspect(engine).has_table("cp_durable_snapshot"):
        return {}
    identities: dict[tuple[str, str, str, str, str], set[tuple[str, str, str]]] = {}
    with engine.connect() as connection:
        snapshots = connection.execute(
            text("SELECT payload_json FROM cp_durable_snapshot")
        )
        for (payload_json,) in snapshots:
            try:
                payload = json.loads(payload_json or "{}")
            except (TypeError, json.JSONDecodeError) as exc:
                raise RuntimeError(
                    "Cannot resolve CP1 principals from a malformed CP3 snapshot"
                ) from exc
            if not isinstance(payload, dict):
                raise RuntimeError(
                    "Cannot resolve CP1 principals from a malformed CP3 snapshot"
                )
            payload_data = cast(dict[str, object], payload)
            submissions: object = payload_data.get("submissions") or {}
            if not isinstance(submissions, dict):
                raise RuntimeError(
                    "Cannot resolve CP1 principals from a malformed CP3 snapshot"
                )
            raw_submissions = cast(dict[str, object], submissions)
            for raw_value in raw_submissions.values():
                if not isinstance(raw_value, dict):
                    continue
                raw = cast(dict[str, object], raw_value)
                tenant_id = raw.get("tenant_id")
                if not isinstance(tenant_id, str) or not tenant_id:
                    continue
                workspace_id = raw.get("workspace_id")
                if not isinstance(workspace_id, str) or not workspace_id:
                    continue
                submission_id = raw.get("submission_id")
                if not isinstance(submission_id, str) or not submission_id:
                    continue
                operation = raw.get("operation")
                if not isinstance(operation, str) or not operation:
                    continue
                idempotency_key = raw.get("idempotency_key")
                if not isinstance(idempotency_key, str) or not idempotency_key:
                    continue
                subject = raw.get("principal_subject")
                if not isinstance(subject, str) or not subject:
                    continue
                kind = raw.get("principal_kind")
                if not isinstance(kind, str) or not kind:
                    continue
                issuer = raw.get("principal_issuer")
                if issuer is not None and not isinstance(issuer, str):
                    continue
                identity = (issuer or "", kind, subject)
                identities.setdefault(
                    (
                        tenant_id,
                        workspace_id,
                        submission_id,
                        operation,
                        idempotency_key,
                    ),
                    set(),
                ).add(identity)
    return identities


def _restore_legacy_identities(
    engine: Engine, *, sqlite_table: str | None = None
) -> None:
    """Backfill provable identities; mark every other old receipt unresolved."""
    identities = _cp3_principal_identities(engine)
    table = sqlite_table or "cp_submissions"
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                f"SELECT id, tenant_id, workspace_id, submission_id, operation, "
                f"idempotency_key, principal_subject FROM {table} "
                "WHERE principal_kind = :unresolved"
            ),
            {"unresolved": _UNRESOLVED_PRINCIPAL_KIND},
        ).all()
        for row in rows:
            matches = identities.get(
                (
                    row.tenant_id,
                    row.workspace_id,
                    row.submission_id,
                    row.operation,
                    row.idempotency_key,
                ),
                set(),
            )
            if len(matches) == 1:
                issuer, kind, subject = next(iter(matches))
                if subject == row.principal_subject:
                    connection.execute(
                        text(
                            f"UPDATE {table} SET principal_issuer = :issuer, "
                            "principal_kind = :kind WHERE id = :id"
                        ),
                        {"issuer": issuer, "kind": kind, "id": row.id},
                    )
                    continue
            connection.execute(
                text(f"UPDATE {table} SET principal_kind = :kind WHERE id = :id"),
                {"kind": _UNRESOLVED_PRINCIPAL_KIND, "id": row.id},
            )


def _rebuild_sqlite(engine: Engine, *, downgrade: bool = False) -> None:
    target = "cp_submissions_legacy" if downgrade else "cp_submissions_v14"
    columns = (
        _OLD_COLUMNS
        if downgrade
        else (
            "id, tenant_id, workspace_id, principal_issuer, principal_kind, "
            "principal_subject, operation, idempotency_key, acceptance_id, "
            "submission_id, created_at, status, resource_type, resource_id, "
            "payload_json, run_status, updated_at, definition_id"
        )
    )
    with engine.begin() as connection:
        connection.execute(text(f"DROP TABLE IF EXISTS {target}"))
        if downgrade:
            connection.execute(
                text(
                    "CREATE TABLE cp_submissions_legacy ("
                    "id INTEGER NOT NULL PRIMARY KEY, tenant_id VARCHAR NOT NULL, "
                    "workspace_id VARCHAR NOT NULL, principal_subject VARCHAR NOT NULL, "
                    "operation VARCHAR NOT NULL, idempotency_key VARCHAR NOT NULL, "
                    "acceptance_id VARCHAR NOT NULL, submission_id VARCHAR NOT NULL, "
                    "created_at VARCHAR NOT NULL, status VARCHAR NOT NULL, "
                    "resource_type VARCHAR NOT NULL, resource_id VARCHAR, "
                    "payload_json VARCHAR NOT NULL, run_status VARCHAR NOT NULL, "
                    "updated_at VARCHAR, definition_id VARCHAR, "
                    "CONSTRAINT uq_cp_submission_idem UNIQUE "
                    "(tenant_id, workspace_id, principal_subject, operation, idempotency_key))"
                )
            )
            connection.execute(
                text(
                    f"INSERT INTO cp_submissions_legacy ({columns}) "
                    f"SELECT {_OLD_COLUMNS} FROM cp_submissions"
                )
            )
        else:
            connection.execute(
                text(
                    "CREATE TABLE cp_submissions_v14 ("
                    "id INTEGER NOT NULL PRIMARY KEY, tenant_id VARCHAR NOT NULL, "
                    "workspace_id VARCHAR NOT NULL, principal_issuer VARCHAR NOT NULL DEFAULT '', "
                    "principal_kind VARCHAR NOT NULL DEFAULT 'human', "
                    "principal_subject VARCHAR NOT NULL, operation VARCHAR NOT NULL, "
                    "idempotency_key VARCHAR NOT NULL, acceptance_id VARCHAR NOT NULL, "
                    "submission_id VARCHAR NOT NULL, created_at VARCHAR NOT NULL, "
                    "status VARCHAR NOT NULL, resource_type VARCHAR NOT NULL, "
                    "resource_id VARCHAR, payload_json VARCHAR NOT NULL, "
                    "run_status VARCHAR NOT NULL, updated_at VARCHAR, definition_id VARCHAR, "
                    "CONSTRAINT uq_cp_submission_idem UNIQUE "
                    "(tenant_id, workspace_id, principal_issuer, principal_kind, "
                    "principal_subject, operation, idempotency_key))"
                )
            )
            connection.execute(
                text(
                    f"INSERT INTO cp_submissions_v14 ({columns}) "
                    "SELECT id, tenant_id, workspace_id, '', "
                    "'legacy_unresolved', "
                    f"{_OLD_COLUMNS.split(',', 3)[3]} FROM cp_submissions"
                )
            )
        connection.execute(text("DROP TABLE cp_submissions"))
        connection.execute(text(f"ALTER TABLE {target} RENAME TO cp_submissions"))
        for column in (
            "tenant_id",
            "workspace_id",
            "principal_subject",
            "operation",
            "idempotency_key",
            "submission_id",
        ):
            connection.execute(
                text(
                    f"CREATE INDEX ix_cp_submissions_{column} "
                    f"ON cp_submissions ({column})"
                )
            )
        if not downgrade:
            for column in ("principal_issuer", "principal_kind"):
                connection.execute(
                    text(
                        f"CREATE INDEX ix_cp_submissions_{column} "
                        f"ON cp_submissions ({column})"
                    )
                )
    if not downgrade:
        _restore_legacy_identities(engine)


def upgrade(engine: Engine) -> None:
    """Add issuer/kind identity columns while retaining existing receipts."""
    inspector = inspect(engine)
    if not inspector.has_table("cp_submissions"):
        return
    columns = {column["name"] for column in inspector.get_columns("cp_submissions")}
    if {"principal_issuer", "principal_kind"}.issubset(columns):
        _restore_legacy_identities(engine)
        return
    if engine.dialect.name == "sqlite":
        _rebuild_sqlite(engine)
        return
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE cp_submissions ADD COLUMN principal_issuer VARCHAR "
                "NOT NULL DEFAULT ''"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE cp_submissions ADD COLUMN principal_kind VARCHAR "
                "NOT NULL DEFAULT 'human'"
            )
        )
        connection.execute(
            text("ALTER TABLE cp_submissions DROP CONSTRAINT uq_cp_submission_idem")
        )
        connection.execute(
            text(
                "ALTER TABLE cp_submissions ADD CONSTRAINT uq_cp_submission_idem "
                "UNIQUE (tenant_id, workspace_id, principal_issuer, principal_kind, "
                "principal_subject, operation, idempotency_key)"
            )
        )
        connection.execute(
            text("UPDATE cp_submissions SET principal_kind = 'legacy_unresolved'")
        )
        connection.execute(
            text(
                "CREATE INDEX ix_cp_submissions_principal_issuer "
                "ON cp_submissions (principal_issuer)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX ix_cp_submissions_principal_kind "
                "ON cp_submissions (principal_kind)"
            )
        )
    _restore_legacy_identities(engine)


def downgrade(engine: Engine) -> None:
    """Restore the subject-only key if full-identity receipts can be collapsed."""
    inspector = inspect(engine)
    if not inspector.has_table("cp_submissions"):
        return
    columns = {column["name"] for column in inspector.get_columns("cp_submissions")}
    if not {"principal_issuer", "principal_kind"}.issubset(columns):
        return
    with engine.connect() as connection:
        conflicts = connection.execute(
            text(
                "SELECT 1 FROM cp_submissions GROUP BY tenant_id, workspace_id, "
                "principal_subject, operation, idempotency_key HAVING COUNT(*) > 1 "
                "LIMIT 1"
            )
        ).first()
        non_legacy = connection.execute(
            text(
                "SELECT 1 FROM cp_submissions WHERE principal_issuer != '' "
                "OR principal_kind != 'human' LIMIT 1"
            )
        ).first()
    if conflicts is not None or non_legacy is not None:
        raise RuntimeError(
            "Cannot downgrade CP1 principal identity while issuer/kind-scoped receipts remain"
        )
    if engine.dialect.name == "sqlite":
        _rebuild_sqlite(engine, downgrade=True)
        return
    with engine.begin() as connection:
        connection.execute(text("DROP INDEX ix_cp_submissions_principal_issuer"))
        connection.execute(text("DROP INDEX ix_cp_submissions_principal_kind"))
        connection.execute(
            text("ALTER TABLE cp_submissions DROP CONSTRAINT uq_cp_submission_idem")
        )
        connection.execute(
            text(
                "ALTER TABLE cp_submissions ADD CONSTRAINT uq_cp_submission_idem "
                "UNIQUE (tenant_id, workspace_id, principal_subject, operation, "
                "idempotency_key)"
            )
        )
        connection.execute(
            text("ALTER TABLE cp_submissions DROP COLUMN principal_issuer")
        )
        connection.execute(
            text("ALTER TABLE cp_submissions DROP COLUMN principal_kind")
        )


__all__ = ["downgrade", "upgrade"]
