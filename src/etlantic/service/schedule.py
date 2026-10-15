"""Authorized, transport-independent schedule commands."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable, Iterable, Mapping
from contextlib import suppress
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar, cast, overload
from urllib.parse import quote

from etlantic.control_plane import (
    MAX_TRIGGER_FUTURE_SKEW_SECONDS,
    TRIGGER_ENVELOPE_SCHEMA,
    ControlPlaneContext,
    ControlPlaneError,
    Principal,
    ScheduleSpec,
    TriggerEnvelope,
    TriggerReceipt,
    external_occurrence_id,
    next_fire_after,
    require_authorized,
    validate_control_plane_context,
)
from etlantic.control_plane.durable_models import (
    execution_route_backend,
    validate_execution_route,
)
from etlantic.control_plane.errors import is_permanent_control_plane_error
from etlantic.control_plane.protocols import Authorizer
from etlantic.control_plane.schedule_models import (
    FiringStatus,
    ScheduleRecord,
    ScheduleRevisionPolicy,
    TimerOwner,
)
from etlantic.control_plane.schedule_protocols import ScheduleStore

T = TypeVar("T")


@overload
def _iso(value: datetime) -> str: ...


@overload
def _iso(value: datetime | None) -> str | None: ...


def _iso(value: datetime | None) -> str | None:
    return (
        value.astimezone(UTC).isoformat().replace("+00:00", "Z")
        if value is not None
        else None
    )


def _is_text(value: object) -> bool:
    return isinstance(value, str)


def _is_nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_timer_binding_fingerprint(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _is_aware_datetime(value: object) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def _managed_schedule_policy_fingerprint(
    *,
    revision_policy: ScheduleRevisionPolicy,
    definition_revision_id: str | None,
    parameter_refs: Mapping[str, str],
    secret_refs: Mapping[str, Any],
    workload_identity: Principal | None,
    profile_name: str,
    execution_route: str,
    timer_owner: TimerOwner,
) -> str:
    policy_data = {
        "revision_policy": revision_policy,
        "definition_revision_id": definition_revision_id,
        "parameter_refs": dict(parameter_refs),
        "secret_refs": dict(secret_refs),
        "workload_identity": (
            workload_identity.to_dict() if workload_identity is not None else None
        ),
        "profile_name": profile_name,
        "execution_route": execution_route,
        "timer_owner": timer_owner,
    }
    return hashlib.sha256(
        json.dumps(
            policy_data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _bad_request(message: str) -> ControlPlaneError:
    return ControlPlaneError(
        message,
        code="PMCP400",
        status=400,
        title="Bad Request",
        type="etlantic.control_plane/bad_request",
    )


class ScheduleApplicationService:
    """Own schedule authorization and command orchestration for every adapter.

    Contexts must be derived by the caller from trusted identity. The service
    validates their shape and applies authorization before store access.
    """

    def __init__(
        self,
        *,
        authorizer: Authorizer,
        schedule_store: ScheduleStore | None,
        managed_service: Any = None,
        durable_work: Any = None,
        clock: Any = None,
    ) -> None:
        self.authorizer = authorizer
        self.schedule_store = schedule_store
        self.managed_service = managed_service
        self.durable_work = durable_work
        self.clock = clock or (lambda: datetime.now(UTC))

    def authorize(self, ctx: ControlPlaneContext, action: str, resource: str) -> None:
        """Apply canonical schedule authorization before adapter parsing."""
        validate_control_plane_context(ctx)
        require_authorized(
            self.authorizer,
            ctx,
            action,
            resource,
            resource_in_caller_scope=False,
        )

    def _require_schedule_store(self) -> ScheduleStore:
        if self.schedule_store is None:
            raise ControlPlaneError(
                "Schedule store is not configured",
                code="PMCP501",
                status=501,
                title="Not Implemented",
                type="etlantic.control_plane/not_implemented",
            )
        return self.schedule_store

    def _now(self) -> datetime:
        value: object = self.clock() if callable(self.clock) else self.clock.now()
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError("schedule clock must return a timezone-aware datetime")
        return value

    def create(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        *,
        spec: ScheduleSpec,
        profile_name: str | None = None,
        policy_fingerprint: str = "",
        parameter_refs: Mapping[str, Any] | None = None,
        secret_refs: Mapping[str, Any] | None = None,
        revision_selector: str = "current",
        workload_identity: Principal | None = None,
        schedule_id: str | None = None,
        timer_owner: TimerOwner = "local",
        timer_binding_fingerprint: str | None = None,
    ) -> Any:
        validate_control_plane_context(ctx)
        require_authorized(
            self.authorizer,
            ctx,
            "schedule.write",
            f"definition:{definition_id}:schedules",
            resource_in_caller_scope=False,
        )
        schedule_store = self._require_schedule_store()
        sid = schedule_id or f"sch-{uuid.uuid4().hex[:16]}"
        parameters = self._normalize_parameter_refs(parameter_refs)
        secrets = self._normalize_secret_refs(secret_refs)
        if workload_identity is not None:
            self._validate_workload_identity(workload_identity)
        if not _is_nonempty_text(revision_selector):
            raise _bad_request("revision_selector must be a non-empty string")
        if profile_name is not None and not _is_nonempty_text(profile_name):
            raise _bad_request("profile_name must be a string")
        if not _is_text(policy_fingerprint):
            raise _bad_request("policy_fingerprint must be a string")
        if timer_owner not in ("local", "external"):
            raise _bad_request("timer_owner must be local or external")
        if timer_binding_fingerprint is not None and not _is_timer_binding_fingerprint(
            cast(object, timer_binding_fingerprint)
        ):
            raise _bad_request(
                "timer_binding_fingerprint must be a lowercase SHA-256 value"
            )
        if timer_owner == "external":
            if self.managed_service is None or self.durable_work is None:
                raise ControlPlaneError(
                    "External timer ownership requires managed durable scheduling",
                    code="PMCP503",
                    status=503,
                    title="Service Unavailable",
                    type="etlantic.control_plane/unavailable",
                )
            if workload_identity is None:
                raise _bad_request(
                    "External timer ownership requires a workload_identity"
                )
            require_authorized(
                self.authorizer,
                ctx,
                "schedule.bind_external_timer",
                f"schedule:{sid}",
                resource_in_caller_scope=False,
            )
        definition_revision_id = None
        revision_policy = "pinned"
        execution_route = "local"
        if self.managed_service is not None:
            execution_route = validate_execution_route(
                getattr(self.managed_service, "execution_route", "local")
            )
            if workload_identity is not None:
                if workload_identity.kind not in ("workload", "service"):
                    raise _bad_request(
                        "Scheduled workload identity must have workload or service kind"
                    )
                require_authorized(
                    self.authorizer,
                    ctx,
                    "schedule.bind_workload",
                    "principal:"
                    + (workload_identity.issuer or "")
                    + "/"
                    + workload_identity.subject,
                    resource_in_caller_scope=False,
                )
            normalized_secrets = self.managed_service.validate_schedule_references(
                parameters, secrets
            )
            selected_revision, effective_profile = (
                self.managed_service.pin_schedule_definition_revision(
                    ctx, definition_id, revision_selector=revision_selector
                )
            )
            if revision_selector == "latest-approved":
                revision_policy = "latest-approved"
            else:
                definition_revision_id = selected_revision
            if profile_name is not None and profile_name != effective_profile:
                raise ControlPlaneError.conflict(
                    "Schedule profile differs from the managed service profile"
                )
            profile_name = effective_profile
            secrets = normalized_secrets
            policy_fingerprint = _managed_schedule_policy_fingerprint(
                revision_policy=revision_policy,
                definition_revision_id=definition_revision_id,
                parameter_refs=parameters,
                secret_refs=secrets,
                workload_identity=workload_identity,
                profile_name=effective_profile,
                execution_route=execution_route,
                timer_owner=timer_owner,
            )

        profile_name = profile_name or "default"
        schedule_start = self._now()
        if timer_owner == "external":
            schedule_start = schedule_start.replace(microsecond=0)
        next_fire = next_fire_after(spec, after=schedule_start)
        timer_schedule_start_at = (
            _iso(schedule_start) if timer_owner == "external" else None
        )
        reference_id = self._schedule_route_reference_id(ctx, sid)
        reserved = execution_route_backend(execution_route) != "local"
        if reserved:
            self._reserve_schedule_route_reference(ctx, execution_route, reference_id)
        try:
            return schedule_store.create(
                ctx,
                definition_id=definition_id,
                profile_name=profile_name,
                spec=spec,
                schedule_id=sid,
                next_fire_at=_iso(next_fire),
                policy_fingerprint=policy_fingerprint,
                definition_revision_id=definition_revision_id,
                parameter_refs=parameters,
                secret_refs=secrets,
                revision_policy=revision_policy,
                workload_identity=workload_identity,
                execution_route=execution_route,
                timer_owner=timer_owner,
                timer_schedule_start_at=timer_schedule_start_at,
                timer_binding_fingerprint=timer_binding_fingerprint,
            )
        except BaseException:
            # The store may have committed before a connection failure. Keep
            # the reservation unless a follow-up read proves the record absent.
            if reserved:
                self._release_if_schedule_absent(
                    ctx, schedule_store, sid, execution_route, reference_id
                )
            raise

    def list_definition(
        self, ctx: ControlPlaneContext, definition_id: str
    ) -> tuple[Any, ...]:
        validate_control_plane_context(ctx)
        require_authorized(
            self.authorizer,
            ctx,
            "schedule.read",
            f"definition:{definition_id}:schedules",
            resource_in_caller_scope=False,
        )
        schedule_store = self._require_schedule_store()
        records = [
            record
            for record in schedule_store.list_schedules(ctx)
            if record.definition_id == definition_id
        ]
        return self._visible(
            ctx, "schedule.read", records, lambda item: f"schedule:{item.schedule_id}"
        )

    def get(self, ctx: ControlPlaneContext, schedule_id: str) -> Any:
        validate_control_plane_context(ctx)
        require_authorized(
            self.authorizer,
            ctx,
            "schedule.read",
            f"schedule:{schedule_id}",
            resource_in_caller_scope=False,
        )
        return self._require_schedule_store().get(ctx, schedule_id)

    def amend(
        self,
        ctx: ControlPlaneContext,
        schedule_id: str,
        *,
        expected_revision_id: str,
        spec: ScheduleSpec,
        transfer_execution_route: bool = False,
        timer_binding_fingerprint: str | None = None,
    ) -> Any:
        validate_control_plane_context(ctx)
        require_authorized(
            self.authorizer,
            ctx,
            "schedule.write",
            f"schedule:{schedule_id}",
            resource_in_caller_scope=False,
        )
        schedule_store = self._require_schedule_store()
        if not _is_nonempty_text(expected_revision_id):
            raise _bad_request("Schedule amendment requires an expected revision")
        if type(transfer_execution_route) is not bool:
            raise _bad_request("transfer_execution_route must be a boolean")
        if timer_binding_fingerprint is not None and not _is_timer_binding_fingerprint(
            cast(object, timer_binding_fingerprint)
        ):
            raise _bad_request(
                "timer_binding_fingerprint must be a lowercase SHA-256 value"
            )
        amend_method = getattr(schedule_store, "amend", None)
        if not callable(amend_method):
            raise ControlPlaneError(
                "Schedule store does not support safe amendments",
                code="PMCP501",
                status=501,
                title="Not Implemented",
                type="etlantic.control_plane/not_implemented",
            )
        amend = cast(Callable[..., ScheduleRecord], amend_method)
        existing_record = schedule_store.get(ctx, schedule_id)
        execution_route: str | None = None
        policy_fingerprint: str | None = None
        prior_route: str | None = None
        if transfer_execution_route:
            if self.managed_service is None:
                raise _bad_request(
                    "Execution-route transfer requires managed execution"
                )
            current = existing_record
            prior_route = current.execution_route
            execution_route = validate_execution_route(
                getattr(self.managed_service, "execution_route", "local")
            )
            policy_fingerprint = _managed_schedule_policy_fingerprint(
                revision_policy=current.revision_policy,
                definition_revision_id=current.definition_revision_id,
                parameter_refs=current.parameter_refs,
                secret_refs=current.secret_refs,
                workload_identity=current.workload_identity,
                profile_name=current.profile_name,
                execution_route=execution_route,
                timer_owner=current.timer_owner,
            )
        schedule_start = self._now()
        if existing_record.timer_owner == "external":
            schedule_start = schedule_start.replace(microsecond=0)
        next_fire = next_fire_after(spec, after=schedule_start)
        timer_schedule_start_at = (
            _iso(schedule_start) if existing_record.timer_owner == "external" else None
        )
        reference_id = self._schedule_route_reference_id(ctx, schedule_id)
        reserved_new_route = (
            execution_route is not None
            and execution_route_backend(execution_route) != "local"
            and execution_route != prior_route
        )
        if reserved_new_route:
            assert execution_route is not None
            self._reserve_schedule_route_reference(ctx, execution_route, reference_id)
        try:
            amended = amend(
                ctx,
                schedule_id,
                expected_revision_id=expected_revision_id,
                spec=spec,
                next_fire_at=_iso(next_fire),
                timer_schedule_start_at=timer_schedule_start_at,
                timer_binding_fingerprint=timer_binding_fingerprint,
                execution_route=execution_route,
                policy_fingerprint=policy_fingerprint,
                durable=self.durable_work,
            )
        except BaseException:
            if reserved_new_route and execution_route is not None:
                self._release_if_schedule_route_is_not(
                    ctx,
                    schedule_store,
                    schedule_id,
                    execution_route,
                    reference_id,
                )
            raise
        if (
            prior_route
            and execution_route_backend(prior_route) != "local"
            and prior_route != amended.execution_route
        ):
            self._release_schedule_route_reference(ctx, prior_route, reference_id)
        return amended

    def pause(self, ctx: ControlPlaneContext, schedule_id: str) -> Any:
        return self._mutate(ctx, schedule_id, "pause")

    def transfer_timer_owner(
        self,
        ctx: ControlPlaneContext,
        schedule_id: str,
        *,
        expected_revision_id: str,
        expected_generation: int,
        timer_owner: TimerOwner,
        workload_identity: Principal | None = None,
        timer_binding_fingerprint: str | None = None,
    ) -> ScheduleRecord:
        """Fence the current timer generation before activating its successor."""
        validate_control_plane_context(ctx)
        require_authorized(
            self.authorizer,
            ctx,
            "schedule.transfer_timer",
            f"schedule:{schedule_id}",
            resource_in_caller_scope=False,
        )
        if self.managed_service is None or self.durable_work is None:
            raise ControlPlaneError(
                "Timer ownership transfer requires managed durable scheduling",
                code="PMCP503",
                status=503,
                title="Service Unavailable",
                type="etlantic.control_plane/unavailable",
            )
        if timer_owner not in ("local", "external"):
            raise _bad_request("timer_owner must be local or external")
        if not _is_nonempty_text(expected_revision_id):
            raise _bad_request("Timer transfer requires an expected revision")
        if type(expected_generation) is not int or expected_generation < 1:
            raise _bad_request("expected_generation must be positive")
        if timer_binding_fingerprint is not None and not _is_timer_binding_fingerprint(
            cast(object, timer_binding_fingerprint)
        ):
            raise _bad_request(
                "timer_binding_fingerprint must be a lowercase SHA-256 value"
            )
        schedule_store = self._require_schedule_store()
        current = schedule_store.get(ctx, schedule_id)
        if workload_identity is not None:
            self._validate_workload_identity(workload_identity)
            require_authorized(
                self.authorizer,
                ctx,
                "schedule.bind_workload",
                "principal:"
                + (workload_identity.issuer or "")
                + "/"
                + workload_identity.subject,
                resource_in_caller_scope=False,
            )
        if timer_owner == "external":
            if workload_identity is None:
                raise _bad_request(
                    "External timer transfer requires a workload_identity"
                )
            require_authorized(
                self.authorizer,
                ctx,
                "schedule.bind_external_timer",
                f"schedule:{schedule_id}",
                resource_in_caller_scope=False,
            )
        else:
            workload_identity = workload_identity or current.workload_identity
        policy_fingerprint = _managed_schedule_policy_fingerprint(
            revision_policy=current.revision_policy,
            definition_revision_id=current.definition_revision_id,
            parameter_refs=current.parameter_refs,
            secret_refs=current.secret_refs,
            workload_identity=workload_identity,
            profile_name=current.profile_name,
            execution_route=current.execution_route,
            timer_owner=timer_owner,
        )
        schedule_start = self._now()
        if timer_owner == "external":
            schedule_start = schedule_start.replace(microsecond=0)
        timer_schedule_start_at = (
            _iso(schedule_start) if timer_owner == "external" else None
        )
        return schedule_store.transfer_timer_owner(
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

    def resume(self, ctx: ControlPlaneContext, schedule_id: str) -> Any:
        return self._mutate(ctx, schedule_id, "resume")

    def delete(self, ctx: ControlPlaneContext, schedule_id: str) -> Any:
        validate_control_plane_context(ctx)
        require_authorized(
            self.authorizer,
            ctx,
            "schedule.write",
            f"schedule:{schedule_id}",
            resource_in_caller_scope=False,
        )
        schedule_store = self._require_schedule_store()
        reference_id = self._schedule_route_reference_id(ctx, schedule_id)
        try:
            deleted = schedule_store.delete(ctx, schedule_id)
        except ControlPlaneError as exc:
            if exc.status == 404:
                release = getattr(
                    self.durable_work, "release_execution_route_reference_id", None
                )
                if callable(release):
                    release(ctx, reference_id)
            raise
        if execution_route_backend(deleted.execution_route) != "local":
            self._release_schedule_route_reference(
                ctx,
                deleted.execution_route,
                reference_id,
            )
        return deleted

    def preview(self, ctx: ControlPlaneContext, schedule_id: str) -> dict[str, Any]:
        record = self.get(ctx, schedule_id)
        return {
            "schedule_id": record.schedule_id,
            "next_fire_at": _iso(next_fire_after(record.spec, after=self._now())),
        }

    def trigger(
        self,
        ctx: ControlPlaneContext,
        schedule_id: str,
        *,
        nominal_fire_time: datetime | None = None,
    ) -> tuple[Any, bool]:
        validate_control_plane_context(ctx)
        require_authorized(
            self.authorizer,
            ctx,
            "schedule.write",
            f"schedule:{schedule_id}",
            resource_in_caller_scope=False,
        )
        schedule_store = self._require_schedule_store()
        record = schedule_store.get(ctx, schedule_id)
        if record.timer_owner != "local":
            raise ControlPlaneError.forbidden(
                "Externally owned schedules require an authenticated trigger envelope"
            )
        occurrence_ctx = ctx
        if record.workload_identity is not None:
            occurrence_ctx = replace(
                ctx,
                principal=record.workload_identity,
                idempotency_key=None,
            )
        if self.managed_service is not None:
            require_authorized(
                self.authorizer,
                occurrence_ctx,
                "run.submit",
                f"definition:{record.definition_id}",
                resource_in_caller_scope=False,
            )
        when: datetime = (
            nominal_fire_time if nominal_fire_time is not None else self._now()
        )
        if not _is_aware_datetime(cast(object, when)):
            raise _bad_request(
                "nominal_fire_time must be an ISO-8601 timestamp with a timezone"
            )
        return self._trigger_record(
            occurrence_ctx,
            schedule_store,
            record,
            when,
            expected_timer_owner="local",
            expected_timer_owner_generation=record.timer_owner_generation,
            require_active=True,
        )

    def _trigger_record(
        self,
        ctx: ControlPlaneContext,
        schedule_store: ScheduleStore,
        record: ScheduleRecord,
        when: datetime,
        *,
        trigger_metadata: Mapping[str, Any] | None = None,
        advance_schedule: bool = False,
        advance_after: datetime | None = None,
        skip_status: FiringStatus | None = None,
        expected_next_fire_at: str | None = None,
        expected_timer_owner: TimerOwner | None = None,
        expected_timer_owner_generation: int | None = None,
        require_active: bool = False,
    ) -> tuple[Any, bool]:
        nominal = _iso(when.astimezone(UTC))
        managed = self.managed_service
        if managed is not None:
            if self.durable_work is None:
                raise ControlPlaneError(
                    "Managed schedule trigger requires durable work storage",
                    code="PMCP503",
                    status=503,
                    title="Service Unavailable",
                    type="etlantic.control_plane/unavailable",
                )
            existing = next(
                (
                    item
                    for item in schedule_store.list_firings(ctx, record.schedule_id)
                    if item.revision_id == record.revision_id
                    and item.nominal_fire_time == nominal
                ),
                None,
            )
            if existing is None:
                next_fire_at = record.next_fire_at
                if advance_schedule:
                    next_fire_at = _iso(
                        next_fire_after(
                            record.spec,
                            after=advance_after or when,
                            last_nominal=when,
                        )
                    )
                firing, created = schedule_store.claim_firing(
                    ctx,
                    schedule_id=record.schedule_id,
                    revision_id=record.revision_id,
                    nominal_fire_time=nominal,
                    owner_id="gateway",
                    fencing_token=0,
                    plan_fingerprint="managed-admission-pending",
                    durable=self.durable_work,
                    next_fire_at=next_fire_at,
                    require_leader_lease=False,
                    admit_submission=False,
                    skip_status=skip_status,
                    metadata=trigger_metadata,
                    expected_next_fire_at=expected_next_fire_at,
                    expected_timer_owner=expected_timer_owner,
                    expected_timer_owner_generation=expected_timer_owner_generation,
                    require_active=require_active,
                )
            else:
                firing, created = existing, False
            if firing.status != "accepted" or firing.submission_id is not None:
                return firing, created

            occurrence = self._occurrence_record(record, firing)
            recovered = managed.recover_scheduled_occurrence(ctx, occurrence, nominal)
            if recovered is not None:
                submission_id, fingerprint = recovered
                linked = schedule_store.link_firing_submission(
                    ctx,
                    firing.firing_id,
                    submission_id=submission_id,
                    plan_fingerprint=fingerprint,
                    durable=self.durable_work,
                    recovered=True,
                )
                return linked, created

            preparation_owner = f"trigger-{uuid.uuid4().hex}"
            firing, acquired = schedule_store.acquire_firing_preparation(
                ctx,
                firing.firing_id,
                owner_id=preparation_owner,
            )
            if not acquired:
                return firing, created
            fencing_token = firing.preparation_fencing_token
            try:

                def checkpoint(values: Mapping[str, Any]) -> None:
                    schedule_store.update_firing_metadata(
                        ctx,
                        firing.firing_id,
                        metadata=values,
                        owner_id=preparation_owner,
                        fencing_token=fencing_token,
                    )

                try:
                    prepared = managed.prepare_scheduled_occurrence(
                        ctx,
                        occurrence,
                        nominal,
                        existing_firing=firing,
                        checkpoint=checkpoint,
                    )
                    schedule_store.update_firing_metadata(
                        ctx,
                        firing.firing_id,
                        metadata={
                            **dict(prepared.occurrence_snapshot or {}),
                            **dict(trigger_metadata or {}),
                        },
                        owner_id=preparation_owner,
                        fencing_token=fencing_token,
                    )
                except Exception as exc:
                    if is_permanent_control_plane_error(exc):
                        with suppress(Exception):
                            schedule_store.fail_firing_preparation(
                                ctx,
                                firing.firing_id,
                                owner_id=preparation_owner,
                                fencing_token=fencing_token,
                            )
                    raise

                attempt_id: str | None = None

                def begin_admission() -> Callable[[], None]:
                    nonlocal attempt_id
                    attempt_id_value = uuid.uuid4().hex
                    attempt_id = attempt_id_value
                    schedule_store.begin_firing_submission(
                        ctx,
                        firing.firing_id,
                        owner_id=preparation_owner,
                        fencing_token=fencing_token,
                        attempt_id=attempt_id_value,
                    )

                    def reject_admission() -> None:
                        schedule_store.reject_firing_submission(
                            ctx, firing.firing_id, attempt_id=attempt_id_value
                        )

                    return reject_admission

                def fail_after_compensation() -> None:
                    if attempt_id is not None:
                        schedule_store.fail_firing_after_compensated_submission(
                            ctx, firing.firing_id, attempt_id=attempt_id
                        )

                prepared = replace(
                    prepared,
                    occurrence_acceptance_guard=begin_admission,
                    occurrence_compensation_guard=fail_after_compensation,
                )
                submission_id, fingerprint = managed.submit_scheduled_run(
                    ctx, prepared, nominal
                )
                linked = schedule_store.link_firing_submission(
                    ctx,
                    firing.firing_id,
                    submission_id=submission_id,
                    plan_fingerprint=fingerprint,
                    durable=self.durable_work,
                    preparation_owner_id=preparation_owner,
                    preparation_fencing_token=fencing_token,
                )
                return linked, created
            except Exception:
                # Preserve the original failure if compensation already
                # terminalized the firing and released its preparation lease.
                with suppress(Exception):
                    schedule_store.release_firing_preparation(
                        ctx,
                        firing.firing_id,
                        owner_id=preparation_owner,
                        fencing_token=fencing_token,
                    )
                raise

        firing, created = schedule_store.claim_firing(
            ctx,
            schedule_id=record.schedule_id,
            revision_id=record.revision_id,
            nominal_fire_time=nominal,
            owner_id="gateway",
            fencing_token=0,
            plan_fingerprint=str(record.policy_fingerprint or "gateway"),
            durable=self.durable_work,
            require_leader_lease=False,
            expected_next_fire_at=expected_next_fire_at,
            expected_timer_owner=expected_timer_owner,
            expected_timer_owner_generation=expected_timer_owner_generation,
            require_active=require_active,
        )
        return firing, created

    def trigger_external(
        self,
        ctx: ControlPlaneContext,
        envelope: TriggerEnvelope,
    ) -> TriggerReceipt:
        """Admit an authenticated occurrence from an external timer owner.

        Authorization precedes schedule/firing lookup. Retries resolve to the
        same schedule firing key and therefore the same durable submission.
        """
        validate_control_plane_context(ctx)
        envelope_value = cast(object, envelope)
        if not isinstance(envelope_value, TriggerEnvelope):
            raise _bad_request("trigger envelope must be a validated TriggerEnvelope")
        envelope = envelope_value
        require_authorized(
            self.authorizer,
            ctx,
            "schedule.trigger",
            f"schedule:{envelope.schedule_id}",
            resource_in_caller_scope=False,
        )
        schedule_store = self._require_schedule_store()
        if self.managed_service is None or self.durable_work is None:
            raise ControlPlaneError(
                "External trigger admission requires managed durable scheduling",
                code="PMCP503",
                status=503,
                title="Service Unavailable",
                type="etlantic.control_plane/unavailable",
            )
        record = schedule_store.get(ctx, envelope.schedule_id)
        if record.timer_owner != "external":
            raise ControlPlaneError.forbidden(
                "Schedule is not owned by an external timer"
            )
        if record.revision_id != envelope.schedule_revision_id:
            raise ControlPlaneError.conflict("Trigger schedule revision is stale")
        if record.timer_owner_generation != envelope.timer_owner_generation:
            raise ControlPlaneError.conflict("Trigger timer owner generation is stale")
        if record.workload_identity != ctx.principal:
            raise ControlPlaneError.forbidden(
                "Trigger principal does not match the bound workload identity"
            )
        require_authorized(
            self.authorizer,
            ctx,
            "run.submit",
            f"definition:{record.definition_id}",
            resource_in_caller_scope=False,
        )

        when = datetime.fromisoformat(envelope.scheduled_at.replace("Z", "+00:00"))
        now = self._now()
        when_utc = when.astimezone(UTC)
        now_utc = now.astimezone(UTC)
        skip_misfire = (record.spec.misfire == "skip" and when_utc < now_utc) or (
            record.spec.misfire == "catch_up"
            and record.spec.catch_up_max == 0
            and when_utc <= now_utc
        )
        existing = next(
            (
                item
                for item in schedule_store.list_firings(ctx, record.schedule_id)
                if item.revision_id == record.revision_id
                and item.nominal_fire_time == envelope.scheduled_at
            ),
            None,
        )
        expected = record.next_fire_at
        if existing is None and record.status != "active":
            raise ControlPlaneError.conflict("Schedule is not active")
        if existing is None:
            if when.astimezone(UTC) > now.astimezone(UTC) + timedelta(
                seconds=MAX_TRIGGER_FUTURE_SKEW_SECONDS
            ):
                raise ControlPlaneError.conflict(
                    "External trigger arrived before its scheduled occurrence"
                )
            if expected is None:
                raise ControlPlaneError.conflict(
                    "External trigger has no next scheduled occurrence"
                )
            try:
                expected_time = datetime.fromisoformat(
                    expected.replace("Z", "+00:00")
                ).astimezone(UTC)
            except (AttributeError, TypeError, ValueError) as exc:
                raise ControlPlaneError.conflict(
                    "Schedule next occurrence is invalid"
                ) from exc
            if expected_time != when.astimezone(UTC):
                raise ControlPlaneError.conflict(
                    "Trigger timestamp does not match the next scheduled occurrence"
                )

        firing, created = self._trigger_record(
            ctx,
            schedule_store,
            record,
            when,
            trigger_metadata={
                "external_trigger_schema": TRIGGER_ENVELOPE_SCHEMA,
                "external_trigger_occurrence_id": envelope.occurrence_id,
                "external_trigger_fingerprint": envelope.semantic_fingerprint,
            },
            advance_schedule=True,
            skip_status="skipped_misfire" if skip_misfire else None,
            advance_after=now if skip_misfire else None,
            # Compare against the exact cursor read above. Older snapshots may
            # store the same instant with a non-UTC offset.
            expected_next_fire_at=expected,
            expected_timer_owner="external",
            expected_timer_owner_generation=envelope.timer_owner_generation,
            require_active=True,
        )
        run_id = None
        if firing.submission_id is not None:
            submission = self.durable_work.get_submission(ctx, firing.submission_id)
            run_id = submission.run_id
        return TriggerReceipt(
            status=(
                "skipped"
                if firing.status != "accepted"
                else "accepted"
                if firing.submission_id is not None
                else "pending"
            ),
            firing_status=firing.status,
            schedule_id=record.schedule_id,
            schedule_revision_id=record.revision_id,
            occurrence_id=envelope.occurrence_id,
            submission_id=firing.submission_id,
            run_id=run_id,
            status_reference=self._trigger_status_reference(
                record.schedule_id, envelope.occurrence_id
            ),
            duplicate=not created,
        )

    def get_external_trigger_receipt(
        self,
        ctx: ControlPlaneContext,
        schedule_id: str,
        occurrence_id: str,
    ) -> TriggerReceipt:
        """Return the scoped status for one canonical external occurrence."""
        validate_control_plane_context(ctx)
        require_authorized(
            self.authorizer,
            ctx,
            "schedule.trigger",
            f"schedule:{schedule_id}",
            resource_in_caller_scope=False,
        )
        occurrence_value = cast(object, occurrence_id)
        if not isinstance(occurrence_value, str) or not occurrence_value.strip():
            raise _bad_request("occurrence_id must be non-empty")
        occurrence_id = occurrence_value
        schedule_store = self._require_schedule_store()
        firing = next(
            (
                item
                for item in schedule_store.list_firings(ctx, schedule_id)
                if external_occurrence_id(
                    item.schedule_id, item.revision_id, item.nominal_fire_time
                )
                == occurrence_id
            ),
            None,
        )
        if firing is None:
            raise ControlPlaneError.not_found("schedule occurrence not found")
        submission_id = firing.submission_id
        run_id = None
        if submission_id is None and self.durable_work is not None:
            occurrence_ctx = ctx
            schedule = None
            try:
                schedule = schedule_store.get(ctx, schedule_id)
            except ControlPlaneError as exc:
                if exc.status != 404:
                    raise
            if schedule is not None and schedule.workload_identity is not None:
                occurrence_ctx = replace(
                    ctx,
                    principal=schedule.workload_identity,
                    idempotency_key=None,
                )
            occurrence_key = firing.logical_key
            idempotency_key = (
                "schedule-" + hashlib.sha256(occurrence_key.encode("utf-8")).hexdigest()
            )
            recovered = self.durable_work.get_submission_by_idempotency(
                occurrence_ctx,
                idempotency_key=idempotency_key,
                operation="run.submit",
            )
            if recovered is not None:
                selected_revision = firing.metadata.get(
                    "selected_definition_revision_id"
                )
                expected_fingerprint = firing.metadata.get("plan_fingerprint")
                if (
                    recovered.operation != "run.submit"
                    or not recovered.input_snapshot
                    or (
                        isinstance(selected_revision, str)
                        and recovered.revision_id != selected_revision
                    )
                    or (
                        isinstance(expected_fingerprint, str)
                        and recovered.plan_fingerprint != expected_fingerprint
                    )
                ):
                    raise ControlPlaneError.conflict(
                        "Recovered schedule submission does not match its occurrence"
                    )
                submission_id = recovered.submission_id
                run_id = recovered.run_id
        if (
            submission_id is not None
            and run_id is None
            and self.durable_work is not None
        ):
            run_id = self.durable_work.get_submission(ctx, submission_id).run_id
        return TriggerReceipt(
            status=(
                "skipped"
                if firing.status != "accepted"
                else "accepted"
                if submission_id is not None
                else "pending"
            ),
            firing_status=firing.status,
            schedule_id=firing.schedule_id,
            schedule_revision_id=firing.revision_id,
            occurrence_id=occurrence_id,
            submission_id=submission_id,
            run_id=run_id,
            status_reference=self._trigger_status_reference(
                firing.schedule_id, occurrence_id
            ),
        )

    @staticmethod
    def _trigger_status_reference(schedule_id: str, occurrence_id: str) -> str:
        return (
            f"/v1/schedules/{quote(schedule_id, safe='')}/occurrences/"
            f"{quote(occurrence_id, safe='')}"
        )

    def list_firings(
        self, ctx: ControlPlaneContext, schedule_id: str
    ) -> tuple[Any, ...]:
        validate_control_plane_context(ctx)
        require_authorized(
            self.authorizer,
            ctx,
            "schedule.read",
            f"schedule:{schedule_id}:firings",
            resource_in_caller_scope=False,
        )
        schedule_store = self._require_schedule_store()
        return self._visible(
            ctx,
            "schedule.read",
            schedule_store.list_firings(ctx, schedule_id),
            lambda item: f"schedule:firing:{item.firing_id}",
        )

    def _mutate(
        self, ctx: ControlPlaneContext, schedule_id: str, operation: str
    ) -> Any:
        validate_control_plane_context(ctx)
        require_authorized(
            self.authorizer,
            ctx,
            "schedule.write",
            f"schedule:{schedule_id}",
            resource_in_caller_scope=False,
        )
        schedule_store = self._require_schedule_store()
        if operation == "resume":
            current = schedule_store.get(ctx, schedule_id)
            if current.timer_owner == "external":
                resume_external = getattr(schedule_store, "resume_external", None)
                if not callable(resume_external):
                    raise ControlPlaneError(
                        "Schedule store does not support fenced external resume",
                        code="PMCP501",
                        status=501,
                        title="Not Implemented",
                        type="etlantic.control_plane/not_implemented",
                    )
                schedule_start = self._now().replace(microsecond=0)
                next_fire = next_fire_after(current.spec, after=schedule_start)
                if next_fire is None:
                    raise _bad_request(
                        "External schedule has no future occurrence to resume"
                    )
                return resume_external(
                    ctx,
                    schedule_id,
                    expected_revision_id=current.revision_id,
                    expected_generation=current.timer_owner_generation,
                    next_fire_at=_iso(next_fire),
                    timer_schedule_start_at=_iso(schedule_start),
                )
        return getattr(schedule_store, operation)(ctx, schedule_id)

    def _reserve_schedule_route_reference(
        self, ctx: ControlPlaneContext, execution_route: str, reference_id: str
    ) -> None:
        reserve = getattr(self.durable_work, "reserve_execution_route_reference", None)
        if not callable(reserve):
            raise ControlPlaneError(
                "Managed schedule route fencing requires durable work storage",
                code="PMCP503",
                status=503,
                title="Service Unavailable",
                type="etlantic.control_plane/unavailable",
            )
        reserve(ctx, execution_route, reference_id)

    def _release_schedule_route_reference(
        self, ctx: ControlPlaneContext, execution_route: str, reference_id: str
    ) -> None:
        release = getattr(self.durable_work, "release_execution_route_reference", None)
        if not callable(release):
            raise ControlPlaneError(
                "Managed schedule route fencing requires durable work storage",
                code="PMCP503",
                status=503,
                title="Service Unavailable",
                type="etlantic.control_plane/unavailable",
            )
        release(ctx, execution_route, reference_id)

    def _release_if_schedule_absent(
        self,
        ctx: ControlPlaneContext,
        schedule_store: ScheduleStore,
        schedule_id: str,
        execution_route: str,
        reference_id: str,
    ) -> None:
        try:
            record = schedule_store.get(ctx, schedule_id)
        except ControlPlaneError as exc:
            if exc.status == 404:
                self._release_schedule_route_reference(
                    ctx, execution_route, reference_id
                )
            return
        if record.execution_route != execution_route:
            self._release_schedule_route_reference(ctx, execution_route, reference_id)

    def _release_if_schedule_route_is_not(
        self,
        ctx: ControlPlaneContext,
        schedule_store: ScheduleStore,
        schedule_id: str,
        execution_route: str,
        reference_id: str,
    ) -> None:
        try:
            record = schedule_store.get(ctx, schedule_id)
        except ControlPlaneError as exc:
            if exc.status == 404:
                self._release_schedule_route_reference(
                    ctx, execution_route, reference_id
                )
            return
        if record.execution_route != execution_route:
            self._release_schedule_route_reference(ctx, execution_route, reference_id)

    @staticmethod
    def _schedule_route_reference_id(ctx: ControlPlaneContext, schedule_id: str) -> str:
        encoded = json.dumps(
            [ctx.tenant.tenant_id, ctx.workspace.workspace_id, schedule_id],
            separators=(",", ":"),
        ).encode("utf-8")
        return "schedule:" + hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _occurrence_record(record: Any, firing: Any) -> Any:
        if firing is None:
            return record
        return replace(
            record,
            revision_id=firing.revision_id,
            occurrence_snapshot=dict(firing.metadata),
            occurrence_inputs=None,
        )

    @staticmethod
    def _validate_workload_identity(identity: object) -> None:
        if (
            not isinstance(identity, Principal)
            or not _is_nonempty_text(identity.subject)
            or identity.kind not in ("workload", "service")
            or (identity.issuer is not None and not _is_nonempty_text(identity.issuer))
        ):
            raise _bad_request("workload_identity is invalid")

    @staticmethod
    def _normalize_parameter_refs(value: object) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise _bad_request("parameter_refs must be an object")
        refs = cast(Mapping[Any, Any], value)
        result: dict[str, str] = {}
        for key, ref in refs.items():
            if not _is_nonempty_text(key) or not _is_nonempty_text(ref):
                raise _bad_request("parameter_refs must map names to references")
            result[cast(str, key)] = cast(str, ref)
        return result

    @staticmethod
    def _normalize_secret_refs(
        value: object,
    ) -> dict[str, Mapping[str, Any] | str]:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise _bad_request("secret_refs must be an object")
        refs = cast(Mapping[Any, Any], value)
        result: dict[str, Mapping[str, Any] | str] = {}
        for key, ref in refs.items():
            if not _is_nonempty_text(key):
                raise _bad_request("secret_refs contains an invalid alias")
            if isinstance(ref, str) and ref.strip():
                result[cast(str, key)] = ref
            elif isinstance(ref, Mapping):
                reference = cast(Mapping[object, object], ref)
                if not all(isinstance(name, str) for name in reference):
                    raise _bad_request("secret_refs contains an invalid reference")
                result[cast(str, key)] = cast(Mapping[str, Any], dict(reference))
            else:
                raise _bad_request("secret_refs contains an invalid reference")
        return result

    def _visible(
        self,
        ctx: ControlPlaneContext,
        action: str,
        records: Iterable[T],
        resource: Callable[[T], str],
    ) -> tuple[T, ...]:
        visible: list[T] = []
        try:
            for record in records:
                if (
                    self.authorizer.authorize(ctx, action, resource(record)).allowed
                    is True
                ):
                    visible.append(record)
        except Exception:
            raise ControlPlaneError(
                "Authorization service unavailable",
                code="PMCP503",
                status=503,
                title="Service Unavailable",
            ) from None
        return tuple(visible)


__all__ = ["ScheduleApplicationService"]
