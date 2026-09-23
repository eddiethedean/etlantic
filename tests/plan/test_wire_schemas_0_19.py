# pyright: reportMissingTypeArgument=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownVariableType=false
"""Validate golden plan/report dicts against packaged JSON Schemas (0.19)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from etlantic import Data, Extract, Load, Pipeline
from etlantic.plan.planner import plan_pipeline

pytest.importorskip("jsonschema")
import jsonschema

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "src" / "etlantic" / "schemas"


class Row(Data):
    id: int


class Sample(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    out: Load[Row] = Load(input=raw, asset="out")


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_sample_plan_matches_pipeline_plan_schema() -> None:
    schema = _load_schema("pipeline-plan.schema.json")
    data = plan_pipeline(Sample, profile="local").to_dict()
    jsonschema.validate(instance=data, schema=schema)


def test_profile_schema_accepts_written_profile() -> None:
    from etlantic.profile import production_profile

    schema = _load_schema("profile.schema.json")
    data = production_profile(
        name="ci-prod",
        plugin_allowlist={"local": None},
        assets={"rows": "json"},
    ).to_dict()
    jsonschema.validate(instance=data, schema=schema)
