"""Filesystem-backed durable run report store."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from etlantic.io_policy import SafeIoPolicy, read_text_safe, write_text_safe
from etlantic.reports.model import PipelineRunReport
from etlantic.reports.store import ReportStore
from etlantic.serialization_policy import assert_safe_load_path

_LOG = logging.getLogger(__name__)


@dataclass
class FileReportStore:
    """Durable report store writing one JSON file per run_id via SafeIoPolicy."""

    root: Path
    policy: SafeIoPolicy | None = None
    _memory: ReportStore = field(default_factory=ReportStore)

    def __post_init__(self) -> None:
        self.root = Path(self.root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if self.policy is None:
            self.policy = SafeIoPolicy.for_root(self.root)
        for path in sorted(self.root.rglob("*.json")):
            if path.name.endswith(".lock") or path.suffix == ".tmp":
                continue
            try:
                assert_safe_load_path(path)
                _resolved, text, _events = read_text_safe(
                    path, self.policy, run_id="report-load"
                )
                data = json.loads(text)
                report = PipelineRunReport.from_dict(data)
                self._memory.put(report)
            except Exception as exc:
                _LOG.warning("Skipping report file %s: %s", path, exc)
                continue

    def put(self, report: PipelineRunReport) -> None:
        from etlantic.runtime.faults import FaultBoundary, maybe_inject

        maybe_inject(FaultBoundary.REPORT_PERSIST)
        assert self.policy is not None
        path = self.root / f"{report.run_id}.json"
        # Durable write first so a failed write cannot leave SUCCEEDED in memory.
        write_text_safe(
            path,
            report.to_json(),
            self.policy,
            run_id=report.run_id,
        )
        self._memory.put(report)

    def get(self, run_id: str) -> PipelineRunReport | None:
        return self._memory.get(run_id)

    def list(
        self,
        *,
        pipeline_id: str | None = None,
        limit: int | None = None,
    ) -> list[PipelineRunReport]:
        return self._memory.list(pipeline_id=pipeline_id, limit=limit)


def compare_reports(
    left: PipelineRunReport,
    right: PipelineRunReport,
) -> dict[str, Any]:
    """Compare two normalized reports without backend-specific classes."""
    left_steps = {s.step_name: s.status.value for s in left.steps}
    right_steps = {s.step_name: s.status.value for s in right.steps}
    return {
        "left_run_id": left.run_id,
        "right_run_id": right.run_id,
        "status_equal": left.status.value == right.status.value,
        "left_status": left.status.value,
        "right_status": right.status.value,
        "step_names_equal": set(left_steps) == set(right_steps),
        "step_status_diffs": {
            name: {"left": left_steps.get(name), "right": right_steps.get(name)}
            for name in sorted(set(left_steps) | set(right_steps))
            if left_steps.get(name) != right_steps.get(name)
        },
        "plan_fingerprint_equal": left.plan_fingerprint == right.plan_fingerprint,
        "artifact_count_left": len(left.artifacts),
        "artifact_count_right": len(right.artifacts),
    }
