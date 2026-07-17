"""Unit tests for 0.9 tooling surfaces."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from etlantic.diagnostics import Diagnostic, Severity
from etlantic.diagnostics.sarif import diagnostics_to_sarif
from etlantic.ide import get_command_schema, list_commands, write_schemas
from etlantic.plugin_trust import filter_plugins_by_allowlist
from etlantic.profile import Profile
from etlantic.reports.file_store import FileReportStore, compare_reports
from etlantic.reports.model import PipelineRunReport, RunSummary
from etlantic.runtime.request import RunIntent
from etlantic.runtime.state import RunStatus
from etlantic.schema_drift import NormalizedField, NormalizedSchema, SchemaObservation
from etlantic.schema_history import FileSchemaHistoryProvider
from etlantic.viz import graph_to_dot, logical_graph_to_ir
from tests.fixtures.sample_pipeline import SamplePipeline


def test_sarif_renderer() -> None:
    payload = diagnostics_to_sarif(
        [
            Diagnostic(
                code="PMTEST001",
                severity=Severity.ERROR,
                message="boom",
                path=("pipeline",),
            )
        ]
    )
    assert payload["version"] == "2.1.0"
    assert payload["runs"][0]["results"][0]["ruleId"] == "PMTEST001"


def test_production_allowlist_fail_closed() -> None:
    class _P:
        info = type("I", (), {"name": "evil", "engine": "evil", "version": "1.0.0"})()

    profile = Profile(
        name="production",
        security_domain="production",
        plugin_allowlist={"good": ">=1.0"},
    )
    kept, diags = filter_plugins_by_allowlist({"evil": _P()}, profile)
    assert kept == {}
    assert any(d.code == "PMPLUG402" for d in diags)


def test_empty_production_allowlist_rejects_all() -> None:
    profile = Profile(name="production", security_domain="production")
    kept, diags = filter_plugins_by_allowlist({"x": object()}, profile)
    assert kept == {}
    assert any(d.code == "PMPLUG401" for d in diags)


def test_file_schema_history(tmp_path: Path) -> None:
    provider = FileSchemaHistoryProvider(tmp_path)
    schema = NormalizedSchema(
        identity="s",
        fields=(NormalizedField(name="id", logical_type="integer"),),
    )
    obs = SchemaObservation(subject_id="orders", schema=schema, inspector="test")
    provider.record(obs)
    assert provider.latest("orders") is not None
    ack = provider.acknowledge("orders", note="ok")
    assert ack["acknowledged_fingerprint"] == schema.fingerprint()

    # Innocent keys that contain "rows"/"records" as substrings must be allowed.
    provider.record(
        SchemaObservation(
            subject_id="browsers_ok",
            schema=schema,
            inspector="test",
            metadata={"browsers": 1, "nrows": 10, "records_checked": 5},
        )
    )
    assert provider.latest("browsers_ok") is not None

    with pytest.raises(ValueError, match="source rows"):
        provider.record(
            SchemaObservation(
                subject_id="bad",
                schema=schema,
                inspector="test",
                metadata={"sample_rows": [{"id": 1}]},
            )
        )


def test_file_report_store_compare(tmp_path: Path) -> None:
    store = FileReportStore(tmp_path)
    report = PipelineRunReport(
        pipeline_id="p",
        plan_id="plan",
        run_id="run-1",
        intent=RunIntent.STANDARD,
        profile="local",
        status=RunStatus.SUCCEEDED,
        started_at=datetime(2026, 1, 1),
        summary=RunSummary(total_steps=1, succeeded=1),
    )
    store.put(report)
    loaded = store.get("run-1")
    assert loaded is not None
    assert compare_reports(loaded, report)["status_equal"] is True


def test_viz_dot_from_pipeline() -> None:
    ir = logical_graph_to_ir(SamplePipeline.inspect())
    dot = graph_to_dot(ir)
    assert "digraph" in dot
    assert "->" in dot


def test_ide_schemas(tmp_path: Path) -> None:
    assert "validate" in list_commands()
    schema = get_command_schema("validate")
    assert schema["required"] == ["target"]
    written = write_schemas(tmp_path)
    assert (tmp_path / "command_validate.json").exists()
    assert "command:validate" in written
