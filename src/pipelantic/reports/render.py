"""Render PipelineRunReport to text and HTML."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pipelantic.reports.model import PipelineRunReport


def render_text(report: PipelineRunReport) -> str:
    """Render a compact human-readable report."""
    lines = [
        f"PipelineRunReport {report.run_id}",
        f"  pipeline: {report.pipeline_id}",
        f"  plan:     {report.plan_id}",
        f"  profile:  {report.profile}",
        f"  intent:   {report.intent.value}",
        f"  status:   {report.status.value}",
        f"  started:  {report.started_at.isoformat()}",
    ]
    if report.ended_at is not None:
        lines.append(f"  ended:    {report.ended_at.isoformat()}")
    if report.duration_seconds is not None:
        lines.append(f"  duration: {report.duration_seconds:.3f}s")
    s = report.summary
    lines.append(
        "  summary:  "
        f"total={s.total_steps} ok={s.succeeded} failed={s.failed} "
        f"skipped={s.skipped} cancelled={s.cancelled}"
    )
    if report.steps:
        lines.append("  steps:")
        for step in report.steps:
            dur = (
                f" {step.duration_seconds:.3f}s"
                if step.duration_seconds is not None
                else ""
            )
            err = f" — {step.error_message}" if step.error_message else ""
            lines.append(f"    - {step.step_name}: {step.status.value}{dur}{err}")
    if report.diagnostics:
        lines.append("  diagnostics:")
        for diag in report.diagnostics:
            lines.append(f"    - [{diag.severity}] {diag.code}: {diag.message}")
    return "\n".join(lines)


def render_html(report: PipelineRunReport) -> str:
    """Render a minimal HTML report (secret-free)."""
    rows = "".join(
        f"<tr><td>{_esc(s.step_name)}</td><td>{_esc(s.status.value)}</td>"
        f"<td>{s.duration_seconds if s.duration_seconds is not None else ''}</td>"
        f"<td>{_esc(s.error_message or '')}</td></tr>"
        for s in report.steps
    )
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>Run {_esc(report.run_id)}</title></head><body>"
        f"<h1>Pipeline run {_esc(report.run_id)}</h1>"
        f"<p>Status: <strong>{_esc(report.status.value)}</strong></p>"
        f"<p>Pipeline: {_esc(report.pipeline_id)} · Profile: {_esc(report.profile)}</p>"
        "<table border='1' cellpadding='4' cellspacing='0'>"
        "<thead><tr><th>Step</th><th>Status</th><th>Duration (s)</th>"
        "<th>Error</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        "</body></html>"
    )


def _esc(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
