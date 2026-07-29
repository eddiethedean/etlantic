"""Connection / transaction execution for compiled SQL."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError

from etlantic.runtime.logging import redact_message
from etlantic.sql.helpers import require_safe_identifier
from etlantic.sql.protocol import (
    CompiledSql,
    RelationRef,
    SqlExecutionContext,
    SqlExecutionResult,
    SqlMetrics,
    SqlQuery,
    TransactionOutcome,
)
from etlantic_sql.compiler import SqlCompiler
from etlantic_sql.dialect_postgresql import quote_identifier


def _classify_failure(exc: BaseException, *, started: bool) -> TransactionOutcome:
    """Classify transaction failure; ambiguous post-start failures → UNKNOWN."""
    if isinstance(exc, (InterfaceError, OperationalError)):
        return TransactionOutcome.UNKNOWN if started else TransactionOutcome.ROLLED_BACK
    if isinstance(exc, DBAPIError) and getattr(exc, "connection_invalidated", False):
        return TransactionOutcome.UNKNOWN
    msg = str(exc).lower()
    if started and (
        "commit" in msg
        or "connection" in msg
        or "server closed" in msg
        or "broken pipe" in msg
    ):
        return TransactionOutcome.UNKNOWN
    return TransactionOutcome.ROLLED_BACK


class SqlExecutor:
    """Run compiled statements inside a transaction."""

    def __init__(
        self,
        *,
        engine: Engine,
        dialect: str,
        rows_fetched_counter: list[int],
        bound_params: MutableMapping[str, dict[str, Any]],
        staging_tables: list[str],
    ) -> None:
        self.engine = engine
        self.dialect = dialect
        self._rows_fetched = rows_fetched_counter
        self._bound_params = bound_params
        self._staging_tables = staging_tables

    def _resolve_bound(
        self, stmt: CompiledSql, params: Mapping[str, Any]
    ) -> dict[str, Any]:
        bound = dict(self._bound_params.pop(stmt.statement_id, {}))
        bound.update(params)
        return bound

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
        started = False
        try:
            with self.engine.begin() as conn:
                started = True
                for stmt in compiled:
                    bound = self._resolve_bound(stmt, params)
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
                            if not str(k).startswith("_")
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
                outcome = TransactionOutcome.COMMITTED
        except Exception as exc:
            outcome = _classify_failure(exc, started=started)
            return SqlExecutionResult(
                outcome=outcome,
                metrics=metrics,
                compiled=results,
                diagnostics=[
                    {
                        "code": "PMSQL500",
                        "severity": "error",
                        "message": redact_message(str(exc)),
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
        seal: Any,
    ) -> SqlExecutionResult:
        """Materialize as a durable run-scoped table (visible across pool checkouts)."""
        require_safe_identifier(temp_name)
        compiled = seal(compiler.compile_query(query, context=context))
        bound = dict(self._bound_params.get(compiled.statement_id) or {})
        bound.update(params)
        # Re-register after peek so execute can consume.
        if bound:
            self._bound_params[compiled.statement_id] = bound
        qid = quote_identifier(temp_name, dialect=self.dialect)
        sql = f"DROP TABLE IF EXISTS {qid};;CREATE TABLE {qid} AS {compiled.text}"
        stmt = seal(
            CompiledSql(
                statement_id=f"temp:{temp_name}:{compiled.statement_id}",
                text=sql,
                param_names=tuple(bound.keys()),
                redacted_params={k: "<redacted>" for k in bound},
                dialect=self.dialect,
                logical_nodes=(context.step_name,),
                metadata={"_bound_params": bound},
            )
        )
        result = self.execute([stmt], params={}, context=context, fetch=False)
        if result.outcome is TransactionOutcome.COMMITTED:
            result.relation = RelationRef(name=temp_name)
            if temp_name not in self._staging_tables:
                self._staging_tables.append(temp_name)
        else:
            result.relation = None
        result.metrics.fused_steps = 1
        return result

    def publish_replace(
        self,
        *,
        target: RelationRef,
        staging: RelationRef,
        compiler: SqlCompiler,
        context: SqlExecutionContext,
    ) -> SqlExecutionResult:
        """Swap staging into target without dropping the live table first."""
        _ = context
        target_sql = compiler.qid(target)
        staging_sql = compiler.qid(staging)
        old_name = f"{target.name}__old_{staging.name[-8:]}"
        require_safe_identifier(old_name)
        old = RelationRef(
            name=old_name, namespace=target.namespace, catalog=target.catalog
        )
        old_sql = compiler.qid(old)
        started = False
        try:
            with self.engine.begin() as conn:
                started = True
                # Detect existing target.
                exists = False
                if self.dialect == "postgresql":
                    row = conn.execute(
                        text(
                            "SELECT 1 FROM information_schema.tables "
                            "WHERE table_name = :name "
                            "AND (:schema IS NULL OR table_schema = :schema)"
                        ),
                        {"name": target.name, "schema": target.namespace or "public"},
                    ).first()
                    exists = row is not None
                else:
                    row = conn.execute(
                        text(
                            "SELECT 1 FROM sqlite_master "
                            "WHERE type='table' AND name = :name"
                        ),
                        {"name": target.name},
                    ).first()
                    exists = row is not None
                conn.execute(text(f"DROP TABLE IF EXISTS {old_sql}"))
                if exists:
                    conn.execute(
                        text(
                            f"ALTER TABLE {target_sql} RENAME TO "
                            f"{quote_identifier(old_name, dialect=self.dialect)}"
                        )
                    )
                conn.execute(
                    text(
                        f"ALTER TABLE {staging_sql} RENAME TO "
                        f"{quote_identifier(target.name, dialect=self.dialect)}"
                    )
                )
                if exists:
                    conn.execute(text(f"DROP TABLE IF EXISTS {old_sql}"))
            return SqlExecutionResult(
                outcome=TransactionOutcome.COMMITTED,
                relation=target,
                metrics=SqlMetrics(statements=1, phases=["publish"]),
                backend_ref=f"sqlalchemy:{self.dialect}",
            )
        except Exception as exc:
            return SqlExecutionResult(
                outcome=_classify_failure(exc, started=started),
                diagnostics=[
                    {"code": "PMSQL520", "severity": "error", "message": redact_message(str(exc))}
                ],
            )

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
        started = False
        try:
            with self.engine.begin() as conn:
                started = True
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
                outcome=_classify_failure(exc, started=started),
                diagnostics=[
                    {"code": "PMSQL510", "severity": "error", "message": redact_message(str(exc))}
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
        seal: Any = None,
    ) -> SqlExecutionResult:
        if isinstance(relation, SqlQuery):
            compiled = compiler.compile_query(relation, context=context)
            if seal is not None:
                compiled = seal(compiled)
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

    def cleanup_staging(self) -> None:
        if not self._staging_tables:
            return
        try:
            with self.engine.begin() as conn:
                for name in list(self._staging_tables):
                    try:
                        require_safe_identifier(name)
                        qid = quote_identifier(name, dialect=self.dialect)
                        conn.execute(text(f"DROP TABLE IF EXISTS {qid}"))
                    except Exception:
                        continue
        finally:
            self._staging_tables.clear()
