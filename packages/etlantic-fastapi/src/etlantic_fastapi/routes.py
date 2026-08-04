"""Control-plane route builders (definitions, runs, stubs, health)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from starlette.responses import StreamingResponse

from etlantic.control_plane import (
    AliasRecord,
    ControlPlaneContext,
    ControlPlaneError,
    LifecycleState,
    TenantRecord,
    WorkspaceRecord,
    authorized_get_definition,
    redact_control_plane_payload,
    redact_control_plane_text,
    require_authorized,
    require_authorized_run,
)
from etlantic_fastapi.schemas import (
    AcceptReceiptResponse,
    AliasPutBody,
    AliasResponse,
    ArtifactMeta,
    ArtifactsResponse,
    DefinitionGetResponse,
    DefinitionListResponse,
    DefinitionSummary,
    DurableCheckpointCasBody,
    DurableFinishAttemptBody,
    DurableLeaseBody,
    DurableLeaseTokenBody,
    DurablePreviewBody,
    DurableReplayBody,
    DurableStartAttemptBody,
    HealthResponse,
    LineageStubResponse,
    PlanResponse,
    PromoteBody,
    PromotionResponse,
    ReadyResponse,
    ReliabilityListResponse,
    ReportStubResponse,
    RevisionListResponse,
    RevisionResponse,
    RunStatusResponse,
    RunSubmitBody,
    SchemaObservationAckResponse,
    SchemaObservationsResponse,
    TenantListResponse,
    TenantPutBody,
    TenantRecordResponse,
    ValidateResponse,
    WorkspaceListResponse,
    WorkspacePutBody,
    WorkspaceRecordResponse,
)
from etlantic_fastapi.sse import (
    resolve_resume_cursor,
    sse_streaming_response,
)
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status

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


def _run_exists_probe(api: ETLanticAPI, ctx: ControlPlaneContext, run_id: str) -> bool:
    get_run_fn, _ = _run_store_methods(api)

    def _probe() -> bool:
        try:
            get_run_fn(ctx, run_id)
            return True
        except KeyError:
            return False

    return _probe()


def _resolve_run_submission_id(record: Any, run_id: str) -> str:
    """Resolve durable submission_id from a CP1 run record (fail closed)."""
    if isinstance(record, Mapping):
        raw = record.get("submission_id")
        if raw is None:
            raise ControlPlaneError(
                "Run record is missing submission_id",
                code="PMCP500",
                status=500,
                title="Internal Server Error",
                type="etlantic.control_plane/error",
                extensions={"run_id": run_id},
            )
        submission_id = str(raw).strip()
        if not submission_id or submission_id == "None":
            raise ControlPlaneError(
                "Run record has an invalid submission_id",
                code="PMCP500",
                status=500,
                title="Internal Server Error",
                type="etlantic.control_plane/error",
                extensions={"run_id": run_id},
            )
        return submission_id
    return run_id


def _profile_meta(api: ETLanticAPI) -> tuple[Any, bool, dict[str, Any]]:
    """Resolve injected profile and Experimental vs production-capable metadata."""
    from etlantic.plugin_trust import is_production_profile
    from etlantic.profile import resolve_profile

    raw = getattr(api, "profile", "development")
    try:
        profile = resolve_profile(raw, allow_adhoc_profile=False)
    except Exception as exc:
        raise ControlPlaneError(
            redact_control_plane_text(str(exc)) or "Profile resolution failed",
            code="PMCP400",
            status=400,
            title="Bad Request",
            type="etlantic.control_plane/bad_request",
        ) from exc
    production_like = False
    try:
        production_like = is_production_profile(profile)
    except Exception:
        mode = getattr(profile, "security_mode", None)
        production_like = str(mode or "").lower() == "production"
    name = getattr(profile, "name", None) or (
        raw if isinstance(raw, str) else "development"
    )
    metadata = {
        "label": "Experimental",
        "mode": "production" if production_like else "experimental_preview",
        "profile": str(name),
        "note": (
            "CP1 validate/plan uses production-capable verify when "
            "profile.security_mode is production; otherwise Experimental preview."
        ),
    }
    return profile, production_like, metadata


def _redact_diagnostics(
    diagnostics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    redacted: list[dict[str, Any]] = []
    for item in diagnostics:
        row = redact_control_plane_payload(dict(item))
        if isinstance(row, dict) and "message" in row and row["message"] is not None:
            row["message"] = redact_control_plane_text(str(row["message"]))
        redacted.append(row if isinstance(row, dict) else {"message": str(row)})
    return redacted


def _validate_document(
    document: Mapping[str, Any],
    definition_id: str,
    *,
    api: ETLanticAPI,
) -> ValidateResponse:
    """Validate a stored definition document without executing pipelines."""
    profile, production_like, metadata = _profile_meta(api)
    fingerprint = None
    diagnostics: list[dict[str, Any]] = []
    ok = True
    if document.get("schema") == "etlantic.pipeline/1" or "nodes" in document:
        try:
            from etlantic.authoring.serialize import (
                pipeline_fingerprint,
                pipeline_from_dict,
            )

            defn = pipeline_from_dict(dict(document), verify=production_like)
            if production_like:
                from etlantic.authoring.lifecycle import validate_pipeline_like

                report = validate_pipeline_like(defn, profile=profile)
            else:
                from etlantic.authoring.preview import structural_validate_preview

                report = structural_validate_preview(defn, profile=profile)
            diagnostics = [d.to_dict() for d in report.diagnostics]
            ok = not report.has_errors
            fingerprint = defn.fingerprint or pipeline_fingerprint(defn)
        except Exception as exc:
            ok = False
            diagnostics = [
                {
                    "code": "PMCPVALIDATE",
                    "severity": "error",
                    "message": redact_control_plane_text(str(exc)),
                }
            ]
    else:
        fingerprint = str(document.get("fingerprint") or definition_id)
    return ValidateResponse(
        ok=ok,
        definition_id=definition_id,
        diagnostics=_redact_diagnostics(diagnostics),
        fingerprint=fingerprint,
        metadata=metadata,
    )


def _plan_document(
    document: Mapping[str, Any],
    definition_id: str,
    *,
    api: ETLanticAPI,
) -> PlanResponse:
    profile, production_like, metadata = _profile_meta(api)
    diagnostics: list[dict[str, Any]] = []
    plan: dict[str, Any] | None = None
    ok = False
    if document.get("schema") == "etlantic.pipeline/1" or "nodes" in document:
        try:
            from etlantic.authoring.serialize import pipeline_from_dict

            defn = pipeline_from_dict(dict(document), verify=production_like)
            if production_like:
                from etlantic.authoring.lifecycle import plan_pipeline_like

                planned = plan_pipeline_like(defn, profile=profile)
                from etlantic.authoring.lifecycle import validate_pipeline_like

                report = validate_pipeline_like(defn, profile=profile)
                diagnostics = [d.to_dict() for d in report.diagnostics]
                plan = planned.to_dict() if planned is not None else None
                ok = planned is not None and not report.has_errors
            else:
                from etlantic.authoring.preview import plan_preview

                planned, report = plan_preview(defn, profile=profile)
                diagnostics = [d.to_dict() for d in report.diagnostics]
                plan = (
                    redact_control_plane_payload(planned.to_dict())
                    if planned is not None
                    else None
                )
                ok = planned is not None and not report.has_errors
            if plan is not None and production_like:
                plan = redact_control_plane_payload(plan)
        except Exception as exc:
            diagnostics = [
                {
                    "code": "PMCPPLAN",
                    "severity": "error",
                    "message": redact_control_plane_text(str(exc)),
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
        diagnostics=_redact_diagnostics(diagnostics),
        plan=plan,
        metadata=metadata,
    )


def _receipt_with_urls(receipt: Any) -> Any:
    run_id = receipt.resource_id or receipt.submission_id
    return replace(
        receipt,
        status_url=f"/v1/runs/{run_id}",
        events_url=f"/v1/runs/{run_id}/events",
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
        responses={503: {"description": "Control-plane stores not injected"}},
    )
    def ready(response: Response) -> ReadyResponse:
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
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
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
            definition_id=definition_id,
            document=redact_control_plane_payload(dict(document)),
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
        return _validate_document(document, definition_id, api=api)

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
        return _plan_document(document, definition_id, api=api)

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
        if (
            "definition_id" in payload
            and payload["definition_id"] is not None
            and str(payload["definition_id"]) != definition_id
        ):
            raise ControlPlaneError(
                "payload.definition_id must match path definition_id",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
                extensions={
                    "path_definition_id": definition_id,
                    "payload_definition_id": str(payload["definition_id"]),
                },
            )
        payload["definition_id"] = definition_id
        result = api.submissions.accept(
            ctx,
            idempotency_key=idem,
            payload=payload,
            resource_type="run",
            operation="run.submit",
        )
        durable_created = False
        if api.durable_work is not None:
            plan_fp = str(
                payload.get("plan_fingerprint")
                or payload.get("plan_id")
                or f"definition:{definition_id}"
            )
            try:
                _durable_row, durable_created = api.durable_work.accept(
                    ctx,
                    idempotency_key=idem,
                    operation="run.submit",
                    plan_fingerprint=plan_fp,
                    revision_id=(
                        str(payload["revision_id"])
                        if payload.get("revision_id") is not None
                        else None
                    ),
                    plugin_fingerprint=(
                        str(payload["plugin_fingerprint"])
                        if payload.get("plugin_fingerprint") is not None
                        else None
                    ),
                    policy_fingerprint=(
                        str(payload["policy_fingerprint"])
                        if payload.get("policy_fingerprint") is not None
                        else None
                    ),
                    input_snapshot=(
                        str(payload["input_snapshot"])
                        if payload.get("input_snapshot") is not None
                        else None
                    ),
                    schema_baseline_id=(
                        str(payload["schema_baseline_id"])
                        if payload.get("schema_baseline_id") is not None
                        else None
                    ),
                    schema_observation_fingerprint=(
                        str(payload["schema_observation_fingerprint"])
                        if payload.get("schema_observation_fingerprint") is not None
                        else None
                    ),
                    submission_id=result.receipt.submission_id,
                )
            except Exception as exc:
                # Compensate a freshly created CP1 accept so dual-write hosts do
                # not leave accepted runs without durable outbox coordination.
                if result.created:
                    run_id = result.receipt.resource_id or result.receipt.submission_id
                    try:
                        _, cancel_fn = _run_store_methods(api)
                        cancel_fn(ctx, run_id)
                    except Exception:
                        pass
                if isinstance(exc, ControlPlaneError):
                    raise
                raise ControlPlaneError(
                    "Durable accept failed after CP1 accept; "
                    "CP1 run was compensated when newly created",
                    code="PMCP503",
                    status=503,
                    title="Service Unavailable",
                    type="etlantic.control_plane/unavailable",
                    extensions={
                        "submission_id": result.receipt.submission_id,
                        "compensated": bool(result.created),
                    },
                ) from exc
        receipt = _receipt_with_urls(result.receipt)
        # Emit on CP1 create or when durable accept first succeeds after a split.
        if api.events is not None and (result.created or durable_created):
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

    def _authorize_run(ctx: ControlPlaneContext, action: str, run_id: str) -> None:
        require_authorized_run(
            api.authorizer,
            ctx,
            action,
            run_id,
            probe_exists=lambda: _run_exists_probe(api, ctx, run_id),
        )

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
        _authorize_run(ctx, "run.read", run_id)
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
        _authorize_run(ctx, "run.cancel", run_id)
        get_run_fn, cancel_fn = _run_store_methods(api)
        try:
            existing = get_run_fn(ctx, run_id)
        except KeyError as exc:
            raise ControlPlaneError.not_found(f"Run {run_id!r} not found") from exc
        submission_id = _resolve_run_submission_id(existing, run_id)
        # Durable cancel first so CP1 is not flipped when durable coordination fails.
        if api.durable_work is not None:
            try:
                api.durable_work.cancel_submission(ctx, submission_id)
            except ControlPlaneError as exc:
                # Missing durable row (CP1-only) or already-terminal durable:
                # continue so CP1 observation can still converge.
                if int(getattr(exc, "status", 500)) not in {404, 409}:
                    raise
        try:
            cancelled = cancel_fn(ctx, run_id)
        except KeyError as exc:
            raise ControlPlaneError.not_found(f"Run {run_id!r} not found") from exc
        if isinstance(cancelled, tuple):
            record, changed = cancelled
        else:
            record = cancelled
            changed = True
        if changed and api.events is not None:
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
            description=(
                "When true, keep polling for new events after history "
                "(capped: max 100 polls / 60s)"
            ),
        ),
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ) -> StreamingResponse:
        """Stream ordered run events as ``text/event-stream``.

        Authz precedes existence lookup. Cross-tenant runs map to opaque 404.
        Unknown/expired cursors return **410 Gone** (prefer reconnect without
        cursor to replay from the beginning) — see package README.
        """
        _authorize_run(ctx, "run.events", run_id)
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
        _authorize_run(ctx, "run.report", run_id)
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
        _authorize_run(ctx, "run.artifacts", run_id)
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
        _authorize_run(ctx, "run.lineage", run_id)
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
        history = getattr(api, "history_store", None)
        if history is not None:
            items = [rec.to_dict() for rec in history.list_schema_observations(ctx)]
            return SchemaObservationsResponse(items=items)
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
        history = getattr(api, "history_store", None)
        if history is not None:
            # Unknown observation → 404; ack is non-authority (observation only).
            history.acknowledge_baseline(ctx, observation_id, kind="schema")
            return SchemaObservationAckResponse(observation_id=observation_id)
        known = getattr(api, "known_observation_ids", set()) or set()
        if observation_id not in known:
            raise ControlPlaneError.not_found(
                f"Schema observation {observation_id!r} not found"
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
        history = getattr(api, "history_store", None)
        if history is not None:
            items = [
                rec.to_dict() for rec in history.list_reliability_observations(ctx)
            ]
            return ReliabilityListResponse(items=items)
        return ReliabilityListResponse(items=[])

    # ------------------------------------------------------------------
    # CP2 registry admin routes under /v1/registry
    # (chosen over /v1/admin to keep admin/ops naming free for later hosts)
    # Authz always runs before directory/revision lookup (non-enumeration).
    # ------------------------------------------------------------------

    def _require_registry():
        if api.registry is None:
            raise ControlPlaneError(
                "Registry provider is not configured",
                code="PMCP501",
                status=501,
                title="Not Implemented",
            )
        return api.registry

    @router.get(
        "/v1/registry/tenants",
        operation_id="cp_registry_list_tenants",
        response_model=TenantListResponse,
        tags=["registry"],
    )
    def registry_list_tenants(
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> TenantListResponse:
        require_authorized(
            api.authorizer,
            ctx,
            "registry.tenant.list",
            "registry:tenant:*",
            resource_in_caller_scope=True,
        )
        registry = _require_registry()
        items = [
            TenantRecordResponse.model_validate(t.to_dict())
            for t in registry.tenants.list(ctx)
        ]
        return TenantListResponse(items=items)

    @router.get(
        "/v1/registry/tenants/{tenant_id}",
        operation_id="cp_registry_get_tenant",
        response_model=TenantRecordResponse,
        tags=["registry"],
    )
    def registry_get_tenant(
        tenant_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> TenantRecordResponse:
        require_authorized(
            api.authorizer,
            ctx,
            "registry.tenant.read",
            f"registry:tenant:{tenant_id}",
            resource_in_caller_scope=False,
        )
        registry = _require_registry()
        record = registry.tenants.get(ctx, tenant_id)
        return TenantRecordResponse.model_validate(record.to_dict())

    @router.put(
        "/v1/registry/tenants/{tenant_id}",
        operation_id="cp_registry_put_tenant",
        response_model=TenantRecordResponse,
        tags=["registry"],
    )
    def registry_put_tenant(
        tenant_id: str,
        body: TenantPutBody,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> TenantRecordResponse:
        require_authorized(
            api.authorizer,
            ctx,
            "registry.tenant.write",
            f"registry:tenant:{tenant_id}",
            resource_in_caller_scope=False,
        )
        registry = _require_registry()
        record = TenantRecord(
            tenant_id=tenant_id,
            lifecycle=LifecycleState(body.lifecycle),
            display_name=body.display_name,
            security_domain_id=body.security_domain_id or ctx.security_domain.domain_id,
            metadata=dict(body.metadata),
        )
        registry.tenants.put(ctx, record)
        stored = registry.tenants.get(ctx, tenant_id)
        return TenantRecordResponse.model_validate(stored.to_dict())

    @router.get(
        "/v1/registry/workspaces",
        operation_id="cp_registry_list_workspaces",
        response_model=WorkspaceListResponse,
        tags=["registry"],
    )
    def registry_list_workspaces(
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> WorkspaceListResponse:
        require_authorized(
            api.authorizer,
            ctx,
            "registry.workspace.list",
            "registry:workspace:*",
            resource_in_caller_scope=True,
        )
        registry = _require_registry()
        items = [
            WorkspaceRecordResponse.model_validate(w.to_dict())
            for w in registry.workspaces.list(ctx)
        ]
        return WorkspaceListResponse(items=items)

    @router.get(
        "/v1/registry/workspaces/{workspace_id}",
        operation_id="cp_registry_get_workspace",
        response_model=WorkspaceRecordResponse,
        tags=["registry"],
    )
    def registry_get_workspace(
        workspace_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> WorkspaceRecordResponse:
        require_authorized(
            api.authorizer,
            ctx,
            "registry.workspace.read",
            f"registry:workspace:{workspace_id}",
            resource_in_caller_scope=False,
        )
        registry = _require_registry()
        record = registry.workspaces.get(ctx, workspace_id)
        return WorkspaceRecordResponse.model_validate(record.to_dict())

    @router.put(
        "/v1/registry/workspaces/{workspace_id}",
        operation_id="cp_registry_put_workspace",
        response_model=WorkspaceRecordResponse,
        tags=["registry"],
    )
    def registry_put_workspace(
        workspace_id: str,
        body: WorkspacePutBody,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> WorkspaceRecordResponse:
        require_authorized(
            api.authorizer,
            ctx,
            "registry.workspace.write",
            f"registry:workspace:{workspace_id}",
            resource_in_caller_scope=False,
        )
        registry = _require_registry()
        record = WorkspaceRecord(
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=workspace_id,
            lifecycle=LifecycleState(body.lifecycle),
            display_name=body.display_name,
            metadata=dict(body.metadata),
        )
        registry.workspaces.put(ctx, record)
        stored = registry.workspaces.get(ctx, workspace_id)
        return WorkspaceRecordResponse.model_validate(stored.to_dict())

    @router.get(
        "/v1/registry/logicals/{logical_id}/revisions",
        operation_id="cp_registry_list_revisions",
        response_model=RevisionListResponse,
        tags=["registry"],
    )
    def registry_list_revisions(
        logical_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> RevisionListResponse:
        require_authorized(
            api.authorizer,
            ctx,
            "registry.revision.list",
            f"registry:logical:{logical_id}",
            resource_in_caller_scope=False,
        )
        registry = _require_registry()
        items = [
            RevisionResponse.model_validate(redact_control_plane_payload(r.to_dict()))
            for r in registry.revisions.list_revisions(ctx, logical_id)
        ]
        return RevisionListResponse(items=items)

    @router.get(
        "/v1/registry/revisions/{revision_id}",
        operation_id="cp_registry_get_revision",
        response_model=RevisionResponse,
        tags=["registry"],
    )
    def registry_get_revision(
        revision_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> RevisionResponse:
        require_authorized(
            api.authorizer,
            ctx,
            "registry.revision.read",
            f"registry:revision:{revision_id}",
            resource_in_caller_scope=False,
        )
        registry = _require_registry()
        revision = registry.revisions.get_revision(ctx, revision_id)
        return RevisionResponse.model_validate(
            redact_control_plane_payload(revision.to_dict())
        )

    @router.put(
        "/v1/registry/aliases/{alias}",
        operation_id="cp_registry_put_alias",
        response_model=AliasResponse,
        tags=["registry"],
    )
    def registry_put_alias(
        alias: str,
        body: AliasPutBody,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> AliasResponse:
        require_authorized(
            api.authorizer,
            ctx,
            "registry.alias.write",
            f"registry:alias:{alias}",
            resource_in_caller_scope=False,
        )
        registry = _require_registry()
        record = AliasRecord(
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            alias=alias,
            logical_id=body.logical_id,
            revision_id=body.revision_id,
            metadata=dict(body.metadata),
        )
        stored = registry.revisions.put_alias(ctx, record)
        return AliasResponse(
            tenant_id=stored.tenant_id,
            workspace_id=stored.workspace_id,
            alias=stored.alias,
            logical_id=stored.logical_id,
            revision_id=stored.revision_id,
            metadata=dict(stored.metadata),
        )

    @router.post(
        "/v1/registry/promotions",
        operation_id="cp_registry_promote",
        response_model=PromotionResponse,
        tags=["registry"],
    )
    def registry_promote(
        body: PromoteBody,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> PromotionResponse:
        require_authorized(
            api.authorizer,
            ctx,
            "registry.promote",
            f"registry:logical:{body.logical_id}",
            resource_in_caller_scope=False,
        )
        registry = _require_registry()
        promotion = registry.revisions.promote(
            ctx,
            logical_id=body.logical_id,
            from_revision_id=body.from_revision_id,
            from_environment=body.from_environment,
            to_environment=body.to_environment,
            content=body.content,
            metadata=body.metadata,
        )
        return PromotionResponse.model_validate(promotion.to_dict())

    # CP3 durable work host routes under /v1/durable
    def _require_durable():
        if api.durable_work is None:
            raise ControlPlaneError(
                "Durable work store is not configured",
                code="PMCP501",
                status=501,
                title="Not Implemented",
            )
        return api.durable_work

    @router.get(
        "/v1/durable/outbox",
        operation_id="cp_durable_pending_outbox",
        tags=["durable"],
    )
    def durable_pending_outbox(
        limit: int = 100,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> list[dict[str, Any]]:
        require_authorized(
            api.authorizer,
            ctx,
            "durable.outbox.read",
            "durable:outbox",
            resource_in_caller_scope=False,
        )
        store = _require_durable()
        return [row.to_dict() for row in store.pending_outbox(ctx, limit=limit)]

    @router.post(
        "/v1/durable/outbox/{outbox_id}/published",
        operation_id="cp_durable_mark_published",
        tags=["durable"],
    )
    def durable_mark_published(
        outbox_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "durable.outbox.write",
            f"durable:outbox:{outbox_id}",
            resource_in_caller_scope=False,
        )
        return _require_durable().mark_published(ctx, outbox_id).to_dict()

    @router.post(
        "/v1/durable/submissions/{submission_id}/cancel",
        operation_id="cp_durable_cancel",
        tags=["durable"],
    )
    def durable_cancel(
        submission_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "durable.cancel",
            f"durable:submission:{submission_id}",
            resource_in_caller_scope=False,
        )
        return _require_durable().cancel_submission(ctx, submission_id).to_dict()

    @router.post(
        "/v1/durable/submissions/{submission_id}/leases",
        operation_id="cp_durable_acquire_lease",
        tags=["durable"],
    )
    def durable_acquire_lease(
        submission_id: str,
        body: DurableLeaseBody,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "durable.lease.write",
            f"durable:submission:{submission_id}",
            resource_in_caller_scope=False,
        )
        return (
            _require_durable()
            .acquire_lease(
                ctx,
                submission_id,
                owner_id=body.owner_id,
                ttl_seconds=body.ttl_seconds,
            )
            .to_dict()
        )

    @router.post(
        "/v1/durable/submissions/{submission_id}/leases/heartbeat",
        operation_id="cp_durable_heartbeat",
        tags=["durable"],
    )
    def durable_heartbeat(
        submission_id: str,
        body: DurableLeaseTokenBody,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "durable.lease.write",
            f"durable:submission:{submission_id}",
            resource_in_caller_scope=False,
        )
        return (
            _require_durable()
            .heartbeat(
                ctx,
                submission_id,
                owner_id=body.owner_id,
                fencing_token=body.fencing_token,
                ttl_seconds=body.ttl_seconds,
            )
            .to_dict()
        )

    @router.post(
        "/v1/durable/submissions/{submission_id}/leases/release",
        operation_id="cp_durable_release_lease",
        tags=["durable"],
    )
    def durable_release_lease(
        submission_id: str,
        body: DurableLeaseTokenBody,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, str]:
        require_authorized(
            api.authorizer,
            ctx,
            "durable.lease.write",
            f"durable:submission:{submission_id}",
            resource_in_caller_scope=False,
        )
        _require_durable().release_lease(
            ctx,
            submission_id,
            owner_id=body.owner_id,
            fencing_token=body.fencing_token,
        )
        return {"status": "released"}

    @router.post(
        "/v1/durable/submissions/{submission_id}/attempts",
        operation_id="cp_durable_start_attempt",
        tags=["durable"],
    )
    def durable_start_attempt(
        submission_id: str,
        body: DurableStartAttemptBody,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "durable.attempt.write",
            f"durable:submission:{submission_id}",
            resource_in_caller_scope=False,
        )
        return (
            _require_durable()
            .start_attempt(
                ctx,
                submission_id,
                owner_id=body.owner_id,
                fencing_token=body.fencing_token,
                context=body.context,
            )
            .to_dict()
        )

    @router.post(
        "/v1/durable/attempts/{attempt_id}/finish",
        operation_id="cp_durable_finish_attempt",
        tags=["durable"],
    )
    def durable_finish_attempt(
        attempt_id: str,
        body: DurableFinishAttemptBody,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "durable.attempt.write",
            f"durable:attempt:{attempt_id}",
            resource_in_caller_scope=False,
        )
        return (
            _require_durable()
            .finish_attempt(
                ctx,
                attempt_id,
                owner_id=body.owner_id,
                fencing_token=body.fencing_token,
                status=body.status,
            )
            .to_dict()
        )

    @router.post(
        "/v1/durable/checkpoints/{checkpoint_id}/cas",
        operation_id="cp_durable_checkpoint_cas",
        tags=["durable"],
    )
    def durable_checkpoint_cas(
        checkpoint_id: str,
        body: DurableCheckpointCasBody,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "durable.checkpoint.write",
            f"durable:checkpoint:{checkpoint_id}",
            resource_in_caller_scope=False,
        )
        return (
            _require_durable()
            .compare_and_swap_checkpoint(
                ctx,
                checkpoint_id,
                expected_version=body.expected_version,
                value_fingerprint=body.value_fingerprint,
                attempt_id=body.attempt_id,
                fencing_token=body.fencing_token,
                schema_baseline_id=body.schema_baseline_id,
            )
            .to_dict()
        )

    @router.post(
        "/v1/durable/submissions/{submission_id}/replay",
        operation_id="cp_durable_replay",
        tags=["durable"],
    )
    def durable_replay(
        submission_id: str,
        body: DurableReplayBody | None = None,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "durable.replay",
            f"durable:submission:{submission_id}",
            resource_in_caller_scope=False,
        )
        body = body or DurableReplayBody()
        return (
            _require_durable()
            .replay(ctx, submission_id, checkpoint_id=body.checkpoint_id)
            .to_dict()
        )

    @router.post(
        "/v1/durable/previews",
        operation_id="cp_durable_create_preview",
        tags=["durable"],
    )
    def durable_create_preview(
        body: DurablePreviewBody,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        from etlantic.control_plane import PreviewWorkspace

        require_authorized(
            api.authorizer,
            ctx,
            "durable.preview.write",
            "durable:preview",
            resource_in_caller_scope=False,
        )
        preview = PreviewWorkspace(
            body.preview_id,
            ctx.tenant.tenant_id,
            ctx.workspace.workspace_id,
            body.base_revision_id,
            body.candidate_revision_id,
            body.created_at,
            body.expires_at,
            body.quota,
            body.code_fingerprint,
            body.plan_fingerprint,
            body.policy_fingerprint,
            body.environment_fingerprint,
            body.commit_ref,
            body.pull_request_ref,
        )
        return _require_durable().create_preview(ctx, preview).to_dict()

    # 041-P1-02 — complete DurableWorkStore HTTP surface
    @router.post(
        "/v1/durable/effects",
        operation_id="cp_durable_record_effect",
        tags=["durable"],
    )
    def durable_record_effect(
        body: dict[str, Any],
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        from datetime import UTC, datetime

        from etlantic.control_plane import EffectRecord

        require_authorized(
            api.authorizer,
            ctx,
            "durable.effect.write",
            "durable:effect",
            resource_in_caller_scope=False,
        )
        effect = EffectRecord(
            effect_id=str(body["effect_id"]),
            submission_id=str(body["submission_id"]),
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            status=str(body.get("status") or "pending"),  # type: ignore[arg-type]
            recorded_at=str(
                body.get("recorded_at")
                or datetime.now(UTC).isoformat().replace("+00:00", "Z")
            ),
            idempotency_evidence=body.get("idempotency_evidence"),
            reconciliation_evidence=body.get("reconciliation_evidence"),
            publication_evidence=body.get("publication_evidence"),
            compensation_evidence=body.get("compensation_evidence"),
            authoritative=bool(body.get("authoritative", True)),
            metadata=dict(body.get("metadata") or {}),
        )
        return _require_durable().record_effect(ctx, effect).to_dict()

    @router.post(
        "/v1/durable/submissions/{submission_id}/repair",
        operation_id="cp_durable_plan_repair",
        tags=["durable"],
    )
    def durable_plan_repair(
        submission_id: str,
        body: dict[str, Any] | None = None,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "durable.repair",
            f"durable:submission:{submission_id}",
            resource_in_caller_scope=False,
        )
        payload = body or {}
        return _require_durable().plan_repair(
            ctx,
            submission_id,
            checkpoint_id=payload.get("checkpoint_id"),
            invalidated_partition_ids=tuple(
                payload.get("invalidated_partition_ids") or ()
            ),
            reusable_artifact_ids=tuple(payload.get("reusable_artifact_ids") or ()),
        ).to_dict()

    @router.get(
        "/v1/durable/checkpoints/{checkpoint_id}/diagnose",
        operation_id="cp_durable_diagnose_checkpoint",
        tags=["durable"],
    )
    def durable_diagnose_checkpoint(
        checkpoint_id: str,
        kind: str = Query("corruption"),
        detail: str = Query(""),
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "durable.checkpoint.read",
            f"durable:checkpoint:{checkpoint_id}",
            resource_in_caller_scope=False,
        )
        return (
            _require_durable()
            .diagnose_checkpoint(ctx, checkpoint_id, kind=kind, detail=detail)
            .to_dict()
        )

    @router.post(
        "/v1/durable/shadow",
        operation_id="cp_durable_authorize_shadow",
        tags=["durable"],
    )
    def durable_authorize_shadow(
        body: dict[str, Any],
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        from datetime import UTC, datetime

        from etlantic.control_plane import ShadowRunRecord

        require_authorized(
            api.authorizer,
            ctx,
            "durable.shadow.write",
            "durable:shadow",
            resource_in_caller_scope=False,
        )
        record = ShadowRunRecord(
            shadow_run_id=str(body.get("shadow_run_id") or body["shadow_id"]),
            preview_id=str(body["preview_id"]),
            submission_id=str(body.get("submission_id") or ""),
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            authorized_by=str(
                body.get("authorized_by") or ctx.principal.subject
            ),
            created_at=str(
                body.get("created_at")
                or datetime.now(UTC).isoformat().replace("+00:00", "Z")
            ),
            effect_ids=tuple(body.get("effect_ids") or ()),
            production_authority=bool(body.get("production_authority", False)),
        )
        return _require_durable().authorize_shadow_run(ctx, record).to_dict()

    # CP4 governance routes
    @router.post(
        "/v1/policy/decide",
        operation_id="cp_policy_decide",
        tags=["policy"],
    )
    def policy_decide(
        body: dict[str, Any],
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "policy.decide",
            "policy:decide",
            resource_in_caller_scope=False,
        )
        if api.policy is None:
            raise HTTPException(status_code=503, detail="policy provider not configured")
        decision = api.policy.decide(
            ctx,
            hook=body.get("hook", "privileged_op"),
            plan_fingerprint=body.get("plan_fingerprint"),
            revision_id=body.get("revision_id"),
            resource=body.get("resource"),
            attributes=body.get("attributes"),
            bundle_id=body.get("bundle_id"),
        )
        if api.audit is not None:
            api.audit.append(
                ctx,
                action="policy.decide",
                resource=str(body.get("resource") or decision.hook),
                decision_refs=[decision.decision_id],
            )
        return decision.to_dict()

    @router.post(
        "/v1/approvals",
        operation_id="cp_approval_create",
        tags=["approvals"],
    )
    def approval_create(
        body: dict[str, Any],
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "approval.write",
            "approval:create",
            resource_in_caller_scope=False,
        )
        if api.approvals is None:
            raise HTTPException(status_code=503, detail="approval store not configured")
        from datetime import datetime

        expires = body.get("expires_at")
        expires_at = datetime.fromisoformat(expires) if expires else None
        return api.approvals.create(
            ctx,
            hook=str(body.get("hook") or "pre_promote"),
            plan_fingerprint=str(body["plan_fingerprint"]),
            policy_fingerprint=str(body["policy_fingerprint"]),
            revision_id=body.get("revision_id"),
            expires_at=expires_at,
            approval_id=body.get("approval_id"),
        ).to_dict()

    @router.post(
        "/v1/approvals/{approval_id}/decide",
        operation_id="cp_approval_decide",
        tags=["approvals"],
    )
    def approval_decide(
        approval_id: str,
        body: dict[str, Any],
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "approval.decide",
            f"approval:{approval_id}",
            resource_in_caller_scope=False,
        )
        if api.approvals is None:
            raise HTTPException(status_code=503, detail="approval store not configured")
        result = api.approvals.decide(
            ctx,
            approval_id=approval_id,
            approve=bool(body.get("approve", False)),
            reason=body.get("reason"),
            plan_fingerprint=body.get("plan_fingerprint"),
            policy_fingerprint=body.get("policy_fingerprint"),
        )
        if api.audit is not None:
            api.audit.append(
                ctx,
                action="approval.decide",
                resource=approval_id,
                decision_refs=[d.decision_id for d in result.decisions],
            )
        return result.to_dict()

    @router.post(
        "/v1/quotas/admit",
        operation_id="cp_quota_admit",
        tags=["quotas"],
    )
    def quota_admit(
        body: dict[str, Any],
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "quota.admit",
            "quota:admit",
            resource_in_caller_scope=False,
        )
        if api.quotas is None:
            raise HTTPException(status_code=503, detail="quota provider not configured")
        return api.quotas.admit(
            ctx,
            resource=body.get("resource", "concurrency"),
            units=int(body.get("units") or 1),
        ).to_dict()

    @router.post(
        "/v1/erasure/requests",
        operation_id="cp_erasure_create",
        tags=["erasure"],
    )
    def erasure_create(
        body: dict[str, Any],
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "erasure.write",
            "erasure:request",
            resource_in_caller_scope=False,
        )
        if api.erasure is None:
            raise HTTPException(status_code=503, detail="erasure store not configured")
        return api.erasure.create_request(
            ctx,
            subject_key_fingerprint=str(body["subject_key_fingerprint"]),
            field_paths=list(body.get("field_paths") or ()),
            legal_hold=bool(body.get("legal_hold")),
            request_id=body.get("request_id"),
        ).to_dict()

    @router.get(
        "/v1/audit",
        operation_id="cp_audit_list",
        tags=["audit"],
    )
    def audit_list(
        limit: int = 100,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "audit.read",
            "audit:list",
            resource_in_caller_scope=False,
        )
        if api.audit is None:
            raise HTTPException(status_code=503, detail="audit store not configured")
        records = api.audit.list(ctx, limit=limit)
        return {"records": [r.to_dict() for r in records]}

    @router.get(
        "/v1/audit/export",
        operation_id="cp_audit_export",
        tags=["audit"],
    )
    def audit_export(
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "audit.export",
            "audit:export",
            resource_in_caller_scope=False,
        )
        if api.audit is None:
            raise HTTPException(status_code=503, detail="audit store not configured")
        return api.audit.export(ctx).to_dict()

    @router.post(
        "/v1/attestations/verify-plan",
        operation_id="cp_attestation_verify_plan",
        tags=["attestations"],
    )
    def attestation_verify_plan(
        body: dict[str, Any],
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        require_authorized(
            api.authorizer,
            ctx,
            "attestation.verify",
            "attestation:verify",
            resource_in_caller_scope=False,
        )
        if api.attestations is None:
            raise HTTPException(
                status_code=503, detail="attestation store not configured"
            )
        results = api.attestations.verify_plan(
            ctx,
            plan_fingerprint=str(body["plan_fingerprint"]),
            revision_id=str(body["revision_id"]),
            policy_fingerprint=str(body["policy_fingerprint"]),
            plugin_fingerprints=list(body.get("plugin_fingerprints") or ()),
            sbom_digest=body.get("sbom_digest"),
        )
        return {"results": [r.to_dict() for r in results]}

    return router


__all__ = ["build_control_plane_router"]
