"""Rich Portable Analytics authoring tests (0.11 W3)."""

from __future__ import annotations

import pytest

from etlantic import Data, Input, Output, Transformation
from etlantic.exceptions import ModelDefinitionError
from etlantic.transform import Window
from etlantic.transform import functions as F
from etlantic.transform.lambda_expr import exists, lambda_
from etlantic.transform.protocol import (
    PROFILE_COMPLEX_VALUES,
    PROFILE_NONDETERMINISTIC,
    PROFILE_STRING_ADVANCED,
    PROFILE_WINDOW_V2,
)


class Row(Data):
    id: int
    name: str
    tags: str
    created_at: str


class Out(Data):
    id: int
    name: str
    rank: int


class Advanced(Transformation):
    rows: Input[Row]
    result: Output[Out]


@Advanced.portable
def _advanced(rows):
    w = Window.partitionBy("id").orderBy(F.col("created_at").desc_nulls_last())
    return (
        rows.withColumn("name", F.trim(F.col("name")))
        .withColumn("rank", F.row_number().over(w))
        .withColumn("noise", F.rand(1))
        .select("id", "name", "rank")
    )


def test_rich_profiles_emitted() -> None:
    defn = Advanced.portable_definition()
    assert defn is not None
    profiles = set(defn.requirements["profiles"])
    assert PROFILE_STRING_ADVANCED in profiles
    assert PROFILE_WINDOW_V2 in profiles or "dtcs:profile/portable-window/1" in profiles
    assert PROFILE_NONDETERMINISTIC in profiles
    assert "dtcs:trim" in defn.requirements["functions"]


def test_lambda_and_complex() -> None:
    class T(Transformation):
        rows: Input[Row]
        result: Output[Out]

    @T.portable
    def define(rows):
        pred = lambda_("element", body=lambda element: element > F.lit(0))
        flag = exists(F.array(F.lit(1), F.lit(2)), pred)
        return (
            rows.withColumn("name", F.lower(F.col("name")))
            .withColumn("id", F.when(flag, F.col("id")).otherwise(F.lit(0)))
            .select("id", "name")
        )

    defn = T.portable_definition()
    assert PROFILE_COMPLEX_VALUES in defn.requirements["profiles"]


def test_lambda_rejects_outer_capture() -> None:
    with pytest.raises(ModelDefinitionError):
        lambda_("element", body=F.col("name") > 0)


def test_explode_reshape() -> None:
    class T(Transformation):
        rows: Input[Row]
        result: Output[Out]

    @T.portable
    def define(rows):
        return rows.explode("tags").select("id", "name")

    assert (
        "dtcs:profile/portable-reshape/1"
        in T.portable_definition().requirements["profiles"]
    )
