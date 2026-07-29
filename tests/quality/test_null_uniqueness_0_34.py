"""Regression tests for portable quality null/uniqueness fixes."""

from __future__ import annotations

from etlantic.quality.evaluate import evaluate_rule, split_by_quality
from etlantic.quality.model import QualityRule, QualityRuleset


def test_membership_fails_closed_on_null() -> None:
    rule = QualityRule(
        kind="membership",
        field="status",
        node={"values": ["a", "b"], "allowed": False},
    )
    assert evaluate_rule(rule, {"status": None}) == "status is null"


def test_uniqueness_skips_null_keys_and_rejected_rows() -> None:
    ruleset = QualityRuleset(
        rules=(
            QualityRule(kind="not_null", field="name", node={}),
            QualityRule(
                kind="uniqueness",
                field="id",
                node={"fields": ["id"]},
            ),
        )
    )
    valid, invalid, _diags = split_by_quality(
        [
            {"id": 1, "name": None},
            {"id": 1, "name": "ok"},
            {"id": None, "name": "a"},
            {"id": None, "name": "b"},
        ],
        ruleset,
    )
    assert {"id": 1, "name": "ok"} in valid
    assert {"id": None, "name": "a"} in valid
    assert {"id": None, "name": "b"} in valid
    assert any(r.get("name") is None and r.get("id") == 1 for r in invalid)
