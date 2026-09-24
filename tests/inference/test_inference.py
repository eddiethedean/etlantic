# pyright: reportArgumentType=false, reportMissingParameterType=false, reportOptionalMemberAccess=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false
from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

import etlantic as etl
from etlantic.inference import (
    InferenceLimits,
    backfill_schema,
    check_write_compatibility,
    infer_records,
    infer_source,
)
from etlantic.schema_drift import (
    NormalizedField,
    NormalizedSchema,
    normalize_schema_from_fields,
)
from etlantic.transform.functions import col, lit


def test_records_inference_promotes_across_all_rows_and_tracks_missing() -> None:
    result = infer_records(row for row in [{"id": 1}, {"id": 2.5, "name": "a"}])
    fields = {field.name: field for field in result.schema.fields}
    assert fields["id"].logical_type == "number"
    assert fields["name"].nullable is True
    assert result.provenance["rows_observed"] == 2
    assert "rows" not in result.to_dict()
    assert "rows" not in result.to_dict(include_rows=True)


def test_records_inference_is_bounded() -> None:
    result = infer_records(
        ({"id": i} for i in range(10)), limits=InferenceLimits(max_rows=2)
    )
    assert result.rows == ()
    assert list(result.replay.take()) == [{"id": i} for i in range(10)]
    assert "INFER_LIMIT" in {diagnostic.code for diagnostic in result.diagnostics}


def test_inference_result_serialization_cannot_walk_runtime_rows() -> None:
    result = infer_records([{"secret": "value"}], retain_rows=True)
    with pytest.raises(TypeError):
        asdict(result)
    assert result.to_dict(include_rows=True)["schema"]["fields"][0]["name"] == "secret"
    observation = result.to_observation()
    assert observation.to_dict()["version"] == 1
    assert "rows" not in observation.to_dict()
    assert result.replace(provenance={"source": "test"}).provenance == {
        "source": "test"
    }


def test_records_inference_enforces_byte_and_timeout_limits() -> None:
    byte_limited = infer_records(
        [{"value": "x" * 100}], limits=InferenceLimits(max_bytes=10)
    )
    assert "INFER_LIMIT" in {diagnostic.code for diagnostic in byte_limited.diagnostics}
    timeout_limited = infer_records(
        [{"value": 1}], limits=InferenceLimits(timeout_seconds=1e-12)
    )
    assert "INFER_LIMIT" in {
        diagnostic.code for diagnostic in timeout_limited.diagnostics
    }


def test_csv_inference_parses_common_scalars(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id,active\n1,true\n2,false\n", encoding="utf-8")
    dataset = etl.read_csv(str(path), name="events")
    assert [field.logical_type for field in dataset.schema.fields] == [
        "boolean",
        "integer",
    ]
    assert dataset.preview() == [{"id": 1, "active": True}, {"id": 2, "active": False}]


def test_csv_date_only_values_are_dates(tmp_path) -> None:
    path = tmp_path / "dates.csv"
    path.write_text("day\n2024-01-01\n", encoding="utf-8")
    result = etl.infer_csv(path, retain_rows=True)
    assert result.schema.fields[0].logical_type == "date"
    assert result.rows[0]["day"].isoformat() == "2024-01-01"


def test_hints_are_validated_and_do_not_override_conflicting_values() -> None:
    result = infer_records([{"id": 1}], hints={"id": "string", "other": "bogus"})
    assert result.schema.fields[0].logical_type == "integer"
    codes = {diagnostic.code for diagnostic in result.diagnostics}
    assert "INFER_HINT_CONFLICT" in codes
    assert "INFER_HINT_UNSUPPORTED" in codes


def test_unknown_hint_is_an_error() -> None:
    result = infer_records([{"id": 1}], hints={"id": "bogus"})
    assert result.schema.fields[0].logical_type == "integer"
    assert "INFER_HINT_UNSUPPORTED" in {d.code for d in result.diagnostics}


def test_data_first_transformations_refresh_model() -> None:
    dataset = etl.from_records([{"id": 1}, {"id": 2}], name="users")
    transformed = dataset.withColumn("next_id", col("id") + lit(1)).select("next_id")
    assert transformed.schema.fields[0].logical_type == "integer"
    assert transformed.collect() == [{"next_id": 2}, {"next_id": 3}]
    assert transformed.model.model_fields["next_id"].annotation is int


def test_existing_target_backfills_source_type() -> None:
    source = normalize_schema_from_fields(
        [{"name": "id", "logical_type": "string"}], identity="source"
    )
    target = normalize_schema_from_fields(
        [{"name": "id", "logical_type": "integer"}], identity="target"
    )
    result = backfill_schema(source, target)
    assert result.schema.fields[0].logical_type == "integer"
    assert "INFER_TARGET_CONFLICT" in {
        diagnostic.code for diagnostic in result.diagnostics
    }


def test_data_first_target_backfill_uses_existing_schema() -> None:
    target = normalize_schema_from_fields(
        [{"name": "id", "logical_type": "integer"}], identity="target"
    )
    dataset = etl.from_records_for_target([{"id": "12"}], target, name="source")
    assert dataset.schema.fields[0].logical_type == "integer"
    assert dataset.collect() == [{"id": 12}]


def test_target_conflict_preserves_source_type() -> None:
    source = normalize_schema_from_fields(
        [{"name": "payload", "logical_type": "object"}], identity="source"
    )
    target = normalize_schema_from_fields(
        [{"name": "payload", "logical_type": "integer"}], identity="target"
    )
    result = backfill_schema(source, target)
    assert result.schema.fields[0].logical_type == "object"


def test_target_backfill_reports_failed_runtime_conversion() -> None:
    target = normalize_schema_from_fields(
        [{"name": "id", "logical_type": "integer"}], identity="target"
    )
    dataset = etl.from_records_for_target([{"id": "not-an-int"}], target)
    assert dataset.schema.fields[0].logical_type == "string"
    assert "INFER_RUNTIME_CONVERSION" in {
        diagnostic.code for diagnostic in dataset.diagnostics
    }


def test_target_backfill_validates_when_rows_are_not_retained() -> None:
    target = normalize_schema_from_fields(
        [{"name": "id", "logical_type": "integer"}], identity="target"
    )
    result = etl.infer_records_for_target(
        [{"id": "not-an-int"}], target, retain_rows=False
    )
    assert result.rows == ()
    assert result.provenance["target_validation"] == "failed"
    assert "INFER_RUNTIME_CONVERSION" in {d.code for d in result.diagnostics}


def test_target_path_with_unsupported_extension_fails_closed(tmp_path) -> None:
    path = tmp_path / "target.parquet"
    path.write_bytes(b"not a csv")
    observation = etl.inspect_target(path)
    assert observation.exists == "unknown"
    assert observation.inspector is None


def test_target_inspection_preserves_normalized_field_objects() -> None:
    class Target:
        def inspect_schema(self):
            return {"fields": [NormalizedField("id", "integer")]}

    observation = etl.inspect_target(Target())
    assert observation.schema is not None
    assert observation.schema.fields[0].logical_type == "integer"
    direct = etl.inspect_target({"id": "INTEGER"})
    assert direct.schema is not None
    assert direct.schema.fields[0].logical_type == "integer"


def test_jsonl_invalid_rows_are_diagnosed_without_fake_fields(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text('{"id": 1}\nnot-json\n', encoding="utf-8")
    result = etl.infer_json(path, lines=True)
    assert [field.name for field in result.schema.fields] == ["id"]
    assert "INFER_JSON_ROW" in {diagnostic.code for diagnostic in result.diagnostics}


def test_source_dispatch_uses_provider_metadata_without_consuming_rows() -> None:
    class Source:
        def __init__(self) -> None:
            self.schema = {"id": "INTEGER", "name": "VARCHAR"}

    result = infer_source(Source(), identity="catalog")
    assert [field.logical_type for field in result.schema.fields] == [
        "integer",
        "string",
    ]
    assert result.provenance["method"] == "provider_schema"


def test_source_dispatch_accepts_inspect_schema_provider() -> None:
    class Source:
        def inspect_schema(self):
            return {"fields": {"id": "INTEGER"}}

    result = infer_source(Source(), identity="catalog")
    assert result.schema.fields[0].logical_type == "integer"
    assert result.provenance["method"] == "inspect_schema"


def test_provider_preview_does_not_narrow_declared_field_flags() -> None:
    class Source:
        def inspect_schema(self):
            return {
                "fields": [
                    {
                        "name": "id",
                        "type": "INTEGER",
                        "required": False,
                        "nullable": True,
                    }
                ]
            }

        def head(self, count):
            return View()

    class View:
        __etlantic_bounded_view__ = True

        def to_dicts(self):
            return [{"id": 1}]

    result = infer_source(Source(), identity="provider")
    field = result.schema.fields[0]

    assert field.required is False
    assert field.nullable is True


def test_provider_type_aliases_are_normalized() -> None:
    class Source:
        def __init__(self) -> None:
            self.schema = {"id": "Int64", "name": "Utf8"}

    result = infer_source(Source(), identity="catalog")
    assert [field.logical_type for field in result.schema.fields] == [
        "integer",
        "string",
    ]


def test_async_source_schema_inspection_is_supported() -> None:
    class Source:
        async def schema(self) -> dict[str, str]:
            return {"id": "INTEGER"}

    result = asyncio.run(etl.infer_source_async(Source(), identity="catalog"))
    assert result.schema.fields[0].logical_type == "integer"


def test_source_dataframe_adapter_applies_row_limit_before_materialization() -> None:
    class Frame:
        def __init__(self, rows):
            self.rows = rows

        def head(self, count):
            return Frame(self.rows[:count])

        def to_dicts(self):
            return list(self.rows)

    result = infer_source(
        Frame([{"id": i} for i in range(10)]),
        limits=InferenceLimits(max_rows=2),
    )
    assert result.provenance["rows_observed"] == 2


def test_missing_target_is_absent() -> None:
    assert (
        etl.inspect_target("/tmp/etlantic-inference-no-such-target.csv").exists
        == "absent"
    )


def test_async_target_inspection_is_supported() -> None:
    class Target:
        async def inspect_schema(self) -> dict[str, object]:
            return {"fields": [{"name": "id", "type": "integer"}]}

    import asyncio

    observation = asyncio.run(etl.inspect_target_async(Target()))
    assert observation.exists == "present"
    assert observation.schema is not None


def test_async_target_schema_method_is_supported() -> None:
    class Target:
        async def schema(self) -> dict[str, str]:
            return {"id": "INTEGER"}

    observation = asyncio.run(etl.inspect_target_async(Target()))
    assert observation.schema is not None
    assert observation.schema.fields[0].logical_type == "integer"


def test_async_target_backfill_uses_connector_schema() -> None:
    class Target:
        async def inspect_schema(self) -> dict[str, object]:
            return {"fields": [{"name": "id", "type": "integer"}]}

    import asyncio

    result = asyncio.run(
        etl.infer_records_for_target_async([{"id": "7"}], Target(), retain_rows=True)
    )
    assert result.schema.fields[0].logical_type == "integer"
    assert result.rows == ({"id": 7},)


def test_target_backfill_marks_unvalidated_replay_and_fails_lazily() -> None:
    target = normalize_schema_from_fields(
        [{"name": "id", "logical_type": "integer"}], identity="target"
    )
    dataset = etl.from_records_for_target(
        ({"id": value} for value in ("1", "bad")),
        target,
        limits=InferenceLimits(max_rows=1),
    )
    assert dataset.provenance["target_validation"] == "prefix_only"
    assert dataset.provenance["target_validation_fields"] == ["id"]
    assert dataset.replay is not None
    with pytest.raises(etl.InferenceReplayError) as error:
        list(dataset.replay.take())
    assert error.value.row_index == 1
    assert error.value.diagnostic.code == "INFER_RUNTIME_CONVERSION"
    assert "bad" not in str(error.value)
    assert "bad" not in str(error.value.diagnostic.to_dict())
    assert dataset.provenance["target_validation"] == "failed"
    assert dataset.provenance["replay_status"]["state"] == "failed"
    with pytest.raises(RuntimeError, match="already been consumed"):
        dataset.replay.take()


def test_nonretained_target_replay_failure_updates_public_result() -> None:
    target = normalize_schema_from_fields(
        [{"name": "id", "logical_type": "integer"}], identity="target"
    )
    result = etl.infer_records_for_target(
        ({"id": value} for value in ("1", "bad")),
        target,
        limits=InferenceLimits(max_rows=1),
        retain_rows=False,
    )
    assert result.rows == ()
    assert result.provenance["target_validation"] == "prefix_only"
    with pytest.raises(etl.InferenceReplayError) as error:
        list(result.replay.take())
    assert error.value.row_index == 1
    assert result.provenance["target_validation"] == "failed"
    assert result.provenance["replay_status"]["state"] == "failed"
    assert "INFER_RUNTIME_CONVERSION" in {d.code for d in result.diagnostics}


def test_async_nonretained_target_replay_failure_updates_public_result() -> None:
    target = normalize_schema_from_fields(
        [{"name": "id", "logical_type": "integer"}], identity="target"
    )

    async def run() -> etl.InferenceResult:
        return await etl.infer_records_for_target_async(
            ({"id": value} for value in ("1", "bad")),
            target,
            limits=InferenceLimits(max_rows=1),
            retain_rows=False,
        )

    result = asyncio.run(run())
    assert result.rows == ()
    assert result.provenance["target_validation"] == "prefix_only"
    with pytest.raises(etl.InferenceReplayError) as error:
        list(result.replay.take())
    assert error.value.row_index == 1
    assert result.provenance["target_validation"] == "failed"
    assert result.provenance["replay_status"]["state"] == "failed"
    assert "INFER_RUNTIME_CONVERSION" in {d.code for d in result.diagnostics}


def test_target_backfill_marks_replay_complete_after_valid_remainder() -> None:
    target = normalize_schema_from_fields(
        [{"name": "id", "logical_type": "integer"}], identity="target"
    )
    dataset = etl.from_records_for_target(
        ({"id": value} for value in ("1", "2")),
        target,
        limits=InferenceLimits(max_rows=1),
    )
    assert dataset.provenance["replay_status"]["state"] == "prefix_only"
    assert list(dataset.replay.take()) == [{"id": 1}, {"id": 2}]
    assert dataset.provenance["target_validation"] == "complete"
    assert dataset.provenance["replay_status"]["state"] == "complete"


def test_target_replay_failure_is_revision_bound_and_wire_safe() -> None:
    target_schema = NormalizedSchema(
        "sink",
        (NormalizedField("id", "integer"),),
    )
    target = etl.TargetObservation(
        target_schema,
        "present",
        revision="r7",
        metadata={"identity": "sink"},
    )
    dataset = etl.from_records_for_target(
        ({"id": value} for value in ("1", "bad")),
        target,
        limits=InferenceLimits(max_rows=1),
    )
    with pytest.raises(etl.InferenceReplayError):
        list(dataset.replay.take())
    status = dataset.provenance["replay_status"]
    assert status["target_identity"] == "sink"
    assert status["target_revision"] == "r7"
    assert status["row_index"] == 1
    payload = dataset.observation.to_dict()
    assert "bad" not in str(payload)
    restored = etl.InferenceObservation.from_dict(payload)
    assert restored.provenance["replay_status"]["state"] == "failed"
    assert restored.provenance["replay_status"]["target_revision"] == "r7"


def test_target_replay_fails_closed_for_incompatible_object_values() -> None:
    target = normalize_schema_from_fields(
        [{"name": "payload", "logical_type": "number"}], identity="target"
    )
    dataset = etl.from_records_for_target(
        ({"payload": value} for value in ({"nested": True}, {"nested": False})),
        target,
        limits=InferenceLimits(max_rows=1),
    )
    assert dataset.provenance["target_validation"] == "failed"
    with pytest.raises(etl.InferenceReplayError) as error:
        list(dataset.replay.take())
    assert error.value.diagnostic.metadata["source_logical_type"] == "object"
    assert error.value.diagnostic.metadata["target_logical_type"] == "number"
    assert "nested" not in str(error.value.diagnostic.to_dict())


def test_target_replay_reports_all_invalid_fields_on_first_bad_row() -> None:
    target = normalize_schema_from_fields(
        [
            {"name": "id", "logical_type": "integer"},
            {"name": "amount", "logical_type": "number"},
        ],
        identity="target",
    )
    dataset = etl.from_records_for_target(
        (
            {"id": row_id, "amount": amount}
            for row_id, amount in (("1", "2.5"), ("bad", "wat"))
        ),
        target,
        limits=InferenceLimits(max_rows=1),
    )
    with pytest.raises(etl.InferenceReplayError) as error:
        list(dataset.replay.take())
    assert {item.path for item in error.value.diagnostics} == {("id",), ("amount",)}
    assert "bad" not in str(dataset.provenance["replay_status"])
    assert "wat" not in str(dataset.provenance["replay_status"])


def test_target_replay_reuses_decimal_and_date_conversion_policy() -> None:
    target = normalize_schema_from_fields(
        [
            {"name": "amount", "logical_type": "number"},
            {"name": "day", "logical_type": "datetime"},
        ],
        identity="target",
    )
    dataset = etl.from_records_for_target(
        (
            {"amount": amount, "day": day}
            for amount, day in (
                (Decimal("1.25"), date(2024, 1, 1)),
                (Decimal("2.50"), date(2024, 1, 2)),
            )
        ),
        target,
        limits=InferenceLimits(max_rows=1),
    )
    rows = list(dataset.replay.take())
    assert rows[0]["amount"] == 1.25
    assert rows[0]["day"].isoformat() == "2024-01-01T00:00:00"
    assert rows[1]["amount"] == 2.5
    assert rows[1]["day"].isoformat() == "2024-01-02T00:00:00"
    assert dataset.provenance["replay_status"]["state"] == "complete"


def test_target_replay_preserves_revision_mismatch_without_casting() -> None:
    target_schema = NormalizedSchema(
        "sink",
        (NormalizedField("id", "integer"),),
    )
    target = etl.TargetObservation(
        target_schema,
        "present",
        revision="r1",
        metadata={"identity": "sink"},
    )
    result = etl.infer_records_for_target(
        ({"id": value} for value in ("1", "2")),
        target,
        limits=InferenceLimits(max_rows=1),
        expected_revision="r2",
    )
    assert result.provenance["target_validation"] == "stale"
    assert list(result.replay.take()) == [{"id": "1"}, {"id": "2"}]


def test_storage_records_accepts_generator_of_mappings() -> None:
    from etlantic.storage.protocol import records_to_dicts

    assert records_to_dicts({"id": i} for i in range(2)) == [{"id": 0}, {"id": 1}]


def test_local_schema_inspection_stops_before_exhausting_generator() -> None:
    from etlantic.dataframe.local import LocalDataframePlugin

    def rows():
        for index in range(10_001):
            yield {"id": index}
        raise AssertionError("schema inspection exhausted the source")

    result = LocalDataframePlugin().inspect_schema(rows(), identity="bounded")
    assert result is not None
    assert result["fields"][0]["name"] == "id"


def test_json_array_inference_respects_row_limit(tmp_path) -> None:
    path = tmp_path / "events.json"
    path.write_text('[{"id": 1}, {"id": 2}, {"id": 3}]', encoding="utf-8")
    result = etl.infer_json(path, limits=InferenceLimits(max_rows=1))
    assert result.provenance["rows_observed"] == 1
    assert "INFER_LIMIT" in {diagnostic.code for diagnostic in result.diagnostics}


def test_model_preserves_required_nullable_field() -> None:
    model = etl.model_from_schema(
        NormalizedSchema(
            "model",
            (NormalizedField("value", "integer", required=True, nullable=True),),
        )
    )
    with pytest.raises(ValidationError):
        model.model_validate({})
    assert model.model_validate({"value": None}).value is None


def test_mixed_scalar_preview_matches_generated_model() -> None:
    dataset = etl.from_records([{"value": 1}, {"value": "one"}])
    assert dataset.collect() == [{"value": "1"}, {"value": "one"}]
    assert all(dataset.model.model_validate(row) for row in dataset.collect())


def test_write_compatibility_checks_missing_and_nullable_target_fields() -> None:
    source = NormalizedSchema(
        "source", (NormalizedField("id", "integer", required=False, nullable=True),)
    )
    target = NormalizedSchema(
        "target",
        (
            NormalizedField("id", "integer", required=True, nullable=False),
            NormalizedField("created_at", "datetime"),
        ),
    )
    result = check_write_compatibility(source, target)
    assert result.status == "conflict"
    assert {"id", "created_at"} <= set(result.incompatible_fields)


def test_backfill_from_converts_preview_rows() -> None:
    target = normalize_schema_from_fields(
        [{"name": "id", "logical_type": "integer"}], identity="target"
    )
    dataset = etl.from_records([{"id": "12"}]).backfill_from(target)
    assert dataset.collect() == [{"id": 12}]


def test_unsupported_transfer_is_unknown_and_diagnosed() -> None:
    dataset = etl.from_records([{"id": 1}])
    frame = dataset.frame.join(dataset.frame, on="id")
    schema = etl.forward_schema(frame, dataset.schema)
    assert schema.fields[0].logical_type == "unknown"
    assert "INFER_BACKWARD_UNSUPPORTED" in {
        item["code"] for item in schema.metadata["inference_diagnostics"]
    }


def test_unknown_transfer_action_fails_closed() -> None:
    dataset = etl.from_records([{"id": 1}])
    frame = dataset.frame._extend(action="dtcs:sample", parameters={})
    schema = etl.forward_schema(frame, dataset.schema)
    assert schema.fields[0].logical_type == "unknown"
    assert "INFER_BACKWARD_UNSUPPORTED" in {
        item["code"] for item in schema.metadata["inference_diagnostics"]
    }


def test_csv_header_and_ragged_rows_are_diagnosed(tmp_path) -> None:
    header = tmp_path / "header.csv"
    header.write_text("id,name\n", encoding="utf-8")
    result = etl.infer_csv(header)
    assert [field.name for field in result.schema.fields] == ["id", "name"]

    ragged = tmp_path / "ragged.csv"
    ragged.write_text("id,name\n1\n", encoding="utf-8")
    result = etl.infer_csv(ragged)
    assert "INFER_CSV_ROW" in {diagnostic.code for diagnostic in result.diagnostics}


def test_json_array_rejects_trailing_content(tmp_path) -> None:
    path = tmp_path / "trailing.json"
    path.write_text('[{"id": 1}] trailing', encoding="utf-8")
    result = etl.infer_json(path)
    assert "INFER_JSON_PARSE" in {diagnostic.code for diagnostic in result.diagnostics}


def test_evidence_does_not_count_missing_as_null() -> None:
    result = infer_records([{"value": 1}, {"other": 2}], retain_rows=True)
    evidence = next(item for item in result.evidence if item.field == "value")
    assert evidence.null_values == 0
    assert evidence.missing_values == 1
    assert evidence.type_counts == {"integer": 1}


def test_decimal_and_binary_values_keep_logical_types() -> None:
    decimal_result = infer_records([{"value": Decimal("1.20")}])
    binary_result = infer_records([{"value": b"bytes"}])
    assert decimal_result.schema.fields[0].logical_type == "decimal"
    assert decimal_result.evidence[0].type_counts == {"decimal": 1}
    assert binary_result.schema.fields[0].logical_type == "binary"
    assert etl.model_from_schema(decimal_result.schema).model_validate(
        {"value": Decimal("2.30")}
    ).value == Decimal("2.30")


def test_decimal_literals_are_evaluated_as_decimals() -> None:
    dataset = etl.from_records([{"value": Decimal("1.20")}])
    transformed = dataset.withColumn("total", col("value") + lit(Decimal("0.10")))
    assert transformed.collect()[0]["total"] == Decimal("1.30")
    assert transformed.schema.fields[-1].logical_type == "decimal"


def test_model_field_alias_collisions_are_deterministic() -> None:
    schema = NormalizedSchema(
        "aliases",
        (NormalizedField("a-b", "string"), NormalizedField("a_b", "string")),
    )
    model = etl.model_from_schema(schema)
    assert set(model.model_fields) == {"a_b", "a_b_2"}
    assert model.model_validate({"a-b": "x", "a_b": "y"}).a_b_2 == "y"


def test_negative_limit_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        etl.from_records([{"id": 1}]).limit(-1)


def test_write_compatibility_exposes_runtime_cast_obligations() -> None:
    source = NormalizedSchema("source", (NormalizedField("id", "string"),))
    target = NormalizedSchema("target", (NormalizedField("id", "integer"),))
    result = check_write_compatibility(source, target)
    assert result.status == "conditional"
    assert result.obligations == (
        {
            "field": "id",
            "cast": "integer",
            "validation": "all_values",
            "on_failure": "error",
        },
    )


def test_decimal_csv_preserves_precision_and_redacts_path(tmp_path) -> None:
    path = tmp_path / "precise.csv"
    path.write_text("amount\n12345678901234567890.123456789\n", encoding="utf-8")
    result = etl.infer_csv(path, retain_rows=True)
    assert result.schema.fields[0].logical_type == "decimal"
    assert str(result.rows[0]["amount"]) == "12345678901234567890.123456789"
    assert str(tmp_path) not in result.schema.identity


def test_transform_preserves_prior_diagnostics_and_detects_missing_projection() -> None:
    source = etl.from_records([{"id": 1}], hints={"id": "string"})
    transformed = source.select("missing")
    codes = {diagnostic.code for diagnostic in transformed.diagnostics}
    assert "INFER_HINT_CONFLICT" in codes
    assert "INFER_LINEAGE_MISSING" in codes
    assert [field.name for field in transformed.schema.fields] == ["missing"]


def test_target_backfill_stops_at_derived_lineage() -> None:
    source = etl.from_records([{"id": "1"}]).select(
        (col("id") + lit(1)).alias("new_id")
    )
    target = NormalizedSchema(
        "target", (NormalizedField("new_id", "integer", required=True, nullable=False),)
    )
    result = source.backfill_from(target)
    assert result.schema.fields[0].logical_type == "string"
    assert "INFER_BACKWARD_UNSUPPORTED" in {d.code for d in result.diagnostics}


def test_malformed_target_schema_fails_closed() -> None:
    observation = etl.inspect_target({"fields": [{"type": "integer"}]})
    assert observation.exists == "unknown"
    assert "INFER_TARGET_UNSUPPORTED" in {d.code for d in observation.diagnostics}


def test_target_and_write_compatibility_wire_round_trip() -> None:
    target = etl.TargetObservation(
        None,
        "present",
        inspector="test",
        metadata={"empty": True},
    )
    assert (
        etl.TargetObservation.from_dict(target.to_dict()).to_dict() == target.to_dict()
    )
    compatibility = check_write_compatibility(
        NormalizedSchema("source", (NormalizedField("id", "integer"),)),
        NormalizedSchema("target", (NormalizedField("id", "number"),)),
        mode="merge",
    )
    restored = etl.WriteCompatibility.from_dict(compatibility.to_dict())
    assert restored.mode == "merge"
    assert restored.casts == {"id": "number"}
