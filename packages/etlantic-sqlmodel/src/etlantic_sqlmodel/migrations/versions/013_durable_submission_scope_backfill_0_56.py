"""013 — backfill submission mirrors used by bounded retention scope pages."""

from __future__ import annotations

import json
from typing import Any, cast

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

_INSERT_SUBMISSION = text(
    "INSERT INTO cp_durable_submission_entity "
    "(store_id, tenant_id, workspace_id, submission_id, payload_json) "
    "VALUES (:store_id, :tenant_id, :workspace_id, :submission_id, :payload_json)"
)


def upgrade(engine: Engine) -> None:
    """Populate missing normalized rows from the canonical durable snapshots."""
    inspector = inspect(engine)
    if not inspector.has_table("cp_durable_snapshot"):
        raise RuntimeError("Cannot backfill submission mirrors before migration 002")
    if not inspector.has_table("cp_durable_submission_entity"):
        raise RuntimeError("Cannot backfill submission mirrors before migration 003")

    with engine.begin() as connection:
        existing = {
            (
                str(row["store_id"]),
                str(row["tenant_id"]),
                str(row["workspace_id"]),
                str(row["submission_id"]),
            )
            for row in connection.execute(
                text(
                    "SELECT store_id, tenant_id, workspace_id, submission_id "
                    "FROM cp_durable_submission_entity"
                )
            ).mappings()
        }
        snapshots = list(
            connection.execute(
                text("SELECT store_id, payload_json FROM cp_durable_snapshot")
            ).mappings()
        )

        batch: list[dict[str, str]] = []
        for snapshot in snapshots:
            try:
                payload = json.loads(snapshot["payload_json"] or "{}")
            except (TypeError, json.JSONDecodeError) as exc:
                raise RuntimeError(
                    "Cannot backfill submission mirrors from a malformed snapshot"
                ) from exc
            if not isinstance(payload, dict):
                raise RuntimeError(
                    "Cannot backfill submission mirrors from a malformed snapshot"
                )
            payload_data = cast(dict[str, Any], payload)
            raw_submissions: object = payload_data.get("submissions") or {}
            if not isinstance(raw_submissions, dict):
                raise RuntimeError(
                    "Cannot backfill submission mirrors from a malformed snapshot"
                )
            submissions = cast(dict[str, Any], raw_submissions)
            store_id = str(snapshot["store_id"])
            for raw_value in submissions.values():
                if not isinstance(raw_value, dict):
                    continue
                raw_submission = cast(dict[str, Any], raw_value)
                tenant_id = raw_submission.get("tenant_id")
                workspace_id = raw_submission.get("workspace_id")
                submission_id = raw_submission.get("submission_id")
                if not isinstance(tenant_id, str) or not tenant_id:
                    continue
                if not isinstance(workspace_id, str) or not workspace_id:
                    continue
                if not isinstance(submission_id, str) or not submission_id:
                    continue
                identity = (store_id, tenant_id, workspace_id, submission_id)
                if identity in existing:
                    continue
                existing.add(identity)
                batch.append(
                    {
                        "store_id": store_id,
                        "tenant_id": tenant_id,
                        "workspace_id": workspace_id,
                        "submission_id": submission_id,
                        "payload_json": json.dumps(raw_submission, sort_keys=True),
                    }
                )
                if len(batch) == 500:
                    connection.execute(_INSERT_SUBMISSION, batch)
                    batch.clear()
        if batch:
            connection.execute(_INSERT_SUBMISSION, batch)


def downgrade(engine: Engine) -> None:
    """Keep backfilled mirrors; deleting valid normalized work data is unsafe."""
    del engine


__all__ = ["downgrade", "upgrade"]
