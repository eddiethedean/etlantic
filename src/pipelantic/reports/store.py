"""In-process run report history."""

from __future__ import annotations

from dataclasses import dataclass, field

from pipelantic.reports.model import PipelineRunReport


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
