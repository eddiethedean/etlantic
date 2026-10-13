"""Thin FastAPI adapter for transport-independent schedule commands."""

# pyright: reportUnusedFunction=false

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, cast

from starlette.concurrency import run_in_threadpool

from etlantic.control_plane import (
    MAX_TRIGGER_ENVELOPE_BYTES,
    ControlPlaneContext,
    ControlPlaneError,
    Principal,
    ScheduleSpec,
    require_authorized,
    trigger_envelope_json_schema,
)
from etlantic_fastapi.schemas import (
    ScheduleCreateBody,
    ScheduleTimerTransferBody,
    TriggerReceiptResponse,
)
from fastapi import APIRouter, Depends, Request, Response


def register_schedule_routes(
    router: APIRouter,
    api: Any,
    get_ctx: Callable[..., Any],
) -> None:
    def service() -> Any:
        return api.get_schedule_service()

    def spec_from(raw: Any) -> ScheduleSpec:
        if not isinstance(raw, dict):
            raise ControlPlaneError(
                "Schedule specification must be an object",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        try:
            return ScheduleSpec.from_dict(cast(Mapping[str, Any], raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise ControlPlaneError(
                "Schedule specification is invalid",
                code="PMCP422",
                status=422,
                title="Unprocessable Entity",
                type="etlantic.control_plane/validation_error",
            ) from exc

    async def bounded_trigger_body(request: Request) -> bytes:
        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                declared_length = int(declared)
            except ValueError as exc:
                raise ControlPlaneError(
                    "Trigger content length is invalid",
                    code="PMTRG400",
                    status=400,
                    title="Bad Request",
                    type="etlantic.control_plane/bad_request",
                ) from exc
            if declared_length < 0:
                raise ControlPlaneError(
                    "Trigger content length is invalid",
                    code="PMTRG400",
                    status=400,
                    title="Bad Request",
                    type="etlantic.control_plane/bad_request",
                )
            if declared_length > MAX_TRIGGER_ENVELOPE_BYTES:
                raise ControlPlaneError(
                    "Trigger envelope exceeds the size limit",
                    code="PMTRG413",
                    status=413,
                    title="Payload Too Large",
                    type="etlantic.control_plane/payload_too_large",
                )
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_TRIGGER_ENVELOPE_BYTES:
                raise ControlPlaneError(
                    "Trigger envelope exceeds the size limit",
                    code="PMTRG413",
                    status=413,
                    title="Payload Too Large",
                    type="etlantic.control_plane/payload_too_large",
                )
            body.extend(chunk)
        return bytes(body)

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
        service().authorize(
            ctx, "schedule.write", f"definition:{definition_id}:schedules"
        )
        body_data = body.model_dump(exclude_none=True)
        managed = api.managed_service
        raw_identity = (
            body_data.get("workload_identity") if managed is not None else None
        )
        workload_identity = None
        if raw_identity is not None:
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
        record = service().create(
            ctx,
            definition_id,
            spec=spec_from(body_data.get("spec") or body_data),
            profile_name=(
                str(body_data["profile_name"])
                if body_data.get("profile_name") is not None
                else None
            ),
            policy_fingerprint=str(body_data.get("policy_fingerprint") or ""),
            parameter_refs=body_data.get("parameter_refs") or {},
            secret_refs=body_data.get("secret_refs") or {},
            revision_selector=str(body_data.get("revision_selector") or "current"),
            workload_identity=workload_identity,
            timer_owner=str(body_data.get("timer_owner") or "local"),
        )
        return record.to_dict()

    @router.get(
        "/v1/definitions/{definition_id}/schedules",
        operation_id="cp_list_definition_schedules",
        tags=["schedules"],
    )
    def list_definition_schedules(
        definition_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        return {
            "schedules": [
                item.to_dict() for item in service().list_definition(ctx, definition_id)
            ]
        }

    @router.get(
        "/v1/schedules/{schedule_id}",
        operation_id="cp_get_schedule",
        tags=["schedules"],
    )
    def get_schedule(
        schedule_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        return service().get(ctx, schedule_id).to_dict()

    @router.delete(
        "/v1/schedules/{schedule_id}",
        operation_id="cp_delete_schedule",
        tags=["schedules"],
    )
    def delete_schedule(
        schedule_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        service().authorize(ctx, "schedule.write", f"schedule:{schedule_id}")
        return service().delete(ctx, schedule_id).to_dict()

    @router.post(
        "/v1/schedules/{schedule_id}/timer-owner-transfer",
        operation_id="cp_transfer_schedule_timer_owner",
        tags=["schedules"],
    )
    def transfer_schedule_timer_owner(
        schedule_id: str,
        body: ScheduleTimerTransferBody,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        workload_identity = (
            Principal.from_dict(body.workload_identity.model_dump())
            if body.workload_identity is not None
            else None
        )
        return (
            service()
            .transfer_timer_owner(
                ctx,
                schedule_id,
                expected_revision_id=body.expected_revision_id,
                expected_generation=body.expected_generation,
                timer_owner=body.timer_owner,
                workload_identity=workload_identity,
            )
            .to_dict()
        )

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
        service().authorize(ctx, "schedule.write", f"schedule:{schedule_id}")
        if not {"expected_revision_id", "spec"}.issubset(body) or set(body) - {
            "expected_revision_id",
            "spec",
            "transfer_execution_route",
        }:
            raise ControlPlaneError(
                "Schedule amendment requires expected_revision_id and spec; only the managed route transfer option may also be supplied",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        revision = body.get("expected_revision_id")
        if not isinstance(revision, str) or not revision.strip():
            raise ControlPlaneError(
                "Schedule amendment requires a non-empty expected_revision_id",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        transfer_execution_route = body.get("transfer_execution_route", False)
        if type(transfer_execution_route) is not bool:
            raise ControlPlaneError(
                "transfer_execution_route must be a boolean",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        return (
            service()
            .amend(
                ctx,
                schedule_id,
                expected_revision_id=revision,
                spec=spec_from(body.get("spec")),
                transfer_execution_route=transfer_execution_route,
            )
            .to_dict()
        )

    @router.post(
        "/v1/schedules/{schedule_id}/pause",
        operation_id="cp_pause_schedule",
        tags=["schedules"],
    )
    def pause_schedule(
        schedule_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        return service().pause(ctx, schedule_id).to_dict()

    @router.post(
        "/v1/schedules/{schedule_id}/resume",
        operation_id="cp_resume_schedule",
        tags=["schedules"],
    )
    def resume_schedule(
        schedule_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        return service().resume(ctx, schedule_id).to_dict()

    @router.get(
        "/v1/schedules/{schedule_id}/preview",
        operation_id="cp_preview_schedule",
        tags=["schedules"],
    )
    def preview_schedule(
        schedule_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        return service().preview(ctx, schedule_id)

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
        service().authorize(ctx, "schedule.write", f"schedule:{schedule_id}")
        requested = (body or {}).get("nominal_fire_time")
        when = None
        if requested is not None:
            try:
                when = datetime.fromisoformat(str(requested).replace("Z", "+00:00"))
                if when.tzinfo is None or when.utcoffset() is None:
                    raise ValueError
                when = when.astimezone(UTC)
            except (TypeError, ValueError) as exc:
                raise ControlPlaneError(
                    "nominal_fire_time must be an ISO-8601 timestamp with a timezone",
                    code="PMCP400",
                    status=400,
                    title="Bad Request",
                    type="etlantic.control_plane/bad_request",
                ) from exc
        firing, created = service().trigger(ctx, schedule_id, nominal_fire_time=when)
        return {**firing.to_dict(), "created": created}

    @router.post(
        "/v1/schedules/{schedule_id}/external-trigger",
        operation_id="cp_external_schedule_trigger",
        tags=["schedules"],
        response_model=TriggerReceiptResponse,
        responses={202: {"model": TriggerReceiptResponse}},
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {"schema": trigger_envelope_json_schema()}
                },
            }
        },
    )
    async def external_trigger_schedule(
        schedule_id: str,
        request: Request,
        response: Response,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> TriggerReceiptResponse:
        from etlantic.control_plane import TriggerEnvelope

        schedule_service = service()
        await run_in_threadpool(
            schedule_service.authorize,
            ctx,
            "schedule.trigger",
            f"schedule:{schedule_id}",
        )
        envelope = TriggerEnvelope.from_json(await bounded_trigger_body(request))
        if envelope.schedule_id != schedule_id:
            raise ControlPlaneError(
                "Trigger schedule_id must match the route",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        receipt = await run_in_threadpool(
            schedule_service.trigger_external, ctx, envelope
        )
        if receipt.status == "pending":
            response.status_code = 202
        return receipt.to_dict()

    @router.get(
        "/v1/schedules/{schedule_id}/occurrences/{occurrence_id}",
        operation_id="cp_get_external_schedule_occurrence",
        tags=["schedules"],
        response_model=TriggerReceiptResponse,
    )
    def get_external_trigger_receipt(
        schedule_id: str,
        occurrence_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> TriggerReceiptResponse:
        receipt = service().get_external_trigger_receipt(
            ctx, schedule_id, occurrence_id
        )
        return receipt.to_dict()

    @router.get(
        "/v1/schedules/{schedule_id}/firings",
        operation_id="cp_list_firings",
        tags=["schedules"],
    )
    def list_firings(
        schedule_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        return {
            "firings": [
                item.to_dict() for item in service().list_firings(ctx, schedule_id)
            ]
        }

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
        items = api.runtime_role_items()
        role = dict(items).get("scheduler")
        if role is None:
            return {
                "status": "unknown",
                "role": "scheduler",
                "reason_code": "role_not_attached",
            }
        snapshot = role.status()
        return {
            **snapshot.to_dict(),
            "status": "ready"
            if snapshot.ready
            else "unknown"
            if snapshot.prerequisites == "unknown"
            else "unready",
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
        workers = [
            role.status().to_dict()
            for name, role in api.runtime_role_items()
            if name != "scheduler"
        ]
        if not workers or any(item["prerequisites"] == "unknown" for item in workers):
            summary = "unknown"
        elif any(
            item["admission"] == "stopped" or item["prerequisites"] == "unusable"
            for item in workers
        ):
            summary = "unready"
        elif all(item["ready"] for item in workers):
            summary = "ready"
        else:
            summary = "degraded"
        return {"status": summary, "workers": workers}
