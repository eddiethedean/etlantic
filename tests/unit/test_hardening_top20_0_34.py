"""Regression tests for top-20 0.34 fail-closed hardening fixes."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from etlantic.cli import exit_codes as ec
from etlantic.diagnostics import Diagnostic, Severity
from etlantic.exceptions import PipelineExecutionError
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.plugin_trust import (
    filter_plugins_by_allowlist,
    is_non_blocking_trust_diagnostic,
)
from etlantic.profile import Profile, production_profile
from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.incremental import FileStateStore
from etlantic.runtime.state import RunStatus
from etlantic.schema_drift import NormalizedField, NormalizedSchema
from etlantic.schema_history import FileSchemaHistoryProvider
from etlantic.secrets import SecretRef


def test_is_non_blocking_trust_diagnostic_phase_aware() -> None:
    assert is_non_blocking_trust_diagnostic(
        Diagnostic(
            code="PMPLUG402",
            severity=Severity.ERROR,
            message="sibling",
            phase="plugin_discovery",
        )
    )
    assert not is_non_blocking_trust_diagnostic(
        Diagnostic(
            code="PMPLUG402",
            severity=Severity.ERROR,
            message="selected",
            phase="plugin_authorize",
        )
    )
    assert not is_non_blocking_trust_diagnostic(
        Diagnostic(
            code="PMPLUG402",
            severity=Severity.ERROR,
            message="selected",
            phase="plugin_trust",
        )
    )


def test_manual_local_spoof_denied_under_production() -> None:
    class _Info:
        name = "local"
        version = "0.0.0"
        engine = "local"
        protocol_version = "1"
        capabilities = None

    class _Plugin:
        info = _Info()

    runtime = PipelineRuntime()
    profile = production_profile(plugin_allowlist={"etlantic-polars": "==0.35.0"})
    runtime.ensure_plugins_for_profile(profile)
    with pytest.raises(PipelineExecutionError) as exc:
        runtime.register_dataframe_plugin("local", _Plugin())
    assert exc.value.code in {"PMPLUG402", "PMPLUG401"}


def test_observability_register_gated_under_production() -> None:
    class _Provider:
        name = "evil-obs"
        version = "1.0.0"

    runtime = PipelineRuntime()
    profile = production_profile(plugin_allowlist={"etlantic-polars": "==0.35.0"})
    runtime.ensure_plugins_for_profile(profile)
    with pytest.raises(PipelineExecutionError) as exc:
        runtime.register_observability_provider("evil-obs", _Provider())
    assert exc.value.code in {"PMPLUG402", "PMPLUG401"}


def test_builtin_exempt_disabled_for_manual_filter() -> None:
    from etlantic.registry import PluginDescriptor

    profile = production_profile(plugin_allowlist={"etlantic-polars": "==0.35.0"})
    local = PluginDescriptor(
        name="local", kind="runtime", version="0.35.0", engine="local"
    )
    kept_open, _ = filter_plugins_by_allowlist({"local": local}, profile)
    assert "local" in kept_open
    kept_closed, diags = filter_plugins_by_allowlist(
        {"local": local}, profile, allow_builtin_exempt=False
    )
    assert "local" not in kept_closed
    assert any(d.code == "PMPLUG402" for d in diags)


def test_profile_rejects_plaintext_secrets() -> None:
    with pytest.raises(ValueError, match="SecretRef"):
        Profile(name="dev", secrets={"db": "super-secret"})  # type: ignore[arg-type]


def test_profile_to_dict_requires_secret_ref() -> None:
    profile = Profile(
        name="dev",
        secrets={"db": SecretRef(provider="env", name="db", key="DB_URL")},
    )
    data = profile.to_dict()
    assert data["secrets"]["db"]["provider"] == "env"
    assert "value" not in data["secrets"]["db"]


def test_report_metadata_rejects_secret_keys() -> None:
    with pytest.raises(ValueError, match="secret-like key"):
        PipelineRunReport.from_dict(
            {
                "schema": "etlantic.run_report/1",
                "pipeline_id": "p",
                "plan_id": "plan",
                "run_id": "run",
                "intent": "standard",
                "profile": "dev",
                "status": "succeeded",
                "started_at": datetime.now(UTC).isoformat(),
                "summary": {},
                "metadata": {"password": "hunter2"},
            }
        )


def test_file_state_store_fail_closed_on_corrupt(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{not-json", encoding="utf-8")
    store = FileStateStore(path)
    with pytest.raises(RuntimeError, match="failing closed"):
        store.get("subject")


def test_schema_history_fingerprint_mismatch_fail_closed(tmp_path: Path) -> None:
    schema = NormalizedSchema(
        identity="t",
        fields=(NormalizedField(name="a", logical_type="string"),),
    )
    path = tmp_path / "s1.json"
    path.write_text(
        json.dumps(
            {
                "subject_id": "s1",
                "history": [
                    {
                        "subject_id": "s1",
                        "fingerprint": "tampered-fingerprint",
                        "inspector": "file",
                        "observed_at": None,
                        "metadata": {},
                        "schema": schema.to_dict(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="failing closed"):
        FileSchemaHistoryProvider(tmp_path, fail_closed=True)


def test_run_maps_pmplug402_to_trust_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Raised PMPLUG402 maps to TRUST_FAILURE via the CLI run command."""
    from typer.testing import CliRunner

    import etlantic.cli.globals as globals_mod
    from etlantic.cli import app
    from etlantic.cli.context import CliContext

    class _BoomPipeline:
        @classmethod
        def run(cls, **_kwargs: object) -> object:
            raise PipelineExecutionError("plugin denied", code="PMPLUG402")

    monkeypatch.setattr(globals_mod, "load_target", lambda target: _BoomPipeline)
    monkeypatch.setattr(
        CliContext,
        "ensure_plugins",
        lambda self, profile, **kwargs: [],
    )
    runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb"})
    result = runner.invoke(
        app,
        ["run", "dummy:Boom", "--profile", "development", "--format", "text"],
    )
    assert result.exit_code == ec.TRUST_FAILURE, result.stdout + result.stderr


def test_medallion_validation_and_step_status_fail_closed() -> None:
    from medallantic.reports import adapt_run_result

    report = adapt_run_result(
        {
            "status": "succeeded",
            "steps": [{"name": "a", "status": "failed"}],
            "validations": [{"node_name": "a", "boundary": "quality_gate"}],
            "artifacts": [{"identity": "t1"}],
        }
    )
    assert report.status is not RunStatus.SUCCEEDED
    assert any(v.status == "failed" for v in report.validations)
    assert any(a.status == "unknown" for a in report.artifacts)
    assert any(d.code == "PMSF500" for d in report.diagnostics)


def test_empty_write_mode_rejected() -> None:
    from medallantic.compat import write_mode_from_sparkforge

    with pytest.raises(ValueError, match="required"):
        write_mode_from_sparkforge(None)
    with pytest.raises(ValueError, match="required"):
        write_mode_from_sparkforge("")


def test_delta_merge_keys_validated() -> None:
    pytest.importorskip("etlantic_pyspark")
    from etlantic_pyspark.plugin import PySparkPlugin

    plugin = PySparkPlugin()
    diags = plugin._delta_merge(object(), "/tmp/x", ("id OR 1=1",))
    assert any(d.get("code") == "PMDELTA308" for d in diags)


def test_sql_exception_messages_redacted() -> None:
    from etlantic.runtime.logging import redact_message

    msg = redact_message(
        "could not connect to postgresql://user:hunter2@db.example/app"
    )
    assert "hunter2" not in msg
    assert "***" in msg
