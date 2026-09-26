"""Inference parity fixtures for the phase 0.55 differential gate."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

import etlantic as etl
from etlantic.transform.functions import col, to_integer

pd = pytest.importorskip("pandas")
pl = pytest.importorskip("polars")


pytestmark = [pytest.mark.pandas, pytest.mark.polars]

ROWS = [
    {"id": 1, "amount": 2.5, "active": True, "name": "Ada"},
    {"id": 2, "amount": 3.5, "active": False, "name": "Grace"},
]
NULLABLE_ROWS = [
    {"id": 1, "amount": 2.5},
    {"id": 2, "amount": None},
]
MIXED_ROWS = [
    {"id": 1, "amount": 2.5},
    {"id": 2, "amount": "3.5"},
]


def _schema_signature(value: Any) -> list[tuple[Any, ...]]:
    return [
        (field.name, field.logical_type, field.nullable, field.required)
        for field in value.schema.fields
    ]


def _lineage_signature(value: Any) -> str:
    return json.dumps(
        value.schema.metadata.get("lineage", {}), sort_keys=True, separators=(",", ":")
    )


@pytest.mark.parametrize(
    "rows", [[], NULLABLE_ROWS, MIXED_ROWS], ids=["empty", "nullable", "mixed"]
)
def test_source_inference_matches_across_records_pandas_and_polars(
    rows: list[dict[str, Any]],
) -> None:
    results = [
        etl.infer_records(rows, identity="differential-source"),
        etl.infer_source(pd.DataFrame(rows), identity="differential-source"),
        etl.infer_source(pl.DataFrame(rows), identity="differential-source"),
    ]

    assert all(
        _schema_signature(result) == _schema_signature(results[0]) for result in results
    )
    assert all(result.schema.identity == "differential-source" for result in results)


def test_typed_empty_dataframes_preserve_declared_columns() -> None:
    pandas_result = etl.infer_source(
        pd.DataFrame(
            {
                "id": pd.Series([], dtype="int64"),
                "name": pd.Series([], dtype="string"),
            }
        ),
        identity="differential-empty",
    )
    polars_result = etl.infer_source(
        pl.DataFrame(
            {
                "id": pl.Series([], dtype=pl.Int64),
                "name": pl.Series([], dtype=pl.String),
            }
        ),
        identity="differential-empty",
    )

    assert _schema_signature(pandas_result) == _schema_signature(polars_result)
    assert _schema_signature(pandas_result) == [
        ("id", "integer", False, True),
        ("name", "string", False, True),
    ]


def test_lineage_transfer_matches_across_records_pandas_and_polars() -> None:
    datasets = [
        etl.from_records(ROWS, name="differential-source"),
        etl.from_pandas(pd.DataFrame(ROWS), name="differential-source"),
        etl.from_polars(pl.DataFrame(ROWS), name="differential-source"),
    ]
    transformed = [
        dataset.withColumn("total", col("amount") + 1).select("id", "total")
        for dataset in datasets
    ]

    assert all(
        _schema_signature(dataset) == _schema_signature(transformed[0])
        for dataset in transformed
    )
    assert all(
        _lineage_signature(dataset) == _lineage_signature(transformed[0])
        for dataset in transformed
    )
    assert all(
        dataset.schema.metadata["lineage_fingerprint"]
        == transformed[0].schema.metadata["lineage_fingerprint"]
        for dataset in transformed
    )


def test_preview_conversion_filter_matches_polars_portable_execution() -> None:
    from etlantic.transform.compiler import (
        TransformCompileContext,
        TransformExecutionContext,
    )
    from etlantic.transform.protocol import KERNEL_PROFILE_V1, PROFILE_CONVERSION
    from etlantic_polars import create_transform_compiler

    rows = [{"raw": "10"}, {"raw": None}, {"raw": "2"}]
    predicate = to_integer(col("raw")) > 5
    preview = etl.from_records(rows, name="conversion-parity").filter(predicate)
    plan = {
        "planIdentity": "dtcs.transform-plan/2",
        "inputs": {"records": {"id": "records"}},
        "actions": [
            {
                "id": "filter",
                "kind": {
                    "id": "filter",
                    "action": "dtcs:filter",
                    "target": "records",
                    "parameters": {"predicate": predicate.node},
                },
            }
        ],
        "outputs": {"result": {"id": "result"}},
        "requirements": {
            "dependencies": [{"from": "filter", "to": "result", "reason": "lineage"}]
        },
    }
    compiler = create_transform_compiler()
    compiled = compiler.compile(
        plan,
        context=TransformCompileContext(
            pipeline_id="conversion-parity",
            plan_id="conversion-parity",
            step_name="filter",
            profile_name="conformance",
            engine="polars",
        ),
        requirements={
            "profiles": [KERNEL_PROFILE_V1, PROFILE_CONVERSION],
            "actions": ["dtcs:filter"],
            "functions": ["dtcs:to_integer"],
        },
    )
    bundle = asyncio.run(
        compiler.execute(
            compiled,
            inputs={"records": pl.DataFrame(rows)},
            parameters={},
            context=TransformExecutionContext(
                run_id="conversion-parity",
                pipeline_id="conversion-parity",
                plan_id="conversion-parity",
                step_name="filter",
                engine="polars",
            ),
        )
    )
    engine_result = bundle.valid["result"]

    assert preview.preview() == engine_result.to_dicts() == [{"raw": "10"}]
    assert _schema_signature(preview) == [("raw", "string", True, False)]
    assert engine_result.schema["raw"] == pl.String
    assert not any(
        getattr(item.severity, "value", item.severity) == "error"
        for item in preview.diagnostics
    )
