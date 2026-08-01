"""Pydantic request/response models for the control-plane HTTP adapter."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

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


class ValidateResponse(BaseModel):
    ok: bool
    definition_id: str
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    fingerprint: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanResponse(BaseModel):
    ok: bool
    definition_id: str
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    plan: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunSubmitBody(BaseModel):
    """Optional body for run submit; Idempotency-Key header is preferred."""

    idempotency_key: str | None = None
    payload: dict[str, Any] | None = None


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


class ReportStubResponse(BaseModel):
    schema_: str = Field(
        alias="schema", default="etlantic.control_plane.run_report_stub/1"
    )
    run_id: str
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class ArtifactMeta(BaseModel):
    artifact_id: str
    kind: str
    media_type: str | None = None


class ArtifactsResponse(BaseModel):
    run_id: str
    items: list[ArtifactMeta] = Field(default_factory=list)


class LineageStubResponse(BaseModel):
    schema_: str = Field(
        alias="schema", default="etlantic.control_plane.lineage_stub/1"
    )
    run_id: str
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class SchemaObservationsResponse(BaseModel):
    schema_: str = Field(
        alias="schema", default="etlantic.control_plane.schema_observations/1"
    )
    label: Literal["observations"] = "observations"
    note: str = (
        "Schema observations are labeled observations and are not contract authority."
    )
    items: list[dict[str, Any]] = Field(default_factory=list)

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
    items: list[dict[str, Any]] = Field(default_factory=list)

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
    items: list[TenantRecordResponse] = Field(default_factory=list)


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
    items: list[WorkspaceRecordResponse] = Field(default_factory=list)


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
    items: list[RevisionResponse] = Field(default_factory=list)


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
