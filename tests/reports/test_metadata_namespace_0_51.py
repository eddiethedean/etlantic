"""Canonical report metadata namespace tests."""

from __future__ import annotations

import pytest

from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.state import StepStatus


def _report(metadata: dict[str, object]) -> dict[str, object]:
    return {
        "schema": "etlantic.run_report/1",
        "run_id": "run-1",
        "pipeline_id": "p",
        "pipeline_name": "P",
        "profile_name": "local",
        "status": "succeeded",
        "started_at": "2026-01-01T00:00:00",
        "ended_at": "2026-01-01T00:00:01",
        "summary": {},
        "steps": [
            {
                "step_id": "s",
                "step_name": "s",
                "status": StepStatus.SUCCEEDED.value,
                "metadata": metadata,
            }
        ],
    }


@pytest.mark.parametrize("legacy", ["dataframe", "sql", "spark", "spark_schema"])
def test_bare_built_in_metadata_is_rejected(legacy: str) -> None:
    with pytest.raises(ValueError, match="unsupported legacy metadata key"):
        PipelineRunReport.from_dict(_report({legacy: {"rows": 1}}))


def test_namespaced_metadata_reserializes_canonically() -> None:
    report = PipelineRunReport.from_dict(_report({"etlantic.sql": {"source": "ok"}}))
    again = PipelineRunReport.from_dict(report.to_dict())
    assert again.to_dict() == report.to_dict()


def test_built_in_alias_migration_is_limited_to_step_metadata() -> None:
    document = _report({})
    document["metadata"] = {"dataframe": {"owner": "report-extension"}}

    report = PipelineRunReport.from_dict(document)

    assert report.metadata == {"dataframe": {"owner": "report-extension"}}
