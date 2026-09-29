# pyright: reportMissingParameterType=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false
"""Focused regression coverage for the remaining 0.55 review blockers."""

import asyncio
import json
import time
from collections.abc import ItemsView, Iterator, Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

import etlantic as etl
from etlantic.inference import schema_documents
from etlantic.inference.durable import validate_target_binding
from etlantic.inference.facade import _eval
from etlantic.inference.targets import infer_records_for_target, inspect_target
from etlantic.schema_drift import NormalizedField, NormalizedSchema, json_safe_metadata
from etlantic.storage.protocol import records_to_dicts
from etlantic.transform.functions import col, to_integer, when


def test_nested_provider_values_and_identity_are_redacted_on_wire() -> None:
    payload = json_safe_metadata(
        {
            "context": {"record_hint": "alice@example.com", "source_value": 42},
            "identity": "/Users/alice/private/events",
        }
    )
    encoded = json.dumps(payload, sort_keys=True)
    assert "alice@example.com" not in encoded
    assert "/Users/alice" not in encoded


def test_metadata_serialization_bounds_mapping_traversal() -> None:
    class Wide(Mapping[str, int]):
        def __init__(self, width: int) -> None:
            self.width = width
            self.key_visits = 0
            self.value_reads = 0

        def __len__(self) -> int:
            return self.width

        def __iter__(self) -> Iterator[str]:
            for index in range(self.width):
                self.key_visits += 1
                yield str(index)

        def __getitem__(self, key: str) -> int:
            self.value_reads += 1
            return int(key)

    wide = Wide(1_000)
    assert json_safe_metadata(wide) == {}
    assert wide.key_visits == 257
    assert wide.value_reads == 0


def test_record_size_estimation_stops_at_the_materialized_byte_budget() -> None:
    class Wide(Mapping[str, int]):
        def __init__(self, width: int) -> None:
            self.width = width
            self.reads = 0
            self.item_visits = 0

        def __len__(self) -> int:
            return self.width

        def __iter__(self) -> Iterator[str]:
            return (str(index) for index in range(self.width))

        def __getitem__(self, key: str) -> int:
            self.reads += 1
            return 1

        def items(self) -> ItemsView[str, int]:
            self.item_visits += 1
            return ItemsView(self)

    row = Wide(10_000)
    result = etl.infer_records(
        [row],
        limits=etl.InferenceLimits(
            max_rows=1,
            max_fields=1,
            max_materialized_bytes=1,
        ),
    )

    assert row.reads == 1
    assert row.item_visits == 0
    assert result.provenance["limit_reason"] == "materialized_bytes"
    assert "INFER_LIMIT" in {item.code for item in result.diagnostics}


def test_record_field_traversal_is_capped_and_nested_cycles_are_safe() -> None:
    class Wide(Mapping[str, int]):
        def __init__(self, width: int) -> None:
            self.width = width
            self.reads = 0

        def __len__(self) -> int:
            return self.width

        def __iter__(self) -> Iterator[str]:
            return (str(index) for index in range(self.width))

        def __getitem__(self, key: str) -> int:
            self.reads += 1
            return 1

    wide = Wide(10_000)
    bounded = etl.infer_records(
        [wide],
        limits=etl.InferenceLimits(max_rows=1, max_fields=1, max_bytes=10_000),
    )
    assert [field.name for field in bounded.schema.fields] == ["0"]
    assert wide.reads <= 2
    assert bounded.provenance["limit_reason"] == "fields"

    replay_source = [{"a": 1, "extra": 2}, {"a": 3}]
    replayed = etl.infer_records(
        replay_source,
        limits=etl.InferenceLimits(max_fields=1),
        retain_rows=True,
    )
    replay = replayed.replay
    assert replay is not None
    assert list(replay.take()) == replay_source

    cyclic = {"payload": []}
    cyclic["payload"].append(cyclic)
    result = etl.infer_records([cyclic])
    assert result.schema.fields[0].logical_type == "array"


def test_global_field_limit_replays_the_row_that_introduces_a_new_field() -> None:
    records = [{"a": 1, "b": 2}, {"c": 3, "a": 4}]

    result = etl.infer_records(
        records,
        limits=etl.InferenceLimits(max_fields=2),
        retain_rows=True,
    )

    assert result.provenance["limit_reason"] == "fields"
    assert result.replay is not None
    assert list(result.replay.take()) == records


def test_json_whitespace_is_charged_to_raw_not_materialized_bytes(
    tmp_path: Path,
) -> None:
    jsonl = tmp_path / "whitespace.jsonl"
    jsonl.write_text(" " * 100 + '{"id": 1}\n', encoding="utf-8")
    array = tmp_path / "whitespace.json"
    array.write_text('[{"id"' + " " * 100 + ": 1}]", encoding="utf-8")
    limits = etl.InferenceLimits(max_bytes=1_000, max_materialized_bytes=64)

    results = [
        etl.infer_json(jsonl, lines=True, limits=limits, retain_rows=True),
        etl.infer_json(array, limits=limits, retain_rows=True),
    ]

    for result in results:
        assert [field.name for field in result.schema.fields] == ["id"]
        assert result.rows == ({"id": 1},)
        assert result.provenance["limit_reason"] is None
        assert result.provenance["materialized_bytes_observed"] <= 64


def test_json_sources_report_row_and_raw_byte_limit_reasons(
    tmp_path: Path,
) -> None:
    cases = (
        (etl.InferenceLimits(max_rows=1, max_bytes=1_000), "rows"),
        (etl.InferenceLimits(max_rows=10, max_bytes=4), "raw_bytes"),
    )
    for lines in (False, True):
        suffix = ".jsonl" if lines else ".json"
        path = tmp_path / f"bounded{suffix}"
        path.write_text(
            '{"id": 1}\n{"id": 2}\n' if lines else '[{"id": 1}, {"id": 2}]',
            encoding="utf-8",
        )
        for limits, expected_reason in cases:
            result = etl.infer_json(path, lines=lines, limits=limits)

            assert result.provenance["sampled"] is True
            assert result.provenance["limit_reason"] == expected_reason
            assert expected_reason in result.provenance["limit_reasons"]
            assert "INFER_LIMIT" in {item.code for item in result.diagnostics}


def test_provider_stages_share_one_inference_deadline() -> None:
    class View:
        __etlantic_bounded_view__ = True

        def __iter__(self) -> Iterator[Mapping[str, int]]:
            time.sleep(0.07)
            yield {"id": 1}

    class Provider:
        def head(self, count: int) -> View:
            assert count == 2
            time.sleep(0.07)
            return View()

        def to_dicts(self) -> list[Mapping[str, int]]:
            raise AssertionError("the bounded view must be iterated directly")

    result = etl.infer_source(
        Provider(),
        limits=etl.InferenceLimits(max_rows=2, timeout_seconds=0.1),
    )

    assert "INFER_LIMIT" in {item.code for item in result.diagnostics}
    assert result.provenance["sampled"] is True
    assert result.provenance["limit_reason"] == "time"


def test_record_size_estimation_redacts_provider_failures_and_bounds_depth() -> None:
    class Broken(Mapping[str, int]):
        def __len__(self) -> int:
            return 1

        def __iter__(self) -> Iterator[str]:
            raise RuntimeError("private provider detail")

        def __getitem__(self, key: str) -> int:
            raise AssertionError("field access should not follow iterator failure")

    failed = etl.infer_records([Broken()])
    assert "INFER_SOURCE_UNSUPPORTED" in {item.code for item in failed.diagnostics}
    assert "private provider detail" not in repr(failed.diagnostics)
    assert failed.provenance["source_validation"] == "failed"

    nested = 1
    for _ in range(20):
        nested = [nested]
    bounded = etl.infer_records(
        [{"value": nested}],
        limits=etl.InferenceLimits(max_rows=1, max_fields=1, max_bytes=1_000_000),
    )
    assert bounded.provenance["limit_reason"] == "traversal"
    assert "INFER_LIMIT" in {item.code for item in bounded.diagnostics}


def test_provider_schema_with_non_field_items_fails_closed() -> None:
    class Provider:
        def inspect_schema(self):
            return {"fields": [1]}

    result = etl.infer_source(Provider())
    assert not result.schema.fields
    assert "INFER_SOURCE_UNSUPPORTED" in {item.code for item in result.diagnostics}


@pytest.mark.parametrize("flag", ("required", "nullable"))
def test_provider_schema_boolean_flags_are_validated(flag: str) -> None:
    class Provider:
        def inspect_schema(self):
            return {"fields": [{"name": "id", "type": "integer", flag: "false"}]}

    result = etl.infer_source(Provider())

    assert not result.schema.fields
    assert "INFER_SOURCE_UNSUPPORTED" in {item.code for item in result.diagnostics}


def test_normalized_provider_schema_boolean_flags_are_validated() -> None:
    class Provider:
        def inspect_schema(self):
            return NormalizedSchema(
                "provider",
                (NormalizedField("id", "integer", required=cast(bool, "false")),),
            )

    result = etl.infer_source(Provider())

    assert not result.schema.fields
    assert "INFER_SOURCE_UNSUPPORTED" in {item.code for item in result.diagnostics}


def test_async_provider_preview_matches_sync_bounded_preview() -> None:
    class View:
        __etlantic_bounded_view__ = True

        def __init__(self):
            self.rows = [{"id": 1}, {"id": 2}]

    class Provider:
        async def inspect_schema(self):
            return {"fields": [{"name": "id", "type": "integer"}]}

        def head(self, count):
            assert count == 2
            return View()

    result = asyncio.run(
        etl.infer_source_async(Provider(), limits=etl.InferenceLimits(max_rows=2))
    )
    assert result.rows == ({"id": 1}, {"id": 2})
    assert result.provenance["preview_available"] is True


def test_async_inspect_schema_obeys_the_shared_inference_deadline() -> None:
    cancelled: list[bool] = []

    class Provider:
        async def inspect_schema(self):
            try:
                await asyncio.sleep(1)
            finally:
                cancelled.append(True)

    result = asyncio.run(
        etl.infer_source_async(
            Provider(), limits=etl.InferenceLimits(timeout_seconds=0.02)
        )
    )

    assert cancelled == [True]
    assert "INFER_LIMIT" in {item.code for item in result.diagnostics}
    assert result.provenance["limit_reason"] == "time"


def test_async_schema_obeys_the_shared_inference_deadline() -> None:
    cancelled: list[bool] = []

    class Provider:
        async def schema(self):
            try:
                await asyncio.sleep(1)
            finally:
                cancelled.append(True)

    result = asyncio.run(
        etl.infer_source_async(
            Provider(), limits=etl.InferenceLimits(timeout_seconds=0.02)
        )
    )

    assert cancelled == [True]
    assert "INFER_LIMIT" in {item.code for item in result.diagnostics}
    assert result.provenance["limit_reason"] == "time"


def test_unknown_provider_source_size_keeps_preview_provisional() -> None:
    class View:
        __etlantic_bounded_view__ = True

        def __init__(self) -> None:
            self.rows = [{"id": 1}]

    class Provider:
        def inspect_schema(self):
            return {"fields": [{"name": "id", "type": "integer"}]}

        def head(self, count: int) -> View:
            assert count == 10
            return View()

    result = etl.infer_source(Provider(), limits=etl.InferenceLimits(max_rows=10))

    assert result.provenance["sampled"] is True
    assert (
        "provider_preview_truncated_or_unverified" in result.provenance["limitations"]
    )
    assert result.schema.fields[0].required is False
    assert result.schema.fields[0].nullable is True


def test_target_diagnostics_and_provider_identity_are_bounded_and_retained() -> None:
    class Provider:
        def inspect_schema(self):
            return {
                "identity": "provider-target",
                "fields": [{"name": "id", "type": "integer"}],
                "diagnostics": [
                    {"code": f"D{index}", "severity": "warning"} for index in range(10)
                ],
            }

    observation = inspect_target(Provider(), identity="caller", max_diagnostics=1)
    assert observation.identity == "provider-target"
    assert len(observation.diagnostics) == 1


@pytest.mark.parametrize(
    "marker", ("has_default", "generated", "identity", "auto_increment")
)
def test_malformed_target_omission_markers_do_not_qualify_writes(marker: str) -> None:
    target = inspect_target(
        {
            "identity": f"malformed-{marker}",
            "exists": "present",
            "capabilities": {"write_modes": ["append"]},
            "fields": [
                {
                    "name": "id",
                    "type": "integer",
                    "required": True,
                    "nullable": False,
                    marker: "false",
                }
            ],
        }
    )
    source = etl.infer_records([{"id": 1}, {}]).schema

    compatibility = etl.check_write_compatibility(source, target)

    assert not compatibility.compatible
    assert "INFER_WRITE_INCOMPATIBLE" in {
        item.code for item in compatibility.diagnostics
    }


def test_redacted_compatible_target_default_preserves_omission_safety() -> None:
    source = etl.infer_records([{"id": 1}]).schema
    target = inspect_target(
        {
            "identity": "default-target",
            "exists": "present",
            "capabilities": {"write_modes": ["append"]},
            "fields": [
                {
                    "name": "id",
                    "type": "integer",
                    "required": True,
                    "nullable": False,
                },
                {
                    "name": "created_at",
                    "type": "integer",
                    "required": True,
                    "nullable": False,
                    "default": 42,
                },
            ],
        }
    )

    assert target.schema is not None
    created_at = target.schema.fields[1]
    assert created_at.metadata["default"] == "<redacted>"
    assert created_at.metadata["default_omission_safe"] is True
    assert etl.check_write_compatibility(source, target).status == "proven"


def test_redacted_incompatible_target_default_does_not_qualify_omission() -> None:
    source = etl.infer_records([{"id": 1}]).schema
    target = inspect_target(
        {
            "identity": "invalid-default-target",
            "exists": "present",
            "capabilities": {"write_modes": ["append"]},
            "fields": [
                {"name": "id", "type": "integer"},
                {
                    "name": "created_at",
                    "type": "string",
                    "required": True,
                    "nullable": False,
                    "default": 42,
                },
            ],
        }
    )

    assert target.schema is not None
    assert target.schema.fields[1].metadata["default_omission_safe"] is False
    compatibility = etl.check_write_compatibility(source, target)
    assert compatibility.status == "conflict"
    assert "INFER_WRITE_INCOMPATIBLE" in {
        item.code for item in compatibility.diagnostics
    }


@pytest.mark.parametrize(
    ("metadata_key", "mode"),
    (("keys", "merge"), ("partitions", "partition_replace")),
)
def test_malformed_target_constraints_fail_closed(metadata_key: str, mode: str) -> None:
    source = etl.infer_records([{"id": 1}]).schema
    target = inspect_target(
        {
            "identity": f"malformed-{metadata_key}",
            "exists": "present",
            metadata_key: [[]],
            "capabilities": {"write_modes": [mode]},
            "fields": [{"name": "id", "type": "integer"}],
        }
    )

    compatibility = etl.check_write_compatibility(source, target, mode=mode)

    assert not compatibility.compatible
    assert "INFER_TARGET_UNSUPPORTED" in {
        item.code for item in compatibility.diagnostics
    }


def test_target_observation_metadata_copy_and_compatibility_are_bounded() -> None:
    class WideMetadata(Mapping[str, object]):
        def __init__(self, width: int) -> None:
            self.width = width
            self.key_visits = 0

        def __len__(self) -> int:
            return self.width

        def __iter__(self) -> Iterator[str]:
            for index in range(self.width):
                self.key_visits += 1
                yield f"key_{index}"

        def __getitem__(self, key: str) -> object:
            return key

    wide = WideMetadata(1_000)
    schema = NormalizedSchema("target", (NormalizedField("id", "integer"),))
    observation = etl.TargetObservation(
        schema, "present", metadata=cast(dict[str, Any], wide)
    )

    assert wide.key_visits == 257
    assert len(observation.metadata) == 256
    assert "INFER_LIMIT" in {item.code for item in observation.diagnostics}

    observation.metadata.update({f"extra_{index}": index for index in range(1_000)})
    source = etl.infer_records([{"id": 1}]).schema
    compatibility = etl.check_write_compatibility(source, observation)
    assert not compatibility.compatible
    assert "INFER_LIMIT" in {item.code for item in compatibility.diagnostics}


def test_target_schema_field_count_is_bounded() -> None:
    maximum = etl.InferenceLimits().max_fields
    targets = (
        inspect_target(
            {
                "identity": "wide-target",
                "exists": "present",
                "fields": [
                    {"name": f"field_{index}", "type": "integer"}
                    for index in range(maximum + 1)
                ],
            }
        ),
        inspect_target({f"field_{index}": "integer" for index in range(maximum + 1)}),
    )

    for target in targets:
        assert target.schema is None
        assert target.exists == "unknown"
        assert "INFER_LIMIT" in {item.code for item in target.diagnostics}


def test_target_field_metadata_copy_is_bounded() -> None:
    class WideField(Mapping[str, object]):
        def __init__(self) -> None:
            self.entries: dict[str, object] = {
                "name": "id",
                "type": "integer",
            }
            self.entries.update({f"metadata_{index}": index for index in range(1_000)})
            self.key_visits = 0
            self.value_reads = 0

        def __len__(self) -> int:
            return len(self.entries)

        def __iter__(self) -> Iterator[str]:
            for key in self.entries:
                self.key_visits += 1
                yield key

        def __getitem__(self, key: str) -> object:
            self.value_reads += 1
            return self.entries[key]

    field = WideField()
    target = inspect_target(
        {
            "identity": "wide-field-metadata-target",
            "exists": "present",
            "fields": [field],
        }
    )

    assert target.schema is None
    assert target.exists == "unknown"
    assert "INFER_LIMIT" in {item.code for item in target.diagnostics}
    assert field.key_visits <= 257
    assert field.value_reads == 0


def test_target_revision_reader_fences_stale_observation() -> None:
    result = infer_records_for_target(
        [{"id": 1}],
        {"revision": "r1", "fields": [{"name": "id", "type": "integer"}]},
        revision_reader=lambda: "r2",
    )
    assert "INFER_TARGET_STALE" in {item.code for item in result.diagnostics}


def test_preview_evaluator_uses_three_valued_null_logic() -> None:
    row = {"x": None}
    assert (
        _eval(
            {
                "kind": "binary",
                "op": "eq",
                "left": {"kind": "fieldRef", "target": "x"},
                "right": 1,
            },
            row,
        )
        is None
    )
    assert (
        _eval(
            {
                "kind": "binary",
                "op": "not_eq",
                "left": {"kind": "fieldRef", "target": "x"},
                "right": 1,
            },
            row,
        )
        is None
    )
    assert (
        _eval(
            {"kind": "unary", "op": "not", "expr": {"kind": "fieldRef", "target": "x"}},
            row,
        )
        is None
    )


def test_decimal_cast_failure_is_reported_not_raised() -> None:
    dataset = etl.from_records([{"x": "not-a-number"}]).withColumn(
        "converted", col("x").cast("decimal")
    )
    assert "INFER_RUNTIME_CONVERSION" in {item.code for item in dataset.diagnostics}


def test_late_replay_diagnostics_propagate_through_chained_transforms() -> None:
    dataset = etl.from_records(
        ({"value": value} for value in ("1", "invalid")),
        limits=etl.InferenceLimits(max_rows=1),
    )
    first = dataset.select(to_integer(col("value")).alias("number"))
    second = first.select("number")

    assert second.replay is not None
    assert list(second.replay.take()) == [{"number": 1}, {"number": None}]
    assert "INFER_RUNTIME_CONVERSION" in {item.code for item in first.diagnostics}
    assert "INFER_RUNTIME_CONVERSION" in {item.code for item in second.diagnostics}


def test_storage_rejects_provider_object_after_conversion_error() -> None:
    class ProviderFrame:
        def to_dict(self, orient="records"):
            raise TypeError("unsupported orientation")

    try:
        records_to_dicts(ProviderFrame())
    except ValueError as exc:
        assert "provider" in str(exc)
    else:
        raise AssertionError("provider object was silently retained")


def test_exact_jsonl_boundary_is_not_marked_sampled(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text('{"id": 1}\n{"id": 2}\n', encoding="utf-8")
    result = etl.infer_json(path, lines=True, limits=etl.InferenceLimits(max_rows=2))
    assert result.provenance["sampled"] is False
    assert "INFER_LIMIT" not in {item.code for item in result.diagnostics}


def test_jsonl_row_limit_ignores_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text('\n{"id": 1}\n{"id": 2}\n\n', encoding="utf-8")

    result = etl.infer_json(
        path,
        lines=True,
        limits=etl.InferenceLimits(max_rows=2),
        retain_rows=True,
    )

    assert result.rows == ({"id": 1}, {"id": 2})
    assert result.provenance["sampled"] is False
    assert "INFER_LIMIT" not in {item.code for item in result.diagnostics}


def test_case_when_schema_includes_every_value_branch() -> None:
    dataset = etl.from_records([{"flag": True, "text": "yes", "number": 1}]).select(
        when(col("flag"), col("text")).otherwise(col("number")).alias("out")
    )

    assert dataset.schema.fields[0].logical_type == "string"
    assert dataset.preview() == [{"out": "yes"}]


def test_positional_union_preview_uses_right_schema_order() -> None:
    left = etl.from_records([{"id": 1, "payload": "left"}], name="left")
    right = etl.from_records(
        [
            {"payload": 101, "id": "first"},
            {"id": 202, "payload": "second"},
        ],
        name="right",
    )

    result = left.union(right)

    assert result.preview()[2] == {"id": "second", "payload": "202"}


@pytest.mark.parametrize(
    ("field_key", "invalid_value"),
    [("nullable", "false"), ("required", "false")],
)
def test_durable_target_binding_rejects_string_boolean_fields(
    field_key: str, invalid_value: str
) -> None:
    field = {
        "name": "id",
        "logical_type": "integer",
        "required": True,
        "nullable": False,
    }
    field[field_key] = invalid_value
    binding = {
        "version": 1,
        "kind": "target",
        "identity": "target",
        "write_mode": "append",
        "observed": True,
        "requirements": {
            "version": 1,
            "identity": "target",
            "fields": [field],
            "metadata": {"capabilities": {"write_modes": ["append"]}},
        },
    }

    with pytest.raises(ValueError, match="INFER_TARGET_BINDING"):
        validate_target_binding(binding)


@pytest.mark.parametrize(
    "schema_payload",
    [
        {
            "fields": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
                {"name": "active", "type": "boolean"},
            ]
        },
        {"id": "integer", "name": "string", "active": "boolean"},
    ],
)
def test_provider_schema_obeys_max_fields(schema_payload: Mapping[str, object]) -> None:
    class Provider:
        def inspect_schema(self):
            return schema_payload

    result = etl.infer_source(Provider(), limits=etl.InferenceLimits(max_fields=1))

    assert [field.name for field in result.schema.fields] == ["id"]
    assert result.provenance["sampled"] is True
    assert result.provenance["limit_reason"] == "fields"
    assert "INFER_LIMIT" in {item.code for item in result.diagnostics}


def test_normalized_schema_obeys_max_fields() -> None:
    source_schema = NormalizedSchema(
        "wide",
        (
            NormalizedField("id", "integer"),
            NormalizedField("name", "string"),
        ),
    )

    result = etl.infer_source(source_schema, limits=etl.InferenceLimits(max_fields=1))

    assert [field.name for field in result.schema.fields] == ["id"]
    assert result.provenance["limit_reason"] == "fields"
    assert "INFER_LIMIT" in {item.code for item in result.diagnostics}


def test_provider_field_metadata_copy_is_bounded() -> None:
    class WideField(Mapping[str, object]):
        def __init__(self) -> None:
            self.entries: dict[str, object] = {
                "name": "id",
                "type": "integer",
            }
            self.entries.update({f"metadata_{index}": index for index in range(1_000)})
            self.key_visits = 0
            self.value_reads = 0

        def __len__(self) -> int:
            return len(self.entries)

        def __iter__(self) -> Iterator[str]:
            for key in self.entries:
                self.key_visits += 1
                yield key

        def __getitem__(self, key: str) -> object:
            self.value_reads += 1
            return self.entries[key]

    field = WideField()

    class Provider:
        def inspect_schema(self):
            return {"fields": [field]}

    result = etl.infer_source(Provider(), limits=etl.InferenceLimits(max_fields=1))

    assert [item.name for item in result.schema.fields] == ["id"]
    assert field.key_visits <= 257
    assert field.value_reads <= 5


def test_provider_materialization_limit_is_checked_before_record_conversion() -> None:
    conversions = []

    class View:
        __etlantic_bounded_view__ = True
        estimated_size = 128

        def to_dicts(self):
            conversions.append(True)
            return [{"value": "large"}]

    class Provider:
        def head(self, count):
            return View()

        def to_dicts(self):
            raise AssertionError("the source conversion hook must not be called")

    result = etl.infer_source(
        Provider(),
        limits=etl.InferenceLimits(max_bytes=1_000, max_materialized_bytes=1),
    )

    assert conversions == []
    assert "INFER_LIMIT" in {item.code for item in result.diagnostics}
    assert result.provenance["effective_materialized_bytes_limit"] == 1
    assert result.provenance["sampled"] is True
    assert result.provenance["limit_reason"] == "materialized_bytes"


def test_provider_stream_is_accounted_before_rows_are_retained() -> None:
    yielded: list[str] = []

    class View:
        __etlantic_bounded_view__ = True
        estimated_size = 1

        def iter_rows(self, *, named: bool):
            assert named is True
            yielded.append("large")
            yield {"value": "x" * 200}
            raise AssertionError("conversion should stop at the first oversized row")

    class Provider:
        def head(self, count: int):
            return View()

        def to_dicts(self):
            raise AssertionError("materializing conversion must not be called")

    result = etl.infer_source(
        Provider(),
        limits=etl.InferenceLimits(max_bytes=1_000, max_materialized_bytes=64),
    )

    assert yielded == ["large"]
    assert result.provenance["sampled"] is True
    assert result.provenance["limit_reason"] == "materialized_bytes"
    assert "INFER_LIMIT" in {item.code for item in result.diagnostics}


def test_provider_preview_refines_explicit_nullability_on_a_sample() -> None:
    class View:
        __etlantic_bounded_view__ = True

        def __init__(self, rows: Sequence[Mapping[str, object]]) -> None:
            self.rows = list(rows)

    class Provider:
        def __init__(self):
            self.schema = {
                "fields": [
                    {
                        "name": "value",
                        "type": "string",
                        "required": True,
                        "nullable": False,
                    }
                ]
            }
            self.rows = [{"value": None}, {"value": "later"}]

        def __len__(self) -> int:
            return len(self.rows)

        def head(self, count: int) -> View:
            return View(self.rows[:count])

    result = etl.infer_source(Provider(), limits=etl.InferenceLimits(max_rows=1))

    assert result.provenance["sampled"] is True
    assert result.schema.fields[0].nullable is True


def test_provider_metadata_preserves_sampling_from_preview_inference() -> None:
    class View:
        __etlantic_bounded_view__ = True

        def __init__(self) -> None:
            self.rows = [{"id": 1, "extra": 2}]

    class Provider:
        def __init__(self) -> None:
            self.schema = {
                "fields": [
                    {"name": "id", "type": "integer"},
                    {"name": "extra", "type": "integer"},
                ]
            }

        def __len__(self) -> int:
            return 1

        def head(self, count: int) -> View:
            return View()

    result = etl.infer_source(
        Provider(), limits=etl.InferenceLimits(max_rows=10, max_fields=1)
    )

    assert result.provenance["sampled"] is True
    assert all(not field.required and field.nullable for field in result.schema.fields)


def test_json_materialization_limit_is_enforced_while_reading(tmp_path: Path) -> None:
    jsonl = tmp_path / "rows.jsonl"
    jsonl.write_text('{"id": 1}\n{"payload": "' + "x" * 200 + '"}\n')
    array = tmp_path / "rows.json"
    array.write_text('[{"id": 1}, {"payload": "' + "x" * 200 + '"}]')

    limits = etl.InferenceLimits(max_bytes=1_000, max_materialized_bytes=64)
    results = [
        etl.infer_json(jsonl, lines=True, limits=limits, retain_rows=True),
        etl.infer_json(array, limits=limits, retain_rows=True),
    ]

    for result in results:
        assert result.provenance["sampled"] is True
        assert result.provenance["limit_reason"] == "materialized_bytes"
        assert result.provenance["materialized_bytes_observed"] <= 64
        assert len(result.rows) == 1


def test_schema_document_byte_limit_rejects_oversized_text_before_encoding() -> None:
    class NoEncode(str):
        def encode(self, *args: object, **kwargs: object) -> bytes:
            raise AssertionError("oversized schema text must be rejected first")

    result = etl.infer_schema_document(
        NoEncode("x" * 1_000),
        format="json_schema",
        limits=etl.InferenceLimits(max_bytes=32),
    )

    assert "INFER_LIMIT" in {item.code for item in result.diagnostics}


def test_schema_document_byte_limit_counts_utf8_bytes() -> None:
    result = etl.infer_schema_document(
        "é" * 16,
        format="json_schema",
        limits=etl.InferenceLimits(max_bytes=24),
    )

    assert "INFER_LIMIT" in {item.code for item in result.diagnostics}


def test_schema_document_mapping_byte_limit_preflights_large_scalars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_encoding(*args: object, **kwargs: object) -> object:
        raise AssertionError("oversized schema mapping reached JSON encoding")

    monkeypatch.setattr(
        schema_documents.json.JSONEncoder, "iterencode", reject_encoding
    )
    result = etl.infer_schema_document(
        {
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "x" * 1_000_000}},
        },
        format="json_schema",
        limits=etl.InferenceLimits(max_bytes=1_024),
    )

    assert "INFER_LIMIT" in {item.code for item in result.diagnostics}


def test_mixed_decimal_and_float_use_lossless_decimal_policy() -> None:
    result = etl.infer_records(
        [{"x": Decimal("9007199254740993")}, {"x": 1.0}], retain_rows=True
    )
    assert result.schema.fields[0].logical_type == "decimal"
    assert all(isinstance(row["x"], Decimal) for row in result.rows)


def test_async_provider_timeout_is_not_misreported_as_an_inference_limit() -> None:
    class Provider:
        async def inspect_schema(self):
            raise TimeoutError("connector request timed out")

    result = asyncio.run(
        etl.infer_source_async(
            Provider(), limits=etl.InferenceLimits(timeout_seconds=1)
        )
    )

    assert "INFER_SOURCE_UNKNOWN" in {item.code for item in result.diagnostics}
    assert "INFER_LIMIT" not in {item.code for item in result.diagnostics}
