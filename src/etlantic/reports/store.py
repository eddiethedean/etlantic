# pyright: reportUnknownVariableType=false
"""In-process run report history."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from etlantic.reports.model import PipelineRunReport
from etlantic.reports.retention import (
    RUN_ARTIFACT_RETENTION_STATE_KEY,
    TERMINAL_RUN_STATUSES,
)


@dataclass
class ReportStore:
    """Process-local store of completed/partial run reports."""

    _by_id: dict[str, PipelineRunReport] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)

    def put(self, report: PipelineRunReport) -> None:
        if report.run_id not in self._by_id:
            self._order.append(report.run_id)
        self._by_id[report.run_id] = report

    def get(self, run_id: str) -> PipelineRunReport | None:
        return self._by_id.get(run_id)

    def list(
        self,
        *,
        pipeline_id: str | None = None,
        limit: int | None = None,
    ) -> list[PipelineRunReport]:
        items = [
            self._by_id[rid] for rid in reversed(self._order) if rid in self._by_id
        ]
        if pipeline_id is not None:
            items = [r for r in items if r.pipeline_id == pipeline_id]
        if limit is not None:
            items = items[:limit]
        return items

    def list_expired_artifact_reports(
        self, *, cutoff: datetime, limit: int
    ) -> list[PipelineRunReport]:
        """Return oldest terminal reports whose artifact window has elapsed."""
        if limit < 1:
            return []

        def ended_at(report: PipelineRunReport) -> datetime | None:
            value = report.ended_at
            if value is None:
                return None
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value.astimezone(UTC)

        boundary = (
            cutoff.astimezone(UTC) if cutoff.tzinfo else cutoff.replace(tzinfo=UTC)
        )
        candidates = [
            report
            for report in self.list()
            if report.status.value in TERMINAL_RUN_STATUSES
            and report.metadata.get(RUN_ARTIFACT_RETENTION_STATE_KEY) != "complete"
            and (finished := ended_at(report)) is not None
            and finished <= boundary
        ]
        candidates.sort(
            key=lambda report: (ended_at(report) or boundary, report.run_id)
        )
        return candidates[:limit]
