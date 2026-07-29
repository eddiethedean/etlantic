"""Secret-free query helpers over run reports and history."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from etlantic.observability.history import (
    RunHistoryProvider,
    RunHistoryQuery,
    coerce_utc,
)
from etlantic.reports.file_store import compare_reports
from etlantic.reports.model import PipelineRunReport
from etlantic.reports.store import ReportStore


@runtime_checkable
class ReportQueryable(Protocol):
    def list(
        self,
        *,
        pipeline_id: str | None = None,
        limit: int | None = None,
    ) -> list[PipelineRunReport]: ...

    def get(self, run_id: str) -> PipelineRunReport | None: ...


def query_reports(
    store: ReportQueryable,
    *,
    pipeline_id: str | None = None,
    status: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int | None = None,
) -> list[PipelineRunReport]:
    """Filter in-process or file-backed reports without backend-specific classes."""
    since_utc = coerce_utc(since) if since is not None else None
    until_utc = coerce_utc(until) if until is not None else None
    items = store.list(pipeline_id=pipeline_id, limit=None)
    filtered: list[PipelineRunReport] = []
    for report in items:
        if status and report.status.value != status:
            continue
        if since_utc and report.started_at < since_utc:
            continue
        if until_utc and report.started_at > until_utc:
            continue
        filtered.append(report)
    filtered.sort(key=lambda r: r.started_at, reverse=True)
    if limit is not None:
        filtered = filtered[:limit]
    return filtered


def query_history(
    provider: RunHistoryProvider,
    *,
    pipeline_id: str | None = None,
    status: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return run history entries as JSON-friendly dicts."""
    query = RunHistoryQuery(
        pipeline_id=pipeline_id,
        status=status,
        since=since,
        until=until,
        limit=limit,
    )
    return [entry.to_dict() for entry in provider.list_runs(query)]


def compare_run_reports(
    left: PipelineRunReport,
    right: PipelineRunReport,
) -> dict[str, Any]:
    """Compare two normalized reports."""
    return compare_reports(left, right)


def get_report_from_history(
    provider: RunHistoryProvider,
    run_id: str,
) -> PipelineRunReport | None:
    """Load a terminal report from a run-history provider when present."""
    payload = provider.read_run(run_id)
    if not payload:
        return None
    report_raw = payload.get("report") or {}
    if not report_raw:
        return None
    return PipelineRunReport.from_dict(report_raw)


__all__ = [
    "ReportQueryable",
    "ReportStore",
    "compare_run_reports",
    "get_report_from_history",
    "query_history",
    "query_reports",
]
