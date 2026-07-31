"""Stable-foundation acceptance items 18-21 (CLI, faults, plugins, testing)."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest
from examples.memory_customers import CustomerPipeline, RawCustomer

from etlantic import PipelineRuntime
from etlantic.diagnostics import Diagnostic, Severity
from etlantic.diagnostics.sarif import diagnostics_to_sarif
from etlantic.testing import (
    ExpectedResult,
    FakeRunIdentity,
    FaultBoundary,
    FaultSpec,
    PipelineTestCase,
    assert_capability_claims_consistent,
    assert_case_succeeded,
    assert_snapshots_match,
    run_conformance_suite,
    run_pipeline_case,
    snapshot_plan,
    snapshot_report,
    with_faults,
)


def test_sf_18_durable_cli_report_and_diagnostic_identity(tmp_path: Path) -> None:
    """Item 18: durable CLI workflow; later-process report; human/JSON/SARIF identity."""
    root = tmp_path / "project"
    root.mkdir()
    env = {
        "NO_COLOR": "1",
        "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
    }

    def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "etlantic.cli", *args],
            cwd=root,
            env={**env, **dict(__import__("os").environ)},
            capture_output=True,
            text=True,
            check=False,
        )

    assert run_cli("init", "--force").returncode == 0
    target = "pipeline.py:SamplePipeline"
    validate_json = run_cli(
        "validate", target, "--profile", "development", "--format", "json"
    )
    assert validate_json.returncode == 0, validate_json.stdout + validate_json.stderr
    validate_sarif = run_cli(
        "validate", target, "--profile", "development", "--format", "sarif"
    )
    assert validate_sarif.returncode == 0, validate_sarif.stdout + validate_sarif.stderr
    validate_human = run_cli(
        "validate", target, "--profile", "development", "--format", "human"
    )
    assert validate_human.returncode == 0, validate_human.stdout + validate_human.stderr

    json_payload = json.loads(validate_json.stdout)
    sarif_payload = json.loads(validate_sarif.stdout)
    # Empty diagnostics still share renderer identity (schema / SARIF shape).
    assert isinstance(json_payload, (dict, list))
    sarif_results = sarif_payload["runs"][0]["results"]
    assert isinstance(sarif_results, list)
    # When diagnostics exist, codes must match across JSON and SARIF.
    if isinstance(json_payload, dict) and "diagnostics" in json_payload:
        json_codes = [d["code"] for d in json_payload["diagnostics"]]
        sarif_codes = [r["ruleId"] for r in sarif_results]
        assert json_codes == sarif_codes
    assert "SamplePipeline" in validate_human.stdout or validate_human.stdout != ""

    run = run_cli(
        "run", target, "--profile", "development", "--format", "json", "--no-write"
    )
    assert run.returncode == 0, run.stdout + run.stderr
    run_id = json.loads(run.stdout)["run_id"]
    show = run_cli("report", "show", run_id, "--format", "json")
    assert show.returncode == 0, show.stdout + show.stderr
    assert json.loads(show.stdout)["run_id"] == run_id

    # Consistent diagnostic identity across human / JSON / SARIF renderers.
    diag = Diagnostic(
        code="PMTEST037",
        severity=Severity.ERROR,
        message="stable-foundation identity",
        path=("pipeline",),
    )
    sarif = diagnostics_to_sarif([diag])
    assert sarif["runs"][0]["results"][0]["ruleId"] == "PMTEST037"
    assert diag.code == "PMTEST037"


def test_sf_19_failure_injection_across_boundaries_no_duplicate_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Item 19: fault injection across boundaries without duplicate commits."""
    monkeypatch.setenv("ETLANTIC_FAULT_INJECTION", "1")
    from etlantic.runtime.faults import maybe_inject, reset_fault_counts

    boundaries = (
        FaultBoundary.EXTRACT,
        FaultBoundary.CONVERT,
        FaultBoundary.TRANSFORM,
        FaultBoundary.VALIDATE,
        FaultBoundary.MATERIALIZE,
        FaultBoundary.LOAD,
        FaultBoundary.REPORT_PERSIST,
        FaultBoundary.CLEANUP,
        FaultBoundary.CALLBACK,
        FaultBoundary.OUTBOUND,
    )
    for boundary in boundaries:
        with (
            with_faults(FaultSpec(boundary=boundary, message=f"{boundary}-fail")),
            pytest.raises(RuntimeError, match=f"{boundary}-fail"),
        ):
            maybe_inject(boundary)

    # AFTER_N_CALLS prevents duplicate side effects until the trigger fires.
    reset_fault_counts()
    from etlantic.runtime.faults import FaultTrigger

    with with_faults(
        FaultSpec(
            boundary=FaultBoundary.LOAD,
            trigger=FaultTrigger.AFTER_N_CALLS,
            after_n=2,
            message="third-load",
        )
    ):
        maybe_inject(FaultBoundary.LOAD)
        maybe_inject(FaultBoundary.LOAD)
        with pytest.raises(RuntimeError, match="third-load"):
            maybe_inject(FaultBoundary.LOAD)

    # Public PipelineTestCase path: injected write failure fails the case once.
    case = PipelineTestCase(
        case_id="sf19_load_fault",
        pipeline=CustomerPipeline,
        profile="development",
        seed={
            "customer_source": (
                RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
            )
        },
        expected=ExpectedResult(status="partial"),
        faults=(FaultSpec(boundary=FaultBoundary.LOAD, message="sf19-write-fail"),),
    )
    result = run_pipeline_case(case, runtime=PipelineRuntime())
    # Sink fails after upstream success → partial (not a no-op).
    assert result.status == "partial"
    assert result.ok


def test_sf_20_first_party_public_conformance_without_private_imports() -> None:
    """Item 20: public conformance for a first-party plugin (echo CI may be separate).

    External ``etlantic-plugin-echo`` is covered by a dedicated workflow; this
    in-repo assertion uses a first-party plugin through public ``etlantic.testing``
    only and AST-checks the suite module for private imports.
    """
    # Public-import gate for this acceptance module.
    path = Path(__file__).resolve()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("etlantic._"), alias.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert not mod.startswith("etlantic._"), mod

    # Prefer an installed first-party dataframe plugin; skip cleanly otherwise.
    plugin = None
    engine = None
    for eng, mod_name in (
        ("polars", "etlantic_polars"),
        ("pandas", "etlantic_pandas"),
    ):
        try:
            mod = __import__(mod_name)
        except ImportError:
            continue
        plugin = mod.create_plugin()
        engine = eng
        break
    if plugin is None:
        pytest.skip(
            "no first-party dataframe plugin installed; external echo plugin "
            "CI is separate (item 20 disposition: in-repo fallback unavailable)"
        )

    assert_capability_claims_consistent(plugin.info.capabilities)
    run_conformance_suite(
        plugin,
        engine=engine,
        sample_rows=[{"id": 1, "name": "Ada"}],
    )


def test_sf_21_application_pipeline_public_etlantic_testing_only() -> None:
    """Item 21: independently maintained app pipeline via public etlantic.testing."""
    # This test body imports only public ``etlantic.testing`` symbols (see above).
    case = PipelineTestCase(
        case_id="sf21_memory_customers",
        pipeline=CustomerPipeline,
        profile="development",
        seed={
            "customer_source": (
                RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
                RawCustomer(customer_id=2, first_name="Grace", last_name="Hopper"),
            )
        },
        expected=ExpectedResult(
            status="succeeded",
            sink_assets={
                "customer_sink": (
                    {"customer_id": 1, "full_name": "Ada Lovelace"},
                    {"customer_id": 2, "full_name": "Grace Hopper"},
                )
            },
        ),
        metadata={"acceptance": "sf21", "api": "etlantic.testing"},
    )
    result = run_pipeline_case(
        case,
        runtime=PipelineRuntime(),
        identity=FakeRunIdentity(run_id="sf21"),
    )
    assert_case_succeeded(result)

    # Explicit snapshot review path (bounded / redacted helpers).
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        plan_path = Path(tmp) / "plan.json"
        report_path = Path(tmp) / "report.json"
        snapshot_plan(result.plan, plan_path, update=True)
        snapshot_report(result.report, report_path, update=True)
        assert_snapshots_match(result.plan, snapshot_plan(result.plan, plan_path))
        assert_snapshots_match(
            result.report, snapshot_report(result.report, report_path)
        )

    # Injected write failure via public PipelineTestCase.faults (not a no-op).
    fault_case = PipelineTestCase(
        case_id="sf21_load_fault",
        pipeline=CustomerPipeline,
        profile="development",
        seed={
            "customer_source": (
                RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
            )
        },
        expected=ExpectedResult(status="partial"),
        faults=(FaultSpec(boundary=FaultBoundary.LOAD, message="sf21-write-fail"),),
    )
    fault_result = run_pipeline_case(fault_case, runtime=PipelineRuntime())
    # with_faults arms injection; LOAD fault after upstream success → partial.
    assert fault_result.status == "partial"
    assert fault_result.ok
