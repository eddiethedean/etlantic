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


def test_truncated_pandas_and_polars_previews_are_provisional() -> None:
    rows = [{"id": 1, "late": "present"}, {"id": 2, "late": None}]
    limits = etl.InferenceLimits(max_rows=1)
    providers = (
        (pd.DataFrame(rows), "pandas"),
        (pl.DataFrame(rows), "polars"),
    )

    for frame, provider_name in providers:
        result = etl.infer_source(frame, limits=limits)

        assert result.provenance["provider_name"] == provider_name
        assert result.provenance["inspection_method"] in {
            "provider_schema",
            "to_dict",
            "to_dicts",
            "schema",
        }
        assert result.provenance["limits"]["max_rows"] == 1
        assert result.provenance["sampled"] is True
        assert (
            "provider_preview_truncated_or_unverified"
            in result.provenance["limitations"]
        )
        assert all(
            field.required is False and field.nullable is True
            for field in result.schema.fields
        )
        assert all(evidence.sampled for evidence in result.evidence)
        assert {field.name for field in result.schema.fields} == {"id", "late"}


def test_pandas_and_polars_honor_materialized_byte_limits_before_conversion() -> None:
    rows = [{"id": 1, "payload": "x" * 32}]
    limits = etl.InferenceLimits(max_bytes=1_000_000, max_materialized_bytes=1)

    for frame in (pd.DataFrame(rows), pl.DataFrame(rows)):
        result = etl.infer_source(frame, limits=limits)

        assert "INFER_LIMIT" in {item.code for item in result.diagnostics}
        assert result.provenance["effective_materialized_bytes_limit"] == 1
        assert result.provenance["limit_reason"] == "materialized_bytes"
        assert result.provenance["sampled"] is True


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
    assert _schema_signature(preview) == [("raw", "string", True, True)]
    assert engine_result.schema["raw"] == pl.String
    assert not any(
        getattr(item.severity, "value", item.severity) == "error"
        for item in preview.diagnostics
    )


def test_duckdb_relation_inference_uses_metadata_without_rows() -> None:
    duckdb = pytest.importorskip("duckdb")
    relation = duckdb.sql(
        "select cast(1 as integer) as id, cast(null as varchar) as name"
    )

    result = etl.infer_source(relation, identity="duckdb-relation")

    assert [(field.name, field.logical_type) for field in result.schema.fields] == [
        ("id", "integer"),
        ("name", "string"),
    ]
    assert all(field.nullable for field in result.schema.fields)
    assert result.provenance["method"] == "relation_metadata"
    assert result.provenance["rows_observed"] == 0
    hinted = etl.infer_source(relation, hints={"id": "string"})
    assert "INFER_HINT_UNSUPPORTED" in {item.code for item in hinted.diagnostics}


def test_datafusion_frame_inference_uses_arrow_schema_without_rows() -> None:
    datafusion = pytest.importorskip("datafusion")
    frame = datafusion.SessionContext().sql(
        "select cast(1 as bigint) as id, cast(null as varchar) as name"
    )

    result = etl.infer_source(frame, identity="datafusion-frame")

    assert [(field.name, field.logical_type) for field in result.schema.fields] == [
        ("id", "integer"),
        ("name", "string"),
    ]
    assert result.provenance["method"] == "datafusion_schema"
    assert result.provenance["rows_observed"] == 0
    hinted = etl.infer_source(frame, hints={"id": "string"})
    assert "INFER_HINT_UNSUPPORTED" in {item.code for item in hinted.diagnostics}


def test_pyspark_frame_inference_uses_struct_metadata() -> None:
    pyspark = pytest.importorskip("pyspark.sql")
    types = pytest.importorskip("pyspark.sql.types")
    try:
        spark = (
            pyspark.SparkSession.builder.master("local[1]")
            .appName("etlantic-inference-metadata")
            .getOrCreate()
        )
    except Exception as exc:
        pytest.skip(f"local Spark is unavailable: {type(exc).__name__}")
    try:
        schema = types.StructType(
            [types.StructField("id", types.IntegerType(), nullable=True)]
        )
        frame = spark.createDataFrame([(1,)], schema)
        result = etl.infer_source(frame, identity="spark-frame")
        assert [
            (field.name, field.logical_type, field.required, field.nullable)
            for field in result.schema.fields
        ] == [("id", "integer", True, True)]
        assert not result.diagnostics
        assert result.provenance["method"] == "spark_schema"
        assert result.provenance["rows_observed"] == 0
    finally:
        spark.stop()


def test_aggregate_schema_transfer_uses_function_signatures() -> None:
    from etlantic.inference import forward_schema
    from etlantic.schema_drift import NormalizedField, NormalizedSchema
    from etlantic.transform import functions as F
    from etlantic.transform.dataframe import input_frame

    source = NormalizedSchema(
        "orders",
        (
            NormalizedField("customer_id", "integer", True, False),
            NormalizedField("amount", "number", True, True),
        ),
    )
    frame = (
        input_frame("orders")
        .groupBy("customer_id")
        .agg(total=F.sum(F.col("amount")), count=F.count_all())
    )

    result = forward_schema(frame, source)

    assert [
        (field.name, field.logical_type, field.required, field.nullable)
        for field in result.fields
    ] == [
        ("customer_id", "integer", True, False),
        ("total", "number", True, True),
        ("count", "integer", True, False),
    ]
    assert "inference_diagnostics" not in result.metadata
    assert result.metadata["lineage"]["total"]["invertible"] is False


def test_parquet_footer_inference_and_durable_binding(tmp_path) -> None:
    arrow = pytest.importorskip("pyarrow")
    parquet = pytest.importorskip("pyarrow.parquet")
    path = tmp_path / "records.parquet"
    schema = arrow.schema(
        [
            arrow.field("id", arrow.int64(), nullable=False),
            arrow.field("value", arrow.string(), nullable=True),
        ]
    )
    parquet.write_table(
        arrow.Table.from_pylist([{"id": 1, "value": None}], schema=schema), path
    )

    dataset = etl.read_parquet(str(path))
    assert dataset.preview() == []
    assert [
        (field.name, field.logical_type, field.required, field.nullable)
        for field in dataset.schema.fields
    ] == [
        ("id", "integer", True, False),
        ("value", "string", True, True),
    ]
    assert dataset.provenance["rows_observed"] == 0
    definition = dataset.definition()
    assert definition.nodes[0].bindings["source"]["format"] == "parquet"
    assert (
        etl.reopen_source_binding(definition.nodes[0].bindings["source"]).schema.fields
        == dataset.schema.fields
    )
    target = etl.inspect_target(path)
    assert target.exists == "present"
    assert target.schema is not None
    assert target.schema.fields == dataset.schema.fields
    limited = etl.infer_parquet(path, limits=etl.InferenceLimits(max_bytes=8))
    assert "INFER_LIMIT" in {item.code for item in limited.diagnostics}


def test_schema_document_registry_identity_is_verified() -> None:
    from etlantic.streaming.registry import InMemorySchemaRegistry, SchemaFormat

    document = '{"type":"object","properties":{"id":{"type":"integer"},"note":{"type":["string","null"]}},"required":["id"]}'
    registry = InMemorySchemaRegistry()
    from etlantic.streaming.registry import schema_fingerprint

    registered = registry.register(
        "orders",
        schema_fingerprint(document, format=SchemaFormat.JSON_SCHEMA),
        format=SchemaFormat.JSON_SCHEMA,
    )
    result = etl.infer_schema_document(
        document,
        format="json_schema",
        registry=registry,
        subject="orders",
        version=registered.version,
    )
    assert result.valid
    assert [
        (field.name, field.logical_type, field.required, field.nullable)
        for field in result.schema.fields
    ] == [
        ("id", "integer", True, False),
        ("note", "string", False, True),
    ]
    assert result.provenance["fingerprint"] == registered.fingerprint
    assert "properties" not in result.to_observation().to_dict()["provenance"]

    changed = etl.infer_schema_document(
        document.replace('"integer"', '"string"'),
        format="json_schema",
        registry=registry,
        subject="orders",
    )
    assert "INFER_SOURCE_SCHEMA_MISMATCH" in {item.code for item in changed.diagnostics}
    avro = etl.infer_schema_document(
        {
            "type": "record",
            "name": "Orders",
            "fields": [
                {"name": "id", "type": "long"},
                {
                    "name": "amount",
                    "type": ["null", {"type": "bytes", "logicalType": "decimal"}],
                },
            ],
        },
        format="avro",
    )
    assert [(field.logical_type, field.nullable) for field in avro.schema.fields] == [
        ("integer", False),
        ("decimal", True),
    ]
    assert "INFER_LIMIT" in {
        item.code
        for item in etl.infer_schema_document(
            document,
            format="json_schema",
            limits=etl.InferenceLimits(max_bytes=8),
        ).diagnostics
    }
    target = etl.inspect_schema_document_target(
        document,
        format="json_schema",
        identity="orders-schema",
        registry=registry,
        subject="orders",
    )
    assert target.exists == "present"
    assert target.revision == registered.fingerprint
    assert target.schema is not None
    assert "capabilities" not in target.metadata


def test_multi_input_join_and_union_have_both_bound_sources() -> None:
    from etlantic.authoring.definition import PipelineDefinition
    from etlantic.authoring.lifecycle import validate_pipeline_like
    from etlantic.transform.functions import col

    left = etl.from_records([{"id": 1, "left_value": 2}], name="join_left")
    right = etl.from_records([{"id": 1, "right_value": 3}], name="join_right")
    joined = left.join(right, on="id").withColumn(
        "total", col("left_value") + col("right_value")
    )
    assert joined.preview() == [
        {"id": 1, "left_value": 2, "right_value": 3, "total": 5}
    ]
    definition = joined.definition()
    assert validate_pipeline_like(definition).valid
    assert len([node for node in definition.nodes if node.kind == "source"]) == 2
    combine = next(node for node in definition.nodes if node.name.endswith("_combine"))
    incoming = [edge for edge in definition.edges if edge.consumer_node == combine.name]
    assert {edge.consumer_port for edge in incoming} == {"left", "right"}
    assert all(
        edge.producer_contract_id == edge.consumer_contract_id for edge in incoming
    )
    assert [item.name for item in definition.transformations][-2:] == [
        "dtcs:join",
        "dtcs:with_fields",
    ]
    reloaded = PipelineDefinition.from_dict(definition.to_dict())
    assert validate_pipeline_like(reloaded).valid
    assert len([node for node in reloaded.nodes if node.kind == "source"]) == 2
    with pytest.raises(ValueError, match="multi-input target backfill"):
        joined.backfill_from(joined.schema)

    union = left.unionByName(right, allowMissingColumns=True)
    assert union.preview() == [
        {"id": 1, "left_value": 2, "right_value": None},
        {"id": 1, "left_value": None, "right_value": 3},
    ]
    assert validate_pipeline_like(union.definition()).valid


def test_multi_input_rebind_requires_each_source_node(tmp_path) -> None:
    left = etl.from_records([{"id": 1, "left_value": 2}], name="bound_left")
    right = etl.from_records([{"id": 1, "right_value": 3}], name="bound_right")
    definition = left.join(right, on="id").definition()
    left_file = tmp_path / "left.csv"
    right_file = tmp_path / "right.csv"
    left_file.write_text("id,left_value\n1,2\n", encoding="utf-8")
    right_file.write_text("id,right_value\n1,3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="per-node sources"):
        etl.rebind_definition(definition, source=str(left_file))
    rebound = etl.rebind_definition(
        definition,
        sources={
            "bound_left_source": str(left_file),
            "bound_right_source": str(right_file),
        },
    )
    assert [
        node.bindings["source"]["format"]
        for node in rebound.nodes
        if node.kind == "source"
    ] == ["csv", "csv"]


def test_multi_input_outer_join_and_empty_union_preserve_contract_fields() -> None:
    left = etl.from_records([{"id": 1, "left_value": 2}], name="outer_left")
    right = etl.from_records([{"id": 2, "right_value": 3}], name="outer_right")
    joined = left.join(right, on="id", how="full")
    assert joined.preview() == [
        {"id": 1, "left_value": 2, "right_value": None},
        {"id": 2, "left_value": None, "right_value": 3},
    ]
    assert next(
        field for field in joined.schema.fields if field.name == "left_value"
    ).nullable
    assert next(
        field for field in joined.schema.fields if field.name == "right_value"
    ).nullable

    empty_left = etl.from_records([], name="empty_left")
    # Empty observations cannot establish a durable contract; the schema rule
    # still includes the other input's fields when one preview is empty.
    union = empty_left.unionByName(right, allowMissingColumns=True)
    assert [field.name for field in union.schema.fields] == [
        "id",
        "right_value",
    ]
    assert union.preview() == [{"id": 2, "right_value": 3}]
