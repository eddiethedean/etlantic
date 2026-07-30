"""Submission, cancellation, polling, and report correlation models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from etlantic.reports.model import (
    BackendRunReference,
    PipelineRunReport,
    RunDiagnostic,
    RunStatus,
    StepRunReport,
    StepStatus,
)


class SubmissionStatus(StrEnum):
    """Lifecycle of an externally submitted orchestration run."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CorrelationKeys:
    """Keys linking ETLantic runs to backend orchestrator identities."""

    run_id: str
    plan_id: str
    pipeline_id: str
    dag_id: str
    backend: str = "airflow"
    backend_run_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "plan_id": self.plan_id,
            "pipeline_id": self.pipeline_id,
            "dag_id": self.dag_id,
            "backend": self.backend,
            "backend_run_id": self.backend_run_id,
            "metadata": dict(self.metadata),
        }

    def to_backend_reference(self) -> BackendRunReference:
        return BackendRunReference(
            backend=self.backend,
            backend_run_id=self.backend_run_id or self.run_id,
            metadata={
                "dag_id": self.dag_id,
                "plan_id": self.plan_id,
                "pipeline_id": self.pipeline_id,
                "run_id": self.run_id,
                **dict(self.metadata),
            },
        )


@dataclass(frozen=True, slots=True)
class SubmissionResult:
    """Result of submitting a compiled artifact to an orchestrator."""

    correlation: CorrelationKeys
    status: SubmissionStatus = SubmissionStatus.QUEUED
    submitted_at: datetime | None = None
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation": self.correlation.to_dict(),
            "status": self.status.value,
            "submitted_at": (
                self.submitted_at.isoformat() if self.submitted_at else None
            ),
            "message": self.message,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class PollResult:
    """Polled status for an external orchestration run."""

    correlation: CorrelationKeys
    status: SubmissionStatus
    task_states: dict[str, str] = field(default_factory=dict)
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation": self.correlation.to_dict(),
            "status": self.status.value,
            "task_states": dict(self.task_states),
            "message": self.message,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class CancellationResult:
    """Result of requesting cancellation of an external run."""

    correlation: CorrelationKeys
    status: SubmissionStatus
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation": self.correlation.to_dict(),
            "status": self.status.value,
            "message": self.message,
            "metadata": dict(self.metadata),
        }


_STATUS_MAP = {
    "success": RunStatus.SUCCEEDED,
    "succeeded": RunStatus.SUCCEEDED,
    "failed": RunStatus.FAILED,
    "upstream_failed": RunStatus.FAILED,
    "skipped": RunStatus.SUCCEEDED,
    "running": RunStatus.RUNNING,
    "queued": RunStatus.RUNNING,
    "cancelled": RunStatus.CANCELLED,
    "canceled": RunStatus.CANCELLED,
}

_STEP_STATUS_MAP = {
    "success": StepStatus.SUCCEEDED,
    "succeeded": StepStatus.SUCCEEDED,
    "failed": StepStatus.FAILED,
    "upstream_failed": StepStatus.FAILED,
    "skipped": StepStatus.SKIPPED,
    "running": StepStatus.RUNNING,
    "queued": StepStatus.PENDING,
    "cancelled": StepStatus.CANCELLED,
    "canceled": StepStatus.CANCELLED,
}


def correlate_poll_to_report(
    report: PipelineRunReport,
    poll: PollResult,
) -> PipelineRunReport:
    """Attach backend correlation and task states onto a normalized report."""
    from dataclasses import replace

    backend_ref = poll.correlation.to_backend_reference()
    backend_runs = tuple([*report.backend_runs, backend_ref])

    step_updates: list[StepRunReport] = []
    for step in report.steps:
        state = poll.task_states.get(step.step_name) or poll.task_states.get(
            step.step_id
        )
        if state is None:
            step_updates.append(step)
            continue
        mapped = _STEP_STATUS_MAP.get(state.lower(), step.status)
        step_updates.append(
            replace(
                step,
                status=mapped,
                metadata={
                    **dict(step.metadata),
                    "etlantic.orchestrator_task_state": state,
                    "etlantic.orchestrator": poll.correlation.backend,
                    "etlantic.dag_id": poll.correlation.dag_id,
                },
            )
        )

    run_status = _STATUS_MAP.get(poll.status.value, report.status)
    diagnostics = report.diagnostics
    if poll.message:
        diagnostics = tuple(
            [
                *diagnostics,
                RunDiagnostic(
                    code="PMORCH400",
                    severity="info",
                    message=poll.message,
                    metadata={"backend": poll.correlation.backend},
                ),
            ]
        )

    return replace(
        report,
        status=run_status,
        steps=tuple(step_updates) if step_updates else report.steps,
        backend_runs=backend_runs,
        diagnostics=diagnostics,
        metadata={
            **dict(report.metadata),
            "orchestration": poll.correlation.to_dict(),
        },
    )


def comparable_report_shape(report: PipelineRunReport) -> dict[str, Any]:
    """Normalized shape for comparing local vs orchestrated runs."""
    return {
        "pipeline_id": report.pipeline_id,
        "plan_id": report.plan_id,
        "status": report.status.value,
        "step_names": [s.step_name for s in report.steps],
        "step_statuses": {s.step_name: s.status.value for s in report.steps},
        "artifact_ids": [a.identity for a in report.artifacts],
        "plan_fingerprint": report.plan_fingerprint,
    }
