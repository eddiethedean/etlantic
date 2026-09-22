"""Regression coverage for the 0.55 review closure work."""

import asyncio
import json
from dataclasses import replace
from decimal import Decimal

import pytest

import etlantic as etl
from etlantic.diagnostics import Diagnostic
from etlantic.exceptions import PipelineValidationError
from etlantic.inference import (
    InferenceObservation,
    OutputProposal,
    check_write_compatibility,
    infer_records,
    inspect_target,
    inspect_target_async,
    solve_backward_constraints,
)
from etlantic.schema_drift import NormalizedField, NormalizedSchema
from etlantic.storage.protocol import records_to_dicts
from etlantic.transform.functions import (
    ceil,
    col,
    floor,
    power,
    sqrt,
    to_decimal,
    to_integer,
)


def test_provider_metadata_is_json_safe_and_python_types_are_normalized() -> None:
    class Target:
        def inspect_schema(self):
            return {
                "revision": "v1",
                "fields": [
                    {
                        "name": "id",
                        "type": int,
                        "metadata": {"provider_object": object()},
                    }
                ],
            }

    observation = inspect_target(Target())
    assert observation.schema is not None
    assert observation.schema.fields[0].logical_type == "integer"
    assert observation.revision == "v1"
    json.dumps(observation.to_dict())


def test_malformed_target_payloads_fail_closed_and_empty_is_explicit() -> None:
    assert inspect_target({"fields": [1]}).exists == "unknown"
    assert inspect_target({"fields": "abc"}).exists == "unknown"
    empty = inspect_target({"fields": []})
    assert empty.exists == "present"
    assert empty.schema is None


def test_target_inspection_error_cannot_backfill_partial_schema() -> None:
    result = etl.infer_records_for_target(
        [{"id": "7"}],
        {
            "fields": [{"name": "id", "type": "integer"}],
            "diagnostics": [{"code": "PROVIDER_READ_FAILED", "severity": "error"}],
        },
    )
    assert result.schema.fields[0].logical_type == "string"
    assert "PROVIDER_READ_FAILED" in {item.code for item in result.diagnostics}


def test_lossy_target_cast_is_not_applied_to_preview_rows() -> None:
    result = etl.infer_records_for_target(
        [{"id": 1.5}],
        {"fields": [{"name": "id", "type": "integer"}]},
        retain_rows=True,
    )
    assert result.rows == ({"id": 1.5},)
    assert result.schema.fields[0].logical_type == "number"
    assert "INFER_RUNTIME_CONVERSION" in {item.code for item in result.diagnostics}


def test_unknown_target_types_are_diagnosed() -> None:
    observation = inspect_target(
        {"fields": [{"name": "value", "type": "made_up_type"}]}
    )
    assert observation.schema is not None
    assert observation.schema.fields[0].logical_type == "unknown"
    assert "INFER_UNKNOWN_TYPE" in {item.code for item in observation.diagnostics}


def test_missing_expression_reference_is_diagnosed() -> None:
    dataset = etl.from_records([{"id": 1}]).select(col("missing").alias("value"))
    assert "INFER_LINEAGE_MISSING" in {item.code for item in dataset.diagnostics}


def test_date_datetime_promotion_and_decimal_compatibility() -> None:
    import datetime as dt
    from decimal import Decimal

    result = infer_records(
        [{"value": dt.date(2024, 1, 1)}, {"value": dt.datetime(2024, 1, 2)}]
    )
    assert result.schema.fields[0].logical_type == "datetime"
    source = NormalizedSchema("source", (NormalizedField("value", "decimal"),))
    target = NormalizedSchema("target", (NormalizedField("value", "number"),))
    assert check_write_compatibility(source, target).status == "conditional"
    assert Decimal("1.0000000000000000001")


def test_path_identities_do_not_collide_on_same_filename(tmp_path) -> None:
    left = tmp_path / "left" / "events.csv"
    right = tmp_path / "right" / "events.csv"
    left.parent.mkdir()
    right.parent.mkdir()
    left.write_text("id\n1\n", encoding="utf-8")
    right.write_text("id\n1\n", encoding="utf-8")
    assert etl.infer_csv(left).schema.identity != etl.infer_csv(right).schema.identity


def test_target_revision_mismatch_does_not_backfill() -> None:
    result = etl.infer_records_for_target(
        [{"id": "1"}],
        {"revision": "v1", "fields": [{"name": "id", "type": "integer"}]},
        expected_revision="v2",
    )
    assert result.schema.fields[0].logical_type == "string"
    assert "INFER_TARGET_STALE" in {item.code for item in result.diagnostics}


def test_write_check_accepts_revision_aware_target_observation() -> None:
    observation = inspect_target(
        {
            "revision": "v1",
            "capabilities": {"write_modes": ["append"]},
            "fields": [{"name": "id", "type": "integer"}],
        }
    )
    source = NormalizedSchema("source", (NormalizedField("id", "integer"),))
    assert check_write_compatibility(source, observation).status == "proven"


def test_backward_solver_retains_qualified_source_constraint() -> None:
    dataset = etl.from_records([{"id": "1"}]).select(col("id").alias("value"))
    target = NormalizedSchema("target", (NormalizedField("value", "integer"),))
    result = solve_backward_constraints(dataset.schema, [target])
    assert result.schema.fields[0].logical_type == "integer"
    constraint = result.schema.metadata["backward_constraints"]["id"]
    assert constraint["observed_type"] == "string"
    assert constraint["target_type"] == "integer"


def test_output_proposal_is_explicit_and_row_free() -> None:
    proposal = etl.from_records([{"id": 1}]).propose_output(
        "/tmp/etlantic-review-target-does-not-exist.csv"
    )
    assert isinstance(proposal, OutputProposal)
    payload = proposal.to_dict()
    assert payload["create_required"] is True
    assert proposal.can_create is False
    assert "rows" not in payload
    json.dumps(payload)


def test_definition_and_plan_use_pipeline_definition() -> None:
    dataset = etl.from_records([{"id": 1}], name="users")
    definition = dataset.definition()
    assert definition.schema == "etlantic.pipeline/1"
    assert dataset.plan().pipeline_id == definition.pipeline_id


def test_one_shot_sampled_sources_cannot_be_exported_as_durable_definitions() -> None:
    dataset = etl.from_records(
        ({"id": index} for index in range(3)),
        limits=etl.InferenceLimits(max_rows=1),
    )
    with pytest.raises(ValueError, match="one-shot"):
        dataset.definition()


def test_definition_contains_each_portable_transformation_step() -> None:
    dataset = etl.from_records([{"id": "1", "amount": 2}], name="orders")
    transformed = dataset.withColumn("total", col("amount") + 1).select("id", "total")
    definition = transformed.definition()
    steps = [node for node in definition.nodes if node.kind == "step"]
    assert len(steps) == 2
    assert [step.transformation_id for step in steps] == [
        transformation.identity for transformation in definition.transformations
    ]
    assert len(definition.edges) == len(definition.nodes) - 1


def test_cumulative_schema_transfer_replays_from_root_schema() -> None:
    dataset = etl.from_records([{"id": "1", "amount": 2}], name="orders")
    transformed = dataset.withColumn("total", col("amount") + 1).rename(
        {"id": "order_id"}
    )
    assert {field.name for field in transformed.schema.fields} == {
        "order_id",
        "amount",
        "total",
    }
    assert transformed.schema.metadata["lineage_version"] == 1
    assert transformed.schema.metadata["lineage_fingerprint"]


def test_mapping_record_is_inferred_as_records_not_schema() -> None:
    result = etl.infer_source({"id": 1, "name": "Ada"})
    assert [field.name for field in result.schema.fields] == ["id", "name"]


def test_target_capabilities_and_revision_are_retained_for_writes() -> None:
    observation = inspect_target(
        {
            "revision": "r1",
            "keys": ["id"],
            "capabilities": {"write_modes": ["append", "merge"]},
            "fields": [{"name": "id", "type": "integer"}],
        }
    )
    assert observation.schema is not None
    source = NormalizedSchema("source", (NormalizedField("id", "integer"),))
    assert check_write_compatibility(source, observation, mode="merge").compatible
    assert not check_write_compatibility(
        source, observation, mode="overwrite"
    ).compatible


def test_wire_diagnostic_round_trip_rehydrates_diagnostic() -> None:
    result = infer_records([{"id": None}])
    restored = InferenceObservation.from_dict(result.to_observation().to_dict())
    assert all(isinstance(item, Diagnostic) for item in restored.diagnostics)


def test_wire_ingress_redacts_row_like_metadata_and_preserves_target_identity() -> None:
    observation = InferenceObservation.from_dict(
        {
            "schema": {
                "identity": "source",
                "fields": [],
                "metadata": {"sampleRows": [{"id": 1}]},
            },
            "provenance": {"provider_payload": [{"id": 1}]},
        }
    )
    assert observation.schema.metadata["sampleRows"] == "<redacted>"
    assert observation.provenance["provider_payload"] == "<redacted>"
    target = etl.TargetObservation.from_dict(
        {"identity": "target-x", "exists": "present", "schema": None}
    )
    assert target.identity == "target-x"


def test_local_provider_conversion_without_head_fails_closed() -> None:
    from etlantic.dataframe.local import LocalDataframePlugin

    class Unbounded:
        def to_dicts(self):
            raise AssertionError("unbounded conversion must not run")

    result = LocalDataframePlugin().inspect_schema(Unbounded(), identity="source")
    assert result is not None
    assert result["diagnostics"][0]["code"] == "INFER_SOURCE_UNBOUNDED"


def test_provider_head_must_return_a_distinct_bounded_view() -> None:
    class Unbounded:
        def head(self, count):
            return self

        def to_dicts(self):
            raise AssertionError("self-returning head must not be materialized")

    result = etl.infer_source(Unbounded(), limits=etl.InferenceLimits(max_rows=2))
    assert "INFER_SOURCE_UNBOUNDED" in {item.code for item in result.diagnostics}


def test_provider_iterator_failure_is_a_bounded_diagnostic() -> None:
    def broken():
        yield {"id": 1}
        raise RuntimeError("provider failure")

    result = etl.infer_records(broken())
    assert result.schema.fields[0].name == "id"
    assert "INFER_SOURCE_UNSUPPORTED" in {item.code for item in result.diagnostics}


def test_invalid_csv_options_are_diagnosed(tmp_path) -> None:
    path = tmp_path / "rows.csv"
    path.write_text("id\n1\n", encoding="utf-8")
    result = etl.infer_csv(path, options=123)  # type: ignore[arg-type]
    assert "INFER_CSV_OPTIONS" in {item.code for item in result.diagnostics}


def test_jsonl_byte_limit_precedes_oversized_line_parse(tmp_path) -> None:
    path = tmp_path / "rows.jsonl"
    path.write_text('{"value":"this line is too large"}\n', encoding="utf-8")
    result = etl.infer_json(
        path, lines=True, limits=etl.InferenceLimits(max_rows=10, max_bytes=8)
    )
    assert result.schema.fields == ()
    assert "INFER_LIMIT" in {item.code for item in result.diagnostics}


def test_csv_field_limit_precedes_oversized_field_parse(tmp_path) -> None:
    path = tmp_path / "rows.csv"
    path.write_text("value\nthis value is too large\n", encoding="utf-8")
    result = etl.infer_csv(path, limits=etl.InferenceLimits(max_rows=10, max_bytes=8))
    assert result.schema.fields[0].metadata["header_only"] is True
    assert "INFER_SOURCE_UNSUPPORTED" in {item.code for item in result.diagnostics}


def test_datafusion_schema_is_metadata_first_when_installed() -> None:
    datafusion = pytest.importorskip("datafusion")
    context = datafusion.SessionContext()
    frame = context.from_pydict({"id": [1], "name": ["x"]})
    result = etl.infer_source(frame, identity="datafusion")
    assert [(field.name, field.logical_type) for field in result.schema.fields] == [
        ("id", "integer"),
        ("name", "string"),
    ]


def test_identical_observations_are_byte_stable() -> None:
    left = infer_records([{"id": 1}]).to_dict()
    right = infer_records([{"id": 1}]).to_dict()
    assert json.dumps(left, sort_keys=True, separators=(",", ":")) == json.dumps(
        right, sort_keys=True, separators=(",", ":")
    )


def test_metadata_aliases_and_paths_are_redacted() -> None:
    from etlantic.schema_drift import json_safe_metadata

    payload = json_safe_metadata(
        {
            "sampleRows": [{"secret": "row"}],
            "provider_payload": {"token": "secret"},
            "path": "/Users/example/input.csv",
        }
    )
    assert payload == {
        "sampleRows": "<redacted>",
        "provider_payload": "<redacted>",
        "path": "<path-redacted>",
    }


def test_optional_non_nullable_model_rejects_explicit_null() -> None:
    from pydantic import ValidationError

    model = etl.model_from_schema(
        NormalizedSchema(
            "optional",
            (NormalizedField("id", "integer", required=False, nullable=False),),
        )
    )
    model.model_validate({})
    with pytest.raises(ValidationError):
        model.model_validate({"id": None})


def test_target_inspector_error_fails_closed_even_with_schema() -> None:
    observation = inspect_target(
        {
            "fields": [{"name": "id", "type": "integer"}],
            "diagnostics": [
                {"code": "DENIED", "severity": "error", "message": "denied"}
            ],
        }
    )
    result = check_write_compatibility(
        NormalizedSchema("source", (NormalizedField("id", "integer"),)), observation
    )
    assert result.compatible is False
    assert "INFER_TARGET_UNKNOWN" in {item.code for item in result.diagnostics}


def test_target_observation_round_trips_into_durable_definitions() -> None:
    dataset = etl.from_records_for_target(
        [{"id": "7"}],
        {
            "revision": "r1",
            "capabilities": {"write_modes": ["append", "merge"]},
            "fields": [{"name": "id", "type": "integer"}],
        },
        name="users",
    )
    observation = dataset.observation.to_dict()
    restored = InferenceObservation.from_dict(observation)
    assert restored.target_observation is not None
    assert restored.target_observation.revision == "r1"
    definition = dataset.definition().to_dict()
    assert "r1" in json.dumps(definition, sort_keys=True)
    assert "merge" in json.dumps(definition, sort_keys=True)


@pytest.mark.parametrize("severity", ["ERROR", "Warning"])
def test_any_target_diagnostic_fails_closed_and_normalizes_severity(
    severity: str,
) -> None:
    observation = inspect_target(
        {
            "fields": [{"name": "id", "type": "integer"}],
            "diagnostics": [{"code": "DENIED", "severity": severity}],
        }
    )
    assert observation.diagnostics[0].severity.value == severity.lower()
    result = etl.infer_records_for_target([{"id": "7"}], observation, retain_rows=True)
    assert result.schema.fields[0].logical_type == "string"
    assert result.target_observation == observation
    assert result.provenance["target_validation"] == "failed"
    compatibility = check_write_compatibility(
        NormalizedSchema("source", (NormalizedField("id", "integer"),)), observation
    )
    assert compatibility.compatible is False
    assert "INFER_TARGET_UNKNOWN" in {item.code for item in compatibility.diagnostics}


def test_metadata_redaction_preserves_inference_control_values() -> None:
    from etlantic.schema_drift import json_safe_metadata

    safe = json_safe_metadata(
        {"max_rows": 2, "rows_observed": 2, "sampled": True, "sampleRows": [{"id": 1}]}
    )
    assert safe == {
        "max_rows": 2,
        "rows_observed": 2,
        "sampled": True,
        "sampleRows": "<redacted>",
    }


def test_provider_head_must_prove_conversion_bound() -> None:
    class Provider:
        def inspect_schema(self):
            return {"fields": [{"name": "id", "type": "integer"}]}

        def head(self, count):
            return View()

    class View:
        def to_dicts(self):
            return [{"id": index} for index in range(1000)]

    result = etl.infer_source(Provider(), limits=etl.InferenceLimits(max_rows=2))
    assert "INFER_SOURCE_UNBOUNDED" in {item.code for item in result.diagnostics}


def test_storage_materialization_is_bounded_by_default() -> None:
    consumed = 0

    def rows():
        nonlocal consumed
        for index in range(1000):
            consumed += 1
            yield {"id": index}

    with pytest.raises(ValueError, match="max_rows"):
        records_to_dicts(rows(), max_rows=2)
    assert consumed == 3


def test_preview_evaluator_covers_numeric_and_conversion_functions() -> None:
    dataset = etl.from_records([{"value": 9.5, "text": "9"}]).select(
        floor(col("value")).alias("floor"),
        ceil(col("value")).alias("ceil"),
        power(col("value"), 2).alias("power"),
        sqrt(col("value")).alias("sqrt"),
        to_integer(col("text")).alias("integer"),
        to_decimal(col("text")).alias("decimal"),
    )
    row = dataset.preview()[0]
    assert row["floor"] == 9
    assert row["ceil"] == 10
    assert row["power"] == 90.25
    assert row["sqrt"] == pytest.approx(3.0822, rel=1e-4)
    assert row["integer"] == 9
    assert row["decimal"] == Decimal("9")
    assert not {
        item.code
        for item in dataset.diagnostics
        if getattr(item.severity, "value", item.severity) == "error"
    }


def test_preview_evaluator_rejects_lossy_explicit_cast() -> None:
    dataset = etl.from_records([{"value": Decimal("9007199254740993")}]).withColumn(
        "converted", col("value").cast("number")
    )
    assert "INFER_RUNTIME_CONVERSION" in {item.code for item in dataset.diagnostics}


def test_schema_only_targets_do_not_invent_revisions() -> None:
    schema = NormalizedSchema("target", (NormalizedField("id", "integer"),))
    assert inspect_target(schema).revision is None

    class AsyncAdapter:
        async def schema(self):
            return schema

    assert asyncio.run(inspect_target_async(AsyncAdapter())).revision is None


def test_target_guidance_does_not_replace_observed_source_contract() -> None:
    dataset = etl.from_records_for_target(
        [{"id": "1"}],
        {
            "revision": "r1",
            "capabilities": {"write_modes": ["append"]},
            "fields": [{"name": "id", "type": "integer"}],
        },
        name="orders",
    )

    definition = dataset.definition()
    source_field = definition.contracts[0].fields[0]
    assert source_field.type == "string"
    assert definition.nodes[-1].bindings["target"]["revision"] == "r1"
    assert (
        definition.nodes[-1].bindings["target"]["requirements"]["fields"][0][
            "logical_type"
        ]
        == "integer"
    )


def test_inferred_definition_round_trips_and_plans_without_runtime_source() -> None:
    dataset = etl.from_records_for_target(
        [{"id": "1"}],
        {
            "revision": "r1",
            "capabilities": {"write_modes": ["append"]},
            "fields": [{"name": "id", "type": "integer"}],
        },
        name="orders",
    )
    restored = etl.authoring.pipeline_from_dict(dataset.definition().to_dict())
    report = etl.authoring.validate_pipeline_like(restored)
    assert report.valid
    assert etl.authoring.plan_pipeline_like(restored).pipeline_name == "orders"


def test_file_bindings_are_row_free_and_rebindable(tmp_path) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    first.write_text("id\n1\n", encoding="utf-8")
    second.write_text("id\n2\n", encoding="utf-8")

    definition = etl.read_csv(str(first), name="events").definition()
    binding = definition.nodes[0].bindings["source"]
    assert binding["kind"] == "file"
    assert binding["uri"].startswith("file-ref:")
    definition_json = json.dumps(definition.to_dict())
    assert str(first.resolve()) not in definition_json
    assert "\n1\n" not in definition_json

    rebound = etl.rebind_definition(definition, source=str(second))
    rebound_uri = rebound.nodes[0].bindings["source"]["uri"]
    assert rebound_uri.startswith("file-ref:")
    assert rebound_uri != binding["uri"]
    assert etl.authoring.pipeline_from_dict(rebound.to_dict()).fingerprint

    resolved = etl.resolve_source_binding(binding)
    assert resolved.path == first.resolve()


def test_file_binding_reopens_with_parser_options(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id;name\n1;one\n", encoding="utf-8")

    dataset = etl.read_csv(
        str(path), name="semicolon_events", options={"delimiter": ";"}
    )
    reopened = etl.reopen_source_binding(
        dataset.definition().nodes[0].bindings["source"]
    )
    assert reopened.preview() == [{"id": 1, "name": "one"}]


def test_rebinding_preserves_valid_binding_mappings(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id\n1\n", encoding="utf-8")

    definition = etl.read_csv(str(path), name="events").definition()
    source_binding = definition.nodes[0].bindings["source"]
    target_binding = definition.nodes[-1].bindings["target"]
    rebound = etl.rebind_definition(
        definition, source=source_binding, target=target_binding
    )

    assert rebound.nodes[0].bindings["source"]["kind"] == "file"
    assert rebound.nodes[-1].bindings["target"]["kind"] == "target"


def test_backfill_preserves_the_durable_source_binding() -> None:
    target = NormalizedSchema("target", (NormalizedField("id", "integer"),))
    dataset = etl.from_records([{"id": "12"}], name="orders").backfill_from(
        target
    )

    assert dataset.definition().nodes[0].bindings["source"]["kind"] == "records"


def test_sampled_csv_with_a_file_binding_can_be_exported(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id\n1\n2\n", encoding="utf-8")

    definition = etl.read_csv(
        str(path), limits=etl.InferenceLimits(max_rows=1)
    ).definition()
    assert definition.nodes[0].bindings["source"]["kind"] == "file"


def test_sampled_one_shot_source_can_be_explicitly_rebound(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id\n1\n", encoding="utf-8")
    dataset = etl.from_records(
        ({"id": value} for value in (1, 2)),
        limits=etl.InferenceLimits(max_rows=1),
    )

    definition = dataset.rebind_source(str(path))
    assert definition.nodes[0].bindings["source"]["kind"] == "file"


def test_jsonl_rebinding_detects_line_format(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text('{"id": 1}\n{"id": 2}\n', encoding="utf-8")

    definition = etl.from_records([{"id": 1}], name="events").definition()
    binding = etl.rebind_definition(definition, source=str(path)).nodes[0].bindings[
        "source"
    ]
    assert binding["format"] == "jsonl"
    assert etl.reopen_source_binding(binding).preview() == [{"id": 1}, {"id": 2}]


def test_reopened_generator_binding_keeps_its_factory() -> None:
    key = "test-reopened-generator-binding"

    def factory():
        return ({"id": value} for value in (1, 2))

    etl.register_source_factory(key, factory)
    try:
        binding = {
            "version": 1,
            "kind": "records",
            "identity": "generator",
            "resolver": "registry",
            "factory_key": key,
        }
        reopened = etl.reopen_source_binding(
            binding, limits=etl.InferenceLimits(max_rows=1)
        )
        assert reopened.definition().nodes[0].bindings["source"]["factory_key"] == key
    finally:
        etl.unregister_source_factory(key)


def test_provider_source_can_be_explicitly_rebound(tmp_path) -> None:
    class Frame:
        def __init__(self) -> None:
            self.schema = {"id": int}

    target = tmp_path / "rebound.csv"
    target.write_text("id\n1\n", encoding="utf-8")
    definition = etl.from_pandas(Frame(), name="frame").rebind_source(str(target))
    assert definition.nodes[0].bindings["source"]["kind"] == "file"


def test_records_definition_requires_a_registered_factory() -> None:
    dataset = etl.from_records(
        ({"id": value} for value in (1, 2)), name="one_shot_records"
    )
    with pytest.raises(ValueError, match="INFER_SOURCE_UNRESOLVABLE"):
        dataset.definition()


def test_materialized_records_register_a_runtime_reopen_factory() -> None:
    dataset = etl.from_records([{"id": 1}], name="materialized_records")
    binding = dataset.definition().nodes[0].bindings["source"]
    assert etl.resolve_source_binding(binding) == [{"id": 1}]


def test_records_bindings_do_not_alias_same_named_sources() -> None:
    first = etl.from_records([{"id": 1}], name="same_name")
    first_binding = first.definition().nodes[0].bindings["source"]
    etl.from_records([{"id": 2}], name="same_name")

    assert etl.resolve_source_binding(first_binding) == [{"id": 1}]


def test_identical_materialized_records_have_deterministic_definitions() -> None:
    first = etl.from_records([{"id": 1}], name="same_name").definition()
    second = etl.from_records([{"id": 1}], name="same_name").definition()

    assert first.fingerprint == second.fingerprint
    assert first.nodes[0].bindings["source"] == second.nodes[0].bindings["source"]


def test_reloaded_definition_fails_closed_when_source_factory_is_missing() -> None:
    dataset = etl.from_records([{"id": 1}], name="missing_factory")
    document = dataset.definition().to_dict()
    binding = document["nodes"][0]["bindings"]["source"]
    etl.unregister_source_factory(binding["factory_key"])

    restored = etl.authoring.pipeline_from_dict(document)
    report = etl.authoring.validate_pipeline_like(restored)
    assert not report.valid
    assert "INFER_SOURCE_UNRESOLVABLE" in {item.code for item in report.errors}
    with pytest.raises(PipelineValidationError) as exc_info:
        etl.authoring.plan_pipeline_like(restored)
    assert "INFER_SOURCE_UNRESOLVABLE" in {
        item.code for item in exc_info.value.report.errors
    }


def test_target_revision_is_rechecked_before_definition() -> None:
    state = {"revision": "r1"}
    dataset = etl.from_records_for_target(
        [{"id": "1"}],
        {"revision": "r1", "fields": [{"name": "id", "type": "integer"}]},
        name="revisioned_target",
        revision_reader=lambda: state["revision"],
    )
    state["revision"] = "r2"

    with pytest.raises(ValueError, match="INFER_TARGET_STALE"):
        dataset.definition()


def test_malformed_csv_options_keep_the_inference_diagnostic(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id\n1\n", encoding="utf-8")

    dataset = etl.read_csv(str(path), options=["bad"])
    with pytest.raises(ValueError, match="INFER_CSV_OPTIONS"):
        dataset.definition()


def test_rebinding_rejects_malformed_source_and_target_bindings() -> None:
    definition = etl.from_records([{"id": 1}], name="binding_shape").definition()

    with pytest.raises(ValueError, match="INFER_SOURCE_BINDING"):
        etl.rebind_definition(definition, source={"version": 1})
    with pytest.raises(ValueError, match="INFER_TARGET_BINDING"):
        etl.rebind_definition(definition, target={"version": 1})


def test_loaded_bindings_validate_parser_options_and_target_requirements(tmp_path) -> None:
    path = tmp_path / "events.csv"
    path.write_text("id\n1\n", encoding="utf-8")
    definition = etl.read_csv(path, name="events").definition()

    bad_source = {
        "version": 1,
        "kind": "file",
        "format": "csv",
        "identity": "events",
        "uri": definition.nodes[0].bindings["source"]["uri"],
        "options": {"delimiter": ["bad"]},
    }
    source_node = replace(definition.nodes[0], bindings={"source": bad_source})
    bad_source_definition = replace(
        definition,
        nodes=(source_node, *definition.nodes[1:]),
        fingerprint=None,
    ).with_fingerprint(None)
    source_report = etl.authoring.validate_pipeline_like(bad_source_definition)
    assert not source_report.valid
    assert "INFER_SOURCE_BINDING" in {item.code for item in source_report.errors}

    bad_target = {
        "version": 1,
        "kind": "target",
        "identity": "events",
        "write_mode": "append",
        "observed": True,
        "requirements": {"fields": "malformed"},
    }
    sink_node = replace(definition.nodes[-1], bindings={"target": bad_target})
    bad_target_definition = replace(
        definition,
        nodes=(*definition.nodes[:-1], sink_node),
        fingerprint=None,
    ).with_fingerprint(None)
    target_report = etl.authoring.validate_pipeline_like(bad_target_definition)
    assert not target_report.valid
    assert "INFER_TARGET_BINDING" in {item.code for item in target_report.errors}


def test_target_backfill_exports_an_explicit_cast_boundary() -> None:
    dataset = etl.from_records_for_target(
        [{"id": "1"}],
        {
            "revision": "r1",
            "capabilities": {"write_modes": ["append"]},
            "fields": [{"name": "id", "type": "integer"}],
        },
        name="orders",
    )

    definition = dataset.definition()
    assert [field.type for field in definition.contracts[0].fields] == ["string"]
    assert [field.type for field in definition.contracts[1].fields] == ["integer"]
    assert definition.transformations[0].portable_plan["parameters"]["assignments"]


def test_target_write_mode_must_be_advertised() -> None:
    dataset = etl.from_records_for_target(
        [{"id": 1}],
        {
            "revision": "r1",
            "capabilities": {"write_modes": ["merge"]},
            "keys": ["id"],
            "fields": [{"name": "id", "type": "integer"}],
        },
        name="orders",
    )

    with pytest.raises(ValueError, match="INFER_TARGET_WRITE_UNQUALIFIED"):
        dataset.definition()

    merge_dataset = etl.from_records_for_target(
        [{"id": 1}],
        {
            "revision": "r1",
            "capabilities": {"write_modes": ["merge"]},
            "keys": ["id"],
            "fields": [{"name": "id", "type": "integer"}],
        },
        name="orders",
        write_mode="merge",
    )
    assert merge_dataset.definition().nodes[-1].bindings["target"]["write_mode"] == "merge"


def test_loaded_malformed_bindings_fail_closed() -> None:
    document = etl.from_records([{"id": 1}], name="loaded_binding_shape").definition()
    payload = document.to_dict()
    payload["nodes"][0]["bindings"]["source"] = {"version": 1}
    payload["nodes"][-1]["bindings"]["target"] = {"version": 1}
    payload.pop("fingerprint")

    restored = etl.authoring.pipeline_from_dict(payload, verify=False)
    report = etl.authoring.validate_pipeline_like(restored)
    assert not report.valid
    assert {"INFER_SOURCE_BINDING", "INFER_TARGET_BINDING"} <= {
        item.code for item in report.errors
    }


def test_unsupported_provider_does_not_look_durable() -> None:
    class Frame:
        def to_dicts(self):
            return [{"id": 1}]

        def head(self, count):
            return self

    dataset = etl.from_pandas(Frame(), name="frame")
    with pytest.raises(ValueError, match="INFER_SOURCE_UNSUPPORTED"):
        dataset.definition()
