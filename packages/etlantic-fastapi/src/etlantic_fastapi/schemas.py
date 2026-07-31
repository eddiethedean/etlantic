"""Pydantic request/response models for the control-plane HTTP adapter."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


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


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    stores_injected: bool
    detail: str | None = None


__all__ = [
    "AcceptReceiptResponse",
    "ArtifactMeta",
    "ArtifactsResponse",
    "DefinitionGetResponse",
    "DefinitionListResponse",
    "DefinitionSummary",
    "HealthResponse",
    "LineageStubResponse",
    "PlanResponse",
    "ReadyResponse",
    "ReliabilityListResponse",
    "ReportStubResponse",
    "RunStatusResponse",
    "RunSubmitBody",
    "SchemaObservationAckResponse",
    "SchemaObservationsResponse",
    "ValidateResponse",
]
