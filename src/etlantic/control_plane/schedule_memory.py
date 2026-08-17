"""In-memory ScheduleStore (tests/dev). Production must reject this class."""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from typing import Any

from etlantic.control_plane.durable_protocols import DurableWorkStore
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.schedule_models import (
    FiringRecord,
    ScheduleRecord,
    ScheduleSpec,
    firing_key,
)
from etlantic.control_plane.schedule_protocols import SchedulerLeaderLease


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat().replace("+00:00", "Z")


def _scope(ctx: ControlPlaneContext) -> tuple[str, str]:
    return ctx.scope_key


class MemoryScheduleStore:
    """Thread-safe reference ScheduleStore. Not for production profiles."""

    def __init__(self) -> None:
        self._schedules: dict[tuple[str, str, str], ScheduleRecord] = {}
        self._firings: dict[str, FiringRecord] = {}
        self._leaders: dict[tuple[str, str], SchedulerLeaderLease] = {}
        self._lock = threading.RLock()

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
        sid = (schedule_id or f"sch-{uuid.uuid4().hex[:16]}").strip()
        revision = f"rev-{uuid.uuid4().hex[:12]}"
        now = _iso()
        record = ScheduleRecord(
            schedule_id=sid,
            definition_id=definition_id,
            revision_id=revision,
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            profile_name=profile_name,
            policy_fingerprint=policy_fingerprint,
            spec=spec,
            created_at=now,
            updated_at=now,
            status="active",
            next_fire_at=next_fire_at,
            parameter_refs=dict(parameter_refs or {}),
            secret_refs=dict(secret_refs or {}),
        )
        key = (*_scope(ctx), sid)
        with self._lock:
            if key in self._schedules:
                raise ControlPlaneError.conflict(f"schedule {sid} already exists")
            self._schedules[key] = record
            return deepcopy(record)

    def get(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord:
        key = (*_scope(ctx), schedule_id)
        with self._lock:
            rec = self._schedules.get(key)
            if rec is None or rec.status == "deleted":
                raise ControlPlaneError.not_found("schedule not found")
            return deepcopy(rec)

    def list_schedules(self, ctx: ControlPlaneContext) -> Sequence[ScheduleRecord]:
        scope = _scope(ctx)
        with self._lock:
            return tuple(
                deepcopy(rec)
                for (tenant, workspace, _), rec in self._schedules.items()
                if (tenant, workspace) == scope and rec.status != "deleted"
            )

    def pause(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord:
        return self._set_status(ctx, schedule_id, "paused")

    def resume(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord:
        return self._set_status(ctx, schedule_id, "active")

    def delete(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord:
        return self._set_status(ctx, schedule_id, "deleted")

    def _set_status(
        self, ctx: ControlPlaneContext, schedule_id: str, status: str
    ) -> ScheduleRecord:
        key = (*_scope(ctx), schedule_id)
        with self._lock:
            rec = self._schedules.get(key)
            if rec is None:
                raise ControlPlaneError.not_found("schedule not found")
            rec = replace(rec, status=status, updated_at=_iso())  # type: ignore[arg-type]
            self._schedules[key] = rec
            return deepcopy(rec)

    def acquire_leader_lease(
        self,
        ctx: ControlPlaneContext,
        *,
        owner_id: str,
        ttl_seconds: int,
    ) -> SchedulerLeaderLease:
        scope = _scope(ctx)
        with self._lock:
            current = self._leaders.get(scope)
            now = _now()
            held = (
                current is not None
                and datetime.fromisoformat(current.expires_at.replace("Z", "+00:00"))
                > now
            )
            if held and current is not None and current.owner_id != owner_id:
                raise ControlPlaneError.conflict("scheduler leader lease held")
            if held and current is not None and current.owner_id == owner_id:
                lease = replace(
                    current,
                    expires_at=_iso(now + timedelta(seconds=ttl_seconds)),
                    heartbeat_at=_iso(now),
                )
                self._leaders[scope] = lease
                return deepcopy(lease)
            token = 1 if current is None else current.fencing_token + 1
            lease = SchedulerLeaderLease(
                owner_id=owner_id,
                fencing_token=token,
                expires_at=_iso(now + timedelta(seconds=ttl_seconds)),
                heartbeat_at=_iso(now),
                tenant_id=ctx.tenant.tenant_id,
                workspace_id=ctx.workspace.workspace_id,
            )
            self._leaders[scope] = lease
            return deepcopy(lease)

    def heartbeat_leader(
        self,
        ctx: ControlPlaneContext,
        *,
        owner_id: str,
        fencing_token: int,
        ttl_seconds: int,
    ) -> SchedulerLeaderLease:
        scope = _scope(ctx)
        with self._lock:
            self._require_leader(scope, owner_id, fencing_token)
            now = _now()
            lease = replace(
                self._leaders[scope],
                expires_at=_iso(now + timedelta(seconds=ttl_seconds)),
                heartbeat_at=_iso(now),
            )
            self._leaders[scope] = lease
            return deepcopy(lease)

    def release_leader(
        self,
        ctx: ControlPlaneContext,
        *,
        owner_id: str,
        fencing_token: int,
    ) -> None:
        scope = _scope(ctx)
        with self._lock:
            old = self._require_leader(scope, owner_id, fencing_token)
            self._leaders[scope] = replace(
                old,
                expires_at=_iso(_now() - timedelta(seconds=1)),
            )

    def _require_leader(
        self, scope: tuple[str, str], owner_id: str, token: int
    ) -> SchedulerLeaderLease:
        lease = self._leaders.get(scope)
        if (
            lease is None
            or lease.owner_id != owner_id
            or lease.fencing_token != token
            or datetime.fromisoformat(lease.expires_at.replace("Z", "+00:00")) <= _now()
        ):
            raise ControlPlaneError.conflict("Stale or invalid scheduler leader lease")
        return lease

    def due_schedules(
        self, ctx: ControlPlaneContext, *, now: str
    ) -> Sequence[ScheduleRecord]:
        scope = _scope(ctx)
        with self._lock:
            due = []
            for (tenant, workspace, _), rec in self._schedules.items():
                if (tenant, workspace) != scope:
                    continue
                if rec.status != "active" or rec.next_fire_at is None:
                    continue
                if rec.next_fire_at <= now:
                    due.append(deepcopy(rec))
            return tuple(due)

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
        logical = firing_key(schedule_id, revision_id, nominal_fire_time)
        scope = _scope(ctx)
        with self._lock:
            self._require_leader(scope, owner_id, fencing_token)
            existing = self._firings.get(logical)
            if existing is not None:
                return deepcopy(existing), False
            firing = FiringRecord(
                firing_id=f"fire-{uuid.uuid4().hex[:16]}",
                schedule_id=schedule_id,
                revision_id=revision_id,
                nominal_fire_time=nominal_fire_time,
                tenant_id=ctx.tenant.tenant_id,
                workspace_id=ctx.workspace.workspace_id,
                created_at=_iso(),
                status="accepted",
            )
            submission_id = None
            if durable is not None:
                submission, _created = durable.accept(
                    ctx,
                    idempotency_key=logical,
                    operation="schedule.fire",
                    plan_fingerprint=plan_fingerprint,
                    revision_id=revision_id,
                    submission_id=firing.firing_id,
                )
                submission_id = submission.submission_id
            firing = replace(firing, submission_id=submission_id)
            self._firings[logical] = firing
            sk = (*scope, schedule_id)
            rec = self._schedules.get(sk)
            if rec is not None:
                self._schedules[sk] = replace(
                    rec, next_fire_at=next_fire_at, updated_at=_iso()
                )
            return deepcopy(firing), True

    def list_firings(
        self, ctx: ControlPlaneContext, schedule_id: str
    ) -> Sequence[FiringRecord]:
        scope = _scope(ctx)
        with self._lock:
            return tuple(
                deepcopy(item)
                for item in self._firings.values()
                if item.schedule_id == schedule_id
                and (item.tenant_id, item.workspace_id) == scope
            )

    def dump(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schedules": {
                    json.dumps(list(key)): rec.to_dict()
                    for key, rec in self._schedules.items()
                },
                "firings": {key: rec.to_dict() for key, rec in self._firings.items()},
                "leaders": {
                    json.dumps(list(key)): asdict(lease)
                    for key, lease in self._leaders.items()
                },
            }

    def load(self, payload: Mapping[str, Any]) -> None:
        with self._lock:
            self._schedules = {
                tuple(json.loads(key)): ScheduleRecord.from_dict(value)
                for key, value in dict(payload.get("schedules") or {}).items()
            }
            self._firings = {
                str(key): FiringRecord.from_dict(value)
                for key, value in dict(payload.get("firings") or {}).items()
            }
            self._leaders = {
                tuple(json.loads(key)): SchedulerLeaderLease(**value)
                for key, value in dict(payload.get("leaders") or {}).items()
            }
