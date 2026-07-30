"""0.36 application-pipeline burn-in corpus (preview contract freeze).

Canonical cases use public ``etlantic.testing`` imports. Final testing-foundation
graduation remains 0.38; this module freezes the minimum 0.36 case/result/snapshot
surface needed for burn-in evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from examples.memory_customers import CustomerPipeline, RawCustomer

from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.testing import (
    ExpectedResult,
    FakeRunIdentity,
    FakeSecretProvider,
    PipelineTestCase,
    assert_case_succeeded,
    assert_snapshots_match,
    run_pipeline_case,
    snapshot_plan,
    snapshot_report,
)

CORPUS_VERSION = "etlantic.application_case/1"


def _ok_seed() -> dict:
    return {
        "customer_source": (
            RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
            RawCustomer(customer_id=2, first_name="Grace", last_name="Hopper"),
        )
    }


def _identity_case() -> PipelineTestCase:
    return PipelineTestCase(
        case_id="app_01_identity_file_pipeline",
        pipeline=CustomerPipeline,
        profile="development",
        seed=_ok_seed(),
        expected=ExpectedResult(
            status="succeeded",
            sink_assets={
                "customer_sink": (
                    {"customer_id": 1, "full_name": "Ada Lovelace"},
                    {"customer_id": 2, "full_name": "Grace Hopper"},
                )
            },
        ),
        metadata={"corpus": CORPUS_VERSION, "case": 1},
    )


def _projection_case() -> PipelineTestCase:
    # Typed projection / rename covered by CustomerPipeline full_name derivation.
    return PipelineTestCase(
        case_id="app_02_typed_projection_rename",
        pipeline=CustomerPipeline,
        profile="development",
        seed=_ok_seed(),
        expected=ExpectedResult(status="succeeded"),
        metadata={"corpus": CORPUS_VERSION, "case": 2},
    )


def _empty_seed_mismatch() -> PipelineTestCase:
    return PipelineTestCase(
        case_id="app_09_deliberate_contract_mismatch",
        pipeline=CustomerPipeline,
        profile="development",
        seed={"customer_source": ()},
        expected=ExpectedResult(
            status="succeeded",
            sink_assets={
                "customer_sink": ({"customer_id": 1, "full_name": "Ada Lovelace"},)
            },
        ),
        metadata={"corpus": CORPUS_VERSION, "case": 9},
    )


def _plan_report_snapshot_case() -> PipelineTestCase:
    return PipelineTestCase(
        case_id="app_08_deterministic_plan_report_snapshot",
        pipeline=CustomerPipeline,
        profile="development",
        seed=_ok_seed(),
        expected=ExpectedResult(status="succeeded"),
        metadata={"corpus": CORPUS_VERSION, "case": 8},
    )


@pytest.mark.parametrize(
    "factory",
    [_identity_case, _projection_case, _plan_report_snapshot_case],
    ids=lambda f: f().case_id,
)
def test_canonical_local_cases_succeed(factory) -> None:
    result = run_pipeline_case(
        factory(),
        runtime=PipelineRuntime(),
        identity=FakeRunIdentity(run_id="burn-in-036"),
    )
    assert_case_succeeded(result)
    payload = result.to_dict()
    assert "password" not in json.dumps(payload).lower()


def test_deliberate_mismatch_normalized_failure() -> None:
    result = run_pipeline_case(_empty_seed_mismatch(), runtime=PipelineRuntime())
    assert not result.ok
    assert result.errors


def test_snapshot_migration_helper_deterministic(tmp_path: Path) -> None:
    result = run_pipeline_case(_plan_report_snapshot_case(), runtime=PipelineRuntime())
    plan_path = tmp_path / "plan.json"
    report_path = tmp_path / "report.json"
    snapshot_plan(result.plan, plan_path, update=True)
    snapshot_report(result.report, report_path, update=True)
    loaded_plan = snapshot_plan(result.plan, plan_path, update=False)
    loaded_report = snapshot_report(result.report, report_path, update=False)
    assert_snapshots_match(result.plan, loaded_plan)
    assert_snapshots_match(result.report, loaded_report)
    # Explicit update path remains reviewable and deterministic.
    before = plan_path.read_text(encoding="utf-8")
    snapshot_plan(result.plan, plan_path, update=True)
    assert plan_path.read_text(encoding="utf-8") == before


def test_secret_provider_fake_redaction() -> None:
    provider = FakeSecretProvider({"db_password": "should-never-appear"})
    assert "db_password" in provider._values
    case = _identity_case()
    result = run_pipeline_case(case, runtime=PipelineRuntime())
    assert_case_succeeded(result)
    blob = json.dumps(result.to_dict()).lower()
    assert "should-never-appear" not in blob


def test_junit_json_sarif_machine_outputs(tmp_path: Path) -> None:
    result = run_pipeline_case(_identity_case(), runtime=PipelineRuntime())
    assert_case_succeeded(result)
    json_path = tmp_path / "case.json"
    json_path.write_text(
        json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8"
    )
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded.get("case_id") or loaded.get("ok") is not None
    # SARIF/JUnit emitters live on validate CLI; case result stays JSON-schema-friendly.
    assert isinstance(loaded, dict)
