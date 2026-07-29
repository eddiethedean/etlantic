"""Unit tests for 0.9 tooling surfaces."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from etlantic.diagnostics import Diagnostic, Severity
from etlantic.diagnostics.sarif import diagnostics_to_sarif
from etlantic.ide import get_command_schema, list_commands, write_schemas
from etlantic.plugin_trust import filter_plugins_by_allowlist, plugin_allowed
from etlantic.profile import Profile
from etlantic.reports.file_store import FileReportStore, compare_reports
from etlantic.reports.model import PipelineRunReport, RunSummary
from etlantic.runtime.request import RunIntent
from etlantic.runtime.state import RunStatus
from etlantic.schema_drift import (
    NormalizedField,
    NormalizedSchema,
    SchemaObservation,
    diff_normalized_schemas,
)
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
        security_mode="production",
        security_domain="production",
        plugin_allowlist={"good": ">=1.0"},
    )
    kept, diags = filter_plugins_by_allowlist({"evil": _P()}, profile)
    assert kept == {}
    assert any(d.code == "PMPLUG402" and d.severity is Severity.ERROR for d in diags)


def test_empty_security_mode_rejected() -> None:
    import pytest

    with pytest.raises(ValueError, match="empty string"):
        Profile(name="x", security_mode="")  # type: ignore[arg-type]


def test_staging_not_inferred_as_production() -> None:
    from etlantic.profile import Profile

    profile = Profile.from_dict({"name": "staging", "security_domain": "staging"})
    assert profile.security_mode == "development"


def test_invalid_allowlist_pin_emits_pmplug403() -> None:
    class _P:
        info = type(
            "I",
            (),
            {"name": "etlantic-polars", "engine": "polars", "version": "0.27.0"},
        )()

    profile = Profile(
        name="production",
        security_mode="production",
        plugin_allowlist={"etlantic-polars": "not a pin!!!"},
    )
    kept, diags = filter_plugins_by_allowlist({"polars": _P()}, profile)
    assert kept == {}
    assert any(d.code == "PMPLUG403" for d in diags)


def test_empty_production_allowlist_rejects_all() -> None:
    profile = Profile(
        name="production",
        security_domain="production",
        security_mode="production",
    )
    kept, diags = filter_plugins_by_allowlist({"x": object()}, profile)
    assert kept == {}
    assert any(d.code == "PMPLUG401" for d in diags)


def test_bare_version_pin_accepted() -> None:
    assert plugin_allowed(
        name="etlantic-polars",
        version="0.12.0",
        allowlist={"etlantic-polars": "0.12.0"},
    )
    assert not plugin_allowed(
        name="etlantic-polars",
        version="0.11.0",
        allowlist={"etlantic-polars": "0.12.0"},
    )


def test_is_production_profile_uses_security_mode() -> None:
    import pytest

    from etlantic.plugin_trust import is_production_profile

    assert is_production_profile(Profile(name="custom", security_mode="production"))
    assert is_production_profile(security_mode="production")
    # Names / domains alone no longer drive fail-closed policy.
    assert not is_production_profile(Profile(name="production"))
    assert not is_production_profile(Profile(name="Prod"))
    assert not is_production_profile(Profile(name="staging"))
    with pytest.warns(UserWarning, match="security_domain looks like production"):
        domain_only = Profile(name="app", security_domain="production")
    assert not is_production_profile(domain_only)
    assert not is_production_profile(name="prod", security_domain="default")
    assert not is_production_profile(Profile(name="development"))
    assert is_production_profile(
        Profile(name="development", security_mode="production")
    )


def test_discover_planning_plugins_early_returns_on_pmplug401() -> None:
    from etlantic.plugins.coordinator import discover_planning_plugins
    from etlantic.profile import production_profile
    from etlantic.registry import builtin_stub_registry

    profile = production_profile(plugin_allowlist={})
    _trust, diags = discover_planning_plugins(
        profile,
        builtin_stub_registry(),
        dataframe_engine="polars",
        sql_engine=None,
        spark_engine=None,
    )
    assert sum(1 for d in diags if d.code == "PMPLUG401") == 1


def test_schema_drift_blocks_production_security_mode() -> None:
    from etlantic.schema_policy import DriftAction, SchemaDriftPolicy

    left = NormalizedSchema(
        identity="s",
        fields=(NormalizedField(name="id", logical_type="integer"),),
    )
    right = NormalizedSchema(
        identity="s",
        fields=(NormalizedField(name="id", logical_type="string"),),
    )
    change_set = diff_normalized_schemas(left, right)
    policy = SchemaDriftPolicy()
    assert (
        policy.decide(
            subject_id="orders",
            change_set=change_set,
            profile_name="custom",
            security_mode="production",
        )
        is DriftAction.BLOCK
    )
    assert (
        policy.decide(
            subject_id="orders",
            change_set=change_set,
            profile_name="prod",
        )
        is DriftAction.RECORD
    )
    assert (
        policy.decide(
            subject_id="orders",
            change_set=change_set,
            profile_name="development",
            security_mode="development",
        )
        is DriftAction.RECORD
    )


def test_production_validate_requires_allowlist() -> None:
    from etlantic.profile import production_profile
    from tests.fixtures.sample_pipeline import SamplePipeline

    report = SamplePipeline.validate(profile=production_profile())
    assert not report.valid
    assert any(d.code == "PMPLUG401" for d in report.diagnostics)

    ok = SamplePipeline.validate(
        profile=production_profile(plugin_allowlist={"etlantic-polars": "==0.27.0"})
    )
    assert not any(d.code == "PMPLUG401" for d in ok.diagnostics)


def test_schema_type_aliases_are_not_breaking() -> None:
    left = NormalizedSchema(
        identity="s",
        fields=(NormalizedField(name="id", logical_type="int"),),
    )
    right = NormalizedSchema(
        identity="s",
        fields=(NormalizedField(name="id", logical_type="integer"),),
    )
    changes = diff_normalized_schemas(left, right)
    assert changes.changes == ()


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

    with pytest.raises(ValueError, match="source rows"):
        provider.record(
            SchemaObservation(
                subject_id="bad_preview",
                schema=schema,
                inspector="test",
                metadata={"preview": [{"id": 1}]},
            )
        )

    with pytest.raises(ValueError, match="source rows"):
        provider.record(
            SchemaObservation(
                subject_id="bad_schema_meta",
                schema=NormalizedSchema(
                    identity="s",
                    fields=(NormalizedField(name="id", logical_type="integer"),),
                    metadata={"data": [{"id": 1}]},
                ),
                inspector="test",
            )
        )

    # Poisoned on-disk history must fail closed on load.
    poison = tmp_path / "poisoned.json"
    poison.write_text(
        json.dumps(
            {
                "subject_id": "poisoned",
                "history": [
                    {
                        "subject_id": "poisoned",
                        "inspector": "test",
                        "metadata": {"sample_rows": [{"id": 1}]},
                        "schema": schema.to_dict(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="source rows"):
        FileSchemaHistoryProvider(tmp_path)

    # Corrupt JSON fails closed by default; opt out to skip and load siblings.
    clean = tmp_path / "corrupt_case"
    clean.mkdir()
    corrupt = clean / "corrupt.json"
    corrupt.write_text("{not-json", encoding="utf-8")
    good = clean / "good.json"
    good.write_text(
        json.dumps(
            {
                "subject_id": "good",
                "history": [
                    {
                        "subject_id": "good",
                        "inspector": "test",
                        "metadata": {},
                        "schema": schema.to_dict(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="failing closed"):
        FileSchemaHistoryProvider(clean)
    provider = FileSchemaHistoryProvider(clean, fail_closed=False)
    assert provider.latest("good") is not None


def test_in_memory_schema_history_rejects_rows() -> None:
    from etlantic.schema_policy import InMemorySchemaHistory

    schema = NormalizedSchema(
        identity="s",
        fields=(NormalizedField(name="id", logical_type="integer"),),
    )
    mem = InMemorySchemaHistory()
    with pytest.raises(ValueError, match="source rows"):
        mem.record(
            SchemaObservation(
                subject_id="bad",
                schema=schema,
                inspector="test",
                metadata={"records": [{"id": 1}]},
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
