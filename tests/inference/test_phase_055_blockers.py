"""Focused regression coverage for the remaining 0.55 review blockers."""

import asyncio
import json
from decimal import Decimal

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

        def to_dicts(self):
            return [{"id": 1}, {"id": 2}]

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


def test_mixed_decimal_and_float_use_lossless_decimal_policy() -> None:
    result = etl.infer_records(
        [{"x": Decimal("9007199254740993")}, {"x": 1.0}], retain_rows=True
    )
    assert result.schema.fields[0].logical_type == "decimal"
    assert all(isinstance(row["x"], Decimal) for row in result.rows)
