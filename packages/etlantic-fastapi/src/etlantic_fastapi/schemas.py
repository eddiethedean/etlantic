"""Pydantic request/response models for the control-plane HTTP adapter."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from etlantic.control_plane import LifecycleState


class AcceptReceiptResponse(BaseModel):
    schema_: str = Field(
        alias="schema", default="etlantic.control_plane.accept_receipt/1"
    )
    acceptance_id: str
    submission_id: str
    tenant_id: str
    workspace_id: str
    idempotency_key: str
    created_at: str
    status: Literal["accepted"] = Field(
        default="accepted",
        description="Durable accept only — not pipeline execution status",
    )
    resource_type: str = "run"
    resource_id: str | None = None
    status_url: str | None = None
    events_url: str | None = None

    model_config = {"populate_by_name": True}


class DefinitionSummary(BaseModel):
    definition_id: str


class DefinitionListResponse(BaseModel):
    items: list[DefinitionSummary]


class DefinitionGetResponse(BaseModel):
    definition_id: str
    document: dict[str, Any]


class DefinitionWriteBody(BaseModel):
    document: dict[str, Any]

    model_config = {"extra": "forbid"}


class DefinitionWriteResponse(BaseModel):
    definition_id: str
    fingerprint: str
    document: dict[str, Any]
    revision_id: str | None = None


class DefinitionEditBody(BaseModel):
    expected_fingerprint: str
    command: dict[str, Any]

    model_config = {"extra": "forbid"}


class PlanRequestBody(BaseModel):
    request: dict[str, Any] | None = None
    revision_selector: str = "current"

    model_config = {"extra": "forbid"}


class ValidateResponse(BaseModel):
    ok: bool
    definition_id: str
    diagnostics: list[dict[str, Any]] = Field(
        default_factory=lambda: list[dict[str, Any]]()
    )
    fingerprint: str | None = None
    revision_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanResponse(BaseModel):
    ok: bool
    definition_id: str
    diagnostics: list[dict[str, Any]] = Field(
        default_factory=lambda: list[dict[str, Any]]()
    )
    plan: dict[str, Any] | None = None
    revision_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunSubmitBody(BaseModel):
    """Optional body for run submit; Idempotency-Key header is preferred."""

    idempotency_key: str | None = None
    payload: dict[str, Any] | None = None


class ScheduleSpecBody(BaseModel):
    """OpenAPI-visible schedule timing policy accepted by CP1."""

    kind: Literal["interval", "cron"]
    timezone: str = "UTC"
    interval_seconds: int | None = None
    cron: str | None = None
    misfire: Literal["skip", "fire_once", "catch_up"] = "fire_once"
    catch_up_max: int = 10
    overlap: Literal["skip", "queue"] = "skip"
    jitter_seconds: int = 0
    window_start: str | None = None
    window_end: str | None = None


class ScheduleSecretRefBody(BaseModel):
    """Versioned secret selector; values are never accepted in this schema."""

    provider: str
    name: str
    key: str
    version: str = "current"
    purpose: str | None = None


class ScheduleWorkloadIdentityBody(BaseModel):
    """Issuer-qualified trigger identity bound by the schedule authorizer."""

    subject: str
    issuer: str | None = None
    kind: Literal["workload", "service"]


class ScheduleCreateBody(BaseModel):
    """Explicit managed schedule policy, inputs and execution identity."""

    model_config = ConfigDict(extra="allow")

    spec: ScheduleSpecBody | None = None
    kind: Literal["interval", "cron"] | None = None
    timezone: str | None = None
    interval_seconds: int | None = None
    cron: str | None = None
    misfire: Literal["skip", "fire_once", "catch_up"] | None = None
    catch_up_max: int | None = None
    overlap: Literal["skip", "queue"] | None = None
    jitter_seconds: int | None = None
    window_start: str | None = None
    window_end: str | None = None
    revision_selector: str | None = None
    profile_name: str | None = None
    parameter_refs: dict[str, str] | None = None
    secret_refs: dict[str, ScheduleSecretRefBody | str] | None = None
    workload_identity: ScheduleWorkloadIdentityBody | None = None
    policy_fingerprint: str | None = None


class InputResourceFinalizeBody(BaseModel):
    expected_sha256: str
    expected_byte_length: int = Field(ge=0)

    model_config = {"extra": "forbid"}


class ConnectorActionSubmitBody(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    deadline_seconds: int = Field(default=30, ge=1, le=300)

    model_config = {"extra": "forbid"}


class ConnectorActionReceiptResponse(BaseModel):
    schema_: str = Field(alias="schema")
    action_id: str
    tenant_id: str
    workspace_id: str
    action: str
    created_at: str
    deadline_at: str
    status: Literal["queued", "running", "succeeded", "failed", "timed_out"]
    attempt: int
    started_at: str | None = None
    completed_at: str | None = None
    result: dict[str, Any] | None = None
    result_expires_at: str | None = None
    error_code: str | None = None

    model_config = {"populate_by_name": True}


class ConnectorActionPageResponse(BaseModel):
    schema_: str = Field(
        alias="schema", default="etlantic.control_plane.action_job_page/1"
    )
    items: list[ConnectorActionReceiptResponse] = Field(
        default_factory=lambda: list[ConnectorActionReceiptResponse]()
    )
    next_cursor: str | None = None
    has_more: bool = False

    model_config = {"populate_by_name": True}


class RunStatusResponse(BaseModel):
    run_id: str
    submission_id: str
    acceptance_id: str
    status: str
    tenant_id: str
    workspace_id: str
    definition_id: str | None = None
    created_at: str
    updated_at: str
    idempotency_key: str
    resource_type: str = "run"


class RunActionItem(BaseModel):
    name: str
    allowed: bool
    reason: str | None = None


class RunActionsResponse(BaseModel):
    schema_: str = Field(alias="schema", default="etlantic.control_plane.run_actions/1")
    run_id: str
    status: str
    actions: list[RunActionItem] = Field(default_factory=lambda: list[RunActionItem]())

    model_config = {"populate_by_name": True}


class ReportStubResponse(BaseModel):
    schema_: str = Field(alias="schema", default="etlantic.control_plane.run_report/1")
    run_id: str
    status: str
    report: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}


class RunEventPageResponse(BaseModel):
    schema_: str = Field(
        alias="schema", default="etlantic.control_plane.run_event_page/1"
    )
    run_id: str
    items: list[dict[str, Any]] = Field(default_factory=lambda: list[dict[str, Any]]())
    next_cursor: str | None = None
    has_more: bool = False

    model_config = {"populate_by_name": True}


class ArtifactMeta(BaseModel):
    artifact_id: str
    kind: str
    media_type: str | None = None
    content_available: bool = False


class ArtifactsResponse(BaseModel):
    run_id: str
    items: list[ArtifactMeta] = Field(default_factory=lambda: list[ArtifactMeta]())


class LineageStubResponse(BaseModel):
    schema_: str = Field(alias="schema", default="etlantic.control_plane.lineage/1")
    run_id: str
    submission_id: str | None = None
    attempt_id: str | None = None
    nodes: list[dict[str, Any]] = Field(default_factory=lambda: list[dict[str, Any]]())
    edges: list[dict[str, Any]] = Field(default_factory=lambda: list[dict[str, Any]]())

    model_config = {"populate_by_name": True}


class SchemaObservationsResponse(BaseModel):
    schema_: str = Field(
        alias="schema", default="etlantic.control_plane.schema_observations/1"
    )
    label: Literal["observations"] = "observations"
    note: str = (
        "Schema observations are labeled observations and are not contract authority."
    )
    items: list[dict[str, Any]] = Field(default_factory=lambda: list[dict[str, Any]]())

    model_config = {"populate_by_name": True}


class SchemaObservationAckResponse(BaseModel):
    schema_: str = Field(
        alias="schema", default="etlantic.control_plane.schema_observation_ack/1"
    )
    observation_id: str
    acknowledged: bool = True
    note: str = (
        "Acknowledgement records observation handling only; "
        "it does not promote observations to contract authority."
    )

    model_config = {"populate_by_name": True}


class ReliabilityListResponse(BaseModel):
    schema_: str = Field(
        alias="schema", default="etlantic.control_plane.reliability_stub/1"
    )
    experimental: bool = True
    note: str = (
        "Experimental stub (not CP-GA) unless a history_store is injected; "
        "empty list is not an authority claim."
    )
    items: list[dict[str, Any]] = Field(default_factory=lambda: list[dict[str, Any]]())

    model_config = {"populate_by_name": True}


class TenantRecordResponse(BaseModel):
    schema_: str = Field(
        alias="schema", default="etlantic.control_plane.tenant_record/1"
    )
    tenant_id: str
    lifecycle: str
    display_name: str | None = None
    security_domain_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class TenantListResponse(BaseModel):
    items: list[TenantRecordResponse] = Field(
        default_factory=lambda: list[TenantRecordResponse]()
    )


class TenantPutBody(BaseModel):
    display_name: str | None = None
    security_domain_id: str | None = None
    lifecycle: LifecycleState = LifecycleState.ACTIVE
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceRecordResponse(BaseModel):
    schema_: str = Field(
        alias="schema", default="etlantic.control_plane.workspace_record/1"
    )
    tenant_id: str
    workspace_id: str
    lifecycle: str
    display_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class WorkspaceListResponse(BaseModel):
    items: list[WorkspaceRecordResponse] = Field(
        default_factory=lambda: list[WorkspaceRecordResponse]()
    )


class WorkspacePutBody(BaseModel):
    display_name: str | None = None
    lifecycle: LifecycleState = LifecycleState.ACTIVE
    metadata: dict[str, Any] = Field(default_factory=dict)


class RevisionResponse(BaseModel):
    schema_: str = Field(
        alias="schema", default="etlantic.control_plane.registry_revision/1"
    )
    logical_id: str
    revision_id: str
    tenant_id: str
    workspace_id: str
    content_fingerprint: str
    content: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    kind: str | None = None

    model_config = {"populate_by_name": True}


class RevisionListResponse(BaseModel):
    items: list[RevisionResponse] = Field(
        default_factory=lambda: list[RevisionResponse]()
    )


class AliasPutBody(BaseModel):
    logical_id: str
    revision_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AliasResponse(BaseModel):
    schema_: str = Field(alias="schema", default="etlantic.control_plane.alias/1")
    tenant_id: str
    workspace_id: str
    alias: str
    logical_id: str
    revision_id: str
    created_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class PromoteBody(BaseModel):
    logical_id: str
    from_revision_id: str
    from_environment: str
    to_environment: str
    content: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromotionResponse(BaseModel):
    schema_: str = Field(alias="schema", default="etlantic.control_plane.promotion/1")
    promotion_id: str
    tenant_id: str
    workspace_id: str
    logical_id: str
    from_revision_id: str
    to_revision_id: str
    from_environment: str
    to_environment: str
    created_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    stores_injected: bool
    detail: str | None = None


class DurableLeaseBody(BaseModel):
    owner_id: str
    ttl_seconds: int = 30


class DurableLeaseTokenBody(BaseModel):
    owner_id: str
    fencing_token: int
    ttl_seconds: int = 30


class DurableStartAttemptBody(BaseModel):
    owner_id: str
    fencing_token: int
    context: dict[str, Any] | None = None


class DurableFinishAttemptBody(BaseModel):
    owner_id: str
    fencing_token: int
    status: str


class DurableCheckpointCasBody(BaseModel):
    value_fingerprint: str
    attempt_id: str
    fencing_token: int
    expected_version: int | None = None
    schema_baseline_id: str | None = None


class DurableReplayBody(BaseModel):
    checkpoint_id: str | None = None


class RunResumeBody(BaseModel):
    checkpoint_id: str


class RunRepairBody(BaseModel):
    invalidated_partition_ids: dict[str, list[str]]
    checkpoint_id: str | None = None
    reusable_artifact_ids: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class RunBackfillBody(BaseModel):
    partition_ids: dict[str, list[str]]
    checkpoint_id: str | None = None

    model_config = {"extra": "forbid"}


class DurablePreviewBody(BaseModel):
    preview_id: str
    base_revision_id: str
    candidate_revision_id: str
    created_at: str
    expires_at: str
    quota: int
    code_fingerprint: str
    plan_fingerprint: str
    policy_fingerprint: str | None = None
    environment_fingerprint: str | None = None
    commit_ref: str | None = None
    pull_request_ref: str | None = None


__all__ = [
    "AcceptReceiptResponse",
    "AliasPutBody",
    "AliasResponse",
    "ArtifactMeta",
    "ArtifactsResponse",
    "DefinitionGetResponse",
    "DefinitionListResponse",
    "DefinitionSummary",
    "DurableCheckpointCasBody",
    "DurableFinishAttemptBody",
    "DurableLeaseBody",
    "DurableLeaseTokenBody",
    "DurablePreviewBody",
    "DurableReplayBody",
    "DurableStartAttemptBody",
    "HealthResponse",
    "LineageStubResponse",
    "PlanResponse",
    "PromoteBody",
    "PromotionResponse",
    "ReadyResponse",
    "ReliabilityListResponse",
    "ReportStubResponse",
    "RevisionListResponse",
    "RevisionResponse",
    "RunBackfillBody",
    "RunRepairBody",
    "RunResumeBody",
    "RunStatusResponse",
    "RunSubmitBody",
    "SchemaObservationAckResponse",
    "SchemaObservationsResponse",
    "TenantListResponse",
    "TenantPutBody",
    "TenantRecordResponse",
    "ValidateResponse",
    "WorkspaceListResponse",
    "WorkspacePutBody",
    "WorkspaceRecordResponse",
]
