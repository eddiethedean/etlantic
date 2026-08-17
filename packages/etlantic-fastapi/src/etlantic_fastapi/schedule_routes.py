"""Schedule and scheduler/worker FastAPI routes (047-API)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    ScheduleSpec,
    next_fire_after,
    require_authorized,
)
from etlantic.runtime.scheduler_service import SchedulerService
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
        body: dict[str, Any],
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "schedule.write",
            f"definition:{definition_id}:schedules",
            resource_in_caller_scope=False,
        )
        spec = ScheduleSpec.from_dict(body.get("spec") or body)
        nxt = next_fire_after(spec, after=datetime.now(UTC))
        rec = _require_schedule().create(
            ctx,
            definition_id=definition_id,
            profile_name=str(body.get("profile_name") or "default"),
            spec=spec,
            next_fire_at=(
                nxt.isoformat().replace("+00:00", "Z") if nxt is not None else None
            ),
            policy_fingerprint=str(body.get("policy_fingerprint") or ""),
            parameter_refs=dict(body.get("parameter_refs") or {}),
            secret_refs=dict(body.get("secret_refs") or {}),
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
            for rec in _require_schedule().list_schedules(ctx)
            if rec.definition_id == definition_id
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
        lease = store.acquire_leader_lease(ctx, owner_id="gateway", ttl_seconds=30)
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        durable = getattr(api, "durable_work", None)
        firing, created = store.claim_firing(
            ctx,
            schedule_id=rec.schedule_id,
            revision_id=rec.revision_id,
            nominal_fire_time=now,
            owner_id="gateway",
            fencing_token=lease.fencing_token,
            plan_fingerprint=str(rec.policy_fingerprint or "gateway"),
            durable=durable,
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
            rec.to_dict() for rec in _require_schedule().list_firings(ctx, schedule_id)
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
