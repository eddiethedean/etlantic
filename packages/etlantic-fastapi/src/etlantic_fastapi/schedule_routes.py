"""Schedule and scheduler/worker FastAPI routes (047-API)."""

# pyright: reportUnusedFunction=false

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    Principal,
    ScheduleSpec,
    next_fire_after,
    require_authorized,
)
from etlantic.runtime.scheduler_service import SchedulerService
from etlantic_fastapi.collections import visible_items
from etlantic_fastapi.schemas import ScheduleCreateBody
from fastapi import APIRouter, Depends

if TYPE_CHECKING:
    from etlantic_fastapi.api import ETLanticAPI


def register_schedule_routes(
    router: APIRouter,
    api: ETLanticAPI,
    get_ctx: Callable[..., Any],
) -> None:
    def _require_schedule():
        store = getattr(api, "schedule_store", None)
        if store is None:
            raise ControlPlaneError(
                "Schedule store is not configured",
                code="PMCP501",
                status=501,
                title="Not Implemented",
            )
        return store

    @router.post(
        "/v1/definitions/{definition_id}/schedules",
        operation_id="cp_create_schedule",
        tags=["schedules"],
        status_code=201,
    )
    def create_schedule(
        definition_id: str,
        body: ScheduleCreateBody,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "schedule.write",
            f"definition:{definition_id}:schedules",
            resource_in_caller_scope=False,
        )
        body_data = body.model_dump(exclude_none=True)
        try:
            spec = ScheduleSpec.from_dict(body_data.get("spec") or body_data)
        except (KeyError, TypeError, ValueError) as exc:
            raise ControlPlaneError(
                "Schedule specification is invalid",
                code="PMCP422",
                status=422,
                title="Unprocessable Entity",
                type="etlantic.control_plane/validation_error",
            ) from exc
        managed = getattr(api, "managed_service", None)
        parameter_refs = dict(body_data.get("parameter_refs") or {})
        secret_refs = dict(body_data.get("secret_refs") or {})
        definition_revision_id = None
        revision_policy = "pinned"
        workload_identity = None
        profile_name = str(body_data.get("profile_name") or "default")
        if managed is not None:
            if body_data.get("workload_identity") is not None:
                raw_identity = body_data.get("workload_identity")
                if not isinstance(raw_identity, dict):
                    raise ControlPlaneError(
                        "workload_identity must be an authenticated workload descriptor",
                        code="PMCP400",
                        status=400,
                        title="Bad Request",
                        type="etlantic.control_plane/bad_request",
                    )
                try:
                    workload_identity = Principal.from_dict(
                        cast(Mapping[str, Any], raw_identity)
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise ControlPlaneError(
                        "workload_identity is invalid",
                        code="PMCP400",
                        status=400,
                        title="Bad Request",
                        type="etlantic.control_plane/bad_request",
                    ) from exc
                if workload_identity.kind not in ("workload", "service"):
                    raise ControlPlaneError(
                        "Scheduled workload identity must have workload or service kind",
                        code="PMCP400",
                        status=400,
                        title="Bad Request",
                        type="etlantic.control_plane/bad_request",
                    )
                require_authorized(
                    api.authorizer,
                    ctx,
                    "schedule.bind_workload",
                    "principal:"
                    + (workload_identity.issuer or "")
                    + "/"
                    + workload_identity.subject,
                    resource_in_caller_scope=False,
                )
            normalized_secret_refs = managed.validate_schedule_references(
                parameter_refs, secret_refs
            )
            selector = str(body_data.get("revision_selector") or "current")
            selected_revision, effective_profile = (
                managed.pin_schedule_definition_revision(
                    ctx,
                    definition_id,
                    revision_selector=selector,
                )
            )
            if selector == "latest-approved":
                revision_policy = "latest-approved"
            else:
                definition_revision_id = selected_revision
            if "profile_name" in body_data and profile_name != effective_profile:
                raise ControlPlaneError.conflict(
                    "Schedule profile differs from the managed service profile"
                )
            profile_name = effective_profile
            secret_refs = normalized_secret_refs
            policy_data = {
                "revision_policy": revision_policy,
                "definition_revision_id": definition_revision_id,
                "parameter_refs": parameter_refs,
                "secret_refs": secret_refs,
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
                ).encode("utf-8")
            ).hexdigest()
        else:
            policy_fingerprint = str(body_data.get("policy_fingerprint") or "")
        nxt = next_fire_after(spec, after=datetime.now(UTC))
        rec = _require_schedule().create(
            ctx,
            definition_id=definition_id,
            profile_name=profile_name,
            spec=spec,
            next_fire_at=(
                nxt.isoformat().replace("+00:00", "Z") if nxt is not None else None
            ),
            policy_fingerprint=policy_fingerprint,
            definition_revision_id=definition_revision_id,
            parameter_refs=parameter_refs,
            secret_refs=secret_refs,
            revision_policy=revision_policy,
            workload_identity=workload_identity,
        )
        return rec.to_dict()

    @router.get(
        "/v1/definitions/{definition_id}/schedules",
        operation_id="cp_list_definition_schedules",
        tags=["schedules"],
    )
    def list_definition_schedules(
        definition_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "schedule.read",
            f"definition:{definition_id}:schedules",
            resource_in_caller_scope=False,
        )
        items = [
            rec.to_dict()
            for rec in visible_items(
                api.authorizer,
                ctx,
                "schedule.read",
                [
                    rec
                    for rec in _require_schedule().list_schedules(ctx)
                    if rec.definition_id == definition_id
                ],
                lambda rec: f"schedule:{rec.schedule_id}",
            )
        ]
        return {"schedules": items}

    @router.get(
        "/v1/schedules/{schedule_id}",
        operation_id="cp_get_schedule",
        tags=["schedules"],
    )
    def get_schedule(
        schedule_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "schedule.read",
            f"schedule:{schedule_id}",
            resource_in_caller_scope=False,
        )
        return _require_schedule().get(ctx, schedule_id).to_dict()

    @router.post(
        "/v1/schedules/{schedule_id}/amend",
        operation_id="cp_amend_schedule",
        tags=["schedules"],
    )
    def amend_schedule(
        schedule_id: str,
        body: dict[str, Any],
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "schedule.write",
            f"schedule:{schedule_id}",
            resource_in_caller_scope=False,
        )
        store = _require_schedule()
        amend = getattr(store, "amend", None)
        if not callable(amend):
            raise ControlPlaneError(
                "Schedule store does not support safe amendments",
                code="PMCP501",
                status=501,
                title="Not Implemented",
                type="etlantic.control_plane/not_implemented",
            )
        if set(body) != {"expected_revision_id", "spec"}:
            raise ControlPlaneError(
                "Schedule amendment requires expected_revision_id and spec",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        expected_revision_id = body.get("expected_revision_id")
        if (
            not isinstance(expected_revision_id, str)
            or not expected_revision_id.strip()
        ):
            raise ControlPlaneError(
                "Schedule amendment requires a non-empty expected_revision_id",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        raw_spec = body.get("spec")
        if not isinstance(raw_spec, dict):
            raise ControlPlaneError(
                "Schedule amendment spec must be an object",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        try:
            spec = ScheduleSpec.from_dict(cast(Mapping[str, Any], raw_spec))
        except (KeyError, TypeError, ValueError) as exc:
            raise ControlPlaneError(
                "Schedule amendment spec is invalid",
                code="PMCP422",
                status=422,
                title="Unprocessable Entity",
                type="etlantic.control_plane/validation_error",
            ) from exc
        next_fire = next_fire_after(spec, after=datetime.now(UTC))
        amended = amend(
            ctx,
            schedule_id,
            expected_revision_id=expected_revision_id,
            spec=spec,
            next_fire_at=(
                next_fire.isoformat().replace("+00:00", "Z")
                if next_fire is not None
                else None
            ),
            durable=getattr(api, "durable_work", None),
        )
        return cast(Any, amended).to_dict()

    @router.post(
        "/v1/schedules/{schedule_id}/pause",
        operation_id="cp_pause_schedule",
        tags=["schedules"],
    )
    def pause_schedule(
        schedule_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "schedule.write",
            f"schedule:{schedule_id}",
            resource_in_caller_scope=False,
        )
        return _require_schedule().pause(ctx, schedule_id).to_dict()

    @router.post(
        "/v1/schedules/{schedule_id}/resume",
        operation_id="cp_resume_schedule",
        tags=["schedules"],
    )
    def resume_schedule(
        schedule_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "schedule.write",
            f"schedule:{schedule_id}",
            resource_in_caller_scope=False,
        )
        return _require_schedule().resume(ctx, schedule_id).to_dict()

    @router.get(
        "/v1/schedules/{schedule_id}/preview",
        operation_id="cp_preview_schedule",
        tags=["schedules"],
    )
    def preview_schedule(
        schedule_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "schedule.read",
            f"schedule:{schedule_id}",
            resource_in_caller_scope=False,
        )
        rec = _require_schedule().get(ctx, schedule_id)
        nxt = next_fire_after(rec.spec, after=datetime.now(UTC))
        return {
            "schedule_id": rec.schedule_id,
            "next_fire_at": nxt.isoformat().replace("+00:00", "Z") if nxt else None,
        }

    @router.post(
        "/v1/schedules/{schedule_id}/trigger",
        operation_id="cp_trigger_schedule",
        tags=["schedules"],
    )
    def trigger_schedule(
        schedule_id: str,
        body: dict[str, Any] | None = None,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "schedule.write",
            f"schedule:{schedule_id}",
            resource_in_caller_scope=False,
        )
        store = _require_schedule()
        rec = store.get(ctx, schedule_id)
        durable = getattr(api, "durable_work", None)
        managed = getattr(api, "managed_service", None)
        if managed is not None:
            if durable is None:
                raise ControlPlaneError(
                    "Managed schedule trigger requires durable work storage",
                    code="PMCP503",
                    status=503,
                    title="Service Unavailable",
                    type="etlantic.control_plane/unavailable",
                )
            requested_nominal = (body or {}).get("nominal_fire_time")
            try:
                parsed_nominal = (
                    datetime.now(UTC)
                    if requested_nominal is None
                    else datetime.fromisoformat(
                        str(requested_nominal).replace("Z", "+00:00")
                    )
                )
                if parsed_nominal.tzinfo is None:
                    raise ValueError("nominal_fire_time must include a timezone")
                now = parsed_nominal.astimezone(UTC).isoformat().replace("+00:00", "Z")
            except (TypeError, ValueError) as exc:
                raise ControlPlaneError(
                    "nominal_fire_time must be an ISO-8601 timestamp with a timezone",
                    code="PMCP400",
                    status=400,
                    title="Bad Request",
                    type="etlantic.control_plane/bad_request",
                ) from exc
            prepared = managed.prepare_scheduled_occurrence(ctx, rec, now)
            firing, created = store.claim_firing(
                ctx,
                schedule_id=rec.schedule_id,
                revision_id=rec.revision_id,
                nominal_fire_time=now,
                owner_id="gateway",
                fencing_token=0,
                plan_fingerprint="managed-admission-pending",
                durable=durable,
                next_fire_at=rec.next_fire_at,
                require_leader_lease=False,
                admit_submission=False,
                metadata=dict(prepared.occurrence_snapshot or {}),
            )
            if firing.status != "accepted" or firing.submission_id is not None:
                return {**firing.to_dict(), "created": created}
            prepared = managed.prepare_scheduled_occurrence(
                ctx, rec, now, existing_firing=firing
            )
            submission_id, fingerprint = managed.submit_scheduled_run(
                ctx, prepared, now
            )
            linked = store.link_firing_submission(
                ctx,
                firing.firing_id,
                submission_id=submission_id,
                plan_fingerprint=fingerprint,
                durable=durable,
            )
            return {**linked.to_dict(), "created": created}

        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        firing, created = store.claim_firing(
            ctx,
            schedule_id=rec.schedule_id,
            revision_id=rec.revision_id,
            nominal_fire_time=now,
            owner_id="gateway",
            fencing_token=0,
            plan_fingerprint=str(rec.policy_fingerprint or "gateway"),
            durable=durable,
            require_leader_lease=False,
        )
        return {**firing.to_dict(), "created": created}

    @router.get(
        "/v1/schedules/{schedule_id}/firings",
        operation_id="cp_list_firings",
        tags=["schedules"],
    )
    def list_firings(
        schedule_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "schedule.read",
            f"schedule:{schedule_id}:firings",
            resource_in_caller_scope=False,
        )
        items = [
            rec.to_dict()
            for rec in visible_items(
                api.authorizer,
                ctx,
                "schedule.read",
                _require_schedule().list_firings(ctx, schedule_id),
                lambda rec: f"schedule:firing:{rec.firing_id}",
            )
        ]
        return {"firings": items}

    @router.get(
        "/v1/scheduler/health",
        operation_id="cp_scheduler_health",
        tags=["schedules"],
    )
    def scheduler_health(
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "scheduler.health",
            "scheduler:health",
            resource_in_caller_scope=False,
        )
        store = getattr(api, "schedule_store", None)
        return {
            "status": "ok" if store is not None else "unconfigured",
            "role": "scheduler",
            "kind": type(SchedulerService).__name__,
        }

    @router.get(
        "/v1/workers/health",
        operation_id="cp_workers_health",
        tags=["schedules"],
    )
    def workers_health(
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "worker.health",
            "worker:health",
            resource_in_caller_scope=False,
        )
        return {"status": "ok", "workers": []}
