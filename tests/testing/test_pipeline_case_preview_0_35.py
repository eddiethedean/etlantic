"""Application-pipeline testing preview (0.35) — public-import examples."""

from __future__ import annotations

from pathlib import Path

import pytest

# Public example pipeline (same surface adopters use).
from examples.memory_customers import CustomerPipeline, RawCustomer

from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.testing import (
    ExpectedResult,
    FakeClock,
    FakeRunIdentity,
    FakeSecretProvider,
    PipelineTestCase,
    assert_case_succeeded,
    assert_snapshots_match,
    run_pipeline_case,
    snapshot_plan,
    snapshot_report,
)


def _succeeding_case() -> PipelineTestCase:
    return PipelineTestCase(
        case_id="memory_customers_ok",
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
        metadata={"preview": True},
    )


def _failing_case() -> PipelineTestCase:
    # Empty seed → extract succeeds with zero rows but sink expectation fails.
    return PipelineTestCase(
        case_id="memory_customers_empty_sink_mismatch",
        pipeline=CustomerPipeline,
        profile="development",
        seed={"customer_source": ()},
        expected=ExpectedResult(
            status="succeeded",
            sink_assets={
                "customer_sink": ({"customer_id": 1, "full_name": "Ada Lovelace"},)
            },
        ),
    )


def test_succeeding_pipeline_case() -> None:
    result = run_pipeline_case(
        _succeeding_case(),
        runtime=PipelineRuntime(),
        identity=FakeRunIdentity(run_id="preview-run"),
    )
    assert_case_succeeded(result)
    assert result.plan
    assert "password" not in str(result.to_dict()).lower()


def test_failing_pipeline_case_documents_mismatch() -> None:
    result = run_pipeline_case(_failing_case(), runtime=PipelineRuntime())
    assert not result.ok
    assert any("customer_sink" in err for err in result.errors)


def test_snapshots_require_explicit_update(tmp_path: Path) -> None:
    result = run_pipeline_case(_succeeding_case(), runtime=PipelineRuntime())
    plan_path = tmp_path / "plan.json"
    report_path = tmp_path / "report.json"
    with pytest.raises(FileNotFoundError):
        snapshot_plan(result.plan, plan_path, update=False)
    snapshot_plan(result.plan, plan_path, update=True)
    loaded = snapshot_plan(result.plan, plan_path, update=False)
    assert_snapshots_match(result.plan, loaded)
    snapshot_report(result.report, report_path, update=True)
    loaded_report = snapshot_report(result.report, report_path, update=False)
    assert_snapshots_match(result.report, loaded_report)
    text = plan_path.read_text(encoding="utf-8").lower()
    assert "password" not in text
    assert "secret" not in text or "secret_providers" in text


def test_fakes_are_deterministic() -> None:
    clock = FakeClock()
    assert clock.now() == clock.now()
    identity = FakeRunIdentity(run_id="fixed")
    assert identity.next_run_id() == "fixed"
    provider = FakeSecretProvider({"demo": "fixture-only"})
    assert provider.descriptor.name == "fake"


def test_public_imports_only() -> None:
    # This module itself uses only public etlantic.* and examples.* imports.
    import etlantic.testing as testing

    assert hasattr(testing, "PipelineTestCase")
    assert hasattr(testing, "run_pipeline_case")
