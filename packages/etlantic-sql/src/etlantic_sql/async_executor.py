"""Async SQLAlchemy execution path for the reference SQL plugin."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError

from etlantic.runtime.logging import redact_message
from etlantic.sql.protocol import (
    CompiledSql,
    SqlExecutionContext,
    SqlExecutionResult,
    SqlMetrics,
    TransactionOutcome,
)


def _classify_failure(exc: BaseException, *, started: bool) -> TransactionOutcome:
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


class AsyncSqlExecutor:
    """Run compiled statements inside an async transaction."""

    def __init__(
        self,
        *,
        engine: Any,
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

    async def execute(
        self,
        compiled: Sequence[CompiledSql],
        *,
        params: Mapping[str, Any],
        context: SqlExecutionContext,
        fetch: bool = False,
    ) -> SqlExecutionResult:
        _ = context
        metrics = SqlMetrics(statements=0, phases=["execute_async"])
        results: list[CompiledSql] = []
        records: list[Any] | None = None
        outcome = TransactionOutcome.NOT_STARTED
        started = False
        try:
            async with self.engine.begin() as conn:
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
                        result = await conn.execute(text(part), bound)
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
            backend_ref=f"sqlalchemy_async:{self.dialect}",
        )
