"""Authorized, transport-independent schedule commands."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, TypeVar, cast, overload

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    Principal,
    ScheduleSpec,
    next_fire_after,
    require_authorized,
    validate_control_plane_context,
)
from etlantic.control_plane.protocols import Authorizer
from etlantic.control_plane.schedule_protocols import ScheduleStore

T = TypeVar("T")


@overload
def _iso(value: datetime) -> str: ...


@overload
def _iso(value: datetime | None) -> str | None: ...


def _iso(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value is not None else None


def _is_text(value: object) -> bool:
    return isinstance(value, str)


def _is_nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_aware_datetime(value: object) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


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
        definition_revision_id = None
        revision_policy = "pinned"
        if self.managed_service is not None:
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
            policy_data = {
                "revision_policy": revision_policy,
                "definition_revision_id": definition_revision_id,
                "parameter_refs": parameters,
                "secret_refs": secrets,
                "workload_identity": (
                    workload_identity.to_dict()
                    if workload_identity is not None
                    else None
                ),
                "profile_name": profile_name,
            }
            policy_fingerprint = hashlib.sha256(
                json.dumps(
                    policy_data,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                ).encode("utf-8")
            ).hexdigest()

        profile_name = profile_name or "default"
        next_fire = next_fire_after(spec, after=self._now())
        return schedule_store.create(
            ctx,
            definition_id=definition_id,
            profile_name=profile_name,
            spec=spec,
            next_fire_at=_iso(next_fire),
            policy_fingerprint=policy_fingerprint,
            definition_revision_id=definition_revision_id,
            parameter_refs=parameters,
            secret_refs=secrets,
            revision_policy=revision_policy,
            workload_identity=workload_identity,
        )

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
        amend = getattr(schedule_store, "amend", None)
        if not callable(amend):
            raise ControlPlaneError(
                "Schedule store does not support safe amendments",
                code="PMCP501",
                status=501,
                title="Not Implemented",
                type="etlantic.control_plane/not_implemented",
            )
        next_fire = next_fire_after(spec, after=self._now())
        return amend(
            ctx,
            schedule_id,
            expected_revision_id=expected_revision_id,
            spec=spec,
            next_fire_at=_iso(next_fire),
            durable=self.durable_work,
        )

    def pause(self, ctx: ControlPlaneContext, schedule_id: str) -> Any:
        return self._mutate(ctx, schedule_id, "pause")

    def resume(self, ctx: ControlPlaneContext, schedule_id: str) -> Any:
        return self._mutate(ctx, schedule_id, "resume")

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
        when: datetime = (
            nominal_fire_time if nominal_fire_time is not None else self._now()
        )
        if not _is_aware_datetime(cast(object, when)):
            raise _bad_request(
                "nominal_fire_time must be an ISO-8601 timestamp with a timezone"
            )
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
                    for item in schedule_store.list_firings(ctx, schedule_id)
                    if item.revision_id == record.revision_id
                    and item.nominal_fire_time == nominal
                ),
                None,
            )
            if existing is not None and existing.status != "accepted":
                return existing, False
            occurrence = self._occurrence_record(record, existing)
            recovered = managed.recover_scheduled_occurrence(ctx, occurrence, nominal)
            if recovered is not None:
                if existing is None:
                    raise ControlPlaneError.conflict(
                        "Recovered scheduled work has no durable firing record"
                    )
                submission_id, fingerprint = recovered
                linked = schedule_store.link_firing_submission(
                    ctx,
                    existing.firing_id,
                    submission_id=submission_id,
                    plan_fingerprint=fingerprint,
                    durable=self.durable_work,
                )
                return linked, False
            if existing is not None and existing.submission_id is not None:
                return existing, False

            prepared = managed.prepare_scheduled_occurrence(
                ctx, occurrence, nominal, existing_firing=existing
            )
            if existing is None:
                firing, created = schedule_store.claim_firing(
                    ctx,
                    schedule_id=record.schedule_id,
                    revision_id=record.revision_id,
                    nominal_fire_time=nominal,
                    owner_id="gateway",
                    fencing_token=0,
                    plan_fingerprint="managed-admission-pending",
                    durable=self.durable_work,
                    next_fire_at=record.next_fire_at,
                    require_leader_lease=False,
                    admit_submission=False,
                    metadata=dict(prepared.occurrence_snapshot or {}),
                )
                if not created:
                    occurrence = self._occurrence_record(record, firing)
                    recovered = managed.recover_scheduled_occurrence(
                        ctx, occurrence, nominal
                    )
                    if recovered is not None:
                        submission_id, fingerprint = recovered
                        linked = schedule_store.link_firing_submission(
                            ctx,
                            firing.firing_id,
                            submission_id=submission_id,
                            plan_fingerprint=fingerprint,
                            durable=self.durable_work,
                        )
                        return linked, False
                    prepared = managed.prepare_scheduled_occurrence(
                        ctx, occurrence, nominal, existing_firing=firing
                    )
            else:
                firing, created = existing, False
            if firing.status != "accepted" or firing.submission_id is not None:
                return firing, created
            submission_id, fingerprint = managed.submit_scheduled_run(
                ctx, prepared, nominal
            )
            linked = schedule_store.link_firing_submission(
                ctx,
                firing.firing_id,
                submission_id=submission_id,
                plan_fingerprint=fingerprint,
                durable=self.durable_work,
            )
            return linked, created

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
        )
        return firing, created

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
        return getattr(schedule_store, operation)(ctx, schedule_id)

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
