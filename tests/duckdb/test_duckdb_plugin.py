from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from threading import Barrier
from typing import Any, cast

import pytest

duckdb = pytest.importorskip("duckdb")
pytestmark = pytest.mark.duckdb

from etlantic_duckdb import create_plugin  # noqa: E402
from etlantic_duckdb.config import DuckDBConfig  # noqa: E402
from etlantic_duckdb.frame import DuckDBFrame  # noqa: E402
from etlantic_duckdb.plugin import DuckDBSqlPlugin  # noqa: E402
from etlantic_duckdb.transform_compiler import DuckDBTransformCompiler  # noqa: E402

from etlantic import (  # noqa: E402
    Data,
    Extract,
    Load,
    Pipeline,
    PipelineRuntime,
    Profile,
)
from etlantic.capabilities import PluginCapabilities  # noqa: E402
from etlantic.exceptions import NodeExecutionError  # noqa: E402
from etlantic.model import LogicalGraph, Node, NodeKind  # noqa: E402
from etlantic.plan.model import PipelinePlan  # noqa: E402
from etlantic.registry import (  # noqa: E402
    BindingDescriptor,
    PlanningContext,
    builtin_stub_registry,
)
from etlantic.runtime.orchestrator import LocalOrchestrator  # noqa: E402
from etlantic.runtime.request import RetryPolicy, RunIntent, RunRequest  # noqa: E402
from etlantic.runtime.sql_exec import (  # noqa: E402
    execute_sql_sink,
    is_sql_engine,
    resolve_sql_plugin,
)
from etlantic.sql.discovery import register_discovered_plugins  # noqa: E402
from etlantic.sql.protocol import (  # noqa: E402
    BinaryExpr,
    ColumnRef,
    CompiledSql,
    CteDef,
    JoinClause,
    LiteralExpr,
    RelationRef,
    SqlExecutionContext,
    SqlQuery,
    TransactionOutcome,
)
from etlantic.testing import run_sql_conformance_suite  # noqa: E402
from etlantic.transform.compiler import (  # noqa: E402
    TransformCompileContext,
    TransformExecutionContext,
    TransformPlanningContext,
)


def _context(run_id: str = "run-a") -> SqlExecutionContext:
    return SqlExecutionContext(
        run_id=run_id,
        pipeline_id="pipeline",
        plan_id="plan",
        step_name="step",
        engine="duckdb",
    )


class _AcmeSqlFixture:
    """Capability-backed third-party SQL fixture used by routing smoke tests."""

    def __init__(self) -> None:
        self.delegate = DuckDBSqlPlugin()
        capabilities = replace(self.delegate.capabilities(), engine="acme_sql")
        self._info = replace(
            self.delegate.info,
            name="acme-sql-fixture",
            engine="acme_sql",
            capabilities=capabilities,
        )

    @property
    def info(self):
        return self._info

    def capabilities(self):
        return self._info.capabilities

    def __getattr__(self, name: str):
        return getattr(self.delegate, name)


def test_duckdb_generic_sql_fixture_routes_by_capability() -> None:
    fixture = _AcmeSqlFixture()
    plugins: dict[str, Any] = {"acme_sql": fixture}
    assert is_sql_engine("acme_sql", plugins)
    assert resolve_sql_plugin("acme_sql", plugins=plugins) is fixture
    context = _context("acme-fixture")
    context = replace(context, engine="acme_sql")
    loaded = fixture.load_records(
        [{"id": 1}], target=RelationRef(name="fixture_items"), context=context
    )
    assert loaded.outcome is TransactionOutcome.COMMITTED
    fetched = fixture.fetch_records(
        RelationRef(name="fixture_items"), params={}, context=context
    )
    assert fetched.records == [{"id": 1}]
    fixture.cleanup_run(run_id=context.run_id)


class _CommitAcknowledgementLost:
    def __init__(
        self,
        connection: Any,
        commands: str | tuple[str, ...] = "COMMIT",
        *,
        fail_once: bool = False,
        fail_close: bool = False,
    ) -> None:
        self.inner = connection
        self.commands = {commands} if isinstance(commands, str) else set(commands)
        self.fail_once = fail_once
        self.fail_close = fail_close
        self.failed = False

    def execute(self, sql: str, *args: Any, **kwargs: Any) -> Any:
        result = self.inner.execute(sql, *args, **kwargs)
        command = str(sql).strip().upper()
        if command in self.commands and (not self.fail_once or not self.failed):
            self.failed = True
            raise RuntimeError("lost acknowledgement")
        return result

    def close(self) -> None:
        self.inner.close()
        if self.fail_close:
            raise RuntimeError("close acknowledgement lost")

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)


class _OrchestrationItem(Data):
    id: int


class _OrchestrationPipeline(Pipeline):
    raw: Extract[_OrchestrationItem] = Extract(asset="raw_items")
    out: Load[_OrchestrationItem] = Load(input=raw, asset="ack_items")


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


def test_duckdb_config_fingerprints_distinguish_logical_paths(
    tmp_path: Path,
) -> None:
    first = DuckDBConfig.from_database("warehouse/a.duckdb")
    second = DuckDBConfig.from_database("warehouse/b.duckdb")
    assert first.fingerprint != second.fingerprint
    with pytest.raises(ValueError):
        first.resolve_database()

    approved_path = tmp_path / "approved.duckdb"
    approved = DuckDBConfig.from_database(
        approved_path, allowed_paths=(str(approved_path),)
    )
    assert approved.resolve_database() == str(approved_path.resolve())
    assert (
        DuckDBConfig(temp_directory="a").fingerprint
        != DuckDBConfig(temp_directory="b").fingerprint
    )
    with pytest.raises(ValueError):
        DuckDBConfig(temp_directory="spill").resolve_temp_directory()
    assert DuckDBConfig(
        temp_directory="spill", allowed_directories=(str(tmp_path),)
    ).resolve_temp_directory() == str((tmp_path / "spill").resolve())
    with pytest.raises(ValueError):
        DuckDBConfig(metadata={"password": "TOP-SECRET"})
    with pytest.raises(ValueError):
        DuckDBConfig(metadata={"api_key": "TOP-SECRET"})
    for key in ("plugin:api_key", "etlantic.api_key", "aws_access_key_id"):
        with pytest.raises(ValueError):
            DuckDBConfig(metadata={key: "TOP-SECRET"})
    DuckDBConfig(metadata={"author": "alice"})
    safe_metadata = DuckDBConfig(metadata={"label": "TOP-SECRET"})
    assert "TOP-SECRET" not in repr(safe_metadata)


def test_duckdb_config_defensively_freezes_nested_values(tmp_path: Path) -> None:
    database = tmp_path / "immutable.duckdb"
    allowed_paths: list[str] = []
    metadata = {"label": "safe"}
    config = DuckDBConfig.from_database(
        database, allowed_paths=allowed_paths, metadata=metadata
    )
    fingerprint = config.fingerprint

    with pytest.raises(ValueError, match="approved root"):
        config.resolve_database()
    allowed_paths.append(str(database))
    metadata["password"] = "late-value"

    with pytest.raises(ValueError, match="approved root"):
        config.resolve_database()
    assert config.metadata == {"label": "safe"}
    assert config.fingerprint == fingerprint
    with pytest.raises(TypeError):
        cast(dict[str, str], config.metadata)["password"] = "late-value"
    with pytest.raises(FrozenInstanceError):
        cast(Any, config).allowed_paths += (str(database),)
    with pytest.raises(TypeError, match="sequence of paths"):
        DuckDBConfig.from_database(database, allowed_paths=str(database))


def test_duckdb_cte_lowering_is_explicit() -> None:
    plugin = create_plugin()
    query = SqlQuery(
        source=RelationRef(name="recent"),
        ctes=(CteDef("recent", SqlQuery(source=RelationRef(name="items"))),),
    )
    compiled = plugin.compile_query(query, context=_context())
    assert compiled.text.startswith("WITH ")
    plugin.cleanup_run(run_id="run-a")


@pytest.mark.parametrize(
    ("left_keys", "right_keys"),
    [(("left_a",), ("right_a", "right_b")), (("left_a", "left_b"), ("right_a",))],
)
def test_duckdb_join_rejects_mismatched_key_counts(
    left_keys: tuple[str, ...], right_keys: tuple[str, ...]
) -> None:
    plugin = create_plugin()
    query = SqlQuery(
        source=RelationRef(name="left_table"),
        source_alias="left_side",
        joins=(
            JoinClause(
                right=RelationRef(name="right_table"),
                left_keys=left_keys,
                right_keys=right_keys,
                right_alias="right_side",
            ),
        ),
    )
    with pytest.raises(ValueError, match="key counts must match"):
        plugin.compile_query(query, context=_context("join-mismatch"))
    plugin.cleanup_run(run_id="join-mismatch")


def test_duckdb_join_preserves_all_valid_key_pairs() -> None:
    plugin = create_plugin()
    query = SqlQuery(
        source=RelationRef(name="left_table"),
        source_alias="left_side",
        joins=(
            JoinClause(
                right=RelationRef(name="right_table"),
                left_keys=("left_a", "left_b"),
                right_keys=("right_a", "right_b"),
                right_alias="right_side",
            ),
        ),
    )
    compiled = plugin.compile_query(query, context=_context("join-valid"))
    assert '"left_side"."left_a" = "right_side"."right_a"' in compiled.text
    assert '"left_side"."left_b" = "right_side"."right_b"' in compiled.text
    plugin.cleanup_run(run_id="join-valid")


def test_duckdb_same_run_concurrent_fetches_have_independent_seals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin = create_plugin()
    context = _context("parallel-fetch")
    loaded = plugin.load_records(
        [{"id": 1}], target=RelationRef(name="items"), context=context
    )
    assert loaded.outcome is TransactionOutcome.COMMITTED
    original_execute = plugin.execute
    barrier = Barrier(2)

    def synchronized_execute(*args: Any, **kwargs: Any) -> Any:
        barrier.wait(timeout=5)
        return original_execute(*args, **kwargs)

    monkeypatch.setattr(plugin, "execute", synchronized_execute)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                plugin.fetch_records,
                RelationRef(name="items"),
                params={},
                context=context,
            )
            for _ in range(2)
        ]
        results = [future.result(timeout=5) for future in futures]

    assert [result.outcome for result in results] == [
        TransactionOutcome.COMMITTED,
        TransactionOutcome.COMMITTED,
    ]
    assert [result.records for result in results] == [[{"id": 1}], [{"id": 1}]]
    assert not plugin._sealed
    plugin.cleanup_run(run_id=context.run_id)
    assert plugin.connections.active_run_ids() == ()


def test_duckdb_portable_preflight_rejects_unsupported_operator() -> None:
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
                            "kind": "operator",
                            "op": "unsupported",
                            "left": {"kind": "fieldRef", "target": "id"},
                            "right": {"kind": "literal", "value": 1},
                        }
                    },
                }
            }
        ],
        "outputs": {"result": {}},
    }
    report = compiler.analyze(
        definition,
        context=TransformPlanningContext(
            pipeline_id="p",
            step_name="step",
            profile_name="test",
            engine="duckdb",
        ),
    )
    assert report.supported is False
    assert any(
        finding.requirement == "operator:unsupported"
        and finding.expression_path == "actions[0].kind.parameters.predicate.op"
        and finding.evidence_fingerprint == compiler.info.evidence_fingerprint
        for finding in report.findings
    )
    with pytest.raises(ValueError, match="operator:unsupported"):
        compiler.compile(
            definition,
            context=TransformCompileContext(
                pipeline_id="p",
                plan_id="plan",
                step_name="step",
                profile_name="test",
                engine="duckdb",
            ),
        )


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("operators", "dtcs:unimplemented", "operator:dtcs:unimplemented"),
        ("types", "dtcs:unimplemented", "type:dtcs:unimplemented"),
        (
            "semantic_modes",
            "three_state_distinct",
            "semantic_mode:three_state_distinct",
        ),
    ],
)
def test_duckdb_portable_preflight_preserves_explicit_capability_requirements(
    key: str, value: str, expected: str
) -> None:
    compiler = DuckDBTransformCompiler()
    definition = {
        "inputs": {"input": {}},
        "actions": [],
        "outputs": {"result": {}},
    }
    report = compiler.analyze(
        definition,
        context=TransformPlanningContext(
            pipeline_id="p",
            step_name="step",
            profile_name="test",
            engine="duckdb",
        ),
        requirements={key: [value]},
    )
    assert report.supported is False
    assert expected in {finding.requirement for finding in report.findings}


def test_duckdb_portable_preflight_resolves_declared_columns() -> None:
    compiler = DuckDBTransformCompiler()
    definition = {
        "inputs": {
            "input": {"schema": {"fields": [{"name": "id", "type": "integer"}]}}
        },
        "actions": [
            {
                "kind": {
                    "id": "filter",
                    "action": "dtcs:filter",
                    "parameters": {
                        "predicate": {
                            "kind": "fieldRef",
                            "target": "missing",
                        }
                    },
                }
            }
        ],
        "outputs": {"result": {}},
    }
    report = compiler.analyze(
        definition,
        context=TransformPlanningContext(
            pipeline_id="p",
            step_name="step",
            profile_name="test",
            engine="duckdb",
        ),
    )
    assert report.supported is False
    assert any(finding.requirement == "column:missing" for finding in report.findings)


def test_duckdb_portable_preflight_rejects_known_join_collisions() -> None:
    compiler = DuckDBTransformCompiler()
    definition = {
        "inputs": {
            "left": {
                "schema": {
                    "fields": [
                        {"name": "id", "type": "integer"},
                        {"name": "shared", "type": "string"},
                    ]
                }
            },
            "right": {
                "schema": {
                    "fields": [
                        {"name": "rid", "type": "integer"},
                        {"name": "shared", "type": "string"},
                    ]
                }
            },
        },
        "actions": [
            {
                "kind": {
                    "id": "join",
                    "action": "dtcs:join",
                    "parameters": {
                        "right": "right",
                        "leftKey": "id",
                        "rightKey": "rid",
                    },
                }
            }
        ],
        "outputs": {"result": {}},
    }
    report = compiler.analyze(
        definition,
        context=TransformPlanningContext(
            pipeline_id="p",
            step_name="step",
            profile_name="test",
            engine="duckdb",
        ),
    )
    assert report.supported is False
    assert any(finding.requirement == "join.collision" for finding in report.findings)


@pytest.mark.parametrize(
    ("predicate", "requirement"),
    [
        (
            {"kind": "call", "callee": "dtcs:lower", "args": []},
            "function:dtcs:lower:arity",
        ),
        ({"kind": "fieldRef", "target": "unsafe-name"}, "identifier"),
    ],
)
def test_duckdb_portable_preflight_validates_expression_shapes(
    predicate: dict[str, Any], requirement: str
) -> None:
    compiler = DuckDBTransformCompiler()
    definition = {
        "inputs": {"input": {}},
        "actions": [
            {
                "kind": {
                    "id": "filter",
                    "action": "dtcs:filter",
                    "parameters": {"predicate": predicate},
                }
            }
        ],
        "outputs": {"result": {}},
    }
    report = compiler.analyze(
        definition,
        context=TransformPlanningContext(
            pipeline_id="p",
            step_name="step",
            profile_name="test",
            engine="duckdb",
        ),
    )
    assert report.supported is False
    assert requirement in {finding.requirement for finding in report.findings}
    with pytest.raises(ValueError, match="Cannot compile unsupported DuckDB plan"):
        compiler.compile(
            definition,
            context=TransformCompileContext(
                pipeline_id="p",
                plan_id="plan",
                step_name="step",
                profile_name="test",
                engine="duckdb",
            ),
        )


def test_duckdb_portable_preflight_rejects_unsupported_declared_type() -> None:
    compiler = DuckDBTransformCompiler()
    definition = {
        "inputs": {
            "input": {"schema": {"fields": [{"name": "value", "type": "STRING[]"}]}}
        },
        "actions": [],
        "outputs": {"result": {}},
    }
    report = compiler.analyze(
        definition,
        context=TransformPlanningContext(
            pipeline_id="p",
            step_name="step",
            profile_name="test",
            engine="duckdb",
        ),
    )
    assert report.supported is False
    assert "type:STRING[]" in {finding.requirement for finding in report.findings}


def test_duckdb_portable_preflight_rejects_malformed_join() -> None:
    compiler = DuckDBTransformCompiler()
    definition = {
        "inputs": {"left": {}, "right": {}},
        "actions": [
            {
                "kind": {
                    "id": "join",
                    "action": "dtcs:join",
                    "parameters": {
                        "right": "right",
                        "leftKey": "id",
                        "collisionPolicy": "suffix",
                    },
                }
            }
        ],
        "outputs": {"result": {}},
    }
    report = compiler.analyze(
        definition,
        context=TransformPlanningContext(
            pipeline_id="p",
            step_name="step",
            profile_name="test",
            engine="duckdb",
        ),
    )
    assert report.supported is False
    requirements = {finding.requirement for finding in report.findings}
    assert "join.collisionPolicy:suffix" in requirements
    assert "identifier" in requirements
    assert all(finding.evidence_fingerprint for finding in report.findings)


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


@pytest.mark.parametrize("fail_execution", [False, True])
def test_duckdb_file_backed_portable_staging_is_temporary(
    tmp_path: Path, fail_execution: bool
) -> None:
    database = tmp_path / f"portable-{fail_execution}.duckdb"
    plugin = DuckDBSqlPlugin(
        config=DuckDBConfig.from_database(database, allowed_paths=(str(database),))
    )
    compiler = DuckDBTransformCompiler()
    predicate_right: dict[str, Any] = (
        {"kind": "fieldRef", "scope": "parameter", "target": "minimum"}
        if fail_execution
        else {"kind": "literal", "value": 0}
    )
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
                            "right": predicate_right,
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
    execution = compiler.execute(
        compiled,
        inputs={"input": [{"id": 1}]},
        parameters={},
        context=TransformExecutionContext(
            run_id=f"temporary-{fail_execution}",
            pipeline_id="p",
            plan_id="plan",
            step_name="step",
            engine="duckdb",
            metadata={"_sql_plugin": plugin},
        ),
    )
    if fail_execution:
        with pytest.raises(ValueError, match="missing DuckDB transform parameter"):
            asyncio.run(execution)
    else:
        output = asyncio.run(execution)
        assert output.valid["result"].to_dicts() == [{"id": 1}]

    plugin.cleanup_run(run_id=f"temporary-{fail_execution}")
    check = duckdb.connect(database=str(database), read_only=True)
    try:
        tables = check.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_name LIKE 'pl_in_%'"
        ).fetchall()
    finally:
        check.close()
    assert tables == []


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


def test_duckdb_load_empty_typed_relation_is_real_and_untyped_load_fails() -> None:
    plugin = create_plugin()
    context = _context("empty-load")
    loaded = plugin.load_records(
        [],
        target=RelationRef(name="empty_items"),
        context=context,
        column_types={"id": "BIGINT", "label": "VARCHAR"},
    )
    assert loaded.outcome.value == "committed"
    inspected = plugin.inspect_relation(
        RelationRef(name="empty_items"), context=context
    )
    assert [field["name"] for field in inspected["fields"]] == ["id", "label"]
    fetched = plugin.fetch_records(
        RelationRef(name="empty_items"), params={}, context=context
    )
    assert fetched.outcome.value == "committed"
    assert fetched.records == []
    untyped = plugin.load_records(
        [], target=RelationRef(name="no_schema"), context=context
    )
    assert untyped.outcome.value == "rolled_back"
    assert untyped.diagnostics[0]["code"] == "PMDUCK510"
    plugin.cleanup_run(run_id=context.run_id)


def test_duckdb_portable_nonempty_input_keeps_declared_missing_fields() -> None:
    compiler = DuckDBTransformCompiler()
    definition = {
        "inputs": {
            "input": {
                "schema": {
                    "fields": [
                        {"name": "id", "type": "integer"},
                        {"name": "label", "type": "string"},
                    ]
                }
            }
        },
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
            inputs={"input": [{"id": 1}]},
            parameters={},
            context=TransformExecutionContext(
                run_id="declared-missing-field",
                pipeline_id="p",
                plan_id="plan",
                step_name="step",
                engine="duckdb",
            ),
        )
    )
    frame = output.valid["result"]
    assert frame.columns == ["id", "label"]
    assert frame.to_dicts() == [{"id": 1, "label": None}]


def test_duckdb_portable_nonempty_input_preserves_declared_column_order() -> None:
    compiler = DuckDBTransformCompiler()
    definition = {
        "inputs": {
            "input": {
                "schema": {
                    "fields": [
                        {"name": "label", "type": "string"},
                        {"name": "id", "type": "integer"},
                    ]
                }
            }
        },
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
            inputs={"input": [{"id": 1}]},
            parameters={},
            context=TransformExecutionContext(
                run_id="declared-order",
                pipeline_id="p",
                plan_id="plan",
                step_name="step",
                engine="duckdb",
            ),
        )
    )
    frame = output.valid["result"]
    assert frame.columns == ["label", "id"]
    assert frame.to_dicts() == [{"label": None, "id": 1}]

    frame_output = asyncio.run(
        compiler.execute(
            compiled,
            inputs={"input": DuckDBFrame([{"id": 1}], ["id"], {"id": "BIGINT"})},
            parameters={},
            context=TransformExecutionContext(
                run_id="declared-order-frame",
                pipeline_id="p",
                plan_id="plan",
                step_name="step",
                engine="duckdb",
            ),
        )
    )
    frame_result = frame_output.valid["result"]
    assert frame_result.columns == ["label", "id"]
    assert frame_result.to_dicts() == [{"label": None, "id": 1}]


def test_duckdb_inspect_unqualified_relation_uses_resolved_schema() -> None:
    plugin = create_plugin()
    context = _context("inspect-schema")
    session = plugin.connections.session(context.run_id)
    session.execute("CREATE TABLE main.same_name (id BIGINT)")
    session.execute("CREATE SCHEMA other")
    session.execute("CREATE TABLE other.same_name (label VARCHAR)")
    inspected = plugin.inspect_relation(RelationRef(name="same_name"), context=context)
    assert [field["name"] for field in inspected["fields"]] == ["id"]
    plugin.cleanup_run(run_id=context.run_id)


def test_duckdb_portable_empty_native_types_round_trip() -> None:
    compiler = DuckDBTransformCompiler()
    definition = {"inputs": {"input": {}}, "actions": [], "outputs": {"result": {}}}
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
    expected_types = {
        "TINYINT": "TINYINT",
        "SMALLINT": "SMALLINT",
        "INTEGER": "INTEGER",
        "INTERVAL": "INTERVAL",
        "TIMESTAMPTZ": "TIMESTAMP WITH TIME ZONE",
        "UUID": "UUID",
        "BLOB": "BLOB",
    }
    for index, native_type in enumerate(expected_types):
        output = asyncio.run(
            compiler.execute(
                compiled,
                inputs={"input": DuckDBFrame([], ["value"], {"value": native_type})},
                parameters={},
                context=TransformExecutionContext(
                    run_id=f"native-round-trip-{index}",
                    pipeline_id="p",
                    plan_id="plan",
                    step_name="step",
                    engine="duckdb",
                ),
            )
        )
        assert (
            output.valid["result"].column_types["value"] == expected_types[native_type]
        )


def test_duckdb_portable_rejects_unsupported_type_shapes() -> None:
    compiler = DuckDBTransformCompiler()
    definition = {"inputs": {"input": {}}, "actions": [], "outputs": {"result": {}}}
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
    for index, unsupported_type in enumerate(("BOOLEAN[]", "TIMESTAMP[]", "STRING[]")):
        with pytest.raises(ValueError, match="unsupported DuckDB declared type"):
            asyncio.run(
                compiler.execute(
                    compiled,
                    inputs={
                        "input": DuckDBFrame([], ["value"], {"value": unsupported_type})
                    },
                    parameters={},
                    context=TransformExecutionContext(
                        run_id=f"unsupported-type-{index}",
                        pipeline_id="p",
                        plan_id="plan",
                        step_name="step",
                        engine="duckdb",
                    ),
                )
            )


def test_duckdb_portable_rejects_unsupported_nonempty_type_shapes() -> None:
    compiler = DuckDBTransformCompiler()
    definition = {"inputs": {"input": {}}, "actions": [], "outputs": {"result": {}}}
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
    for index, (unsupported_type, value) in enumerate(
        (("BOOLEAN[]", True), ("TIMESTAMP[]", "2024-01-01"), ("STRING[]", "x"))
    ):
        plugin = create_plugin()
        run_id = f"unsupported-nonempty-{index}"
        with pytest.raises(ValueError, match="unsupported DuckDB declared type"):
            asyncio.run(
                compiler.execute(
                    compiled,
                    inputs={
                        "input": DuckDBFrame(
                            [{"value": value}],
                            ["value"],
                            {"value": unsupported_type},
                        )
                    },
                    parameters={},
                    context=TransformExecutionContext(
                        run_id=run_id,
                        pipeline_id="p",
                        plan_id="plan",
                        step_name="step",
                        engine="duckdb",
                        metadata={"_sql_plugin": plugin},
                    ),
                )
            )
        relation = plugin.inspect_relation(
            RelationRef(
                name="pl_in_unsupported_nonempty_" + str(index) + "_step_1_input"
            ),
            context=_context(run_id),
        )
        assert relation["fields"] == []
        plugin.cleanup_run(run_id=run_id)


def test_duckdb_compiler_fingerprint_includes_type_semantics() -> None:
    import etlantic_duckdb.transform_compiler as transform_compiler

    original = transform_compiler._NATIVE_DUCKDB_TYPES
    try:
        baseline = DuckDBTransformCompiler().info.evidence_fingerprint
        transform_compiler._NATIVE_DUCKDB_TYPES = frozenset(set(original) - {"UUID"})
        changed = DuckDBTransformCompiler().info.evidence_fingerprint
    finally:
        transform_compiler._NATIVE_DUCKDB_TYPES = original
    assert changed != baseline


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


def test_duckdb_load_statement_budget_is_enforced() -> None:
    plugin = DuckDBSqlPlugin(config=DuckDBConfig(max_statements=1))
    context = _context("load-budget")
    result = plugin.load_records(
        [{"id": 1}], target=RelationRef(name="budget_items"), context=context
    )
    assert result.outcome is TransactionOutcome.ROLLED_BACK
    assert result.diagnostics[0]["code"] == "PMDUCK511"
    assert plugin.connections.session(context.run_id).statement_count == 0
    assert (
        plugin.inspect_relation(RelationRef(name="budget_items"), context=context)[
            "fields"
        ]
        == []
    )
    plugin.cleanup_run(run_id=context.run_id)


def test_duckdb_load_statement_budget_exact_boundaries() -> None:
    empty_plugin = DuckDBSqlPlugin(config=DuckDBConfig(max_statements=1))
    empty_context = _context("load-budget-empty-exact")
    empty = empty_plugin.load_records(
        [],
        target=RelationRef(name="empty_items"),
        context=empty_context,
        column_types={"id": "BIGINT"},
    )
    assert empty.outcome is TransactionOutcome.COMMITTED
    assert empty_plugin.connections.session(empty_context.run_id).statement_count == 1
    empty_plugin.cleanup_run(run_id=empty_context.run_id)

    row_plugin = DuckDBSqlPlugin(config=DuckDBConfig(max_statements=2))
    row_context = _context("load-budget-row-exact")
    row = row_plugin.load_records(
        [{"id": 1}], target=RelationRef(name="row_items"), context=row_context
    )
    assert row.outcome is TransactionOutcome.COMMITTED
    assert row_plugin.connections.session(row_context.run_id).statement_count == 2
    over = row_plugin.load_records(
        [],
        target=RelationRef(name="over_items"),
        context=row_context,
        column_types={"id": "BIGINT"},
    )
    assert over.outcome is TransactionOutcome.ROLLED_BACK
    assert over.diagnostics[0]["code"] == "PMDUCK511"
    assert row_plugin.connections.session(row_context.run_id).statement_count == 2
    row_session = row_plugin.connections.session(row_context.run_id)
    assert row_session.connection.execute(
        "SELECT count(*) FROM row_items"
    ).fetchone() == (1,)
    with pytest.raises(duckdb.CatalogException):
        row_session.connection.execute("SELECT count(*) FROM over_items")
    row_plugin.cleanup_run(run_id=row_context.run_id)


def test_duckdb_execute_begin_acknowledgement_loss_rolls_back_and_recovers() -> None:
    plugin = create_plugin()
    context = _context("execute-begin-ack")
    session = plugin.connections.session(context.run_id)
    session.execute("CREATE TABLE begin_items (id BIGINT)")
    statement = plugin.compile_query(
        SqlQuery(source=RelationRef(name="begin_items")), context=context
    )
    connection = session.connection
    session.connection = cast(
        Any, _CommitAcknowledgementLost(connection, "BEGIN", fail_once=True)
    )
    first = plugin.execute([statement], params={}, context=context)
    assert first.outcome is TransactionOutcome.ROLLED_BACK
    assert plugin.connections.active_run_ids() == (context.run_id,)
    second = plugin.execute([statement], params={}, context=context)
    assert second.outcome is TransactionOutcome.COMMITTED
    plugin.cleanup_run(run_id=context.run_id)


def test_duckdb_load_begin_acknowledgement_loss_rolls_back_and_recovers() -> None:
    plugin = create_plugin()
    context = _context("load-begin-ack")
    session = plugin.connections.session(context.run_id)
    connection = session.connection
    session.connection = cast(
        Any, _CommitAcknowledgementLost(connection, "BEGIN", fail_once=True)
    )
    first = plugin.load_records(
        [{"id": 1}], target=RelationRef(name="begin_items"), context=context
    )
    assert first.outcome is TransactionOutcome.ROLLED_BACK
    second = plugin.load_records(
        [{"id": 2}], target=RelationRef(name="begin_items"), context=context
    )
    assert second.outcome is TransactionOutcome.COMMITTED
    plugin.cleanup_run(run_id=context.run_id)


def test_duckdb_begin_acknowledgement_loss_discards_uncertain_session() -> None:
    plugin = create_plugin()
    context = _context("begin-uncertain")
    session = plugin.connections.session(context.run_id)
    session.execute("CREATE TABLE begin_items (id BIGINT)")
    statement = plugin.compile_query(
        SqlQuery(source=RelationRef(name="begin_items")), context=context
    )
    connection = session.connection
    session.connection = cast(
        Any, _CommitAcknowledgementLost(connection, ("BEGIN", "ROLLBACK"))
    )
    result = plugin.execute([statement], params={}, context=context)
    assert result.outcome is TransactionOutcome.UNKNOWN
    assert plugin.connections.active_run_ids() == ()
    assert statement.statement_id not in plugin._sealed


def test_duckdb_load_commit_acknowledgement_loss_is_unknown(
    tmp_path: Path,
) -> None:
    database = tmp_path / "load-commit-ack.duckdb"
    plugin = DuckDBSqlPlugin(
        config=DuckDBConfig.from_database(database, allowed_paths=(str(database),))
    )
    context = _context("load-commit-ack")
    session = plugin.connections.session(context.run_id)
    connection = session.connection
    session.connection = cast(
        Any, _CommitAcknowledgementLost(connection, fail_close=True)
    )
    result = plugin.load_records(
        [{"id": 1}], target=RelationRef(name="ack_items"), context=context
    )
    assert result.outcome is TransactionOutcome.UNKNOWN
    assert [diagnostic["code"] for diagnostic in result.diagnostics].count(
        "PMDUCK500"
    ) == 1
    assert [diagnostic["code"] for diagnostic in result.diagnostics].count(
        "PMDUCK510"
    ) == 1
    assert plugin.connections.active_run_ids() == ()
    check = duckdb.connect(database=str(database), read_only=True)
    count = check.execute("SELECT count(*) FROM ack_items").fetchone()
    check.close()
    assert count is not None
    assert count[0] == 1
    assert plugin.connections.active_run_ids() == ()


def test_duckdb_selected_sql_engine_survives_spark_primary_profile() -> None:
    plugin = create_plugin()
    registry = builtin_stub_registry()
    register_discovered_plugins(registry, plugins={"duckdb": plugin})
    registry.engines["pyspark"] = PluginCapabilities(
        engine="pyspark",
        spark=True,
        lazy=True,
        schema_inspection=True,
    )
    registry.register_binding(
        BindingDescriptor(binding="raw_items", provider="sql", location="raw_items")
    )
    registry.register_binding(
        BindingDescriptor(
            binding="ack_items",
            provider="sql",
            location="ack_items",
            metadata={"write_intent": "insert_select"},
        )
    )
    profile = Profile(
        name="duckdb-hybrid-planning",
        sql_engine="duckdb",
        spark_engine="pyspark",
    )
    plan = _OrchestrationPipeline.plan(
        profile=profile,
        context=PlanningContext.create(profile, registry=registry),
    )
    assert profile.primary_engine() == "pyspark"
    assert plan.execution_settings["sql_engine"] == "duckdb"
    assert {region.engine for region in plan.regions} == {"duckdb"}
    assert {unit.engine for unit in plan.physical_units} == {"duckdb"}


def test_duckdb_execute_write_commit_acknowledgement_loss_is_unknown(
    tmp_path: Path,
) -> None:
    database = tmp_path / "execute-write-commit-ack.duckdb"
    plugin = DuckDBSqlPlugin(
        config=DuckDBConfig.from_database(database, allowed_paths=(str(database),))
    )
    context = _context("execute-commit-ack")
    session = plugin.connections.session(context.run_id)
    session.execute("CREATE TABLE source_items (id BIGINT)")
    session.execute("INSERT INTO source_items VALUES (1)")
    session.execute("CREATE TABLE ack_items (id BIGINT)")
    connection = session.connection
    session.connection = cast(
        Any, _CommitAcknowledgementLost(connection, fail_close=True)
    )
    plan = PipelinePlan(
        schema="etlantic.plan/1",
        plan_id="ack-plan",
        pipeline_id="ack-pipeline",
        pipeline_name="ack-pipeline",
        profile_name="test",
        fingerprint="ack-fingerprint",
        logical_graph=LogicalGraph(
            pipeline_id="ack-pipeline", pipeline_name="ack-pipeline"
        ),
    )
    node = Node(
        name="sink",
        kind=NodeKind.SINK,
        identity="sink",
        binding="ack_items",
    )
    result = asyncio.run(
        execute_sql_sink(
            plugin=plugin,
            node=node,
            source_value=RelationRef(name="source_items"),
            plan=plan,
            run_id=context.run_id,
            attempt=1,
            target_location="ack_items",
            write_intent="insert_select",
        )
    )
    assert result.outcome is TransactionOutcome.UNKNOWN
    assert any(diagnostic["code"] == "PMSQL440" for diagnostic in result.diagnostics)
    assert [diagnostic["code"] for diagnostic in result.diagnostics].count(
        "PMDUCK500"
    ) == 2
    assert plugin.connections.active_run_ids() == ()
    orchestrator = LocalOrchestrator.__new__(LocalOrchestrator)
    orchestrator.request = RunRequest(
        intent=RunIntent.STANDARD, retry=RetryPolicy(max_attempts=3)
    )
    assert (
        orchestrator._should_retry(
            NodeExecutionError(
                "unknown",
                node_name="sink",
                stage="publication",
                code="PMEXEC434",
            )
        )
        is False
    )
    check = duckdb.connect(database=str(database), read_only=True)
    count = check.execute("SELECT count(*) FROM ack_items").fetchone()
    check.close()
    assert count is not None
    assert count[0] == 1


def test_duckdb_unknown_commit_is_not_retried_by_orchestrator(
    tmp_path: Path,
) -> None:
    database = tmp_path / "orchestration-commit-ack.duckdb"
    plugin = DuckDBSqlPlugin(
        config=DuckDBConfig.from_database(database, allowed_paths=(str(database),))
    )
    setup = plugin.connections.session("setup")
    setup.execute("CREATE TABLE raw_items (id BIGINT)")
    setup.execute("INSERT INTO raw_items VALUES (1)")
    setup.execute("CREATE TABLE ack_items (id BIGINT)")
    plugin.cleanup_run(run_id="setup")

    original_session = plugin.connections.session

    def session_for_run(run_id: str) -> Any:
        session = original_session(run_id)
        if str(run_id) == "orchestration-ack" and not isinstance(
            session.connection, _CommitAcknowledgementLost
        ):
            session.connection = cast(
                Any,
                _CommitAcknowledgementLost(session.connection, fail_close=True),
            )
        return session

    plugin.connections.session = session_for_run
    registry = builtin_stub_registry()
    register_discovered_plugins(registry, plugins={"duckdb": plugin})
    registry.register_binding(
        BindingDescriptor(binding="raw_items", provider="sql", location="raw_items")
    )
    registry.register_binding(
        BindingDescriptor(
            binding="ack_items",
            provider="sql",
            location="ack_items",
            metadata={"write_intent": "insert_select"},
        )
    )
    profile = Profile(name="duckdb-orchestration", sql_engine="duckdb")
    planning = PlanningContext.create(profile, registry=registry)
    plan = _OrchestrationPipeline.plan(profile=profile, context=planning)
    assert {region.engine for region in plan.regions} == {"duckdb"}
    assert {unit.engine for unit in plan.physical_units} == {"duckdb"}
    runtime = PipelineRuntime(registry=registry)
    runtime.register_sql_plugin("duckdb", plugin)
    orchestrator = LocalOrchestrator(
        runtime=runtime,
        plan=plan,
        request=RunRequest(
            intent=RunIntent.STANDARD,
            retry=RetryPolicy(max_attempts=3),
        ),
        pipeline_cls=_OrchestrationPipeline,
        run_id="orchestration-ack",
    )
    report = asyncio.run(orchestrator.execute())

    sink = next(step for step in report.steps if step.step_name == "out")
    assert report.status.value == "partial"
    assert sink.attempts == 1
    assert any(diagnostic.code == "PMEXEC434" for diagnostic in report.diagnostics)
    check = duckdb.connect(database=str(database), read_only=True)
    count = check.execute("SELECT count(*) FROM ack_items").fetchone()
    check.close()
    assert count is not None
    assert count[0] == 1
    assert plugin.connections.active_run_ids() == ()


def test_duckdb_execute_session_failure_is_rolled_back_and_retryable(
    tmp_path: Path,
) -> None:
    database = tmp_path / "execute-session-failure.duckdb"
    plugin = DuckDBSqlPlugin(
        config=DuckDBConfig.from_database(database, allowed_paths=(str(database),))
    )
    setup = plugin.connections.session("setup")
    setup.execute("CREATE TABLE items (id BIGINT)")
    setup.execute("INSERT INTO items VALUES (1)")
    plugin.cleanup_run(run_id="setup")
    context = _context("session-failure-execute")
    statement = plugin.compile_query(
        SqlQuery(source=RelationRef(name="items")), context=context
    )
    original_session = plugin.connections.session
    calls = 0

    def fail_once(run_id: str) -> Any:
        nonlocal calls
        if calls == 0:
            calls += 1
            raise RuntimeError("connection unavailable")
        return original_session(run_id)

    plugin.connections.session = fail_once
    first = plugin.execute([statement], params={}, context=context)
    assert first.outcome is TransactionOutcome.ROLLED_BACK
    assert first.metrics.statements == 0
    assert plugin.connections.active_run_ids() == ()
    second = plugin.execute([statement], params={}, context=context)
    assert second.outcome is TransactionOutcome.COMMITTED
    plugin.cleanup_run(run_id=context.run_id)


def test_duckdb_load_session_failure_is_rolled_back_and_retryable() -> None:
    plugin = create_plugin()
    context = _context("session-failure-load")
    original_session = plugin.connections.session
    calls = 0

    def fail_once(run_id: str) -> Any:
        nonlocal calls
        if calls == 0:
            calls += 1
            raise RuntimeError("connection unavailable")
        return original_session(run_id)

    plugin.connections.session = fail_once
    first = plugin.load_records(
        [{"id": 1}], target=RelationRef(name="items"), context=context
    )
    assert first.outcome is TransactionOutcome.ROLLED_BACK
    assert first.metrics.statements == 0
    assert plugin.connections.active_run_ids() == ()
    second = plugin.load_records(
        [{"id": 1}], target=RelationRef(name="items"), context=context
    )
    assert second.outcome is TransactionOutcome.COMMITTED
    plugin.cleanup_run(run_id=context.run_id)


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
