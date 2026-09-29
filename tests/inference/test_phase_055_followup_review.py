# pyright: reportPrivateUsage=false
"""Regression tests for findings from the Phase 0.55 implementation review."""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

import etlantic as etl
from etlantic.schema_drift import (
    NormalizedField,
    NormalizedSchema,
    json_safe_metadata,
)
from etlantic.transform.functions import coalesce, col, if_null, to_string, when


@pytest.mark.parametrize(
    "limits",
    [
        {"max_rows": 1.5},
        {"max_rows": True},
        {"max_fields": 1.5},
        {"max_diagnostics": False},
        {"max_bytes": 1.5},
        {"max_materialized_bytes": float("nan")},
        {"max_field_size": True},
        {"timeout_seconds": float("nan")},
        {"timeout_seconds": float("inf")},
        {"timeout_seconds": True},
    ],
)
def test_inference_limits_reject_malformed_values(limits: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        etl.InferenceLimits(**limits)


@pytest.mark.parametrize(
    "limits",
    [
        {"max_rows": 1.5},
        {"max_fields": "4"},
        {"max_bytes": 2.0},
        {"timeout_seconds": "2"},
        {"timeout_seconds": float("nan")},
        {"timeout_seconds": float("inf")},
    ],
)
def test_inference_limits_wire_payload_rejects_coercion(
    limits: dict[str, Any],
) -> None:
    with pytest.raises(ValueError):
        etl.InferenceLimits.from_dict(limits)


def test_schema_identity_and_metadata_redact_arbitrary_uri_schemes() -> None:
    identity = "https://alice:secret@example.com/targets/orders?sig=private#fragment"
    schema = NormalizedSchema(identity, (NormalizedField("id", "integer"),))
    serialized = json.dumps(schema.to_dict(), sort_keys=True)

    assert identity not in serialized
    assert "alice:secret" not in serialized
    assert "sig=private" not in serialized
    assert schema.to_dict()["identity"].startswith("path-sha256:")
    assert (
        NormalizedSchema.from_dict(schema.to_dict()).fingerprint()
        == schema.fingerprint()
    )
    assert json_safe_metadata({"message": f"request to {identity}"}) == {
        "message": "<path-redacted>"
    }


def test_with_fields_infers_each_assignment_from_the_same_input_schema() -> None:
    dataset = etl.from_records([{"amount": 7}])
    frame = dataset.frame._extend(
        action="dtcs:with_fields",
        parameters={
            "assignments": [
                {"name": "amount", "expression": to_string(col("amount")).node},
                {"name": "copy", "expression": col("amount").node},
            ]
        },
    )

    result = etl.forward_schema(frame, dataset.schema)
    fields = {field.name: field for field in result.fields}

    assert fields["amount"].logical_type == "string"
    assert fields["copy"].logical_type == "integer"


def test_materialized_snapshot_counts_fields_beyond_schema_field_limit() -> None:
    from etlantic.inference.facade import _bounded_materialized_snapshot

    limits = etl.InferenceLimits(
        max_fields=1,
        max_bytes=64,
        max_materialized_bytes=64,
    )

    snapshot = _bounded_materialized_snapshot(
        [{"first": 1, "uninspected": "x" * 100_000}], limits
    )

    assert snapshot is None


def test_iterable_provider_schema_consumes_only_field_limit_plus_sentinel() -> None:
    consumed = 0

    class ProviderField:
        def __init__(self, index: int) -> None:
            self.name = f"field_{index}"
            self.type = "string"
            self.nullable = True

    class ProviderSchema:
        names = ("field_0", "field_1")

        def __iter__(self):
            nonlocal consumed
            for index in range(10_000):
                consumed += 1
                yield ProviderField(index)

    result = etl.infer_source(
        ProviderSchema(), limits=etl.InferenceLimits(max_fields=2)
    )

    assert consumed == 3
    assert [field.name for field in result.schema.fields] == ["field_0", "field_1"]
    assert "INFER_LIMIT" in {item.code for item in result.diagnostics}


def test_wide_pandas_provider_stops_before_row_conversion() -> None:
    conversions = 0

    class PandasFrame:
        __module__ = "pandas.core.frame"

        def __init__(self) -> None:
            self.columns = ("first", "second", "third")

        def __len__(self) -> int:
            return 1

        def head(self, count: int) -> PandasFrame:
            assert count == 10_000
            return PandasFrame()

        def to_dict(self, *, orient: str) -> list[dict[str, int]]:
            raise AssertionError("bounded row conversion should use itertuples")

        def itertuples(self, *, index: bool, name: Any):
            nonlocal conversions
            conversions += 1
            return iter([(1, 2, 3)])

    result = etl.infer_source(PandasFrame(), limits=etl.InferenceLimits(max_fields=2))

    assert conversions == 0
    assert "INFER_LIMIT" in {item.code for item in result.diagnostics}


def test_generated_models_serialize_original_schema_field_names() -> None:
    from etlantic.storage.protocol import records_to_dicts

    schema = NormalizedSchema(
        "aliases",
        (NormalizedField("a-b", "string"), NormalizedField("a_b", "string")),
    )
    model = etl.model_from_schema(schema)
    record = model.model_validate({"a-b": "first", "a_b": "second"})

    assert records_to_dicts([record]) == [{"a-b": "first", "a_b": "second"}]


@pytest.mark.parametrize(
    "field_name",
    [
        "model_dump",
        "model_validate",
        "model_config",
        "__base__",
        "_private",
        "123column",
        "class",
    ],
)
def test_generated_models_alias_pydantic_reserved_field_names(
    field_name: str,
) -> None:
    from etlantic.storage.protocol import records_to_dicts

    model = etl.model_from_schema(
        NormalizedSchema("reserved", (NormalizedField(field_name, "string"),))
    )
    record = model.model_validate({field_name: "value"})

    assert records_to_dicts([record]) == [{field_name: "value"}]


@pytest.mark.parametrize(
    "fields",
    [
        (NormalizedField("", "integer"),),
        (NormalizedField("id", "integer"), NormalizedField("id", "string")),
        (NormalizedField("id", cast(Any, 7)),),
        (NormalizedField("id", "integer", required=cast(Any, 1)),),
        (NormalizedField("id", "integer", metadata=cast(Any, [])),),
    ],
)
def test_normalized_provider_schemas_reject_malformed_fields(
    fields: tuple[Any, ...],
) -> None:
    result = etl.infer_source(NormalizedSchema("provider", fields))

    assert not result.valid
    assert "INFER_SOURCE_UNSUPPORTED" in {item.code for item in result.diagnostics}


def test_normalized_provider_schema_unknown_types_are_diagnosed() -> None:
    result = etl.infer_source(
        NormalizedSchema("provider", (NormalizedField("id", "vendor-specific"),))
    )

    assert result.schema.fields[0].logical_type == "unknown"
    assert "INFER_UNKNOWN_TYPE" in {item.code for item in result.diagnostics}


def test_mapping_provider_schemas_reject_duplicate_or_nonstring_names() -> None:
    for fields in (
        [{"name": "id", "type": "integer"}, {"name": "id", "type": "string"}],
        [{"name": 1, "type": "integer"}],
        {1: "integer"},
    ):
        result = etl.infer_source({"fields": fields})

        assert not result.valid
        assert "INFER_SOURCE_UNSUPPORTED" in {item.code for item in result.diagnostics}


def test_object_provider_schemas_reject_nonstring_field_names() -> None:
    class ProviderField:
        name = 7
        type = "integer"
        nullable = False

    result = etl.infer_source({"fields": [ProviderField()]})

    assert not result.valid
    assert result.schema.fields == ()
    assert "INFER_SOURCE_UNSUPPORTED" in {item.code for item in result.diagnostics}


def test_pandas_provider_rejects_nonstring_column_names() -> None:
    class PandasFrame:
        __module__ = "pandas"

        columns = (7,)

        def __init__(self, rows: list[tuple[int]]) -> None:
            self.rows = rows

        def __len__(self) -> int:
            return len(self.rows)

        def head(self, count: int) -> PandasFrame:
            return PandasFrame(self.rows[:count])

        def to_dict(self, *, orient: str) -> list[dict[str, int]]:
            raise AssertionError("the provider row adapter should be used")

        def itertuples(self, *, index: bool, name: Any) -> list[tuple[int]]:
            assert index is False
            assert name is None
            return self.rows

    result = etl.infer_source(PandasFrame([(1,)]))

    assert not result.valid
    assert result.schema.fields == ()
    assert "INFER_SOURCE_UNBOUNDED" in {item.code for item in result.diagnostics}


def test_column_metadata_rejects_nonstring_names() -> None:
    from etlantic.inference.sources import _schema_from_column_metadata

    class Provider:
        columns = (7,)
        dtypes = ("integer",)

    result = _schema_from_column_metadata(
        Provider(), identity="provider", limits=etl.InferenceLimits()
    )

    assert result is not None
    assert not result.valid
    assert result.schema.fields == ()
    assert "INFER_SOURCE_UNSUPPORTED" in {item.code for item in result.diagnostics}


@pytest.mark.parametrize("compatible", [0, 1, "false", None])
def test_write_compatibility_wire_payload_rejects_coerced_boolean(
    compatible: Any,
) -> None:
    with pytest.raises(ValueError, match="flag must be a boolean"):
        etl.WriteCompatibility.from_dict({"version": 1, "compatible": compatible})


def test_record_replay_normalizes_date_values_after_datetime_promotion() -> None:
    result = etl.infer_records(
        iter(
            [
                {"created": date(2025, 1, 1)},
                {"created": datetime(2025, 1, 2)},
                {"created": date(2025, 1, 3)},
            ]
        ),
        limits=etl.InferenceLimits(max_rows=2),
    )

    assert result.schema.fields[0].logical_type == "datetime"
    assert result.replay is not None
    replayed = list(result.replay.take())
    assert all(isinstance(row["created"], datetime) for row in replayed)
    assert replayed[-1]["created"] == datetime(2025, 1, 3)


def test_csv_replay_normalizes_date_values_after_datetime_promotion(
    tmp_path: Path,
) -> None:
    source = tmp_path / "mixed-dates.csv"
    source.write_text(
        "created\n2025-01-01\n2025-01-02T00:00:00\n2025-01-03\n",
        encoding="utf-8",
    )

    result = etl.infer_csv(source, limits=etl.InferenceLimits(max_rows=2))

    assert result.schema.fields[0].logical_type == "datetime"
    assert result.replay is not None
    replayed = list(result.replay.take())
    assert all(isinstance(row["created"], datetime) for row in replayed)
    assert replayed[-1]["created"] == datetime(2025, 1, 3)


def test_async_provider_timeout_does_not_wait_for_cancellation_cleanup() -> None:
    async def exercise() -> None:
        cancellation_seen = asyncio.Event()
        release_cleanup = asyncio.Event()
        cleanup_finished = asyncio.Event()

        class Provider:
            async def inspect_schema(self) -> dict[str, Any]:
                try:
                    await asyncio.sleep(60)
                    return {"fields": [{"name": "id", "type": "integer"}]}
                except asyncio.CancelledError:
                    cancellation_seen.set()
                    await release_cleanup.wait()
                    cleanup_finished.set()
                    return {"fields": [{"name": "id", "type": "integer"}]}

        inspection = asyncio.create_task(
            etl.infer_source_async(
                Provider(), limits=etl.InferenceLimits(timeout_seconds=0.01)
            )
        )
        try:
            await asyncio.wait_for(cancellation_seen.wait(), timeout=0.1)
            completed, _ = await asyncio.wait({inspection}, timeout=0.1)
            assert inspection in completed
            result = await inspection
            assert "INFER_LIMIT" in {item.code for item in result.diagnostics}
        finally:
            release_cleanup.set()
            await asyncio.wait_for(cleanup_finished.wait(), timeout=0.2)
            if not inspection.done():
                await asyncio.wait_for(inspection, timeout=0.2)

    asyncio.run(exercise())


def test_avro_schema_document_rejects_duplicate_field_names() -> None:
    result = etl.infer_schema_document(
        {
            "type": "record",
            "name": "DuplicateField",
            "fields": [
                {"name": "id", "type": "int"},
                {"name": "id", "type": "string"},
            ],
        },
        format="avro",
    )

    assert not result.valid
    assert "INFER_SOURCE_UNSUPPORTED" in {item.code for item in result.diagnostics}


def test_normalized_schema_wire_payload_rejects_malformed_and_duplicate_fields() -> (
    None
):
    schema = NormalizedSchema("wire", (NormalizedField("id", "integer"),))
    malformed = schema.to_dict()
    malformed["fields"] = [None]
    duplicate = schema.to_dict()
    duplicate["fields"].append(duplicate["fields"][0])

    with pytest.raises(ValueError, match="field must be a mapping"):
        NormalizedSchema.from_dict(malformed)
    with pytest.raises(ValueError, match="field names must be unique"):
        NormalizedSchema.from_dict(duplicate)


def test_numeric_hints_only_allow_lossless_integer_to_number_widening() -> None:
    unsafe = etl.infer_records([{"value": 1.5}], hints={"value": "integer"})
    safe = etl.infer_records([{"value": 1}], hints={"value": "number"})

    assert unsafe.schema.fields[0].logical_type == "number"
    assert "INFER_HINT_CONFLICT" in {item.code for item in unsafe.diagnostics}
    assert safe.schema.fields[0].logical_type == "number"
    assert "INFER_HINT_CONFLICT" not in {item.code for item in safe.diagnostics}


def test_optional_non_nullable_inferred_model_omits_unset_fields_on_write() -> None:
    from pydantic import ValidationError

    from etlantic.storage.protocol import records_to_dicts

    model = etl.model_from_schema(
        NormalizedSchema(
            "optional_output",
            (NormalizedField("id", "integer", required=False, nullable=False),),
        )
    )
    absent = model.model_validate({})
    present = model.model_validate({"id": 4})

    assert records_to_dicts([absent, present]) == [{}, {"id": 4}]
    with pytest.raises(ValidationError):
        model.model_validate({"id": None})


@pytest.mark.parametrize("operation", ["coalesce", "if_null", "case_when"])
def test_decimal_number_value_merges_fail_closed(operation: str) -> None:
    dataset = etl.from_records(
        [{"decimal_value": None, "number_value": 1.5}],
        hints={"decimal_value": "decimal"},
        name=f"decimal_number_{operation}",
    )
    if operation == "coalesce":
        expression = coalesce(col("decimal_value"), col("number_value"))
    elif operation == "if_null":
        expression = if_null(col("decimal_value"), col("number_value"))
    else:
        expression = when(col("number_value") < 0, col("decimal_value")).otherwise(
            col("number_value")
        )

    result = dataset.withColumn("mixed", expression)

    assert result.schema.fields[-1].logical_type == "unknown"
    assert "INFER_BACKWARD_UNSUPPORTED" in {item.code for item in result.diagnostics}


def test_decimal_number_union_fails_closed() -> None:
    left = etl.from_records([{"value": Decimal("1.25")}], name="decimal_union")
    right = etl.from_records([{"value": 1.25}], name="number_union")

    result = left.unionByName(right)

    assert result.schema.fields[0].logical_type == "unknown"
    assert "INFER_BACKWARD_UNSUPPORTED" in {item.code for item in result.diagnostics}


def test_multi_input_schema_preserves_optional_and_outer_join_fields() -> None:
    left = etl.from_records(
        [{"id": 1, "optional": 2}, {"id": 2}], name="optional_join_left"
    )
    right = etl.from_records([{"id": 1, "payload": "x"}], name="optional_join_right")

    joined = left.join(right, on="id", how="left")
    fields = {field.name: field for field in joined.schema.fields}

    assert (fields["optional"].required, fields["optional"].nullable) == (False, True)
    assert (fields["payload"].required, fields["payload"].nullable) == (True, True)
    assert joined.preview()[-1] == {"id": 2, "payload": None}


def test_multi_input_union_nulls_optional_values_without_false_nonnullability() -> None:
    left = etl.from_records(
        [{"id": 1, "optional": 2}, {"id": 2}], name="optional_union_left"
    )
    right = etl.from_records([{"id": 3, "optional": 4}], name="optional_union_right")

    combined = left.unionByName(right)
    optional = next(
        field for field in combined.schema.fields if field.name == "optional"
    )

    assert (optional.required, optional.nullable) == (True, True)
    assert combined.preview()[1]["optional"] is None


def test_lineage_serialization_bounds_long_operation_history() -> None:
    from etlantic.inference.transfer import forward_schema

    dataset = etl.from_records([{"id": 1}], name="long_lineage")
    frame = dataset.frame
    for _ in range(300):
        frame = frame.limit(1)

    schema = forward_schema(frame, dataset.schema)
    serialized = schema.to_dict()
    operations = serialized["metadata"]["lineage"]["id"]["operations"]

    assert len(operations) == 256
    assert {"operation": "history_truncated"} in operations
    assert operations[-1] == {"operation": "dtcs:limit"}


def test_output_proposal_wire_payload_fails_closed_on_bad_schema_or_intent() -> None:
    schema = NormalizedSchema("target", (NormalizedField("id", "integer"),))
    proposal = etl.OutputProposal(
        schema,
        "target",
        capabilities=("create",),
        create_intent=True,
    ).to_dict()

    malformed = json.loads(json.dumps(proposal))
    malformed["schema"]["fields"] = [None]
    with pytest.raises(ValueError, match="field must be a mapping"):
        etl.OutputProposal.from_dict(malformed)

    malformed_intent = json.loads(json.dumps(proposal))
    malformed_intent["create_intent"] = "false"
    with pytest.raises(ValueError, match="create flags must be booleans"):
        etl.OutputProposal.from_dict(malformed_intent)


@pytest.mark.parametrize("bad_version", [True, 1.9, "1"])
def test_versioned_inference_wire_models_reject_coerced_versions(
    bad_version: Any,
) -> None:
    schema = NormalizedSchema("wire", (NormalizedField("id", "integer"),))
    payloads_and_loaders = [
        (etl.InferenceLimits().to_dict(), etl.InferenceLimits.from_dict),
        (schema.to_dict(), NormalizedSchema.from_dict),
        (
            etl.InferenceObservation(schema).to_dict(),
            etl.InferenceObservation.from_dict,
        ),
        (
            etl.TargetObservation(None, "absent").to_dict(),
            etl.TargetObservation.from_dict,
        ),
        (
            etl.OutputProposal(schema, "wire").to_dict(),
            etl.OutputProposal.from_dict,
        ),
        (
            etl.FieldConstraint("id", "integer").to_dict(),
            etl.FieldConstraint.from_dict,
        ),
        (
            etl.WriteCompatibility(True).to_dict(),
            etl.WriteCompatibility.from_dict,
        ),
    ]

    for payload, loader in payloads_and_loaders:
        malformed = json.loads(json.dumps(payload))
        malformed["version"] = bad_version
        with pytest.raises(ValueError, match="version"):
            loader(malformed)
