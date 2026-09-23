# pyright: reportMissingTypeArgument=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownVariableType=false
"""Schema version gates for PipelinePlan (0.19)."""

from __future__ import annotations

import pytest

from etlantic import Data, Extract, Load, Pipeline
from etlantic.plan.model import PLAN_SCHEMA, PipelinePlan
from etlantic.plan.planner import plan_pipeline
from etlantic.plan.upgrade import UnsupportedPlanSchemaError, upgrade_plan_dict


class Row(Data):
    id: int


class Sample(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    out: Load[Row] = Load(input=raw, asset="out")


def _sample_plan_dict() -> dict:
    return plan_pipeline(Sample, profile="local").to_dict()


def test_missing_plan_schema_rejected() -> None:
    data = _sample_plan_dict()
    del data["schema"]
    with pytest.raises(ValueError, match="missing required 'schema'"):
        PipelinePlan.from_dict(data)


def test_unknown_plan_schema_rejected() -> None:
    data = _sample_plan_dict()
    data["schema"] = "etlantic.plan/999"
    with pytest.raises(ValueError, match="Unsupported PipelinePlan schema"):
        PipelinePlan.from_dict(data)


def test_upgrade_plan_dict_accepts_current_schema() -> None:
    data = _sample_plan_dict()
    upgraded = upgrade_plan_dict(data)
    assert upgraded["schema"] == PLAN_SCHEMA


def test_upgrade_plan_dict_rejects_unknown() -> None:
    with pytest.raises(UnsupportedPlanSchemaError, match="Unsupported"):
        upgrade_plan_dict({"schema": "etlantic.plan/0", "plan_id": "x"})


def test_current_plan_schema_round_trip() -> None:
    data = _sample_plan_dict()
    assert data["schema"] == PLAN_SCHEMA
    restored = PipelinePlan.from_dict(data)
    assert restored.schema == PLAN_SCHEMA
