"""Public import smoke for etlantic.transform."""

from __future__ import annotations


def test_public_imports() -> None:
    from etlantic.transform import PLAN_PROTOCOL, ColumnExpr, FrameExpr, Window
    from etlantic.transform import functions as F

    assert callable(F.col)
    assert Window.currentRow == "currentRow"
    assert PLAN_PROTOCOL == "dtcs.transform-plan/2"
    assert FrameExpr is not None
    assert ColumnExpr is not None
