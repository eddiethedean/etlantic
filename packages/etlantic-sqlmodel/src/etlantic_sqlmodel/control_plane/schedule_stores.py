"""SQLModel-backed ScheduleStore (0.47).

Reference provider: each mutating call loads the schedule snapshot inside a
database transaction, applies MemoryScheduleStore semantics, and writes the
snapshot back. When the paired DurableWorkStore is the SQLModel provider on
the same engine, firing claim and durable accept share one commit.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, TypeVar

from sqlalchemy import text
from sqlalchemy.engine import Engine

from etlantic.control_plane.durable_memory import MemoryDurableWorkStore
from etlantic.control_plane.durable_protocols import DurableWorkStore
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext, Principal
from etlantic.control_plane.schedule_memory import MemoryScheduleStore
from etlantic.control_plane.schedule_models import (
    FiringRecord,
    ScheduleRecord,
    ScheduleRevisionPolicy,
    ScheduleSpec,
    TimerOwner,
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
        tables=[SQLModel.metadata.tables["cp_schedule_snapshot"]],
    )


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class SQLModelScheduleStore:
    """Transactional ScheduleStore backed by a SQL snapshot row."""

    def __init__(self, engine: Engine, *, store_id: str = "default") -> None:
        self.engine = engine
        self.store_id = store_id

    @contextmanager
    def timer_mutation_lock(
        self, ctx: ControlPlaneContext, schedule_id: str
    ) -> Generator[None, None, None]:
        """Serialize an external timer read/modify/write across processes.

        Session advisory locks are deliberately limited to PostgreSQL, whose
        lock lifetime spans the external AWS calls while releasing cleanly on
        connection loss. SQLite and other dialects cannot provide this
        cross-process guarantee and fail closed.
        """
        if self.engine.dialect.name != "postgresql":
            raise RuntimeError(
                "external timer mutation requires PostgreSQL advisory locks"
            )
        identity = "\0".join(
            (
                "schedule-timer-mutation",
                self.store_id,
                ctx.tenant.tenant_id,
                ctx.workspace.workspace_id,
                schedule_id,
            )
        )
        digest = hashlib.sha256(identity.encode("utf-8")).digest()[:8]
        lock_id = int.from_bytes(digest, byteorder="big", signed=True)
        with self.engine.connect() as connection:
            connection.execute(
                text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": lock_id}
            )
            try:
                yield
            finally:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"),
                    {"lock_id": lock_id},
                )

    def _txn(self, fn: Callable[[MemoryScheduleStore], T]) -> T:
        with session_scope(self.engine) as session:
            self._lock_store(session)
            mem, version = self._read(session, for_update=True)
            result = fn(mem)
            self._write(session, mem, expected_version=version)
            return result

    def _lock_store(self, session: Session) -> None:
        """Serialize PostgreSQL mutations even before the snapshot row exists.

        ``SELECT FOR UPDATE`` cannot lock a missing row. Without a transaction
        advisory lock, concurrent first schedule writes both observe version
        zero and race to create the unique snapshot row.
        """
        if self.engine.dialect.name != "postgresql":
            return
        digest = hashlib.sha256(("schedule:" + self.store_id).encode("utf-8")).digest()[
            :8
        ]
        lock_id = int.from_bytes(digest, byteorder="big", signed=True)
        session.connection().execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id}
        )

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
        definition_revision_id: str | None = None,
        parameter_refs: dict[str, str] | None = None,
        secret_refs: dict[str, Mapping[str, Any] | str] | None = None,
        revision_policy: ScheduleRevisionPolicy = "pinned",
        workload_identity: Principal | None = None,
        execution_route: str = "local",
        timer_owner: TimerOwner = "local",
        next_fire_at: str | None = None,
        timer_schedule_start_at: str | None = None,
        timer_binding_fingerprint: str | None = None,
    ) -> ScheduleRecord:
        return self._txn(
            lambda m: m.create(
                ctx,
                definition_id=definition_id,
                profile_name=profile_name,
                spec=spec,
                schedule_id=schedule_id,
                policy_fingerprint=policy_fingerprint,
                definition_revision_id=definition_revision_id,
                parameter_refs=parameter_refs,
                secret_refs=secret_refs,
                revision_policy=revision_policy,
                workload_identity=workload_identity,
                execution_route=execution_route,
                timer_owner=timer_owner,
                next_fire_at=next_fire_at,
                timer_schedule_start_at=timer_schedule_start_at,
                timer_binding_fingerprint=timer_binding_fingerprint,
            )
        )

    def get(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord:
        return self._read_only(lambda m: m.get(ctx, schedule_id))

    def list_schedules(self, ctx: ControlPlaneContext) -> Sequence[ScheduleRecord]:
        return self._read_only(lambda m: m.list_schedules(ctx))

    def execution_route_reference_count(self, execution_route: str) -> int:
        return self._read_only(
            lambda m: m.execution_route_reference_count(execution_route)
        )

    def pause(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord:
        return self._txn(lambda m: m.pause(ctx, schedule_id))

    def resume(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord:
        return self._txn(lambda m: m.resume(ctx, schedule_id))

    def resume_external(
        self,
        ctx: ControlPlaneContext,
        schedule_id: str,
        *,
        expected_revision_id: str,
        expected_generation: int,
        next_fire_at: str,
        timer_schedule_start_at: str,
    ) -> ScheduleRecord:
        return self._txn(
            lambda m: m.resume_external(
                ctx,
                schedule_id,
                expected_revision_id=expected_revision_id,
                expected_generation=expected_generation,
                next_fire_at=next_fire_at,
                timer_schedule_start_at=timer_schedule_start_at,
            )
        )

    def amend(
        self,
        ctx: ControlPlaneContext,
        schedule_id: str,
        *,
        expected_revision_id: str,
        spec: ScheduleSpec,
        next_fire_at: str | None,
        timer_schedule_start_at: str | None = None,
        timer_binding_fingerprint: str | None = None,
        execution_route: str | None = None,
        policy_fingerprint: str | None = None,
        durable: DurableWorkStore | None = None,
    ) -> ScheduleRecord:
        return self._txn(
            lambda m: m.amend(
                ctx,
                schedule_id,
                expected_revision_id=expected_revision_id,
                spec=spec,
                next_fire_at=next_fire_at,
                timer_schedule_start_at=timer_schedule_start_at,
                timer_binding_fingerprint=timer_binding_fingerprint,
                execution_route=execution_route,
                policy_fingerprint=policy_fingerprint,
                durable=durable,
            )
        )

    def transfer_timer_owner(
        self,
        ctx: ControlPlaneContext,
        schedule_id: str,
        *,
        expected_revision_id: str,
        expected_generation: int,
        timer_owner: TimerOwner,
        workload_identity: Principal | None,
        policy_fingerprint: str,
        timer_schedule_start_at: str | None = None,
        timer_binding_fingerprint: str | None = None,
    ) -> ScheduleRecord:
        return self._txn(
            lambda memory: memory.transfer_timer_owner(
                ctx,
                schedule_id,
                expected_revision_id=expected_revision_id,
                expected_generation=expected_generation,
                timer_owner=timer_owner,
                workload_identity=workload_identity,
                policy_fingerprint=policy_fingerprint,
                timer_schedule_start_at=timer_schedule_start_at,
                timer_binding_fingerprint=timer_binding_fingerprint,
            )
        )

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
        require_leader_lease: bool = True,
        admit_submission: bool = True,
        skip_status: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        expected_next_fire_at: str | None = None,
        expected_timer_owner: TimerOwner | None = None,
        expected_timer_owner_generation: int | None = None,
        require_active: bool = False,
    ) -> tuple[FiringRecord, bool]:
        kwargs: dict[str, Any] = {
            "schedule_id": schedule_id,
            "revision_id": revision_id,
            "nominal_fire_time": nominal_fire_time,
            "owner_id": owner_id,
            "fencing_token": fencing_token,
            "plan_fingerprint": plan_fingerprint,
            "next_fire_at": next_fire_at,
            "require_leader_lease": require_leader_lease,
            "admit_submission": admit_submission,
            "skip_status": skip_status,
            "metadata": metadata,
            "expected_next_fire_at": expected_next_fire_at,
            "expected_timer_owner": expected_timer_owner,
            "expected_timer_owner_generation": expected_timer_owner_generation,
            "require_active": require_active,
        }
        if (
            isinstance(durable, SQLModelDurableWorkStore)
            and durable.engine is self.engine
        ):
            with session_scope(self.engine) as session:
                self._lock_store(session)
                sched, sv = self._read(session, for_update=True)

                def claim(
                    durable_memory: MemoryDurableWorkStore,
                ) -> tuple[FiringRecord, bool]:
                    result = sched.claim_firing(ctx, durable=durable_memory, **kwargs)
                    self._write(session, sched, expected_version=sv)
                    return result

                return durable.apply_in_transaction(session, claim)
        return self._txn(lambda m: m.claim_firing(ctx, durable=durable, **kwargs))

    def acquire_firing_preparation(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        owner_id: str,
        ttl_seconds: int = 300,
    ) -> tuple[FiringRecord, bool]:
        return self._txn(
            lambda store: store.acquire_firing_preparation(
                ctx,
                firing_id,
                owner_id=owner_id,
                ttl_seconds=ttl_seconds,
            )
        )

    def update_firing_metadata(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        metadata: Mapping[str, object],
        owner_id: str,
        fencing_token: int,
    ) -> FiringRecord:
        return self._txn(
            lambda store: store.update_firing_metadata(
                ctx,
                firing_id,
                metadata=metadata,
                owner_id=owner_id,
                fencing_token=fencing_token,
            )
        )

    def release_firing_preparation(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        owner_id: str,
        fencing_token: int,
    ) -> None:
        self._txn(
            lambda store: store.release_firing_preparation(
                ctx,
                firing_id,
                owner_id=owner_id,
                fencing_token=fencing_token,
            )
        )

    def begin_firing_submission(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        owner_id: str,
        fencing_token: int,
        attempt_id: str | None = None,
    ) -> FiringRecord:
        return self._txn(
            lambda store: store.begin_firing_submission(
                ctx,
                firing_id,
                owner_id=owner_id,
                fencing_token=fencing_token,
                attempt_id=attempt_id,
            )
        )

    def reject_firing_submission(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        attempt_id: str,
    ) -> FiringRecord:
        return self._txn(
            lambda store: store.reject_firing_submission(
                ctx, firing_id, attempt_id=attempt_id
            )
        )

    def fail_firing_after_compensated_submission(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        attempt_id: str,
    ) -> FiringRecord:
        return self._txn(
            lambda store: store.fail_firing_after_compensated_submission(
                ctx, firing_id, attempt_id=attempt_id
            )
        )

    def fail_firing_preparation(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        owner_id: str,
        fencing_token: int,
    ) -> FiringRecord:
        return self._txn(
            lambda store: store.fail_firing_preparation(
                ctx,
                firing_id,
                owner_id=owner_id,
                fencing_token=fencing_token,
            )
        )

    def link_firing_submission(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        submission_id: str,
        plan_fingerprint: str,
        durable: DurableWorkStore,
        preparation_owner_id: str | None = None,
        preparation_fencing_token: int | None = None,
        recovered: bool = False,
    ) -> FiringRecord:
        if (
            isinstance(durable, SQLModelDurableWorkStore)
            and durable.engine is self.engine
        ):
            with session_scope(self.engine) as session:
                self._lock_store(session)
                sched, version = self._read(session, for_update=True)

                def link(durable_memory: MemoryDurableWorkStore) -> FiringRecord:
                    result = sched.link_firing_submission(
                        ctx,
                        firing_id,
                        submission_id=submission_id,
                        plan_fingerprint=plan_fingerprint,
                        durable=durable_memory,
                        preparation_owner_id=preparation_owner_id,
                        preparation_fencing_token=preparation_fencing_token,
                        recovered=recovered,
                    )
                    self._write(session, sched, expected_version=version)
                    return result

                return durable.apply_in_transaction(session, link)
        return self._txn(
            lambda schedule_memory: schedule_memory.link_firing_submission(
                ctx,
                firing_id,
                submission_id=submission_id,
                plan_fingerprint=plan_fingerprint,
                durable=durable,
                preparation_owner_id=preparation_owner_id,
                preparation_fencing_token=preparation_fencing_token,
                recovered=recovered,
            )
        )


__all__ = [
    "SCHEDULE_TABLES",
    "SQLModelScheduleStore",
    "create_schedule_tables",
]
