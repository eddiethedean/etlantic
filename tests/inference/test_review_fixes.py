"""Regression coverage for the 0.55 review closure work."""

import json

import pytest

import etlantic as etl
from etlantic.diagnostics import Diagnostic
from etlantic.inference import (
    InferenceObservation,
    OutputProposal,
    check_write_compatibility,
    infer_records,
    inspect_target,
    solve_backward_constraints,
)
from etlantic.schema_drift import NormalizedField, NormalizedSchema
from etlantic.transform.functions import col


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


def test_missing_expression_reference_is_diagnosed() -> None:
    dataset = etl.from_records([{"id": 1}]).select(col("missing").alias("value"))
    assert "INFER_LINEAGE_MISSING" in {item.code for item in dataset.diagnostics}


def test_date_datetime_promotion_and_decimal_compatibility() -> None:
    import datetime as dt
    from decimal import Decimal

    result = infer_records([{"value": dt.date(2024, 1, 1)}, {"value": dt.datetime(2024, 1, 2)}])
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
        {"revision": "v1", "fields": [{"name": "id", "type": "integer"}]}
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
    transformed = dataset.withColumn("total", col("amount") + 1).rename({"id": "order_id"})
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


def test_local_provider_conversion_without_head_fails_closed() -> None:
    from etlantic.dataframe.local import LocalDataframePlugin

    class Unbounded:
        def to_dicts(self):
            raise AssertionError("unbounded conversion must not run")

    result = LocalDataframePlugin().inspect_schema(Unbounded(), identity="source")
    assert result is not None
    assert result["diagnostics"][0]["code"] == "INFER_SOURCE_UNBOUNDED"


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
            "diagnostics": [{"code": "DENIED", "severity": "error", "message": "denied"}],
        }
    )
    result = check_write_compatibility(
        NormalizedSchema("source", (NormalizedField("id", "integer"),)), observation
    )
    assert result.compatible is False
    assert "INFER_TARGET_UNKNOWN" in {item.code for item in result.diagnostics}
