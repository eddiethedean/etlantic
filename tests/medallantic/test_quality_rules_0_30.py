"""Medallantic portable rules (0.30 / M2)."""

from __future__ import annotations

import pytest

pytest.importorskip("medallantic")

from etlantic.quality.evaluate import split_by_quality
from etlantic.reports.model import ValidationResult
from medallantic import MedallionBuilder
from medallantic.diagnostics import MDL110_RULES_UNENFORCED
from medallantic.reports import evaluate_accept_rates
from medallantic.rules import RuleDSLError, parse_rules_shorthand

pytestmark = pytest.mark.medallantic


def test_parse_not_null_shorthand() -> None:
    ruleset = parse_rules_shorthand({"order_id": ["not_null"]})
    assert len(ruleset.rules) == 1
    assert ruleset.rules[0].kind == "not_null"
    valid, invalid, _ = split_by_quality([{"order_id": 1}, {"order_id": None}], ruleset)
    assert len(valid) == 1
    assert len(invalid) == 1


def test_unknown_shorthand_fails() -> None:
    with pytest.raises(RuleDSLError):
        parse_rules_shorthand({"x": ["spark_column_expr"]})


def test_bronze_rules_lower_to_quality_gate() -> None:
    result = (
        MedallionBuilder("demo", schema="s")
        .bronze("orders", asset="bronze_orders", rules={"id": ["not_null"]})
        .silver("clean", source="orders", asset="silver_orders", write_mode="overwrite")
        .lower()
    )
    codes = {d.code for d in result.diagnostics}
    assert MDL110_RULES_UNENFORCED not in codes
    names = [n.name for n in result.pipeline_cls.inspect().nodes]
    assert "orders__ingest" in names
    assert "orders" in names
    assert "orders__rejected" in names
    # Gate step carries quality expression metadata
    gate_node = next(
        n for n in result.pipeline_cls.inspect().nodes if n.name == "orders"
    )
    assert "etlantic.quality" in dict(gate_node.metadata)


def test_invalid_length_shorthand_is_mdl110() -> None:
    with pytest.raises(RuleDSLError):
        parse_rules_shorthand({"name": ["length:a:b"]})
    from medallantic import MedallionBuilder
    from medallantic.diagnostics import MDL110_RULES_INVALID
    from medallantic.lower import LoweringError

    with pytest.raises(LoweringError) as exc:
        (
            MedallionBuilder("demo", schema="s")
            .bronze("orders", asset="b", rules={"name": ["length:a:b"]})
            .lower()
        )
    assert any(d.code == MDL110_RULES_INVALID for d in exc.value.report.diagnostics)


def test_accept_rate_threshold_findings() -> None:
    findings = evaluate_accept_rates(
        policy_metadata={"min_accept_rate_ingest": 90.0},
        validations=[
            ValidationResult(
                node_name="orders",
                boundary="quality_gate",
                status="rejected",
                records_checked=10,
                records_invalid=3,
            )
        ],
        layer="bronze",
    )
    assert len(findings) == 1
    assert findings[0]["accept_rate"] == 70.0
