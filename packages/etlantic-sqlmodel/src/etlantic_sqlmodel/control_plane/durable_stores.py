"""SQLModel-backed DurableWorkStore (CP3 / 041-P).

Reference provider: each mutating call loads the durable snapshot inside a
database transaction, applies MemoryDurableWorkStore semantics, and writes the
snapshot back before commit. This preserves accept+outbox atomicity and fencing
CAS concurrency for SQLite/Postgres reference deployments.

Production note: apply versioned migrations — do not rely on
``create_durable_tables`` as the sole schema path.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, TypeVar

from sqlalchemy.engine import Engine

from etlantic.control_plane.durable_memory import MemoryDurableWorkStore
from etlantic.control_plane.durable_models import (
    AttemptRecord,
    BaselineAcknowledgement,
    CheckpointRecord,
    DiffRecord,
    EffectRecord,
    LeaseRecord,
    OutboxRecord,
    PreviewWorkspace,
    ShadowRunRecord,
    StateDiagnostic,
    SubmissionRecord,
)
from etlantic.control_plane.models import ControlPlaneContext
from etlantic_sqlmodel.control_plane.models import DurableSnapshotRow
from etlantic_sqlmodel.control_plane.session import session_scope
from sqlmodel import Session, SQLModel, select

T = TypeVar("T")

DURABLE_TABLES = (DurableSnapshotRow,)


def create_durable_tables(engine: Engine) -> None:
    """Create CP3 durable tables (tests/demos only)."""
    SQLModel.metadata.create_all(
        engine,
        tables=[cls.__table__ for cls in DURABLE_TABLES],  # type: ignore[list-item]
    )


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _dump_store(store: MemoryDurableWorkStore) -> dict[str, Any]:
    return {
        "admission_limit": store.admission_limit,
        "submissions": {"|".join(k): asdict(v) for k, v in store._submissions.items()},
        "idempotency": {"|".join(k): v for k, v in store._idempotency.items()},
        "outbox": {"|".join(k): asdict(v) for k, v in store._outbox.items()},
        "leases": {"|".join(k): asdict(v) for k, v in store._leases.items()},
        "attempts": {"|".join(k): asdict(v) for k, v in store._attempts.items()},
        "checkpoints": {"|".join(k): asdict(v) for k, v in store._checkpoints.items()},
        "effects": {"|".join(k): asdict(v) for k, v in store._effects.items()},
        "previews": {"|".join(k): asdict(v) for k, v in store._previews.items()},
        "diffs": {"|".join(k): asdict(v) for k, v in store._diffs.items()},
        "shadows": {"|".join(k): asdict(v) for k, v in store._shadows.items()},
        "baselines": {"|".join(k): asdict(v) for k, v in store._baselines.items()},
        "diagnostics": [asdict(d) for d in store._diagnostics],
    }


def _key(text: str) -> tuple[str, ...]:
    return tuple(text.split("|"))


def _load_store(payload: Mapping[str, Any]) -> MemoryDurableWorkStore:
    store = MemoryDurableWorkStore(admission_limit=payload.get("admission_limit"))
    store._submissions = {
        _key(k): SubmissionRecord(**v)  # type: ignore[arg-type]
        for k, v in dict(payload.get("submissions") or {}).items()
    }
    store._idempotency = {
        _key(k): v for k, v in dict(payload.get("idempotency") or {}).items()
    }
    store._outbox = {
        _key(k): OutboxRecord(**v)  # type: ignore[arg-type]
        for k, v in dict(payload.get("outbox") or {}).items()
    }
    store._leases = {
        _key(k): LeaseRecord(**v)  # type: ignore[arg-type]
        for k, v in dict(payload.get("leases") or {}).items()
    }
    store._attempts = {
        _key(k): AttemptRecord(**v)  # type: ignore[arg-type]
        for k, v in dict(payload.get("attempts") or {}).items()
    }
    store._checkpoints = {
        _key(k): CheckpointRecord(**v)  # type: ignore[arg-type]
        for k, v in dict(payload.get("checkpoints") or {}).items()
    }
    store._effects = {
        _key(k): EffectRecord(**v)  # type: ignore[arg-type]
        for k, v in dict(payload.get("effects") or {}).items()
    }
    store._previews = {
        _key(k): PreviewWorkspace(**v)  # type: ignore[arg-type]
        for k, v in dict(payload.get("previews") or {}).items()
    }
    store._diffs = {
        _key(k): DiffRecord(**v)  # type: ignore[arg-type]
        for k, v in dict(payload.get("diffs") or {}).items()
    }
    store._shadows = {
        _key(k): ShadowRunRecord(**v)  # type: ignore[arg-type]
        for k, v in dict(payload.get("shadows") or {}).items()
    }
    store._baselines = {
        _key(k): BaselineAcknowledgement(**v)  # type: ignore[arg-type]
        for k, v in dict(payload.get("baselines") or {}).items()
    }
    store._diagnostics = [
        StateDiagnostic(**d)  # type: ignore[arg-type]
        for d in list(payload.get("diagnostics") or [])
    ]
    return store


class SQLModelDurableWorkStore:
    """Transactional DurableWorkStore backed by a SQL snapshot row."""

    def __init__(
        self,
        engine: Engine,
        *,
        admission_limit: int | None = None,
        store_id: str = "default",
    ) -> None:
        self.engine = engine
        self.admission_limit = admission_limit
        self.store_id = store_id

    def _txn(self, fn: Callable[[MemoryDurableWorkStore], T]) -> T:
        with session_scope(self.engine) as session:
            mem = self._read(session)
            if self.admission_limit is not None:
                mem.admission_limit = self.admission_limit
            result = fn(mem)
            self._write(session, mem)
            return result

    def _read(self, session: Session) -> MemoryDurableWorkStore:
        row = session.exec(
            select(DurableSnapshotRow).where(
                DurableSnapshotRow.store_id == self.store_id
            )
        ).first()
        if row is None:
            return MemoryDurableWorkStore(admission_limit=self.admission_limit)
        return _load_store(json.loads(row.payload_json or "{}"))

    def _write(self, session: Session, store: MemoryDurableWorkStore) -> None:
        payload = json.dumps(_dump_store(store), sort_keys=True)
        row = session.exec(
            select(DurableSnapshotRow).where(
                DurableSnapshotRow.store_id == self.store_id
            )
        ).first()
        if row is None:
            session.add(
                DurableSnapshotRow(
                    store_id=self.store_id,
                    payload_json=payload,
                    updated_at=_utcnow_iso(),
                )
            )
        else:
            row.payload_json = payload
            row.updated_at = _utcnow_iso()
            session.add(row)

    def accept(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.accept(ctx, **kwargs))

    def pending_outbox(self, ctx: ControlPlaneContext, *, limit: int = 100):
        return self._txn(lambda m: m.pending_outbox(ctx, limit=limit))

    def mark_published(self, ctx: ControlPlaneContext, outbox_id: str):
        return self._txn(lambda m: m.mark_published(ctx, outbox_id))

    def cancel_submission(self, ctx: ControlPlaneContext, submission_id: str):
        return self._txn(lambda m: m.cancel_submission(ctx, submission_id))

    def acquire_lease(
        self, ctx: ControlPlaneContext, submission_id: str, **kwargs: Any
    ):
        return self._txn(lambda m: m.acquire_lease(ctx, submission_id, **kwargs))

    def heartbeat(self, ctx: ControlPlaneContext, submission_id: str, **kwargs: Any):
        return self._txn(lambda m: m.heartbeat(ctx, submission_id, **kwargs))

    def release_lease(
        self, ctx: ControlPlaneContext, submission_id: str, **kwargs: Any
    ):
        return self._txn(lambda m: m.release_lease(ctx, submission_id, **kwargs))

    def start_attempt(
        self, ctx: ControlPlaneContext, submission_id: str, **kwargs: Any
    ):
        return self._txn(lambda m: m.start_attempt(ctx, submission_id, **kwargs))

    def finish_attempt(self, ctx: ControlPlaneContext, attempt_id: str, **kwargs: Any):
        return self._txn(lambda m: m.finish_attempt(ctx, attempt_id, **kwargs))

    def compare_and_swap_checkpoint(
        self, ctx: ControlPlaneContext, checkpoint_id: str, **kwargs: Any
    ):
        return self._txn(
            lambda m: m.compare_and_swap_checkpoint(ctx, checkpoint_id, **kwargs)
        )

    def explain_transition(
        self, ctx: ControlPlaneContext, checkpoint_id: str, **kwargs: Any
    ):
        return self._txn(lambda m: m.explain_transition(ctx, checkpoint_id, **kwargs))

    def diagnose_checkpoint(
        self, ctx: ControlPlaneContext, checkpoint_id: str, **kwargs: Any
    ):
        return self._txn(lambda m: m.diagnose_checkpoint(ctx, checkpoint_id, **kwargs))

    def acknowledge_baseline(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.acknowledge_baseline(ctx, **kwargs))

    def record_effect(self, ctx: ControlPlaneContext, effect: EffectRecord):
        return self._txn(lambda m: m.record_effect(ctx, effect))

    def replay(self, ctx: ControlPlaneContext, submission_id: str, **kwargs: Any):
        return self._txn(lambda m: m.replay(ctx, submission_id, **kwargs))

    def plan_resume(self, ctx: ControlPlaneContext, submission_id: str, **kwargs: Any):
        return self._txn(lambda m: m.plan_resume(ctx, submission_id, **kwargs))

    def plan_repair(self, ctx: ControlPlaneContext, submission_id: str, **kwargs: Any):
        return self._txn(lambda m: m.plan_repair(ctx, submission_id, **kwargs))

    def plan_backfill(
        self, ctx: ControlPlaneContext, submission_id: str, **kwargs: Any
    ):
        return self._txn(lambda m: m.plan_backfill(ctx, submission_id, **kwargs))

    def create_preview(self, ctx: ControlPlaneContext, preview: PreviewWorkspace):
        return self._txn(lambda m: m.create_preview(ctx, preview))

    def mark_preview_stale(
        self, ctx: ControlPlaneContext, preview_id: str, **kwargs: Any
    ):
        return self._txn(lambda m: m.mark_preview_stale(ctx, preview_id, **kwargs))

    def record_preview_diff(self, ctx: ControlPlaneContext, diff: DiffRecord):
        return self._txn(lambda m: m.record_preview_diff(ctx, diff))

    def authorize_shadow_run(self, ctx: ControlPlaneContext, shadow: ShadowRunRecord):
        return self._txn(lambda m: m.authorize_shadow_run(ctx, shadow))

    def cleanup_expired_previews(self, ctx: ControlPlaneContext):
        return self._txn(lambda m: m.cleanup_expired_previews(ctx))


__all__ = [
    "DURABLE_TABLES",
    "SQLModelDurableWorkStore",
    "create_durable_tables",
]
