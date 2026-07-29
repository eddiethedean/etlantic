"""0.32 PySpark Column rules + callable transform coverage."""

from __future__ import annotations

import pytest

from medallantic.builder import MedallionBuilder
from medallantic.callables import make_callable_transformation
from medallantic.column_rules import (
    NATIVE_QUALITY_CAPABILITY,
    split_portable_and_native_rules,
)
from medallantic.diagnostics import MDL130_NATIVE_COLUMN_RULE
from medallantic.lower import LoweringError, MedallionRow, lower_document
from medallantic.schema import MedallionDocument, MedallionStep


def _double_rows(rows: list[object]) -> list[object]:
    out = []
    for row in rows:
        data = dict(row) if not hasattr(row, "model_dump") else row.model_dump()
        data = {**data, "qty": int(data.get("qty", 0)) * 2}
        out.append(data)
    return out


def _double_df(df: object) -> object:
    if hasattr(df, "withColumn") and hasattr(df, "schema"):
        from pyspark.sql import functions as F

        return df.withColumn("qty", F.col("qty") * 2)
    return _double_rows(list(df))  # type: ignore[arg-type]


def test_split_native_column_rules() -> None:
    portable, native = split_portable_and_native_rules(
        {
            "email": ["not_null", {"kind": "pyspark_column", "expr_ref": "m:col"}],
            "id": [{"kind": "spark_column", "ref": "m:id_ok"}],
        }
    )
    assert portable == {"email": ["not_null"]}
    assert len(native) == 2
    assert native[0].expr_ref == "m:col"
    assert NATIVE_QUALITY_CAPABILITY == "quality.pyspark_column"


def test_builder_silver_gold_accept_rules() -> None:
    doc = (
        MedallionBuilder("demo")
        .bronze("orders", rules={"id": ["not_null"]})
        .silver(
            "clean",
            source="orders",
            rules={"id": [{"kind": "pyspark_column", "expr_ref": "mod:ok"}]},
        )
        .gold("kpis", source="clean", rules={"id": ["not_null"]})
        .to_document()
    )
    assert doc.steps[1].rules
    assert doc.steps[2].rules


def test_native_rules_fail_closed_on_local_engine() -> None:
    doc = MedallionDocument(
        name="native",
        engine="local",
        steps=(
            MedallionStep(
                name="orders",
                layer="bronze",
                kind="bronze_rules",
                rules={
                    "email": [
                        {"kind": "pyspark_column", "expr_ref": "mod:email_ok"}
                    ]
                },
            ),
        ),
    )
    with pytest.raises(LoweringError) as exc:
        lower_document(doc)
    assert any(d.code == MDL130_NATIVE_COLUMN_RULE for d in exc.value.report.diagnostics)


def test_native_rules_allowed_on_pyspark_engine() -> None:
    doc = MedallionDocument(
        name="native_spark",
        engine="pyspark",
        steps=(
            MedallionStep(
                name="orders",
                layer="bronze",
                kind="bronze_rules",
                asset="orders",
                rules={
                    "email": [
                        {"kind": "pyspark_column", "expr_ref": "mod:email_ok"}
                    ]
                },
            ),
        ),
    )
    result = lower_document(doc)
    assert result.pipeline_cls is not None
    assert "orders" in result.step_map
    assert result.diagnostics == () or all(
        d.code != MDL130_NATIVE_COLUMN_RULE for d in result.diagnostics
    )


def test_pyspark_callable_invokes_df_transform() -> None:
    pytest.importorskip("sparkless")
    from etlantic_pyspark.sparkless_shim import install

    install()
    from pyspark.sql import SparkSession

    transform_cls = make_callable_transformation(
        "double",
        transform_ref="tests.medallantic.test_column_rules_0_32:_double_df",
        fn=_double_df,
        row_type=MedallionRow,
    )
    impl = transform_cls.__implementations__["pyspark"].callable
    spark = SparkSession.builder.master("local[1]").appName("t").getOrCreate()
    try:
        df = spark.createDataFrame([{"id": 1, "qty": 2}])
        out = impl(df)
        rows = [r.asDict() for r in out.collect()]
        assert rows[0]["qty"] == 4
    finally:
        spark.stop()
