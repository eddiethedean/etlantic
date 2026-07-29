"""0.33 Moltres native rule coverage."""

from __future__ import annotations

import pytest

from medallantic.diagnostics import MDL132_NATIVE_MOLTRES_RULE
from medallantic.lower import LoweringError, lower_document
from medallantic.moltres_rules import (
    MOLTRES_QUALITY_CAPABILITY,
    split_portable_and_moltres_rules,
)
from medallantic.schema import MedallionDocument, MedallionStep


def test_split_moltres_rules() -> None:
    portable, native = split_portable_and_moltres_rules(
        {
            "email": ["not_null", {"kind": "moltres_expr", "expr_ref": "m:col"}],
            "id": [{"kind": "sqlalchemy_expr", "ref": "m:id_ok"}],
        }
    )
    assert portable == {"email": ["not_null"]}
    assert len(native) == 2
    assert native[0].expr_ref == "m:col"
    assert MOLTRES_QUALITY_CAPABILITY == "quality.moltres_expr"


def test_moltres_rules_fail_closed_on_sql_engine() -> None:
    doc = MedallionDocument(
        name="native_sql",
        engine="sql",
        steps=(
            MedallionStep(
                name="orders",
                layer="bronze",
                kind="bronze_rules",
                rules={"email": [{"kind": "moltres_expr", "expr_ref": "mod:email_ok"}]},
            ),
        ),
    )
    with pytest.raises(LoweringError) as exc:
        lower_document(doc)
    assert any(
        d.code == MDL132_NATIVE_MOLTRES_RULE for d in exc.value.report.diagnostics
    )


def test_moltres_rules_fail_closed_on_local_engine() -> None:
    doc = MedallionDocument(
        name="native_local",
        engine="local",
        steps=(
            MedallionStep(
                name="orders",
                layer="bronze",
                kind="bronze_rules",
                rules={"email": [{"kind": "moltres_expr", "expr_ref": "mod:email_ok"}]},
            ),
        ),
    )
    with pytest.raises(LoweringError) as exc:
        lower_document(doc)
    assert any(
        d.code == MDL132_NATIVE_MOLTRES_RULE for d in exc.value.report.diagnostics
    )
