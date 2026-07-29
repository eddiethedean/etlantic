"""0.32 live PipelineBuilder bridge + runtime_map overrides/invalidation."""

from __future__ import annotations

from types import SimpleNamespace

from etlantic.runtime.request import InvalidationMode, RunIntent
from medallantic.migrate.sparkforge import (
    adapt_pipeline,
    from_pipeline_builder,
    sparkforge_available,
)
from medallantic.runtime_map import (
    debug_request_from_sparkforge,
    invalidation_from_sparkforge,
)


def test_from_pipeline_builder_dict_path() -> None:
    spec, diags = from_pipeline_builder(
        {
            "name": "live_dict",
            "engine": "spark",
            "metadata": {"password": "hunter2", "owner": "team"},
            "steps": [
                {
                    "name": "orders",
                    "kind": "bronze_rules",
                    "layer": "bronze",
                    "rules": {"id": ["not_null"]},
                    "metadata": {"api_key": "abc", "label": "ok"},
                },
                {
                    "name": "clean",
                    "kind": "silver_transform",
                    "layer": "silver",
                    "source": "orders",
                    "write_mode": "overwrite",
                },
            ],
        }
    )
    assert spec.name == "live_dict"
    assert len(spec.steps) == 2
    assert "password" not in spec.metadata
    assert spec.metadata.get("owner") == "team"
    assert "api_key" not in (spec.steps[0].metadata or {})
    assert (spec.steps[0].metadata or {}).get("label") == "ok"
    assert any(d.code == "PMSF351" for d in diags)
    result = adapt_pipeline(spec, strict_delta=False)
    assert "orders" in result.step_map


def test_from_pipeline_builder_duck_typed_object() -> None:
    bronze = SimpleNamespace(
        name="orders",
        layer="bronze",
        kind="bronze_rules",
        rules={"id": ["not_null"]},
        source=None,
        table_name="orders",
        transform_ref=None,
        write_mode=None,
        metadata={},
    )
    silver = SimpleNamespace(
        name="clean",
        layer="silver",
        kind="silver_transform",
        rules={},
        source="orders",
        table_name="clean",
        transform_ref="mod:clean_fn",
        write_mode="overwrite",
        metadata={},
    )
    builder = SimpleNamespace(
        name="duck",
        schema="sales",
        engine="spark",
        steps=[bronze, silver],
        min_bronze_rate=90.0,
        min_silver_rate=95.0,
        min_gold_rate=98.0,
        delta_operations=["merge"],
        metadata={"password": "hunter2", "owner": "team"},
        legacy_engine_extensions=[],
    )
    spec, diags = from_pipeline_builder(builder)
    assert spec.name == "duck"
    assert spec.schema == "sales"
    assert "password" not in spec.metadata
    assert spec.metadata.get("owner") == "team"
    assert spec.metadata.get("delta_operations") == ["merge"]
    assert any(d.code == "PMSF351" for d in diags)


def test_runtime_map_overrides_and_invalidation() -> None:
    req = debug_request_from_sparkforge(
        mode="incremental",
        run_one="clean",
        skip_writes=True,
        parameter_overrides={"clean": {"limit": 10}},
        implementation_overrides={"clean": "pyspark"},
        invalidation="downstream",
    )
    assert req.intent is RunIntent.INCREMENTAL
    assert req.no_write is True
    assert req.selection.kind == "only"
    assert req.selection.nodes == ("clean",)
    assert req.parameter_overrides["clean"]["limit"] == 10
    assert req.implementation_overrides["clean"] == "pyspark"
    assert req.invalidation is InvalidationMode.DOWNSTREAM
    assert invalidation_from_sparkforge("closure") is InvalidationMode.CLOSURE


def test_sparkforge_available_is_bool() -> None:
    assert isinstance(sparkforge_available(), bool)
