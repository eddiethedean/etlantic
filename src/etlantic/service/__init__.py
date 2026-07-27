"""Transport-neutral application service facade for authoring and lifecycle."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from etlantic.authoring.catalog import (
    discover_authoring_catalog,
    negotiate_capabilities,
)
from etlantic.authoring.definition import PipelineDefinition
from etlantic.authoring.edits import EditCommand, EditResult, apply_edit
from etlantic.authoring.lifecycle import plan_pipeline_like, validate_pipeline_like
from etlantic.authoring.preview import plan_preview, structural_validate_preview
from etlantic.authoring.serialize import (
    pipeline_fingerprint,
    pipeline_from_dict,
    pipeline_to_dict,
)
from etlantic.diagnostics import ValidationReport
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.plan.model import PipelinePlan
from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.execute import run_pipeline


@dataclass(frozen=True, slots=True)
class PolicyContext:
    """Host-supplied authority; client payloads cannot expand these grants."""

    tenant: str = "default"
    environment: str = "development"
    profile: str = "development"
    allowed_assets: tuple[str, ...] | None = None
    allowed_plugins: tuple[str, ...] | None = None
    allowed_actions: tuple[str, ...] = (
        "catalog",
        "validate",
        "plan",
        "edit",
        "run",
        "cancel",
        "report",
    )


@dataclass(frozen=True, slots=True)
class ServiceError:
    code: str
    message: str
    path: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "path": list(self.path),
            "details": dict(self.details),
        }


@dataclass
class RunJob:
    job_id: str
    status: str
    created_at: str
    definition_fingerprint: str
    report: PipelineRunReport | None = None
    error: str | None = None


@dataclass
class AuthoringService:
    """In-memory facade mapping request models to public ETLantic operations."""

    policy: PolicyContext = field(default_factory=PolicyContext)
    runtime: PipelineRuntime = field(default_factory=PipelineRuntime)
    definitions: dict[str, PipelineDefinition] = field(default_factory=dict)
    jobs: dict[str, RunJob] = field(default_factory=dict)

    def _require_action(self, action: str) -> None:
        if action not in self.policy.allowed_actions:
            raise PermissionError(f"Action {action!r} is not allowed by policy context")

    def negotiation(self) -> dict[str, Any]:
        self._require_action("catalog")
        return negotiate_capabilities()

    def catalog(self, definition_id: str | None = None) -> dict[str, Any]:
        self._require_action("catalog")
        defn = self.definitions.get(definition_id) if definition_id else None
        return discover_authoring_catalog(definition=defn).to_dict()

    def put_definition(
        self,
        definition_id: str,
        document: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        self._require_action("edit")
        _ = idempotency_key
        defn = pipeline_from_dict(document, verify=True)
        self.definitions[definition_id] = defn
        return {
            "id": definition_id,
            "fingerprint": defn.fingerprint or pipeline_fingerprint(defn),
            "definition": pipeline_to_dict(defn),
        }

    def get_definition(self, definition_id: str) -> dict[str, Any]:
        defn = self.definitions[definition_id]
        return {
            "id": definition_id,
            "fingerprint": defn.fingerprint or pipeline_fingerprint(defn),
            "definition": pipeline_to_dict(defn),
        }

    def apply_edit(
        self,
        definition_id: str,
        command: dict[str, Any],
        *,
        expected_token: str | None = None,
    ) -> dict[str, Any]:
        self._require_action("edit")
        defn = self.definitions[definition_id]
        result: EditResult = apply_edit(
            defn, EditCommand.from_dict(command), expected_token=expected_token
        )
        self.definitions[definition_id] = result.definition
        return {
            "id": definition_id,
            "fingerprint": result.fingerprint,
            "concurrency_token": result.concurrency_token,
            "definition": pipeline_to_dict(result.definition),
        }

    def validate(self, definition_id: str) -> dict[str, Any]:
        self._require_action("validate")
        defn = self.definitions[definition_id]
        report = structural_validate_preview(defn, profile=self.policy.profile)
        return {
            "ok": not report.has_errors,
            "diagnostics": [d.to_dict() for d in report.diagnostics],
            "fingerprint": defn.fingerprint or pipeline_fingerprint(defn),
        }

    def plan(self, definition_id: str) -> dict[str, Any]:
        self._require_action("plan")
        defn = self.definitions[definition_id]
        plan, report = plan_preview(defn, profile=self.policy.profile)
        return {
            "ok": plan is not None and not report.has_errors,
            "diagnostics": [d.to_dict() for d in report.diagnostics],
            "plan": plan.to_dict() if plan is not None else None,
        }

    def submit_run(
        self,
        definition_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        self._require_action("run")
        _ = idempotency_key
        defn = self.definitions[definition_id]
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        created = datetime.now(UTC).isoformat()
        job = RunJob(
            job_id=job_id,
            status="submitted",
            created_at=created,
            definition_fingerprint=defn.fingerprint or pipeline_fingerprint(defn),
        )
        self.jobs[job_id] = job
        try:
            report = run_pipeline(
                defn, profile=self.policy.profile, runtime=self.runtime
            )
            job.status = "succeeded" if report.status.value == "succeeded" else report.status.value
            job.report = report
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
        return self.job_status(job_id)

    def cancel_run(self, job_id: str) -> dict[str, Any]:
        self._require_action("cancel")
        job = self.jobs[job_id]
        if job.status in {"submitted", "running"}:
            job.status = "cancelled"
        return self.job_status(job_id)

    def job_status(self, job_id: str) -> dict[str, Any]:
        self._require_action("report")
        job = self.jobs[job_id]
        return {
            "job_id": job.job_id,
            "status": job.status,
            "created_at": job.created_at,
            "definition_fingerprint": job.definition_fingerprint,
            "error": job.error,
            "report": job.report.to_dict() if job.report is not None else None,
        }


# Re-export helpers used by OpenAPI adapters
__all__ = [
    "AuthoringService",
    "PipelinePlan",
    "PolicyContext",
    "RunJob",
    "ServiceError",
    "ValidationReport",
    "plan_pipeline_like",
    "validate_pipeline_like",
]
