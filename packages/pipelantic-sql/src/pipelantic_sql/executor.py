"""Connection / transaction execution for compiled SQL."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from pipelantic.sql.helpers import require_safe_identifier
from pipelantic.sql.protocol import (
    CompiledSql,
    RelationRef,
    SqlExecutionContext,
    SqlExecutionResult,
    SqlMetrics,
    SqlQuery,
    TransactionOutcome,
)
from pipelantic_sql.compiler import SqlCompiler
from pipelantic_sql.dialect_postgresql import quote_identifier


class SqlExecutor:
    """Run compiled statements inside a transaction."""

    def __init__(
        self,
        *,
        engine: Engine,
        dialect: str,
        rows_fetched_counter: list[int],
    ) -> None:
        self.engine = engine
        self.dialect = dialect
        # mutable single-element list shared with plugin for instrumentation
        self._rows_fetched = rows_fetched_counter

    def execute(
        self,
        compiled: Sequence[CompiledSql],
        *,
        params: Mapping[str, Any],
        context: SqlExecutionContext,
        fetch: bool = False,
    ) -> SqlExecutionResult:
        _ = context
        metrics = SqlMetrics(statements=0, phases=["execute"])
        results: list[CompiledSql] = []
        records: list[Any] | None = None
        outcome = TransactionOutcome.NOT_STARTED
        try:
            with self.engine.begin() as conn:
                outcome = TransactionOutcome.COMMITTED
                for stmt in compiled:
                    bound = dict(stmt.metadata.get("_bound_params") or {})
                    bound.update(params)
                    public = CompiledSql(
                        statement_id=stmt.statement_id,
                        text=stmt.text,
                        param_names=stmt.param_names,
                        redacted_params=stmt.redacted_params,
                        dialect=stmt.dialect,
                        logical_nodes=stmt.logical_nodes,
                        metadata={
                            k: v
                            for k, v in stmt.metadata.items()
                            if k != "_bound_params"
                        },
                    )
                    results.append(public)
                    for part in stmt.text.split(";;"):
                        part = part.strip()
                        if not part:
                            continue
                        result = conn.execute(text(part), bound)
                        metrics.statements += 1
                        if fetch:
                            rows = [dict(row._mapping) for row in result]
                            self._rows_fetched[0] += len(rows)
                            metrics.rows_fetched += len(rows)
                            records = (records or []) + rows
                        elif result.rowcount is not None and result.rowcount >= 0:
                            metrics.rows_affected = (metrics.rows_affected or 0) + int(
                                result.rowcount
                            )
        except Exception as exc:
            if "connection" in str(exc).lower() and "commit" in str(exc).lower():
                outcome = TransactionOutcome.UNKNOWN
            else:
                outcome = TransactionOutcome.ROLLED_BACK
            return SqlExecutionResult(
                outcome=outcome,
                metrics=metrics,
                compiled=results,
                diagnostics=[
                    {
                        "code": "PMSQL500",
                        "severity": "error",
                        "message": str(exc),
                    }
                ],
            )
        return SqlExecutionResult(
            outcome=outcome,
            metrics=metrics,
            compiled=results,
            records=records,
            backend_ref=f"sqlalchemy:{self.dialect}",
        )

    def materialize_temp(
        self,
        compiler: SqlCompiler,
        query: SqlQuery,
        *,
        temp_name: str,
        params: Mapping[str, Any],
        context: SqlExecutionContext,
    ) -> SqlExecutionResult:
        require_safe_identifier(temp_name)
        compiled = compiler.compile_query(query, context=context)
        bound = dict(compiled.metadata.get("_bound_params") or {})
        bound.update(params)
        qid = quote_identifier(temp_name, dialect=self.dialect)
        if self.dialect == "postgresql":
            sql = (
                f"DROP TABLE IF EXISTS {qid};;"
                f"CREATE TEMP TABLE {qid} AS {compiled.text}"
            )
        else:
            sql = (
                f"DROP TABLE IF EXISTS {qid};;"
                f"CREATE TEMPORARY TABLE {qid} AS {compiled.text}"
            )
        stmt = CompiledSql(
            statement_id=f"temp:{temp_name}",
            text=sql,
            param_names=tuple(bound.keys()),
            redacted_params={k: "<redacted>" for k in bound},
            dialect=self.dialect,
            logical_nodes=(context.step_name,),
            metadata={"_bound_params": bound},
        )
        result = self.execute([stmt], params={}, context=context, fetch=False)
        result.relation = RelationRef(name=temp_name)
        result.metrics.fused_steps = 1
        return result

    def load_records(
        self,
        records: Sequence[Any],
        *,
        target: RelationRef,
        context: SqlExecutionContext,
        compiler: SqlCompiler,
    ) -> SqlExecutionResult:
        _ = context
        rows = [
            r.model_dump() if hasattr(r, "model_dump") else dict(r) for r in records
        ]
        if not rows:
            return SqlExecutionResult(
                outcome=TransactionOutcome.COMMITTED,
                relation=target,
                metrics=SqlMetrics(rows_affected=0, phases=["load"]),
            )
        cols = list(rows[0].keys())
        for c in cols:
            require_safe_identifier(c)
        col_sql = ", ".join(compiler.quote(c) for c in cols)
        placeholders = ", ".join(f":{c}" for c in cols)
        target_sql = compiler.qid(target)
        create_cols = ", ".join(f"{compiler.quote(c)} TEXT" for c in cols)
        create = f"CREATE TABLE IF NOT EXISTS {target_sql} ({create_cols})"
        insert = f"INSERT INTO {target_sql} ({col_sql}) VALUES ({placeholders})"
        try:
            with self.engine.begin() as conn:
                conn.execute(text(create))
                for row in rows:
                    conn.execute(text(insert), row)
            return SqlExecutionResult(
                outcome=TransactionOutcome.COMMITTED,
                relation=target,
                metrics=SqlMetrics(
                    rows_affected=len(rows),
                    phases=["load"],
                    statements=1 + len(rows),
                ),
                backend_ref=f"sqlalchemy:{self.dialect}",
            )
        except Exception as exc:
            return SqlExecutionResult(
                outcome=TransactionOutcome.ROLLED_BACK,
                diagnostics=[
                    {"code": "PMSQL510", "severity": "error", "message": str(exc)}
                ],
            )

    def fetch_records(
        self,
        compiler: SqlCompiler,
        relation: RelationRef | SqlQuery,
        *,
        params: Mapping[str, Any],
        context: SqlExecutionContext,
        contract_type: type[Any] | None = None,
    ) -> SqlExecutionResult:
        if isinstance(relation, SqlQuery):
            compiled = compiler.compile_query(relation, context=context)
        else:
            compiled = CompiledSql(
                statement_id=f"fetch:{relation.qualified_name}",
                text=f"SELECT * FROM {compiler.qid(relation)}",
                dialect=self.dialect,
                logical_nodes=(context.step_name,),
            )
        result = self.execute([compiled], params=params, context=context, fetch=True)
        if contract_type is not None and result.records:
            result.records = [contract_type.model_validate(r) for r in result.records]
        return result
