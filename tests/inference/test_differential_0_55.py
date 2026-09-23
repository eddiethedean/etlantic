"""Inference parity fixtures for the phase 0.55 differential gate."""

from __future__ import annotations

import json
from typing import Any

import pytest

import etlantic as etl
from etlantic.transform.functions import col

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
