"""Normalized pipeline run report model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any

from pipelantic.runtime.request import RunIntent
from pipelantic.runtime.state import RunStatus, StepStatus

REPORT_SCHEMA = "pipelantic.run_report/1"


@dataclass(frozen=True, slots=True)
class RunSummary:
    """Aggregate counters for a run."""

    total_steps: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    cancelled: int = 0
    retried: int = 0
    records_in: int | None = None
    records_out: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class StepRunReport:
    """Per-step execution summary (secret-free)."""

    step_id: str
    step_name: str
    status: StepStatus
    attempts: int = 1
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: float | None = None
    failure_stage: str | None = None
    error_message: str | None = None
    records_in: int | None = None
    records_out: int | None = None
    implementation: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_name": self.step_name,
            "status": self.status.value,
            "attempts": self.attempts,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
            "failure_stage": self.failure_stage,
            "error_message": self.error_message,
            "records_in": self.records_in,
            "records_out": self.records_out,
            "implementation": self.implementation,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ArtifactResult:
    """Artifact produced or reused during a run."""

    identity: str
    logical_output: str
    strategy: str
    status: str = "available"
    record_count: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Runtime validation outcome at a boundary."""

    node_name: str
    boundary: str
    status: str
    message: str | None = None
    records_checked: int | None = None
    records_invalid: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class StateTransitionResult:
    """Recorded state transition."""

    subject: str
    from_status: str
    to_status: str
    at: datetime
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "at": self.at.isoformat(),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class RunDiagnostic:
    """Execution diagnostic (secret-free)."""

    code: str
    severity: str
    message: str
    node_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RunRecommendation:
    """Suggested follow-up action after a run."""

    kind: str
    title: str
    detail: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class BackendRunReference:
    """Reference to a backend-specific run identity."""

    backend: str
    backend_run_id: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SchemaObservationResult:
    """Schema observation recorded during a run."""

    subject_id: str
    layer: str  # declared | previous | current
    fingerprint: str | None = None
    drift_decision: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PipelineRunReport:
    """Canonical secret-free summary of a pipeline run."""

    pipeline_id: str
    plan_id: str
    run_id: str
    intent: RunIntent
    profile: str
    status: RunStatus
    started_at: datetime
    pipeline_version: str | None = None
    ended_at: datetime | None = None
    duration: timedelta | None = None
    summary: RunSummary = field(default_factory=RunSummary)
    steps: tuple[StepRunReport, ...] = ()
    artifacts: tuple[ArtifactResult, ...] = ()
    validations: tuple[ValidationResult, ...] = ()
    state_transitions: tuple[StateTransitionResult, ...] = ()
    diagnostics: tuple[RunDiagnostic, ...] = ()
    recommendations: tuple[RunRecommendation, ...] = ()
    backend_runs: tuple[BackendRunReference, ...] = ()
    schema_observations: tuple[SchemaObservationResult, ...] = ()
    plan_fingerprint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema: str = REPORT_SCHEMA

    @property
    def duration_seconds(self) -> float | None:
        if self.duration is None:
            return None
        return self.duration.total_seconds()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "pipeline_id": self.pipeline_id,
            "pipeline_version": self.pipeline_version,
            "plan_id": self.plan_id,
            "run_id": self.run_id,
            "intent": self.intent.value,
            "profile": self.profile,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
            "summary": self.summary.to_dict(),
            "steps": [s.to_dict() for s in self.steps],
            "artifacts": [a.to_dict() for a in self.artifacts],
            "validations": [v.to_dict() for v in self.validations],
            "state_transitions": [t.to_dict() for t in self.state_transitions],
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "backend_runs": [b.to_dict() for b in self.backend_runs],
            "schema_observations": [o.to_dict() for o in self.schema_observations],
            "plan_fingerprint": self.plan_fingerprint,
            "metadata": dict(self.metadata),
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        import json

        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def to_text(self) -> str:
        from pipelantic.reports.render import render_text

        return render_text(self)

    def to_html(self) -> str:
        from pipelantic.reports.render import render_html

        return render_html(self)
