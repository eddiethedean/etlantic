"""Compile portable SQL IR into parameterized dialect SQL."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pipelantic.sql.helpers import require_safe_identifier
from pipelantic.sql.protocol import (
    AliasedExpr,
    AtomicPublicationStrategy,
    ColumnRef,
    CompiledSql,
    ConcatExpr,
    LiteralExpr,
    RelationRef,
    SqlExecutionContext,
    SqlQuery,
    SqlWrite,
    WriteIntentKind,
)
from pipelantic_sql.dialect_postgresql import quote_identifier


class SqlCompiler:
    """IR → parameterized SQL text (values never interpolated)."""

    def __init__(self, *, dialect: str, supports_merge: bool) -> None:
        self.dialect = dialect
        self.supports_merge = supports_merge
        self._param_counter = 0

    def quote(self, name: str) -> str:
        return quote_identifier(name, dialect=self.dialect)

    def qid(self, relation: RelationRef) -> str:
        parts = []
        for part in (relation.catalog, relation.namespace, relation.name):
            if part:
                parts.append(self.quote(require_safe_identifier(part)))
        return ".".join(parts)

    def next_param(self, params: dict[str, Any], value: Any) -> str:
        self._param_counter += 1
        name = f"p{self._param_counter}"
        params[name] = value
        return f":{name}"

    def compile_expr(
        self, expr: Any, *, params: dict[str, Any], relation_sql: str
    ) -> str:
        if isinstance(expr, ColumnRef):
            col = self.quote(require_safe_identifier(expr.column))
            if expr.relation:
                return f"{self.quote(expr.relation)}.{col}"
            return col
        if isinstance(expr, str):
            return self.quote(require_safe_identifier(expr))
        if isinstance(expr, LiteralExpr):
            return self.next_param(params, expr.value)
        if isinstance(expr, ConcatExpr):
            rendered = [
                self.compile_expr(p, params=params, relation_sql=relation_sql)
                for p in expr.parts
            ]
            pieces: list[str] = []
            for i, part in enumerate(rendered):
                if i:
                    pieces.append(self.next_param(params, expr.separator))
                pieces.append(part)
            body = " || ".join(pieces)
            if expr.alias:
                return f"{body} AS {self.quote(expr.alias)}"
            return body
        if isinstance(expr, AliasedExpr):
            inner = self.compile_expr(
                expr.expr, params=params, relation_sql=relation_sql
            )
            return f"{inner} AS {self.quote(expr.alias)}"
        raise ValueError(f"Unsupported SQL expression: {type(expr)!r}")

    def compile_query(
        self,
        query: SqlQuery,
        *,
        context: SqlExecutionContext,
    ) -> CompiledSql:
        params: dict[str, Any] = {}
        source_sql = self.qid(query.source)
        if query.columns:
            cols = ", ".join(
                self.compile_expr(c, params=params, relation_sql=source_sql)
                for c in query.columns
            )
        else:
            cols = "*"
        distinct = "DISTINCT " if query.distinct else ""
        sql = f"SELECT {distinct}{cols} FROM {source_sql}"
        if query.where is not None:
            sql += " WHERE " + self.compile_expr(
                query.where, params=params, relation_sql=source_sql
            )
        if query.limit is not None:
            sql += f" LIMIT {int(query.limit)}"
        return CompiledSql(
            statement_id=f"stmt:{context.step_name}:{uuid4().hex[:8]}",
            text=sql,
            param_names=tuple(params.keys()),
            redacted_params={k: "<redacted>" for k in params},
            dialect=self.dialect,
            logical_nodes=(context.step_name,),
            metadata={"_bound_params": params},
        )

    def compile_write(
        self,
        write: SqlWrite,
        *,
        context: SqlExecutionContext,
    ) -> CompiledSql:
        target = self.qid(write.target)
        if write.intent in {
            WriteIntentKind.APPEND,
            WriteIntentKind.INSERT_SELECT,
        }:
            if isinstance(write.source, SqlQuery):
                compiled = self.compile_query(write.source, context=context)
                sql = f"INSERT INTO {target} {compiled.text}"
                bound = dict(compiled.metadata.get("_bound_params") or {})
                return CompiledSql(
                    statement_id=f"write:{context.step_name}:{uuid4().hex[:8]}",
                    text=sql,
                    param_names=tuple(bound.keys()),
                    redacted_params={k: "<redacted>" for k in bound},
                    dialect=self.dialect,
                    logical_nodes=(context.step_name,),
                    metadata={"_bound_params": bound, "intent": write.intent.value},
                )
            if isinstance(write.source, RelationRef):
                sql = f"INSERT INTO {target} SELECT * FROM {self.qid(write.source)}"
                return CompiledSql(
                    statement_id=f"write:{context.step_name}:{uuid4().hex[:8]}",
                    text=sql,
                    dialect=self.dialect,
                    logical_nodes=(context.step_name,),
                    metadata={"intent": write.intent.value},
                )
        if write.intent in {WriteIntentKind.REPLACE, WriteIntentKind.SNAPSHOT}:
            if write.atomic is AtomicPublicationStrategy.UNSUPPORTED:
                raise ValueError("Atomic publication unsupported for replace")
            staging = RelationRef(
                name=f"{write.target.name}__staging_{uuid4().hex[:8]}",
                namespace=write.target.namespace,
                catalog=write.target.catalog,
            )
            if isinstance(write.source, SqlQuery):
                compiled = self.compile_query(write.source, context=context)
                create = f"CREATE TABLE {self.qid(staging)} AS {compiled.text}"
                bound = dict(compiled.metadata.get("_bound_params") or {})
            elif isinstance(write.source, RelationRef):
                create = (
                    f"CREATE TABLE {self.qid(staging)} AS "
                    f"SELECT * FROM {self.qid(write.source)}"
                )
                bound = {}
            else:
                raise ValueError("Replace requires a source query or relation")
            drop = f"DROP TABLE IF EXISTS {target}"
            rename = (
                f"ALTER TABLE {self.qid(staging)} RENAME TO "
                f"{self.quote(write.target.name)}"
            )
            sql = f"{create};;{drop};;{rename}"
            return CompiledSql(
                statement_id=f"replace:{context.step_name}:{uuid4().hex[:8]}",
                text=sql,
                param_names=tuple(bound.keys()),
                redacted_params={k: "<redacted>" for k in bound},
                dialect=self.dialect,
                logical_nodes=(context.step_name,),
                metadata={
                    "_bound_params": bound,
                    "intent": write.intent.value,
                    "staging": staging.to_dict(),
                },
            )
        if write.intent is WriteIntentKind.MERGE:
            if not self.supports_merge:
                raise ValueError("MERGE unsupported by this dialect")
            raise ValueError("MERGE compilation requires dialect-specific keys")
        raise ValueError(f"Unsupported write intent: {write.intent}")
