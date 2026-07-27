"""WP5: concurrent durable store writers cannot corrupt reports or schema history."""

from __future__ import annotations

import json
import multiprocessing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from etlantic.io_policy import SafeIoPolicy
from etlantic.reports.file_store import FileReportStore
from etlantic.reports.model import PipelineRunReport, RunSummary
from etlantic.runtime.request import RunIntent
from etlantic.runtime.state import RunStatus
from etlantic.schema_drift import NormalizedSchema, normalize_schema_from_fields
from etlantic.schema_history import FileSchemaHistoryProvider
from etlantic.schema_policy import SchemaObservation


def _write_report(root: str, run_id: str) -> None:
    store = FileReportStore(Path(root), policy=SafeIoPolicy.for_root(root))
    report = PipelineRunReport(
        pipeline_id="p",
        plan_id="pl",
        run_id=run_id,
        intent=RunIntent.STANDARD,
        profile="development",
        status=RunStatus.SUCCEEDED,
        started_at=datetime.now(UTC),
        summary=RunSummary(total_steps=1),
    )
    store.put(report)


def test_concurrent_report_writes_remain_valid_json(tmp_path: Path) -> None:
    root = str(tmp_path)
    workers = 4
    with multiprocessing.Pool(workers) as pool:
        pool.starmap(_write_report, [(root, f"run-{i}") for i in range(workers)])

    store = FileReportStore(tmp_path, policy=SafeIoPolicy.for_root(tmp_path))
    listed = store.list(limit=10)
    assert len(listed) == workers
    for path in tmp_path.glob("*.json"):
        if path.name.endswith(".lock"):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["run_id"] == path.stem


def test_schema_history_idempotent_by_fingerprint(tmp_path: Path) -> None:
    provider = FileSchemaHistoryProvider(
        tmp_path, policy=SafeIoPolicy.for_root(tmp_path)
    )
    schema = normalize_schema_from_fields(
        [
            {"name": "id", "logical_type": "integer"},
            {"name": "name", "logical_type": "string"},
        ],
        identity="Customer",
    )
    obs = SchemaObservation(subject_id="Customer", schema=schema, inspector="test")
    provider.record(obs)
    provider.record(obs)
    assert len(provider.history("Customer")) == 1


def test_file_store_skips_incomplete_tmp_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "reports"
    root.mkdir()
    (root / "orphan.json.tmp").write_text('{"incomplete": true', encoding="utf-8")
    store = FileReportStore(root, policy=SafeIoPolicy.for_root(root))
    assert store.list() == []
