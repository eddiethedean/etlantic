"""Control-plane route builders (definitions, runs, stubs, health)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

from starlette.responses import StreamingResponse

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    authorized_get_definition,
    redact_control_plane_payload,
    require_authorized,
)
from etlantic_fastapi.schemas import (
    AcceptReceiptResponse,
    ArtifactMeta,
    ArtifactsResponse,
    DefinitionGetResponse,
    DefinitionListResponse,
    DefinitionSummary,
    HealthResponse,
    LineageStubResponse,
    PlanResponse,
    ReadyResponse,
    ReliabilityListResponse,
    ReportStubResponse,
    RunStatusResponse,
    RunSubmitBody,
    SchemaObservationAckResponse,
    SchemaObservationsResponse,
    ValidateResponse,
)
from etlantic_fastapi.sse import (
    resolve_resume_cursor,
    sse_streaming_response,
)
from fastapi import APIRouter, Depends, Header, Query, Response, status

if TYPE_CHECKING:
    from etlantic_fastapi.api import ETLanticAPI


def _run_store_methods(
    api: ETLanticAPI,
) -> tuple[Callable[..., Any], Callable[..., Any]]:
    get_run = getattr(api.submissions, "get_run", None)
    cancel_run = getattr(api.submissions, "cancel_run", None)
    if get_run is None or cancel_run is None:
        raise ControlPlaneError(
            "Submission store does not support run observation",
            code="PMCP501",
            status=501,
            title="Not Implemented",
        )
    return get_run, cancel_run


def _validate_document(
    document: Mapping[str, Any], definition_id: str
) -> ValidateResponse:
    """Validate a stored definition document without executing pipelines."""
    fingerprint = None
    diagnostics: list[dict[str, Any]] = []
    ok = True
    if document.get("schema") == "etlantic.pipeline/1" or "nodes" in document:
        try:
            from etlantic.authoring.preview import structural_validate_preview
            from etlantic.authoring.serialize import (
                pipeline_fingerprint,
                pipeline_from_dict,
            )

            defn = pipeline_from_dict(dict(document), verify=False)
            report = structural_validate_preview(defn, profile="development")
            diagnostics = [d.to_dict() for d in report.diagnostics]
            ok = not report.has_errors
            fingerprint = defn.fingerprint or pipeline_fingerprint(defn)
        except Exception as exc:
            ok = False
            diagnostics = [
                {
                    "code": "PMCPVALIDATE",
                    "severity": "error",
                    "message": str(exc),
                }
            ]
    else:
        fingerprint = str(document.get("fingerprint") or definition_id)
    return ValidateResponse(
        ok=ok,
        definition_id=definition_id,
        diagnostics=diagnostics,
        fingerprint=fingerprint,
    )


def _plan_document(document: Mapping[str, Any], definition_id: str) -> PlanResponse:
    diagnostics: list[dict[str, Any]] = []
    plan: dict[str, Any] | None = None
    ok = False
    if document.get("schema") == "etlantic.pipeline/1" or "nodes" in document:
        try:
            from etlantic.authoring.preview import plan_preview
            from etlantic.authoring.serialize import pipeline_from_dict

            defn = pipeline_from_dict(dict(document), verify=False)
            planned, report = plan_preview(defn, profile="development")
            diagnostics = [d.to_dict() for d in report.diagnostics]
            plan = planned.to_dict() if planned is not None else None
            ok = planned is not None and not report.has_errors
        except Exception as exc:
            diagnostics = [
                {
                    "code": "PMCPPLAN",
                    "severity": "error",
                    "message": str(exc),
                }
            ]
            ok = False
    else:
        ok = True
        plan = {
            "schema": "etlantic.control_plane.plan_stub/1",
            "definition_id": definition_id,
            "note": "Non-pipeline document; plan stub only",
        }
    return PlanResponse(
        ok=ok,
        definition_id=definition_id,
        diagnostics=diagnostics,
        plan=plan,
    )


def build_control_plane_router(api: ETLanticAPI) -> APIRouter:
    """Build the CP1 router with stable OpenAPI operationIds."""
    router = APIRouter()
    get_ctx = api.context_dependency

    @router.get(
        "/health",
        operation_id="cp_health",
        response_model=HealthResponse,
        tags=["operability"],
    )
    def health() -> HealthResponse:
        return HealthResponse()

    @router.get(
        "/ready",
        operation_id="cp_ready",
        response_model=ReadyResponse,
        tags=["operability"],
    )
    def ready() -> ReadyResponse:
        injected = all(
            store is not None
            for store in (
                api.authorizer,
                api.definitions,
                api.submissions,
                api.events,
                api.context_factory,
            )
        )
        if not injected:
            return ReadyResponse(
                status="not_ready",
                stores_injected=False,
                detail="One or more control-plane stores are missing",
            )
        return ReadyResponse(status="ready", stores_injected=True)

    @router.get(
        "/v1/definitions",
        operation_id="cp_list_definitions",
        response_model=DefinitionListResponse,
        tags=["definitions"],
    )
    def list_definitions(
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> DefinitionListResponse:
        require_authorized(
            api.authorizer,
            ctx,
            "definition.list",
            "definition:*",
            resource_in_caller_scope=True,
        )
        ids = api.definitions.list(ctx)
        return DefinitionListResponse(
            items=[DefinitionSummary(definition_id=i) for i in ids]
        )

    @router.get(
        "/v1/definitions/{definition_id}",
        operation_id="cp_get_definition",
        response_model=DefinitionGetResponse,
        tags=["definitions"],
    )
    def get_definition(
        definition_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> DefinitionGetResponse:
        document = authorized_get_definition(
            api.authorizer, api.definitions, ctx, definition_id
        )
        return DefinitionGetResponse(
            definition_id=definition_id, document=dict(document)
        )

    @router.post(
        "/v1/definitions/{definition_id}/validate",
        operation_id="cp_validate_definition",
        response_model=ValidateResponse,
        tags=["definitions"],
    )
    def validate_definition(
        definition_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> ValidateResponse:
        document = authorized_get_definition(
            api.authorizer,
            api.definitions,
            ctx,
            definition_id,
            action="definition.validate",
        )
        return _validate_document(document, definition_id)

    @router.post(
        "/v1/definitions/{definition_id}/plan",
        operation_id="cp_plan_definition",
        response_model=PlanResponse,
        tags=["definitions"],
    )
    def plan_definition(
        definition_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> PlanResponse:
        document = authorized_get_definition(
            api.authorizer,
            api.definitions,
            ctx,
            definition_id,
            action="definition.plan",
        )
        return _plan_document(document, definition_id)

    @router.post(
        "/v1/definitions/{definition_id}/runs",
        operation_id="cp_submit_run",
        response_model=AcceptReceiptResponse,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["runs"],
    )
    def submit_run(
        definition_id: str,
        response: Response,
        ctx: ControlPlaneContext = Depends(get_ctx),
        body: RunSubmitBody | None = None,
        idempotency_key_header: str | None = Header(
            default=None, alias="Idempotency-Key"
        ),
    ) -> AcceptReceiptResponse:
        require_authorized(
            api.authorizer,
            ctx,
            "run.submit",
            f"definition:{definition_id}",
            resource_in_caller_scope=False,
        )
        # Authz before existence disclosure.
        try:
            api.definitions.get(ctx, definition_id)
        except KeyError as exc:
            raise ControlPlaneError.not_found(
                f"Definition {definition_id!r} not found"
            ) from exc

        body = body or RunSubmitBody()
        idem = (
            idempotency_key_header
            or body.idempotency_key
            or (ctx.idempotency_key.value if ctx.idempotency_key else None)
        )
        if not idem:
            raise ControlPlaneError(
                "Idempotency-Key is required for durable submit",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        payload = dict(body.payload or {})
        payload.setdefault("definition_id", definition_id)
        receipt = api.submissions.accept(
            ctx,
            idempotency_key=idem,
            payload=payload,
            resource_type="run",
        )
        if api.events is not None:
            run_id = receipt.resource_id or receipt.submission_id
            api.events.append(
                ctx,
                kind="run.accepted",
                payload={
                    "run_id": run_id,
                    "submission_id": receipt.submission_id,
                    "acceptance_id": receipt.acceptance_id,
                    "definition_id": definition_id,
                },
            )
        response.status_code = status.HTTP_202_ACCEPTED
        return AcceptReceiptResponse.model_validate(receipt.to_dict())

    @router.get(
        "/v1/runs/{run_id}",
        operation_id="cp_get_run",
        response_model=RunStatusResponse,
        tags=["runs"],
    )
    def get_run(
        run_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> RunStatusResponse:
        require_authorized(
            api.authorizer,
            ctx,
            "run.read",
            f"run:{run_id}",
            resource_in_caller_scope=False,
        )
        get_run_fn, _ = _run_store_methods(api)
        try:
            record = get_run_fn(ctx, run_id)
        except KeyError as exc:
            raise ControlPlaneError.not_found(f"Run {run_id!r} not found") from exc
        return RunStatusResponse.model_validate(record)

    @router.post(
        "/v1/runs/{run_id}/cancel",
        operation_id="cp_cancel_run",
        response_model=RunStatusResponse,
        tags=["runs"],
    )
    def cancel_run(
        run_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> RunStatusResponse:
        require_authorized(
            api.authorizer,
            ctx,
            "run.cancel",
            f"run:{run_id}",
            resource_in_caller_scope=False,
        )
        _, cancel_fn = _run_store_methods(api)
        try:
            record = cancel_fn(ctx, run_id)
        except KeyError as exc:
            raise ControlPlaneError.not_found(f"Run {run_id!r} not found") from exc
        if api.events is not None:
            api.events.append(
                ctx,
                kind="run.cancel_requested",
                payload={"run_id": run_id},
            )
        return RunStatusResponse.model_validate(record)

    @router.get(
        "/v1/runs/{run_id}/events",
        operation_id="cp_stream_run_events",
        tags=["runs"],
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Server-Sent Events stream of run lifecycle events",
                "content": {"text/event-stream": {}},
            },
            410: {
                "description": (
                    "Resume cursor expired or unknown; reconnect without "
                    "cursor to replay from the beginning"
                )
            },
        },
    )
    def stream_run_events(
        run_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
        cursor: str | None = Query(
            default=None,
            description="Opaque resume cursor (etlantic.control_plane.sse_cursor/1)",
        ),
        follow: bool = Query(
            default=False,
            description="When true, keep polling for new events after history",
        ),
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ) -> StreamingResponse:
        """Stream ordered run events as ``text/event-stream``.

        Authz precedes existence lookup. Cross-tenant runs map to opaque 404.
        Unknown/expired cursors return **410 Gone** (prefer reconnect without
        cursor to replay from the beginning) — see package README.
        """
        require_authorized(
            api.authorizer,
            ctx,
            "run.events",
            f"run:{run_id}",
            resource_in_caller_scope=False,
        )
        get_run_fn, _ = _run_store_methods(api)
        try:
            get_run_fn(ctx, run_id)
        except KeyError as exc:
            raise ControlPlaneError.not_found(f"Run {run_id!r} not found") from exc
        resume = resolve_resume_cursor(cursor=cursor, last_event_id=last_event_id)
        return sse_streaming_response(
            api.events,
            ctx,
            run_id,
            cursor=resume,
            follow=follow,
        )

    @router.get(
        "/v1/runs/{run_id}/report",
        operation_id="cp_get_run_report",
        response_model=ReportStubResponse,
        tags=["runs"],
    )
    def get_run_report(
        run_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> ReportStubResponse:
        require_authorized(
            api.authorizer,
            ctx,
            "run.report",
            f"run:{run_id}",
            resource_in_caller_scope=False,
        )
        get_run_fn, _ = _run_store_methods(api)
        try:
            record = get_run_fn(ctx, run_id)
        except KeyError as exc:
            raise ControlPlaneError.not_found(f"Run {run_id!r} not found") from exc
        return ReportStubResponse(
            run_id=run_id,
            status=str(record["status"]),
            metadata=redact_control_plane_payload(
                {
                    "acceptance_id": record.get("acceptance_id"),
                    "definition_id": record.get("definition_id"),
                    "note": (
                        "Minimal report metadata stub; "
                        "full reports arrive with execution hosts."
                    ),
                }
            ),
        )

    @router.get(
        "/v1/runs/{run_id}/artifacts",
        operation_id="cp_list_run_artifacts",
        response_model=ArtifactsResponse,
        tags=["runs"],
    )
    def list_run_artifacts(
        run_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> ArtifactsResponse:
        require_authorized(
            api.authorizer,
            ctx,
            "run.artifacts",
            f"run:{run_id}",
            resource_in_caller_scope=False,
        )
        get_run_fn, _ = _run_store_methods(api)
        try:
            get_run_fn(ctx, run_id)
        except KeyError as exc:
            raise ControlPlaneError.not_found(f"Run {run_id!r} not found") from exc
        return ArtifactsResponse(
            run_id=run_id,
            items=[
                ArtifactMeta(
                    artifact_id=f"{run_id}:accept-receipt",
                    kind="accept_receipt",
                    media_type="application/json",
                )
            ],
        )

    @router.get(
        "/v1/runs/{run_id}/lineage",
        operation_id="cp_get_run_lineage",
        response_model=LineageStubResponse,
        tags=["runs"],
    )
    def get_run_lineage(
        run_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> LineageStubResponse:
        require_authorized(
            api.authorizer,
            ctx,
            "run.lineage",
            f"run:{run_id}",
            resource_in_caller_scope=False,
        )
        get_run_fn, _ = _run_store_methods(api)
        try:
            record = get_run_fn(ctx, run_id)
        except KeyError as exc:
            raise ControlPlaneError.not_found(f"Run {run_id!r} not found") from exc
        definition_id = record.get("definition_id")
        nodes: list[dict[str, Any]] = [{"id": run_id, "kind": "run"}]
        edges: list[dict[str, Any]] = []
        if definition_id:
            nodes.append({"id": str(definition_id), "kind": "definition"})
            edges.append({"from": str(definition_id), "to": run_id, "kind": "produced"})
        return LineageStubResponse(run_id=run_id, nodes=nodes, edges=edges)

    @router.get(
        "/v1/schema/observations",
        operation_id="cp_list_schema_observations",
        response_model=SchemaObservationsResponse,
        tags=["schema"],
    )
    def list_schema_observations(
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> SchemaObservationsResponse:
        require_authorized(
            api.authorizer,
            ctx,
            "schema.observations.list",
            "schema:observations",
            resource_in_caller_scope=True,
        )
        return SchemaObservationsResponse(items=[])

    @router.post(
        "/v1/schema/observations/{observation_id}/ack",
        operation_id="cp_ack_schema_observation",
        response_model=SchemaObservationAckResponse,
        tags=["schema"],
    )
    def ack_schema_observation(
        observation_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> SchemaObservationAckResponse:
        require_authorized(
            api.authorizer,
            ctx,
            "schema.observations.ack",
            f"schema:observation:{observation_id}",
            resource_in_caller_scope=True,
        )
        return SchemaObservationAckResponse(observation_id=observation_id)

    @router.get(
        "/v1/reliability",
        operation_id="cp_list_reliability",
        response_model=ReliabilityListResponse,
        tags=["reliability"],
    )
    def list_reliability(
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> ReliabilityListResponse:
        require_authorized(
            api.authorizer,
            ctx,
            "reliability.list",
            "reliability:*",
            resource_in_caller_scope=True,
        )
        return ReliabilityListResponse(items=[])

    return router


__all__ = ["build_control_plane_router"]
