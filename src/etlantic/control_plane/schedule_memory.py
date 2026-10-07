# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""In-memory ScheduleStore (tests/dev). Production must reject this class."""

from __future__ import annotations

import hashlib
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
from etlantic.control_plane.models import ControlPlaneContext, Principal
from etlantic.control_plane.schedule_clock import _in_window
from etlantic.control_plane.schedule_models import (
    FiringRecord,
    FiringStatus,
    ScheduleRecord,
    ScheduleSpec,
    assert_schedule_payload_clean,
    firing_key,
)
from etlantic.control_plane.schedule_protocols import SchedulerLeaderLease

_NON_TERMINAL = frozenset({"accepted", "dispatched", "cancel_requested"})


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _submission_inflight(
    durable: DurableWorkStore | None,
    ctx: ControlPlaneContext,
    submission_id: str | None,
) -> bool:
    if submission_id is None:
        return True
    if durable is None:
        return True
    status_fn = getattr(durable, "submission_status", None)
    if callable(status_fn):
        status = status_fn(ctx, submission_id)
    else:
        try:
            status = durable.get_submission(ctx, submission_id).status
        except ControlPlaneError:
            return True
    return status in _NON_TERMINAL if status is not None else False


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
        self._firings: dict[tuple[str, str, str], FiringRecord] = {}
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
        definition_revision_id: str | None = None,
        parameter_refs: dict[str, str] | None = None,
        secret_refs: dict[str, Mapping[str, Any] | str] | None = None,
        revision_policy: str = "pinned",
        workload_identity: Principal | None = None,
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
            definition_revision_id=definition_revision_id,
            parameter_refs=dict(parameter_refs or {}),
            secret_refs={
                str(name): dict(value) if isinstance(value, Mapping) else value
                for name, value in (secret_refs or {}).items()
            },
            revision_policy=revision_policy,  # type: ignore[arg-type]
            workload_identity=workload_identity,
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

    def amend(
        self,
        ctx: ControlPlaneContext,
        schedule_id: str,
        *,
        expected_revision_id: str,
        spec: ScheduleSpec,
        next_fire_at: str | None,
        durable: DurableWorkStore | None = None,
    ) -> ScheduleRecord:
        """Create a new schedule revision after active firings have drained."""
        key = (*_scope(ctx), schedule_id)
        with self._lock:
            record = self._schedules.get(key)
            if record is None or record.status == "deleted":
                raise ControlPlaneError.not_found("schedule not found")
            if record.revision_id != expected_revision_id:
                raise ControlPlaneError.conflict(
                    "Schedule revision changed before amendment",
                    code="PMFIRE409",
                    extensions={"reason": "stale_revision"},
                )
            if self._has_inflight_firing(ctx, schedule_id, _scope(ctx), durable):
                raise ControlPlaneError.conflict(
                    "Schedule cannot be amended while a firing is active",
                    code="PMFIRE409",
                    extensions={"reason": "active_firing"},
                )
            metadata = dict(record.metadata)
            metadata["amends_revision_id"] = record.revision_id
            amended = replace(
                record,
                revision_id=f"rev-{uuid.uuid4().hex[:12]}",
                spec=spec,
                next_fire_at=next_fire_at,
                updated_at=_iso(),
                metadata=metadata,
            )
            self._schedules[key] = amended
            return deepcopy(amended)

    def delete(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord:
        return self._set_status(ctx, schedule_id, "deleted")

    def _set_status(
        self, ctx: ControlPlaneContext, schedule_id: str, status: str
    ) -> ScheduleRecord:
        key = (*_scope(ctx), schedule_id)
        with self._lock:
            rec = self._schedules.get(key)
            if rec is None or rec.status == "deleted":
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
        require_leader_lease: bool = True,
        admit_submission: bool = True,
        skip_status: FiringStatus | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[FiringRecord, bool]:
        logical = firing_key(schedule_id, revision_id, nominal_fire_time)
        scope = _scope(ctx)
        firing_scope = (*scope, logical)
        with self._lock:
            if require_leader_lease:
                self._require_leader(scope, owner_id, fencing_token)
            existing = self._firings.get(firing_scope)
            if existing is not None:
                return deepcopy(existing), False
            sk = (*scope, schedule_id)
            rec = self._schedules.get(sk)
            if rec is None:
                raise ControlPlaneError.not_found("schedule not found")
            if rec.status == "deleted":
                raise ControlPlaneError.conflict(
                    "Deleted schedules cannot accept a firing",
                    code="PMFIRE409",
                    extensions={"reason": "schedule_deleted"},
                )
            if rec.revision_id != revision_id:
                raise ControlPlaneError.conflict(
                    "Schedule revision changed before firing claim",
                    code="PMFIRE409",
                    extensions={"reason": "stale_revision"},
                )
            if require_leader_lease and rec.status != "active":
                raise ControlPlaneError.conflict(
                    "Only active schedules can accept a scheduled firing",
                    code="PMFIRE409",
                    extensions={"reason": "schedule_not_active"},
                )
            spec = rec.spec
            nominal_dt = _parse_iso(nominal_fire_time)
            status: FiringStatus = "accepted"
            if skip_status is not None:
                status = skip_status
            elif not _in_window(spec, nominal_dt):
                status = "skipped_window"
            elif spec.overlap == "skip" and self._has_inflight_firing(
                ctx, schedule_id, scope, durable
            ):
                status = "skipped_overlap"
            occurrence_metadata = dict(metadata or {})
            assert_schedule_payload_clean({"metadata": occurrence_metadata})
            firing = FiringRecord(
                firing_id=f"fire-{uuid.uuid4().hex[:16]}",
                schedule_id=schedule_id,
                revision_id=revision_id,
                nominal_fire_time=nominal_fire_time,
                tenant_id=ctx.tenant.tenant_id,
                workspace_id=ctx.workspace.workspace_id,
                created_at=_iso(),
                status=status,
                metadata=occurrence_metadata,
            )
            submission_id = None
            if status == "accepted" and durable is not None and admit_submission:
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
            self._firings[firing_scope] = firing
            self._schedules[sk] = replace(
                rec, next_fire_at=next_fire_at, updated_at=_iso()
            )
            return deepcopy(firing), True

    def link_firing_submission(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        submission_id: str,
        plan_fingerprint: str,
        durable: DurableWorkStore,
    ) -> FiringRecord:
        scope = _scope(ctx)
        with self._lock:
            matching = [
                (key, firing)
                for key, firing in self._firings.items()
                if key[:2] == scope and firing.firing_id == firing_id
            ]
            if not matching:
                raise ControlPlaneError.not_found("schedule firing not found")
            key, firing = matching[0]
            if firing.status != "accepted":
                raise ControlPlaneError.conflict(
                    "Only accepted schedule firings can link managed work"
                )
            if firing.submission_id is not None:
                if firing.submission_id != submission_id:
                    raise ControlPlaneError.conflict(
                        "Schedule firing is already linked to another submission"
                    )
                return deepcopy(firing)
            submission = durable.get_submission(ctx, submission_id)
            schedule = self._schedules.get((*scope, firing.schedule_id))
            selected_revision = firing.metadata.get("selected_definition_revision_id")
            expected_revision = (
                str(selected_revision)
                if isinstance(selected_revision, str) and selected_revision
                else (schedule.definition_revision_id if schedule is not None else None)
            )
            if schedule is None or (
                expected_revision is None or submission.revision_id != expected_revision
            ):
                raise ControlPlaneError.conflict(
                    "Managed schedule submission does not match its occurrence revision"
                )
            if (
                submission.operation != "run.submit"
                or submission.plan_fingerprint != plan_fingerprint
                or submission.idempotency_key
                != "schedule-"
                + hashlib.sha256(firing.logical_key.encode("utf-8")).hexdigest()
                or not submission.input_snapshot
            ):
                raise ControlPlaneError.conflict(
                    "Managed schedule submission is not an accepted executable run"
                )
            metadata = dict(firing.metadata)
            metadata.update(
                {
                    "definition_revision_id": expected_revision,
                    "plan_fingerprint": plan_fingerprint,
                    "admission": "managed",
                }
            )
            linked = replace(firing, submission_id=submission_id, metadata=metadata)
            self._firings[key] = linked
            return deepcopy(linked)

    def _has_inflight_firing(
        self,
        ctx: ControlPlaneContext,
        schedule_id: str,
        scope: tuple[str, str],
        durable: DurableWorkStore | None,
    ) -> bool:
        for item in self._firings.values():
            if item.schedule_id != schedule_id:
                continue
            if (item.tenant_id, item.workspace_id) != scope:
                continue
            if item.status != "accepted":
                continue
            if _submission_inflight(durable, ctx, item.submission_id):
                return True
        return False

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
                "firings": {
                    json.dumps(list(key)): rec.to_dict()
                    for key, rec in self._firings.items()
                },
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
            # Rebuild from canonical record scope so pre-fix snapshots whose
            # index keys omitted tenant/workspace remain readable and retain
            # their original firing and submission identities.
            firings = (
                FiringRecord.from_dict(value)
                for value in dict(payload.get("firings") or {}).values()
            )
            self._firings = {
                (record.tenant_id, record.workspace_id, record.logical_key): record
                for record in firings
            }
            self._leaders = {
                tuple(json.loads(key)): SchedulerLeaderLease(**value)
                for key, value in dict(payload.get("leaders") or {}).items()
            }
