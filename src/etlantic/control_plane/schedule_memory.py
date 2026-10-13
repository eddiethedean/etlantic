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
from typing import Any, cast

from etlantic.control_plane.durable_models import validate_execution_route
from etlantic.control_plane.durable_protocols import DurableWorkStore
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext, Principal
from etlantic.control_plane.schedule_clock import _in_window
from etlantic.control_plane.schedule_models import (
    FiringRecord,
    FiringStatus,
    ScheduleRecord,
    ScheduleRevisionPolicy,
    ScheduleSpec,
    ScheduleStatus,
    TimerOwner,
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
        revision_policy: ScheduleRevisionPolicy = "pinned",
        workload_identity: Principal | None = None,
        execution_route: str = "local",
        timer_owner: TimerOwner = "local",
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
            revision_policy=revision_policy,
            workload_identity=workload_identity,
            execution_route=validate_execution_route(execution_route),
            timer_owner=timer_owner,
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

    def execution_route_reference_count(self, execution_route: str) -> int:
        """Count live schedules across every scope that pin this route."""
        route = validate_execution_route(execution_route)
        with self._lock:
            return sum(
                record.execution_route == route and record.status != "deleted"
                for record in self._schedules.values()
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
        execution_route: str | None = None,
        policy_fingerprint: str | None = None,
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
            amended_route = (
                record.execution_route
                if execution_route is None
                else validate_execution_route(execution_route)
            )
            if amended_route != record.execution_route:
                metadata["execution_route_amended_from"] = record.execution_route
            amended = replace(
                record,
                revision_id=f"rev-{uuid.uuid4().hex[:12]}",
                spec=spec,
                next_fire_at=next_fire_at,
                updated_at=_iso(),
                metadata=metadata,
                execution_route=amended_route,
                policy_fingerprint=(
                    record.policy_fingerprint
                    if policy_fingerprint is None
                    else policy_fingerprint
                ),
            )
            self._schedules[key] = amended
            return deepcopy(amended)

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
    ) -> ScheduleRecord:
        """Fence one timer generation before switching delivery authority."""
        if timer_owner not in ("local", "external"):
            raise ValueError("timer_owner must be local or external")
        if type(expected_generation) is not int or expected_generation < 1:
            raise ValueError("expected_generation must be positive")
        if timer_owner == "external" and workload_identity is None:
            raise ValueError("external timer ownership requires workload_identity")
        if workload_identity is not None and workload_identity.kind not in (
            "workload",
            "service",
        ):
            raise ValueError("timer workload identity must be workload or service")
        key = (*_scope(ctx), schedule_id)
        with self._lock:
            current = self._schedules.get(key)
            if current is None or current.status == "deleted":
                raise ControlPlaneError.not_found("schedule not found")
            if (
                current.revision_id != expected_revision_id
                or current.timer_owner_generation != expected_generation
            ):
                raise ControlPlaneError.conflict(
                    "Schedule timer owner changed before transfer"
                )
            if any(
                firing.schedule_id == schedule_id
                and (firing.tenant_id, firing.workspace_id) == _scope(ctx)
                and firing.status == "accepted"
                and firing.submission_id is None
                for firing in self._firings.values()
            ):
                raise ControlPlaneError.conflict(
                    "Schedule timer owner cannot transfer while an occurrence is unlinked",
                    code="PMFIRE409",
                    extensions={"reason": "occurrence_preparation_pending"},
                )
            updated = replace(
                current,
                timer_owner=timer_owner,
                timer_owner_generation=current.timer_owner_generation + 1,
                workload_identity=workload_identity,
                policy_fingerprint=policy_fingerprint,
                updated_at=_iso(),
            )
            self._schedules[key] = updated
            return deepcopy(updated)

    def delete(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord:
        return self._set_status(ctx, schedule_id, "deleted")

    def _set_status(
        self, ctx: ControlPlaneContext, schedule_id: str, status: ScheduleStatus
    ) -> ScheduleRecord:
        key = (*_scope(ctx), schedule_id)
        with self._lock:
            rec = self._schedules.get(key)
            if rec is None or rec.status == "deleted":
                raise ControlPlaneError.not_found("schedule not found")
            if status == "deleted" and any(
                firing.schedule_id == schedule_id
                and (firing.tenant_id, firing.workspace_id) == _scope(ctx)
                and firing.status == "accepted"
                and firing.submission_id is None
                for firing in self._firings.values()
            ):
                raise ControlPlaneError.conflict(
                    "Schedule cannot be deleted while an occurrence is unlinked",
                    code="PMFIRE409",
                    extensions={"reason": "occurrence_preparation_pending"},
                )
            rec = replace(rec, status=status, updated_at=_iso())
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
            due: list[ScheduleRecord] = []
            for (tenant, workspace, _), rec in self._schedules.items():
                if (tenant, workspace) != scope:
                    continue
                if (
                    rec.status != "active"
                    or rec.timer_owner != "local"
                    or rec.next_fire_at is None
                ):
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
        expected_next_fire_at: str | None = None,
        expected_timer_owner: TimerOwner | None = None,
        expected_timer_owner_generation: int | None = None,
        require_active: bool = False,
    ) -> tuple[FiringRecord, bool]:
        logical = firing_key(schedule_id, revision_id, nominal_fire_time)
        scope = _scope(ctx)
        firing_scope = (*scope, logical)
        with self._lock:
            if require_leader_lease:
                self._require_leader(scope, owner_id, fencing_token)
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
            if require_leader_lease and rec.timer_owner != "local":
                raise ControlPlaneError.conflict(
                    "Polling scheduler cannot claim an externally owned schedule",
                    code="PMFIRE409",
                    extensions={"reason": "timer_owner_changed"},
                )
            if (
                expected_timer_owner is not None
                and rec.timer_owner != expected_timer_owner
            ):
                raise ControlPlaneError.conflict(
                    "Schedule timer owner changed before firing claim",
                    code="PMFIRE409",
                    extensions={"reason": "timer_owner_changed"},
                )
            if (
                expected_timer_owner_generation is not None
                and rec.timer_owner_generation != expected_timer_owner_generation
            ):
                raise ControlPlaneError.conflict(
                    "Schedule timer owner generation changed before firing claim",
                    code="PMFIRE409",
                    extensions={"reason": "timer_generation_changed"},
                )
            existing = self._firings.get(firing_scope)
            if existing is not None:
                return deepcopy(existing), False
            if (
                expected_next_fire_at is not None
                and rec.next_fire_at != expected_next_fire_at
            ):
                raise ControlPlaneError.conflict(
                    "Schedule next occurrence changed before external trigger admission",
                    code="PMFIRE409",
                    extensions={"reason": "stale_occurrence"},
                )
            if (require_active or require_leader_lease) and rec.status != "active":
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

    def acquire_firing_preparation(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        owner_id: object,
        ttl_seconds: int = 300,
    ) -> tuple[FiringRecord, bool]:
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError("preparation owner_id must be non-empty")
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 900:
            raise ValueError("preparation ttl_seconds must be between 1 and 900")
        scope = _scope(ctx)
        with self._lock:
            matches = [
                (key, firing)
                for key, firing in self._firings.items()
                if key[:2] == scope and firing.firing_id == firing_id
            ]
            if not matches:
                raise ControlPlaneError.not_found("schedule firing not found")
            key, firing = matches[0]
            if firing.status != "accepted":
                return deepcopy(firing), False
            if firing.submission_id is not None:
                return deepcopy(firing), False
            now = _now()
            expires = (
                datetime.fromisoformat(
                    firing.preparation_expires_at.replace("Z", "+00:00")
                )
                if firing.preparation_expires_at is not None
                else None
            )
            if (
                firing.preparation_owner_id is not None
                and expires is not None
                and expires > now
                and firing.preparation_owner_id != owner_id
            ):
                return deepcopy(firing), False
            token = firing.preparation_fencing_token
            if (
                firing.preparation_owner_id != owner_id
                or expires is None
                or expires <= now
            ):
                token += 1
            updated = replace(
                firing,
                preparation_owner_id=owner_id,
                preparation_fencing_token=token,
                preparation_expires_at=_iso(now + timedelta(seconds=ttl_seconds)),
            )
            self._firings[key] = updated
            return deepcopy(updated), True

    def update_firing_metadata(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        metadata: Mapping[str, Any],
        owner_id: str,
        fencing_token: int,
    ) -> FiringRecord:
        assert_schedule_payload_clean({"metadata": dict(metadata)})
        scope = _scope(ctx)
        with self._lock:
            matches = [
                (key, firing)
                for key, firing in self._firings.items()
                if key[:2] == scope and firing.firing_id == firing_id
            ]
            if not matches:
                raise ControlPlaneError.not_found("schedule firing not found")
            key, firing = matches[0]
            self._require_firing_preparation_lease(
                firing, owner_id=owner_id, fencing_token=fencing_token
            )
            merged = dict(firing.metadata)
            for name, value in metadata.items():
                if name in merged and merged[name] != value:
                    raise ControlPlaneError.conflict(
                        "Schedule occurrence metadata changed after its durable claim",
                        code="PMFIRE409",
                        extensions={
                            "reason": "occurrence_intent_changed",
                            "field": name,
                        },
                    )
                merged[name] = value
            updated = replace(firing, metadata=merged)
            self._firings[key] = updated
            return deepcopy(updated)

    def release_firing_preparation(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        owner_id: str,
        fencing_token: int,
    ) -> None:
        scope = _scope(ctx)
        with self._lock:
            for key, firing in self._firings.items():
                if key[:2] != scope or firing.firing_id != firing_id:
                    continue
                if (
                    firing.preparation_owner_id == owner_id
                    and firing.preparation_fencing_token == fencing_token
                ):
                    self._firings[key] = replace(
                        firing,
                        preparation_owner_id=None,
                        preparation_expires_at=None,
                    )
                return

    @staticmethod
    def _require_firing_preparation_lease(
        firing: FiringRecord, *, owner_id: str, fencing_token: int
    ) -> None:
        expires = (
            datetime.fromisoformat(firing.preparation_expires_at.replace("Z", "+00:00"))
            if firing.preparation_expires_at is not None
            else None
        )
        if (
            firing.preparation_owner_id != owner_id
            or firing.preparation_fencing_token != fencing_token
            or expires is None
            or expires <= _now()
        ):
            raise ControlPlaneError.conflict(
                "Schedule occurrence preparation lease is stale",
                code="PMFIRE409",
                extensions={"reason": "stale_preparation_lease"},
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
            if firing.preparation_owner_id is not None:
                if recovered:
                    pass
                elif preparation_owner_id is None or preparation_fencing_token is None:
                    raise ControlPlaneError.conflict(
                        "Schedule occurrence preparation lease is required to link managed work"
                    )
                else:
                    self._require_firing_preparation_lease(
                        firing,
                        owner_id=preparation_owner_id,
                        fencing_token=preparation_fencing_token,
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
            linked = replace(
                firing,
                submission_id=submission_id,
                metadata=metadata,
                preparation_owner_id=None,
                preparation_expires_at=None,
            )
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
            schedules: dict[str, Any] = {}
            for key, record in self._schedules.items():
                payload = record.to_dict()
                if record.timer_owner == "external":
                    # 0.58 readers validate revision_policy and will fail
                    # closed instead of treating an external timer as local.
                    payload["timer_revision_policy"] = record.revision_policy
                    payload["revision_policy"] = "external_timer_owned"
                schedules[json.dumps(list(key))] = payload
            return {
                "schedules": schedules,
                "firings": {
                    json.dumps(list(key)): rec.to_storage_dict()
                    for key, rec in self._firings.items()
                },
                "leaders": {
                    json.dumps(list(key)): asdict(lease)
                    for key, lease in self._leaders.items()
                },
            }

    def load(self, payload: Mapping[str, Any]) -> None:
        def checked_mapping(value: object, label: str) -> dict[str, Any]:
            if not isinstance(value, Mapping):
                raise ValueError(f"{label} must be an object")
            result: dict[str, Any] = {}
            for key, item in cast(Mapping[object, Any], value).items():
                if not isinstance(key, str):
                    raise ValueError(f"{label} field names must be strings")
                result[key] = item
            return result

        payload = checked_mapping(payload, "schedule snapshot")
        if set(payload) - {"schedules", "firings", "leaders"}:
            raise ValueError("schedule snapshot contains unsupported fields")

        raw_schedules = checked_mapping(
            payload.get("schedules") or {}, "schedule snapshot schedules"
        )
        schedules: dict[tuple[str, str, str], ScheduleRecord] = {}
        for encoded_key, value in raw_schedules.items():
            row = checked_mapping(value, "schedule snapshot schedule row")
            key_value: object = json.loads(encoded_key)
            if not isinstance(key_value, list):
                raise ValueError("schedule snapshot schedule key is malformed")
            key = cast(list[object], key_value)
            if len(key) != 3 or not all(isinstance(part, str) and part for part in key):
                raise ValueError("schedule snapshot schedule key is malformed")
            record = ScheduleRecord.from_dict(row)
            canonical_key = (record.tenant_id, record.workspace_id, record.schedule_id)
            if tuple(key) != canonical_key:
                raise ValueError("schedule snapshot key does not match its record")
            schedules[canonical_key] = record

        raw_firings = checked_mapping(
            payload.get("firings") or {}, "schedule snapshot firings"
        )
        firings: dict[tuple[str, str, str], FiringRecord] = {}
        for encoded_key, value in raw_firings.items():
            row = checked_mapping(value, "schedule snapshot firing row")
            legacy_key: str | None = None
            try:
                key_value: object = cast(object, json.loads(encoded_key))
            except json.JSONDecodeError:
                # Older snapshots used the logical firing key directly.
                key_value = encoded_key
            if isinstance(key_value, list):
                key = cast(list[object], key_value)
                if not all(isinstance(part, str) for part in key):
                    raise ValueError("schedule snapshot firing key is malformed")
            elif isinstance(key_value, str):
                legacy_key = key_value
            else:
                raise ValueError("schedule snapshot firing key is malformed")
            record = FiringRecord.from_dict(row)
            if legacy_key is not None and legacy_key != record.logical_key:
                raise ValueError("legacy schedule firing key does not match its row")
            # Rebuild from canonical record scope so old snapshots whose index
            # keys omitted tenant/workspace retain firing and submission IDs.
            firings[(record.tenant_id, record.workspace_id, record.logical_key)] = (
                record
            )

        raw_leaders = checked_mapping(
            payload.get("leaders") or {}, "schedule snapshot leaders"
        )
        leaders: dict[tuple[str, str], SchedulerLeaderLease] = {}
        for encoded_key, value in raw_leaders.items():
            row = checked_mapping(value, "schedule snapshot leader row")
            key_value: object = json.loads(encoded_key)
            if not isinstance(key_value, list):
                raise ValueError("schedule snapshot leader key is malformed")
            key = cast(list[object], key_value)
            if len(key) != 2 or not all(isinstance(part, str) and part for part in key):
                raise ValueError("schedule snapshot leader key is malformed")
            lease = SchedulerLeaderLease(**row)
            leader_scope = (cast(str, key[0]), cast(str, key[1]))
            if (lease.tenant_id, lease.workspace_id) != leader_scope:
                raise ValueError("schedule snapshot leader key does not match its row")
            leaders[leader_scope] = lease

        with self._lock:
            self._schedules = schedules
            self._firings = firings
            self._leaders = leaders
