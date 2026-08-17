"""SQLModel-backed ScheduleStore (0.47).

Reference provider: each mutating call loads the schedule snapshot inside a
database transaction, applies MemoryScheduleStore semantics, and writes the
snapshot back. When the paired DurableWorkStore is the SQLModel provider on
the same engine, firing claim and durable accept share one commit.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any, TypeVar

from sqlalchemy.engine import Engine

from etlantic.control_plane.durable_protocols import DurableWorkStore
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.schedule_memory import MemoryScheduleStore
from etlantic.control_plane.schedule_models import (
    FiringRecord,
    ScheduleRecord,
    ScheduleSpec,
)
from etlantic.control_plane.schedule_protocols import SchedulerLeaderLease
from etlantic_sqlmodel.control_plane.durable_stores import SQLModelDurableWorkStore
from etlantic_sqlmodel.control_plane.models import ScheduleSnapshotRow
from etlantic_sqlmodel.control_plane.session import session_scope
from sqlmodel import Session, SQLModel, select

T = TypeVar("T")

SCHEDULE_TABLES = (ScheduleSnapshotRow,)


def create_schedule_tables(engine: Engine) -> None:
    """Create schedule snapshot tables (tests/demos only)."""
    SQLModel.metadata.create_all(
        engine,
        tables=[cls.__table__ for cls in SCHEDULE_TABLES],  # type: ignore[list-item]
    )


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class SQLModelScheduleStore:
    """Transactional ScheduleStore backed by a SQL snapshot row."""

    def __init__(self, engine: Engine, *, store_id: str = "default") -> None:
        self.engine = engine
        self.store_id = store_id

    def _txn(self, fn: Callable[[MemoryScheduleStore], T]) -> T:
        with session_scope(self.engine) as session:
            mem, version = self._read(session, for_update=True)
            result = fn(mem)
            self._write(session, mem, expected_version=version)
            return result

    def _read_only(self, fn: Callable[[MemoryScheduleStore], T]) -> T:
        with session_scope(self.engine) as session:
            mem, _version = self._read(session, for_update=False)
            return fn(mem)

    def _read(
        self, session: Session, *, for_update: bool
    ) -> tuple[MemoryScheduleStore, int]:
        stmt = select(ScheduleSnapshotRow).where(
            ScheduleSnapshotRow.store_id == self.store_id
        )
        if for_update:
            stmt = stmt.with_for_update()
        row = session.exec(stmt).first()
        store = MemoryScheduleStore()
        if row is None:
            return store, 0
        store.load(json.loads(row.payload_json or "{}"))
        return store, int(row.payload_version or 0)

    def _write(
        self,
        session: Session,
        store: MemoryScheduleStore,
        *,
        expected_version: int,
    ) -> None:
        payload = json.dumps(store.dump(), sort_keys=True)
        row = session.exec(
            select(ScheduleSnapshotRow)
            .where(ScheduleSnapshotRow.store_id == self.store_id)
            .with_for_update()
        ).first()
        if row is None:
            if expected_version != 0:
                raise ControlPlaneError.conflict(
                    "Schedule snapshot version conflict (missing row)"
                )
            session.add(
                ScheduleSnapshotRow(
                    store_id=self.store_id,
                    payload_json=payload,
                    payload_version=1,
                    updated_at=_utcnow_iso(),
                )
            )
            return
        current = int(row.payload_version or 0)
        if current != expected_version:
            raise ControlPlaneError.conflict(
                "Schedule snapshot version conflict (stale write)"
            )
        row.payload_json = payload
        row.payload_version = current + 1
        row.updated_at = _utcnow_iso()
        session.add(row)

    def create(
        self,
        ctx: ControlPlaneContext,
        *,
        definition_id: str,
        profile_name: str,
        spec: ScheduleSpec,
        schedule_id: str | None = None,
        policy_fingerprint: str = "",
        parameter_refs: dict[str, str] | None = None,
        secret_refs: dict[str, str] | None = None,
        next_fire_at: str | None = None,
    ) -> ScheduleRecord:
        return self._txn(
            lambda m: m.create(
                ctx,
                definition_id=definition_id,
                profile_name=profile_name,
                spec=spec,
                schedule_id=schedule_id,
                policy_fingerprint=policy_fingerprint,
                parameter_refs=parameter_refs,
                secret_refs=secret_refs,
                next_fire_at=next_fire_at,
            )
        )

    def get(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord:
        return self._read_only(lambda m: m.get(ctx, schedule_id))

    def list_schedules(self, ctx: ControlPlaneContext) -> Sequence[ScheduleRecord]:
        return self._read_only(lambda m: m.list_schedules(ctx))

    def pause(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord:
        return self._txn(lambda m: m.pause(ctx, schedule_id))

    def resume(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord:
        return self._txn(lambda m: m.resume(ctx, schedule_id))

    def delete(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord:
        return self._txn(lambda m: m.delete(ctx, schedule_id))

    def acquire_leader_lease(
        self, ctx: ControlPlaneContext, *, owner_id: str, ttl_seconds: int
    ) -> SchedulerLeaderLease:
        return self._txn(
            lambda m: m.acquire_leader_lease(
                ctx, owner_id=owner_id, ttl_seconds=ttl_seconds
            )
        )

    def heartbeat_leader(
        self,
        ctx: ControlPlaneContext,
        *,
        owner_id: str,
        fencing_token: int,
        ttl_seconds: int,
    ) -> SchedulerLeaderLease:
        return self._txn(
            lambda m: m.heartbeat_leader(
                ctx,
                owner_id=owner_id,
                fencing_token=fencing_token,
                ttl_seconds=ttl_seconds,
            )
        )

    def release_leader(
        self, ctx: ControlPlaneContext, *, owner_id: str, fencing_token: int
    ) -> None:
        self._txn(
            lambda m: m.release_leader(
                ctx, owner_id=owner_id, fencing_token=fencing_token
            )
        )

    def due_schedules(
        self, ctx: ControlPlaneContext, *, now: str
    ) -> Sequence[ScheduleRecord]:
        return self._read_only(lambda m: m.due_schedules(ctx, now=now))

    def list_firings(
        self, ctx: ControlPlaneContext, schedule_id: str
    ) -> Sequence[FiringRecord]:
        return self._read_only(lambda m: m.list_firings(ctx, schedule_id))

    def claim_firing(
        self,
        ctx: ControlPlaneContext,
        *,
        schedule_id: str,
        revision_id: str,
        nominal_fire_time: str,
        owner_id: str,
        fencing_token: int,
        plan_fingerprint: str,
        durable: DurableWorkStore | None = None,
        next_fire_at: str | None = None,
    ) -> tuple[FiringRecord, bool]:
        kwargs: dict[str, Any] = {
            "schedule_id": schedule_id,
            "revision_id": revision_id,
            "nominal_fire_time": nominal_fire_time,
            "owner_id": owner_id,
            "fencing_token": fencing_token,
            "plan_fingerprint": plan_fingerprint,
            "next_fire_at": next_fire_at,
        }
        if (
            isinstance(durable, SQLModelDurableWorkStore)
            and durable.engine is self.engine
        ):
            with session_scope(self.engine) as session:
                sched, sv = self._read(session, for_update=True)
                dur_mem, dv = durable._read(session, for_update=True)
                result = sched.claim_firing(ctx, durable=dur_mem, **kwargs)
                self._write(session, sched, expected_version=sv)
                durable._write(session, dur_mem, expected_version=dv)
                return result
        return self._txn(lambda m: m.claim_firing(ctx, durable=durable, **kwargs))


__all__ = [
    "SCHEDULE_TABLES",
    "SQLModelScheduleStore",
    "create_schedule_tables",
]
