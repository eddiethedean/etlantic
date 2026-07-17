"""Normalize SparkForge-shaped run results into PipelineRunReport."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from etlantic.reports.model import (
    ArtifactResult,
    PipelineRunReport,
    RunDiagnostic,
    RunSummary,
    StepRunReport,
    ValidationResult,
)
from etlantic.runtime.logging import redact_message, redact_value
from etlantic.runtime.request import RunIntent
from etlantic.runtime.state import RunStatus, StepStatus
from etlantic.secrets.value import SecretValue

_STATUS_ALIASES: dict[str, RunStatus] = {
    "ok": RunStatus.SUCCEEDED,
    "success": RunStatus.SUCCEEDED,
    "successful": RunStatus.SUCCEEDED,
    "completed": RunStatus.SUCCEEDED,
    "complete": RunStatus.SUCCEEDED,
    "failed": RunStatus.FAILED,
    "error": RunStatus.FAILED,
    "failure": RunStatus.FAILED,
    "abort": RunStatus.FAILED,
    "aborted": RunStatus.FAILED,
    "cancelled": RunStatus.CANCELLED,
    "canceled": RunStatus.CANCELLED,
    "timeout": RunStatus.TIMED_OUT,
    "timed_out": RunStatus.TIMED_OUT,
    "timedout": RunStatus.TIMED_OUT,
    "partial": RunStatus.PARTIAL,
    "pending": RunStatus.PENDING,
    "running": RunStatus.RUNNING,
    "succeeded": RunStatus.SUCCEEDED,
}

_STEP_STATUS_ALIASES: dict[str, StepStatus] = {
    "ok": StepStatus.SUCCEEDED,
    "success": StepStatus.SUCCEEDED,
    "successful": StepStatus.SUCCEEDED,
    "completed": StepStatus.SUCCEEDED,
    "failed": StepStatus.FAILED,
    "error": StepStatus.FAILED,
    "failure": StepStatus.FAILED,
    "skipped": StepStatus.SKIPPED,
    "skip": StepStatus.SKIPPED,
    "cancelled": StepStatus.CANCELLED,
    "canceled": StepStatus.CANCELLED,
    "timeout": StepStatus.TIMED_OUT,
    "timed_out": StepStatus.TIMED_OUT,
    "retrying": StepStatus.RETRYING,
    "pending": StepStatus.PENDING,
    "running": StepStatus.RUNNING,
    "succeeded": StepStatus.SUCCEEDED,
}


def _redact(value: Any) -> Any:
    """Redact secrets in structured and free-text SparkForge payloads."""
    if isinstance(value, SecretValue):
        return "***"
    if isinstance(value, dict):
        return redact_value(value)
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, str):
        return redact_message(value)
    return value


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    return redact_message(str(value))


def _coalesce_int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    return int(value)


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def _map_run_status(raw: str) -> tuple[RunStatus, bool]:
    """Return (status, known). Unknown → FAILED."""
    key = raw.strip().lower()
    if key in _STATUS_ALIASES:
        return _STATUS_ALIASES[key], True
    try:
        return RunStatus(key), True
    except ValueError:
        return RunStatus.FAILED, False


def _map_step_status(raw: str) -> StepStatus:
    key = raw.strip().lower()
    if key in _STEP_STATUS_ALIASES:
        return _STEP_STATUS_ALIASES[key]
    try:
        return StepStatus(key)
    except ValueError:
        if "fail" in key or "error" in key:
            return StepStatus.FAILED
        if "skip" in key:
            return StepStatus.SKIPPED
        if "cancel" in key:
            return StepStatus.CANCELLED
        return StepStatus.FAILED


def adapt_run_result(
    payload: dict[str, Any],
    *,
    pipeline_id: str | None = None,
    profile: str = "sparkforge",
) -> PipelineRunReport:
    """Convert a SparkForge-shaped result dict into PipelineRunReport.

    Never retains secret-like keys or free-text credentials from the source
    payload. Unknown run statuses fail closed to ``failed`` with diagnostic
    ``PMSF500``.
    """
    safe = _redact(payload)
    status_raw = str(safe.get("status") or safe.get("pipeline_status") or "succeeded")
    status, status_known = _map_run_status(status_raw)
    diagnostics: list[RunDiagnostic] = []
    if not status_known:
        diagnostics.append(
            RunDiagnostic(
                code="PMSF500",
                severity="error",
                message=(
                    f"Unknown SparkForge run status {status_raw!r}; "
                    "mapped to failed (fail closed)."
                ),
            )
        )

    steps_raw = safe.get("steps") or safe.get("step_results") or []
    steps: list[StepRunReport] = []
    for item in steps_raw:
        if not isinstance(item, dict):
            continue
        step_status = _map_step_status(str(item.get("status") or "succeeded"))
        name = str(item.get("name") or item.get("step_name") or "step")
        attempts = item.get("attempts")
        records_in = item.get("records_in")
        if records_in is None:
            records_in = item.get("input_count")
        records_out = item.get("records_out")
        if records_out is None:
            records_out = item.get("output_count")
        steps.append(
            StepRunReport(
                step_id=str(item.get("step_id") or name),
                step_name=name,
                status=step_status,
                attempts=_coalesce_int(attempts, 1) if attempts is not None else 1,
                error_message=_safe_text(
                    item.get("error") or item.get("error_message")
                ),
                records_in=_coalesce_int(records_in),
                records_out=_coalesce_int(records_out),
                metadata={
                    k: _redact(v)
                    for k, v in item.items()
                    if k
                    not in {
                        "name",
                        "step_name",
                        "step_id",
                        "status",
                        "attempts",
                        "error",
                        "error_message",
                        "records_in",
                        "records_out",
                        "input_count",
                        "output_count",
                    }
                },
            )
        )

    validations: list[ValidationResult] = []
    for item in safe.get("validations") or safe.get("quality_results") or []:
        if not isinstance(item, dict):
            continue
        checked = item.get("records_checked")
        if checked is None:
            checked = item.get("total")
        invalid = item.get("records_invalid")
        if invalid is None:
            invalid = item.get("invalid")
        validations.append(
            ValidationResult(
                node_name=str(item.get("node_name") or item.get("step") or "unknown"),
                boundary=str(item.get("boundary") or "quality_gate"),
                status=str(item.get("status") or "passed"),
                message=_safe_text(item.get("message")),
                records_checked=_coalesce_int(checked),
                records_invalid=_coalesce_int(invalid),
            )
        )

    artifacts: list[ArtifactResult] = []
    for item in safe.get("artifacts") or safe.get("tables") or []:
        if not isinstance(item, dict):
            continue
        identity = str(
            item.get("identity") or item.get("table") or item.get("name") or ""
        )
        if not identity:
            continue
        count = item.get("record_count")
        if count is None:
            count = item.get("count")
        artifacts.append(
            ArtifactResult(
                identity=identity,
                logical_output=str(item.get("logical_output") or identity),
                strategy=str(item.get("strategy") or "external"),
                status=str(item.get("status") or "available"),
                record_count=_coalesce_int(count),
            )
        )

    for item in safe.get("diagnostics") or safe.get("errors") or []:
        if isinstance(item, str):
            diagnostics.append(
                RunDiagnostic(
                    code="PMSF500",
                    severity="error",
                    message=redact_message(item),
                )
            )
        elif isinstance(item, dict):
            diagnostics.append(
                RunDiagnostic(
                    code=str(item.get("code") or "PMSF500"),
                    severity=str(item.get("severity") or "error"),
                    message=redact_message(str(item.get("message") or item)),
                )
            )

    succeeded = sum(1 for s in steps if s.status is StepStatus.SUCCEEDED)
    failed = sum(1 for s in steps if s.status is StepStatus.FAILED)
    skipped = sum(1 for s in steps if s.status is StepStatus.SKIPPED)
    cancelled = sum(1 for s in steps if s.status is StepStatus.CANCELLED)
    summary = RunSummary(
        total_steps=len(steps),
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        cancelled=cancelled,
        records_in=_coalesce_int(safe.get("records_in")),
        records_out=_coalesce_int(safe.get("records_out")),
    )

    started_at = _parse_dt(safe.get("started_at")) or datetime.now(UTC)
    ended_at = _parse_dt(safe.get("ended_at"))
    duration: timedelta | None = None
    if safe.get("duration_seconds") is not None:
        duration = timedelta(seconds=float(safe["duration_seconds"]))
    elif ended_at is not None:
        duration = ended_at - started_at

    intent_raw = str(safe.get("intent") or safe.get("mode") or "standard").lower()
    try:
        from etlantic_sparkforge.runtime_map import intent_from_sparkforge

        intent = intent_from_sparkforge(intent_raw)
    except ValueError:
        intent = RunIntent.STANDARD

    return PipelineRunReport(
        pipeline_id=str(
            pipeline_id
            or safe.get("pipeline_id")
            or safe.get("pipeline")
            or "sparkforge"
        ),
        plan_id=str(safe.get("plan_id") or "plan:sparkforge-adapted"),
        run_id=str(safe.get("run_id") or safe.get("execution_id") or "run-sparkforge"),
        intent=intent,
        profile=profile,
        status=status,
        started_at=started_at,
        ended_at=ended_at,
        duration=duration,
        summary=summary,
        steps=tuple(steps),
        artifacts=tuple(artifacts),
        validations=tuple(validations),
        diagnostics=tuple(diagnostics),
        metadata={
            "adapter": "etlantic-sparkforge",
            "source_keys": sorted(str(k) for k in safe),
            "status_raw": status_raw,
        },
    )


def report_to_sparkforge_explain(report: PipelineRunReport) -> dict[str, Any]:
    """Dual-reporting helper: ETLantic report → SparkForge-shaped explain dict."""
    return {
        "pipeline_id": report.pipeline_id,
        "run_id": report.run_id,
        "status": report.status.value,
        "mode": report.intent.value,
        "started_at": report.started_at.isoformat() if report.started_at else None,
        "ended_at": report.ended_at.isoformat() if report.ended_at else None,
        "duration_seconds": report.duration_seconds,
        "steps": [
            {
                "name": s.step_name,
                "status": s.status.value,
                "records_in": s.records_in,
                "records_out": s.records_out,
                "attempts": s.attempts,
            }
            for s in report.steps
        ],
        "validations": [v.to_dict() for v in report.validations],
        "artifacts": [a.to_dict() for a in report.artifacts],
        "diagnostics": [d.to_dict() for d in report.diagnostics],
        "summary": report.summary.to_dict(),
    }
