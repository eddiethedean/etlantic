"""Medallantic 0.31 transform_ref + lifecycle tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from etlantic.reliability import WriteMode
from etlantic.reports.model import PipelineRunReport, ValidationResult
from etlantic.runtime.request import RunIntent
from etlantic.runtime.state import RunStatus
from medallantic.callables import (
    make_callable_transformation,
    resolve_transform_callable,
)
from medallantic.lifecycle import (
    default_write_mode_for_layer,
    lifecycle_policy_for_layer,
)
from medallantic.lower import MedallionRow, lower_document
from medallantic.reports import enforce_accept_rates, evaluate_accept_rates
from medallantic.schema import MedallionDocument, MedallionStep


def _double_rows(rows: list[Any]) -> list[Any]:
    out = []
    for row in rows:
        data = (
            dict(row) if isinstance(row, dict) else dict(getattr(row, "__dict__", {}))
        )
        data["qty"] = int(data.get("qty") or 0) * 2
        out.append(data)
    return out


def test_resolve_transform_callable_module_attr() -> None:
    fn = resolve_transform_callable(
        "tests.medallantic.test_lifecycle_0_31:_double_rows"
    )
    assert callable(fn)
    assert fn.__name__ == "_double_rows"
    assert fn([{"qty": 2}])[0]["qty"] == 4


def test_make_callable_transformation_executes() -> None:
    cls = make_callable_transformation(
        "double",
        transform_ref="tests.medallantic.test_lifecycle_0_31:_double_rows",
        row_type=MedallionRow,
    )
    impl = cls.implementations()["local"].callable
    result = impl([{"qty": 3}])
    assert result[0]["qty"] == 6


def test_lower_transform_ref_no_mdl111_when_resolvable() -> None:
    doc = MedallionDocument(
        name="callable_demo",
        steps=(
            MedallionStep(
                name="raw",
                layer="bronze",
                kind="bronze_rules",
                asset="raw_orders",
            ),
            MedallionStep(
                name="clean",
                layer="silver",
                kind="silver_transform",
                source="raw",
                asset="clean_orders",
                transform_ref="tests.medallantic.test_lifecycle_0_31:_double_rows",
                write_mode="overwrite",
            ),
        ),
    )
    result = lower_document(doc)
    assert not any(d.code == "MDL111" for d in result.diagnostics)
    assert "clean" in result.step_map


def test_layer_defaults() -> None:
    assert default_write_mode_for_layer("bronze") is WriteMode.APPEND
    assert default_write_mode_for_layer("silver") is WriteMode.OVERWRITE
    policy = lifecycle_policy_for_layer(subject_id="g", layer="gold")
    assert policy.default_action.value == "publish"


def test_enforce_accept_rates_fails_report() -> None:
    report = PipelineRunReport(
        pipeline_id="p",
        plan_id="plan",
        run_id="run",
        intent=RunIntent.STANDARD,
        profile="development",
        status=RunStatus.SUCCEEDED,
        started_at=datetime.now(UTC),
        validations=(
            ValidationResult(
                node_name="clean",
                boundary="output",
                status="ok",
                records_checked=100,
                records_invalid=20,
            ),
        ),
    )
    findings = evaluate_accept_rates(
        policy_metadata={"min_accept_rate_clean": 95.0},
        validations=list(report.validations),
        layer="silver",
    )
    assert findings
    failed = enforce_accept_rates(
        report,
        policy_metadata={"min_accept_rate_clean": 95.0},
        layer_by_node={"clean": "silver"},
    )
    assert failed.status is RunStatus.FAILED
    assert any(d.code == "MDL120" for d in failed.diagnostics)
