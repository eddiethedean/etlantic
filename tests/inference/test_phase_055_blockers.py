# pyright: reportMissingParameterType=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false
"""Focused regression coverage for the remaining 0.55 review blockers."""

import asyncio
import json
import time
from collections.abc import ItemsView, Iterator, Mapping, Sequence
from decimal import Decimal
from pathlib import Path

import etlantic as etl
from etlantic.inference.facade import _eval
from etlantic.inference.targets import infer_records_for_target, inspect_target
from etlantic.schema_drift import json_safe_metadata
from etlantic.storage.protocol import records_to_dicts
from etlantic.transform.functions import col


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
