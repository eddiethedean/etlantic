from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")
pytestmark = pytest.mark.duckdb

from etlantic_duckdb import create_plugin  # noqa: E402
from etlantic_duckdb.config import DuckDBConfig  # noqa: E402
from etlantic_duckdb.frame import DuckDBFrame  # noqa: E402
from etlantic_duckdb.plugin import DuckDBSqlPlugin  # noqa: E402
from etlantic_duckdb.transform_compiler import DuckDBTransformCompiler  # noqa: E402

from etlantic.sql.protocol import (  # noqa: E402
    BinaryExpr,
    ColumnRef,
    CompiledSql,
    CteDef,
    LiteralExpr,
    RelationRef,
    SqlExecutionContext,
    SqlQuery,
)
from etlantic.testing import run_sql_conformance_suite  # noqa: E402
from etlantic.transform.compiler import (  # noqa: E402
    TransformCompileContext,
    TransformExecutionContext,
)


def _context(run_id: str = "run-a") -> SqlExecutionContext:
    return SqlExecutionContext(
        run_id=run_id,
        pipeline_id="pipeline",
        plan_id="plan",
        step_name="step",
        engine="duckdb",
    )


def test_duckdb_sql_protocol_and_run_isolation() -> None:
    plugin = create_plugin()
    assert plugin.info.engine == "duckdb"
    assert plugin.capabilities().sql
    loaded = plugin.load_records(
        [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}],
        target=RelationRef(name="items"),
        context=_context(),
    )
    assert loaded.outcome.value == "committed"
    query = SqlQuery(
        source=RelationRef(name="items"),
        columns=(ColumnRef("name"),),
        where=BinaryExpr("eq", ColumnRef("id"), LiteralExpr(2)),
    )
    fetched = plugin.fetch_records(query, params={}, context=_context())
    assert fetched.records == [{"name": "b"}]
    assert plugin.rows_fetched_total() == 1
    plugin.cleanup_run(run_id="run-a")
    assert plugin.connections.active_run_ids() == ()


def test_duckdb_passes_public_sql_conformance() -> None:
    run_sql_conformance_suite(create_plugin(), expected_engine="duckdb")


def test_compiled_statements_are_sealed() -> None:
    plugin = create_plugin()
    context = _context()
    statement = plugin.compile_query(
        SqlQuery(source=RelationRef(name="items")), context=context
    )
    tampered = CompiledSql(
        statement_id=statement.statement_id,
        text="SELECT 1",
        dialect="duckdb",
    )
    result = plugin.execute([tampered], params={}, context=context)
    assert result.outcome.value == "rolled_back"
    assert result.diagnostics
    plugin.cleanup_run(run_id="run-a")


def test_duckdb_result_row_budget_applies_across_statements() -> None:
    plugin = DuckDBSqlPlugin(config=DuckDBConfig(max_result_rows=2))
    context = _context("budget")
    plugin.load_records(
        [{"id": 1}, {"id": 2}], target=RelationRef(name="items"), context=context
    )
    first = plugin.compile_query(
        SqlQuery(source=RelationRef(name="items")), context=context
    )
    second = plugin.compile_query(
        SqlQuery(source=RelationRef(name="items")), context=context
    )
    result = plugin.execute([first, second], params={}, context=context, fetch=True)
    assert result.outcome.value == "rolled_back"
    assert result.diagnostics
    plugin.cleanup_run(run_id=context.run_id)


def test_compiled_statement_cannot_cross_run_or_replay() -> None:
    plugin = create_plugin()
    statement = plugin.compile_query(
        SqlQuery(source=RelationRef(name="items")), context=_context("owner")
    )
    cross_run = plugin.execute([statement], params={}, context=_context("other"))
    assert cross_run.outcome.value == "rolled_back"
    assert cross_run.diagnostics
    plugin.cleanup_run(run_id="owner")
    replay = plugin.execute([statement], params={}, context=_context("owner"))
    assert replay.outcome.value == "rolled_back"


def test_duckdb_diagnostics_do_not_echo_bound_secrets() -> None:
    plugin = create_plugin()
    context = _context()
    plugin.load_records([{"id": 1}], target=RelationRef(name="items"), context=context)
    statement = plugin.compile_query(
        SqlQuery(
            source=RelationRef(name="items"),
            columns=(ColumnRef("missing"),),
            where=BinaryExpr("eq", ColumnRef("missing"), LiteralExpr("TOP-SECRET-123")),
        ),
        context=context,
    )
    result = plugin.execute([statement], params={}, context=context)
    assert result.diagnostics
    assert "TOP-SECRET-123" not in str(result.diagnostics)
    plugin.cleanup_run(run_id=context.run_id)


def test_duckdb_config_fingerprints_distinguish_logical_paths() -> None:
    first = DuckDBConfig.from_database("warehouse/a.duckdb")
    second = DuckDBConfig.from_database("warehouse/b.duckdb")
    assert first.fingerprint != second.fingerprint
    with pytest.raises(ValueError):
        first.resolve_database()

    approved = DuckDBConfig.from_database(
        "/tmp/approved.duckdb", allowed_paths=("/tmp/approved.duckdb",)
    )
    assert approved.resolve_database() == str(Path("/tmp/approved.duckdb").resolve())
    assert (
        DuckDBConfig(temp_directory="a").fingerprint
        != DuckDBConfig(temp_directory="b").fingerprint
    )
    with pytest.raises(ValueError):
        DuckDBConfig(temp_directory="spill").resolve_temp_directory()
    assert DuckDBConfig(
        temp_directory="spill", allowed_directories=("/tmp",)
    ).resolve_temp_directory() == str(Path("/tmp/spill").resolve())
    with pytest.raises(ValueError):
        DuckDBConfig(metadata={"password": "TOP-SECRET"})
    with pytest.raises(ValueError):
        DuckDBConfig(metadata={"api_key": "TOP-SECRET"})
    DuckDBConfig(metadata={"author": "alice"})
    safe_metadata = DuckDBConfig(metadata={"label": "TOP-SECRET"})
    assert "TOP-SECRET" not in repr(safe_metadata)


def test_duckdb_cte_lowering_is_explicit() -> None:
    plugin = create_plugin()
    query = SqlQuery(
        source=RelationRef(name="recent"),
        ctes=(CteDef("recent", SqlQuery(source=RelationRef(name="items"))),),
    )
    compiled = plugin.compile_query(query, context=_context())
    assert compiled.text.startswith("WITH ")
    plugin.cleanup_run(run_id="run-a")


def test_duckdb_portable_parameters_are_bound_and_input_names_are_scoped() -> None:
    compiler = DuckDBTransformCompiler()
    definition = {
        "inputs": {"input": {}},
        "actions": [
            {
                "kind": {
                    "id": "filter",
                    "action": "dtcs:filter",
                    "parameters": {
                        "predicate": {
                            "kind": "binary",
                            "op": "gte",
                            "left": {"kind": "fieldRef", "target": "id"},
                            "right": {
                                "kind": "fieldRef",
                                "scope": "parameter",
                                "target": "minimum",
                            },
                        }
                    },
                }
            }
        ],
        "outputs": {"result": {}},
    }
    compiled = compiler.compile(
        definition,
        context=TransformCompileContext(
            pipeline_id="p",
            plan_id="plan",
            step_name="step",
            profile_name="test",
            engine="duckdb",
        ),
    )
    output = asyncio.run(
        compiler.execute(
            compiled,
            inputs={"input": [{"id": 1}, {"id": 2}]},
            parameters={"minimum": 2},
            context=TransformExecutionContext(
                run_id="portable",
                pipeline_id="p",
                plan_id="plan",
                step_name="step",
                engine="duckdb",
            ),
        )
    )
    assert output.valid["result"].to_dicts() == [{"id": 2}]


def test_duckdb_portable_outputs_follow_lineage() -> None:
    compiler = DuckDBTransformCompiler()
    definition = {
        "inputs": {"input": {}},
        "actions": [
            {
                "id": "low",
                "kind": {
                    "id": "low",
                    "action": "dtcs:filter",
                    "target": "input",
                    "parameters": {
                        "predicate": {
                            "kind": "binary",
                            "op": "lt",
                            "left": {"kind": "fieldRef", "target": "id"},
                            "right": {"kind": "literal", "value": 2},
                        }
                    },
                },
            },
            {
                "id": "high",
                "kind": {
                    "id": "high",
                    "action": "dtcs:filter",
                    "target": "input",
                    "parameters": {
                        "predicate": {
                            "kind": "binary",
                            "op": "gte",
                            "left": {"kind": "fieldRef", "target": "id"},
                            "right": {"kind": "literal", "value": 2},
                        }
                    },
                },
            },
        ],
        "outputs": {"low_output": {}, "high_output": {}},
        "requirements": {
            "dependencies": [
                {"from": "low", "to": "low_output"},
                {"from": "high", "to": "high_output"},
            ]
        },
    }
    compiled = compiler.compile(
        definition,
        context=TransformCompileContext(
            pipeline_id="p",
            plan_id="plan",
            step_name="step",
            profile_name="test",
            engine="duckdb",
        ),
    )
    output = asyncio.run(
        compiler.execute(
            compiled,
            inputs={"input": [{"id": 1}, {"id": 2}]},
            parameters={},
            context=TransformExecutionContext(
                run_id="lineage",
                pipeline_id="p",
                plan_id="plan",
                step_name="step",
                engine="duckdb",
            ),
        )
    )
    assert output.valid["low_output"].to_dicts() == [{"id": 1}]
    assert output.valid["high_output"].to_dicts() == [{"id": 2}]


def test_duckdb_portable_input_identity_is_collision_resistant() -> None:
    compiler = DuckDBTransformCompiler()
    definition = {
        "inputs": {"a-b": {}, "a_b": {}},
        "actions": [],
        "outputs": {"result": {}},
    }
    compiled = compiler.compile(
        definition,
        context=TransformCompileContext(
            pipeline_id="p",
            plan_id="plan",
            step_name="step",
            profile_name="test",
            engine="duckdb",
        ),
    )
    output = asyncio.run(
        compiler.execute(
            compiled,
            inputs={"a-b": [{"id": 1}], "a_b": [{"id": 2}]},
            parameters={},
            context=TransformExecutionContext(
                run_id="collision",
                pipeline_id="p",
                plan_id="plan",
                step_name="step",
                engine="duckdb",
            ),
        )
    )
    assert output.valid["result"].to_dicts() == [{"id": 1}]


def test_duckdb_portable_empty_frame_requires_schema() -> None:
    compiler = DuckDBTransformCompiler()
    definition = {
        "inputs": {"input": {}},
        "actions": [],
        "outputs": {"result": {}},
    }
    compiled = compiler.compile(
        definition,
        context=TransformCompileContext(
            pipeline_id="p",
            plan_id="plan",
            step_name="step",
            profile_name="test",
            engine="duckdb",
        ),
    )
    with pytest.raises(ValueError, match="no declared schema"):
        asyncio.run(
            compiler.execute(
                compiled,
                inputs={"input": []},
                parameters={},
                context=TransformExecutionContext(
                    run_id="empty",
                    pipeline_id="p",
                    plan_id="plan",
                    step_name="step",
                    engine="duckdb",
                ),
            )
        )


def test_duckdb_portable_empty_input_uses_declared_types_and_preserves_schema() -> None:
    compiler = DuckDBTransformCompiler()
    definition = {
        "inputs": {
            "input": {"schema": {"fields": [{"name": "id", "type": "integer"}]}}
        },
        "actions": [
            {
                "id": "filter",
                "kind": {
                    "id": "filter",
                    "action": "dtcs:filter",
                    "target": "input",
                    "parameters": {
                        "predicate": {
                            "kind": "binary",
                            "op": "gt",
                            "left": {"kind": "fieldRef", "target": "id"},
                            "right": {"kind": "literal", "value": 1},
                        }
                    },
                },
            }
        ],
        "outputs": {"result": {}},
        "requirements": {"dependencies": [{"from": "filter", "to": "result"}]},
    }
    compiled = compiler.compile(
        definition,
        context=TransformCompileContext(
            pipeline_id="p",
            plan_id="plan",
            step_name="step",
            profile_name="test",
            engine="duckdb",
        ),
    )
    output = asyncio.run(
        compiler.execute(
            compiled,
            inputs={"input": []},
            parameters={},
            context=TransformExecutionContext(
                run_id="empty-typed",
                pipeline_id="p",
                plan_id="plan",
                step_name="step",
                engine="duckdb",
            ),
        )
    )
    frame = output.valid["result"]
    assert frame.to_dicts() == []
    assert frame.columns == ["id"]
    assert frame.column_types["id"] == "BIGINT"


def test_duckdb_empty_frame_explicit_types_can_be_chained() -> None:
    compiler = DuckDBTransformCompiler()
    definition = {
        "inputs": {"input": {}},
        "actions": [],
        "outputs": {"result": {}},
    }
    compiled = compiler.compile(
        definition,
        context=TransformCompileContext(
            pipeline_id="p",
            plan_id="plan",
            step_name="step",
            profile_name="test",
            engine="duckdb",
        ),
    )
    first = asyncio.run(
        compiler.execute(
            compiled,
            inputs={"input": DuckDBFrame([], ["id"], {"id": "HUGEINT"})},
            parameters={},
            context=TransformExecutionContext(
                run_id="empty-chain-a",
                pipeline_id="p",
                plan_id="plan",
                step_name="step",
                engine="duckdb",
            ),
        )
    ).valid["result"]
    second = asyncio.run(
        compiler.execute(
            compiled,
            inputs={"input": first},
            parameters={},
            context=TransformExecutionContext(
                run_id="empty-chain-b",
                pipeline_id="p",
                plan_id="plan",
                step_name="step",
                engine="duckdb",
            ),
        )
    ).valid["result"]
    assert second.columns == ["id"]
    assert second.column_types["id"] == "HUGEINT"


def test_duckdb_portable_null_only_rows_keep_declared_types() -> None:
    compiler = DuckDBTransformCompiler()
    definition = {
        "inputs": {"input": {}},
        "actions": [
            {
                "id": "filter",
                "kind": {
                    "id": "filter",
                    "action": "dtcs:filter",
                    "target": "input",
                    "parameters": {
                        "predicate": {
                            "kind": "binary",
                            "op": "gt",
                            "left": {"kind": "fieldRef", "target": "total"},
                            "right": {"kind": "literal", "value": 1},
                        }
                    },
                },
            }
        ],
        "outputs": {"result": {}},
        "requirements": {"dependencies": [{"from": "filter", "to": "result"}]},
    }
    compiled = compiler.compile(
        definition,
        context=TransformCompileContext(
            pipeline_id="p",
            plan_id="plan",
            step_name="step",
            profile_name="test",
            engine="duckdb",
        ),
    )
    output = asyncio.run(
        compiler.execute(
            compiled,
            inputs={
                "input": DuckDBFrame([{"total": None}], ["total"], {"total": "HUGEINT"})
            },
            parameters={},
            context=TransformExecutionContext(
                run_id="null-only",
                pipeline_id="p",
                plan_id="plan",
                step_name="step",
                engine="duckdb",
            ),
        )
    )
    frame = output.valid["result"]
    assert frame.to_dicts() == []
    assert frame.column_types["total"] == "HUGEINT"


def test_security_defaults_reject_unsafe_configuration() -> None:
    with pytest.raises(ValueError):
        DuckDBConfig(read_only=True)
    with pytest.raises(ValueError):
        DuckDBConfig(enable_external_access=True)
    with pytest.raises(ValueError):
        DuckDBConfig(autoload_known_extensions=True)
