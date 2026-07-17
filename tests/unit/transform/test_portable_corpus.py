"""Per-profile golden corpus and negative-budget tests (0.11 W5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from etlantic import Data, Input, Output, Transformation
from etlantic.exceptions import ModelDefinitionError
from etlantic.transform import Window
from etlantic.transform import functions as F
from etlantic.transform.dtcs_builder import invoke_portable
from etlantic.transform.lambda_expr import lambda_
from etlantic.transform.protocol import (
    PROFILE_COMPLEX_VALUES,
    PROFILE_CONVERSION,
    PROFILE_NONDETERMINISTIC,
    PROFILE_RELATIONAL_EXTENDED,
    PROFILE_RESHAPE,
    PROFILE_STATISTICS,
    PROFILE_STRING_ADVANCED,
    PROFILE_TEMPORAL_IANA,
    PROFILE_WINDOW_V2,
    RELATIONAL_PROFILE_V1,
    TransformBudgets,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "portable"


class Row(Data):
    id: int
    name: str
    value: float
    ts: str
    tags: str


class Out(Data):
    id: int
    name: str


def _write_or_check(name: str, payload: dict) -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    path = FIXTURES / name
    if not path.exists():
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert payload == expected


def test_profile_family_goldens() -> None:
    class StringT(Transformation):
        rows: Input[Row]
        result: Output[Out]

    @StringT.portable
    def string_def(rows):
        return rows.withColumn(
            "name", F.trim(F.regexp_replace(F.col("name"), F.lit("a"), F.lit("b")))
        ).select("id", "name")

    class ConvT(Transformation):
        rows: Input[Row]
        result: Output[Out]

    @ConvT.portable
    def conv_def(rows):
        return rows.withColumn("name", F.to_string(F.col("id"))).select("id", "name")

    class StatT(Transformation):
        rows: Input[Row]
        result: Output[Out]

    @StatT.portable
    def stat_def(rows):
        return rows.groupBy("name").agg(total=F.variance(F.col("value")).alias("name"))

    class ComplexT(Transformation):
        rows: Input[Row]
        result: Output[Out]

    @ComplexT.portable
    def complex_def(rows):
        _ = lambda_("x", body=lambda x: x > F.lit(0))
        return rows.withColumn("name", F.to_string(F.size(F.array(F.lit(1))))).select(
            "id", "name"
        )

    class ReshapeT(Transformation):
        rows: Input[Row]
        result: Output[Out]

    @ReshapeT.portable
    def reshape_def(rows):
        return rows.explode("tags").select("id", "name")

    class ExtT(Transformation):
        a: Input[Row]
        b: Input[Row]
        result: Output[Out]

    @ExtT.portable
    def ext_def(a, b):
        return a.intersect(b).select("id", "name")

    class TempT(Transformation):
        rows: Input[Row]
        result: Output[Out]

    @TempT.portable
    def temp_def(rows):
        return rows.withColumn(
            "name", F.to_string(F.at_iana_timezone(F.col("ts"), F.lit("UTC")))
        ).select("id", "name")

    class NondetT(Transformation):
        rows: Input[Row]
        result: Output[Out]

    @NondetT.portable
    def nondet_def(rows):
        return rows.withColumn("name", F.to_string(F.uuid())).select("id", "name")

    class WinT(Transformation):
        rows: Input[Row]
        result: Output[Out]

    @WinT.portable
    def win_def(rows):
        w = Window.partitionBy("id").orderBy(F.col("ts").asc())
        return rows.withColumn("name", F.to_string(F.ntile(4).over(w))).select(
            "id", "name"
        )

    cases = [
        ("string_advanced.json", {PROFILE_STRING_ADVANCED}, StringT),
        ("conversion.json", {PROFILE_CONVERSION}, ConvT),
        ("statistics.json", {PROFILE_STATISTICS, RELATIONAL_PROFILE_V1}, StatT),
        ("complex_values.json", {PROFILE_COMPLEX_VALUES}, ComplexT),
        ("reshape.json", {PROFILE_RESHAPE}, ReshapeT),
        ("relational_extended.json", {PROFILE_RELATIONAL_EXTENDED}, ExtT),
        ("temporal_iana.json", {PROFILE_TEMPORAL_IANA}, TempT),
        ("nondeterministic.json", {PROFILE_NONDETERMINISTIC}, NondetT),
        ("window_v2.json", {PROFILE_WINDOW_V2}, WinT),
    ]

    for filename, profiles, cls in cases:
        defn = cls.portable_definition()
        assert defn is not None
        assert profiles <= set(defn.requirements["profiles"])
        payload = {
            "actions": sorted(defn.requirements["actions"]),
            "fingerprint": defn.fingerprint,
            "functions": sorted(defn.requirements["functions"]),
            "planIdentity": defn.plan["planIdentity"],
            "profiles": sorted(profiles),
        }
        _write_or_check(filename, payload)


def test_hostile_depth_budget() -> None:
    class T(Transformation):
        rows: Input[Row]
        result: Output[Out]

    expr = F.col("id")
    for _ in range(40):
        expr = expr + 1

    def define(rows):
        return rows.withColumn("name", F.to_string(expr)).select("id", "name")

    ok = invoke_portable(T, define)
    assert ok.fingerprint

    with pytest.raises(ModelDefinitionError):
        invoke_portable(T, define, budgets=TransformBudgets(max_depth=5))
