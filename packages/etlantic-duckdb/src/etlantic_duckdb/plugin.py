"""DuckDB implementation of ``etlantic.sql/1``."""

from __future__ import annotations

import contextlib
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from etlantic.capabilities import PluginCapabilities
from etlantic.sql.helpers import require_safe_identifier
from etlantic.sql.protocol import (
    SQL_PROTOCOL_VERSION,
    CompiledSql,
    RelationRef,
    SqlExecutionContext,
    SqlExecutionResult,
    SqlMetrics,
    SqlPluginInfo,
    SqlQuery,
    SqlWrite,
    TransactionOutcome,
)
from etlantic_duckdb.config import DuckDBConfig
from etlantic_duckdb.connection import DuckDBConnectionManager
from etlantic_duckdb.dialect import DuckDBCompiler, quote_identifier, statement_digest

__version__ = "0.48.0"


def create_plugin() -> DuckDBSqlPlugin:
    return DuckDBSqlPlugin()


class DuckDBSqlPlugin:
    """Explicit-connection DuckDB SQL plugin.

    The plugin is intentionally conservative: only closed SQL IR can be
    compiled, and only statements sealed by this instance may execute.
    """

    def __init__(self, *, config: DuckDBConfig | None = None) -> None:
        self.config = config or DuckDBConfig()
        self.connections = DuckDBConnectionManager(self.config)
        self._compiler = DuckDBCompiler()
        self._rows_fetched = 0
        self._sealed: dict[str, tuple[str, dict[str, Any], str, str]] = {}
        caps = PluginCapabilities(
            engine="duckdb",
            async_execution=False,
            dataframe=False,
            sql=True,
            transactions=True,
            schema_inspection=True,
            thread_safe=False,
            eager=False,
            lazy=False,
            sql_cte=True,
            sql_returning=True,
            sql_transactional_ddl=True,
            sql_atomic_rename=True,
            sql_catalog_inspect=True,
            sql_trusted_fragments=False,
            extras=frozenset(
                {
                    "portable",
                    "source.batch_snapshot",
                    "write.append",
                    "write.insert_select",
                    "write.replace",
                    "publication.atomic",
                }
            ),
        )
        self._info = SqlPluginInfo(
            name="etlantic-duckdb",
            engine="duckdb",
            dialect="duckdb",
            version=__version__,
            protocol_version=SQL_PROTOCOL_VERSION,
            capabilities=caps,
        )

    @property
    def info(self) -> SqlPluginInfo:
        return self._info

    def capabilities(self) -> PluginCapabilities:
        assert self._info.capabilities is not None
        return self._info.capabilities

    def rows_fetched_total(self) -> int:
        return self._rows_fetched

    def quote_identifier(self, name: str) -> str:
        return quote_identifier(name)

    def relation_from_binding(
        self,
        *,
        binding: str,
        location: str | None,
        metadata: Mapping[str, Any] | None = None,
    ) -> RelationRef:
        del metadata
        value = location or binding
        rel = RelationRef.parse(value)
        for part in (rel.catalog, rel.namespace, rel.name):
            if part is not None:
                require_safe_identifier(part)
        return rel

    def _seal(self, compiled: CompiledSql, *, run_id: str) -> CompiledSql:
        bound = dict(compiled.metadata.get("_bound_params") or {})
        public = replace(
            compiled,
            metadata={
                k: v for k, v in compiled.metadata.items() if not str(k).startswith("_")
            },
        )
        self._sealed[public.statement_id] = (
            statement_digest(public),
            bound,
            public.dialect,
            str(run_id),
        )
        return public

    def compile_query(
        self, query: SqlQuery, *, context: SqlExecutionContext
    ) -> CompiledSql:
        return self._seal(
            self._compiler.query(query, context=context), run_id=context.run_id
        )

    def compile_write(
        self, write: SqlWrite, *, context: SqlExecutionContext
    ) -> CompiledSql:
        return self._seal(
            self._compiler.write(write, context=context), run_id=context.run_id
        )

    def _resolve(
        self, stmt: CompiledSql, params: Mapping[str, Any], *, run_id: str
    ) -> tuple[str, dict[str, Any]]:
        record = self._sealed.get(stmt.statement_id)
        if record is None:
            raise ValueError("compiled DuckDB statement was not sealed by this plugin")
        expected, bound, dialect, owner_run_id = record
        if owner_run_id != str(run_id):
            raise ValueError("compiled DuckDB statement belongs to another run")
        if dialect != stmt.dialect or statement_digest(stmt) != expected:
            raise ValueError("compiled DuckDB statement was mutated or replayed")
        self._sealed.pop(stmt.statement_id, None)
        values = dict(bound)
        values.update(params)
        unknown = set(values) - set(stmt.param_names)
        if unknown:
            raise ValueError("unknown DuckDB SQL parameters")
        return stmt.text, values

    def execute(
        self,
        compiled: Sequence[CompiledSql],
        *,
        params: Mapping[str, Any],
        context: SqlExecutionContext,
        fetch: bool = False,
    ) -> SqlExecutionResult:
        session = self.connections.session(context.run_id)
        metrics = SqlMetrics(phases=["execute"])
        records: list[dict[str, Any]] = []
        started = False
        try:
            with session.lock:
                session.connection.execute("BEGIN")
                started = True
                for stmt in compiled:
                    text, values = self._resolve(stmt, params, run_id=context.run_id)
                    result = session.execute(text, values)
                    metrics.statements += 1
                    if fetch:
                        names = [str(item[0]) for item in result.description or ()]
                        remaining = self.config.max_result_rows - len(records)
                        rows_raw = result.fetchmany(max(remaining, 0) + 1)
                        if len(rows_raw) > remaining:
                            raise RuntimeError("DuckDB result row budget exceeded")
                        rows = [dict(zip(names, row, strict=False)) for row in rows_raw]
                        records.extend(rows)
                        self._rows_fetched += len(rows)
                        metrics.rows_fetched += len(rows)
                    else:
                        count = getattr(result, "rowcount", -1)
                        if isinstance(count, int) and count >= 0:
                            metrics.rows_affected = (metrics.rows_affected or 0) + count
                session.connection.execute("COMMIT")
            outcome = TransactionOutcome.COMMITTED
        except Exception as exc:
            try:
                if started:
                    session.connection.execute("ROLLBACK")
            except Exception:
                pass
            outcome = (
                TransactionOutcome.UNKNOWN
                if started and "commit" in str(exc).lower()
                else TransactionOutcome.ROLLED_BACK
            )
            return SqlExecutionResult(
                outcome=outcome,
                metrics=metrics,
                diagnostics=[
                    {
                        "code": "PMDUCK500",
                        "severity": "error",
                        "message": f"DuckDB execution failed ({type(exc).__name__})",
                    }
                ],
            )
        return SqlExecutionResult(
            outcome=outcome,
            metrics=metrics,
            compiled=list(compiled),
            records=records if fetch else None,
            backend_ref="duckdb",
        )

    def execute_write(
        self,
        write: SqlWrite,
        *,
        params: Mapping[str, Any],
        context: SqlExecutionContext,
    ) -> SqlExecutionResult:
        stmt = self.compile_write(write, context=context)
        result = self.execute([stmt], params=params, context=context)
        result.relation = (
            write.target if result.outcome is TransactionOutcome.COMMITTED else None
        )
        return result

    def materialize_temp(
        self,
        query: SqlQuery,
        *,
        temp_name: str,
        params: Mapping[str, Any],
        context: SqlExecutionContext,
    ) -> SqlExecutionResult:
        require_safe_identifier(temp_name)
        query_stmt = self.compile_query(query, context=context)
        bound = self._sealed[query_stmt.statement_id][1]
        self._sealed.pop(query_stmt.statement_id, None)
        temp_stmt = self._seal(
            CompiledSql(
                statement_id=f"duckdb:{temp_name}:{query_stmt.statement_id}",
                text=f"CREATE TEMP TABLE {quote_identifier(temp_name)} AS {query_stmt.text}",
                param_names=query_stmt.param_names,
                redacted_params=query_stmt.redacted_params,
                dialect="duckdb",
                logical_nodes=query_stmt.logical_nodes,
                metadata={"_bound_params": bound},
            ),
            run_id=context.run_id,
        )
        result = self.execute([temp_stmt], params=params, context=context)
        result.relation = (
            RelationRef(name=temp_name)
            if result.outcome is TransactionOutcome.COMMITTED
            else None
        )
        return result

    def load_records(
        self,
        records: Sequence[Any],
        *,
        target: RelationRef,
        context: SqlExecutionContext,
    ) -> SqlExecutionResult:
        rows = [
            item.model_dump() if hasattr(item, "model_dump") else dict(item)
            for item in records
        ]
        if not rows:
            return SqlExecutionResult(
                outcome=TransactionOutcome.COMMITTED, relation=target
            )
        for row in rows:
            for key in row:
                require_safe_identifier(str(key))
        columns = list(rows[0])
        session = self.connections.session(context.run_id)
        table = ".".join(
            quote_identifier(part)
            for part in (target.catalog, target.namespace, target.name)
            if part
        )
        defs = ", ".join(
            f"{quote_identifier(c)} {_duck_type(rows, c)}" for c in columns
        )
        placeholders = ", ".join("?" for _ in columns)
        try:
            with session.lock:
                session.connection.execute("BEGIN")
                session.connection.execute(
                    f"CREATE TABLE IF NOT EXISTS {table} ({defs})"
                )
                session.connection.executemany(
                    f"INSERT INTO {table} ({', '.join(quote_identifier(c) for c in columns)}) VALUES ({placeholders})",
                    [tuple(row.get(c) for c in columns) for row in rows],
                )
                session.connection.execute("COMMIT")
            return SqlExecutionResult(
                outcome=TransactionOutcome.COMMITTED,
                relation=target,
                metrics=SqlMetrics(
                    rows_affected=len(rows), statements=1 + len(rows), phases=["load"]
                ),
                backend_ref="duckdb",
            )
        except Exception as exc:
            with contextlib.suppress(Exception):
                session.connection.execute("ROLLBACK")
            return SqlExecutionResult(
                outcome=TransactionOutcome.ROLLED_BACK,
                diagnostics=[
                    {
                        "code": "PMDUCK510",
                        "severity": "error",
                        "message": f"DuckDB load failed ({type(exc).__name__})",
                    }
                ],
            )

    def fetch_records(
        self,
        relation: RelationRef | SqlQuery,
        *,
        params: Mapping[str, Any],
        context: SqlExecutionContext,
        contract_type: type[Any] | None = None,
    ) -> SqlExecutionResult:
        if isinstance(relation, SqlQuery):
            stmt = self.compile_query(relation, context=context)
        else:
            stmt = self._seal(
                CompiledSql(
                    # Include the run identity so concurrent executions cannot
                    # overwrite each other's sealed fetch statement.
                    statement_id=(
                        f"duckdb:fetch:{context.run_id}:{relation.qualified_name}"
                    ),
                    text=f"SELECT * FROM {'.'.join(quote_identifier(part) for part in (relation.catalog, relation.namespace, relation.name) if part)}",
                    dialect="duckdb",
                    logical_nodes=(context.step_name,),
                ),
                run_id=context.run_id,
            )
        result = self.execute([stmt], params=params, context=context, fetch=True)
        if contract_type is not None and result.records:
            result.records = [
                contract_type.model_validate(row) for row in result.records
            ]
        return result

    def inspect_relation(
        self, relation: RelationRef, *, context: SqlExecutionContext
    ) -> dict[str, Any]:
        session = self.connections.session(context.run_id)
        name = relation.name.replace("'", "''")
        rows = session.execute(
            "SELECT column_name, column_type, is_nullable FROM information_schema.columns WHERE table_name = ? ORDER BY ordinal_position",
            [name],
        ).fetchall()
        return {
            "identity": relation.qualified_name,
            "fields": [
                {
                    "name": row[0],
                    "type": row[1],
                    "nullable": str(row[2]).upper() == "YES",
                }
                for row in rows
            ],
        }

    def cleanup_run(self, *, run_id: str, **_: Any) -> None:
        owner = str(run_id)
        for statement_id, record in list(self._sealed.items()):
            if record[3] == owner:
                self._sealed.pop(statement_id, None)
        self.connections.cleanup_run(run_id)

    def cleanup_staging(self) -> None:
        # Backward-compatible hook; never closes another run's connection.
        self._sealed.clear()
        self.connections.cleanup_all()


def _duck_type(rows: list[dict[str, Any]], column: str) -> str:
    values = [row.get(column) for row in rows if row.get(column) is not None]
    if not values:
        return "VARCHAR"
    if all(isinstance(v, bool) for v in values):
        return "BOOLEAN"
    if all(isinstance(v, int) and not isinstance(v, bool) for v in values):
        return "BIGINT"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        return "DOUBLE"
    return "VARCHAR"
