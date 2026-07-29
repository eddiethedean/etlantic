"""0.33 live SqlPipelineBuilder bridge tests."""

from __future__ import annotations

from types import SimpleNamespace

from medallantic.migrate.sql import (
    adapt_pipeline,
    from_sql_pipeline_builder,
    sql_pipeline_builder_available,
)


def test_from_sql_pipeline_builder_dict_path() -> None:
    spec, diags = from_sql_pipeline_builder(
        {
            "name": "live_sql_dict",
            "engine": "sql",
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
    assert spec.name == "live_sql_dict"
    assert spec.engine == "sql"
    assert len(spec.steps) == 2
    assert "password" not in spec.metadata
    assert spec.metadata.get("owner") == "team"
    assert "api_key" not in (spec.steps[0].metadata or {})
    assert (spec.steps[0].metadata or {}).get("label") == "ok"
    assert any(d.code == "PMSQ351" for d in diags)
    result = adapt_pipeline(spec, strict_delta=False)
    assert "orders" in result.step_map


def test_from_sql_pipeline_builder_duck_typed_object() -> None:
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
        name="duck_sql",
        schema="sales",
        engine="sql",
        steps=[bronze, silver],
        min_bronze_rate=90.0,
        min_silver_rate=95.0,
        min_gold_rate=98.0,
        models=[type("Customer", (), {})],
        metadata={"password": "hunter2", "owner": "team"},
        legacy_engine_extensions=[],
    )
    spec, diags = from_sql_pipeline_builder(builder)
    assert spec.name == "duck_sql"
    assert spec.schema == "sales"
    assert spec.engine == "sql"
    assert "password" not in spec.metadata
    assert spec.metadata.get("owner") == "team"
    assert "Customer" in (spec.metadata.get("orm_models") or [])
    assert any(d.code == "PMSQ351" for d in diags)


def test_sql_pipeline_builder_available_is_bool() -> None:
    assert isinstance(sql_pipeline_builder_available(), bool)
