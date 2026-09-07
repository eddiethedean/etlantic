"""Small closed-IR compiler for DuckDB SQL."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import uuid4

from etlantic.sql.helpers import require_safe_identifier
from etlantic.sql.protocol import (
    AliasedExpr,
    BinaryExpr,
    CallExpr,
    CaseWhenExpr,
    ColumnRef,
    CompiledSql,
    ConcatExpr,
    JoinClause,
    LiteralExpr,
    RelationRef,
    SqlExecutionContext,
    SqlQuery,
    SqlWrite,
    UnaryExpr,
    WriteIntentKind,
)

_OPS = {
    "eq": "=",
    "neq": "<>",
    "not_eq": "<>",
    "lt": "<",
    "lte": "<=",
    "gt": ">",
    "gte": ">=",
    "add": "+",
    "sub": "-",
    "subtract": "-",
    "mul": "*",
    "multiply": "*",
    "div": "/",
    "divide": "/",
    "modulo": "%",
    "and": "AND",
    "or": "OR",
}

_JOINS = {
    "inner": "INNER JOIN",
    "left": "LEFT JOIN",
    "right": "RIGHT JOIN",
    "full": "FULL OUTER JOIN",
    "outer": "FULL OUTER JOIN",
    "cross": "CROSS JOIN",
}


def quote_identifier(name: str) -> str:
    return '"' + require_safe_identifier(name).replace('"', '""') + '"'


class DuckDBCompiler:
    """Compile only the public :mod:`etlantic.sql` closed IR."""

    def __init__(self) -> None:
        self._counter = 0

    def relation(self, ref: RelationRef) -> str:
        return ".".join(
            quote_identifier(part)
            for part in (ref.catalog, ref.namespace, ref.name)
            if part
        )

    def _param(self, params: dict[str, Any], value: Any) -> str:
        self._counter += 1
        name = f"p{self._counter}"
        params[name] = value
        return f"${name}"

    def expr(self, value: Any, params: dict[str, Any]) -> str:
        if isinstance(value, ColumnRef):
            name = quote_identifier(value.column)
            return (
                f"{quote_identifier(value.relation)}.{name}" if value.relation else name
            )
        if isinstance(value, str):
            return quote_identifier(value)
        if isinstance(value, LiteralExpr):
            return self._param(params, value.value)
        if isinstance(value, BinaryExpr):
            if value.op == "null_safe_eq":
                left = self.expr(value.left, params)
                right = self.expr(value.right, params)
                return f"({left} IS NOT DISTINCT FROM {right})"
            op = _OPS.get(value.op)
            if op is None:
                raise ValueError(f"Unsupported DuckDB binary operator {value.op!r}")
            return f"({self.expr(value.left, params)} {op} {self.expr(value.right, params)})"
        if isinstance(value, UnaryExpr):
            operand = self.expr(value.operand, params)
            if value.op == "not":
                return f"(NOT {operand})"
            if value.op == "negate":
                return f"(-{operand})"
            raise ValueError(f"Unsupported DuckDB unary operator {value.op!r}")
        if isinstance(value, ConcatExpr):
            pieces: list[str] = []
            for index, part in enumerate(value.parts):
                if index:
                    pieces.append(self._param(params, value.separator))
                pieces.append(self.expr(part, params))
            body = " || ".join(pieces) or "''"
            return f"{body} AS {quote_identifier(value.alias)}" if value.alias else body
        if isinstance(value, AliasedExpr):
            return f"{self.expr(value.expr, params)} AS {quote_identifier(value.alias)}"
        if isinstance(value, CallExpr):
            args = ", ".join(self.expr(arg, params) for arg in value.args)
            name = value.callee.removeprefix("dtcs:")
            functions = {
                "lower": "LOWER",
                "upper": "UPPER",
                "length": "LENGTH",
                "abs": "ABS",
                "round": "ROUND",
                "floor": "FLOOR",
                "ceil": "CEIL",
                "sqrt": "SQRT",
                "power": "POWER",
                "least": "LEAST",
                "greatest": "GREATEST",
                "coalesce": "COALESCE",
                "if_null": "COALESCE",
                "null_if": "NULLIF",
                "sum": "SUM",
                "average": "AVG",
                "min": "MIN",
                "max": "MAX",
                "count": "COUNT",
                "count_all": "COUNT(*)",
                "count_distinct": "COUNT(DISTINCT",
            }
            if name == "concat":
                body = " || ".join(self.expr(arg, params) for arg in value.args) or "''"
            elif name == "contains":
                body = f"(STRPOS({args}) > 0)"
            elif name == "starts_with":
                body = f"(STRPOS({args}) = 1)"
            elif name == "ends_with":
                if len(value.args) != 2:
                    raise ValueError("ends_with requires two arguments")
                haystack = self.expr(value.args[0], params)
                suffix = self.expr(value.args[1], params)
                body = f"(RIGHT({haystack}, LENGTH({suffix})) = {suffix})"
            elif name in {"is_null"}:
                body = f"({self.expr(value.args[0], params)} IS NULL)"
            elif name in {"case_when"}:
                raise ValueError("case_when must use CaseWhenExpr")
            elif name == "count_distinct":
                body = f"COUNT(DISTINCT {self.expr(value.args[0], params)})"
            elif name == "count_all":
                body = "COUNT(*)"
            elif name in functions:
                body = f"{functions[name]}({args})"
            else:
                raise ValueError(f"Unsupported DuckDB function {value.callee!r}")
            return f"{body} AS {quote_identifier(value.alias)}" if value.alias else body
        if isinstance(value, CaseWhenExpr):
            parts = ["CASE"]
            for when, then in value.branches:
                parts.extend(
                    ["WHEN", self.expr(when, params), "THEN", self.expr(then, params)]
                )
            if value.otherwise is not None:
                parts.extend(["ELSE", self.expr(value.otherwise, params)])
            return " ".join([*parts, "END"])
        raise ValueError(f"Unsupported DuckDB expression {type(value)!r}")

    def query(self, query: SqlQuery, *, context: SqlExecutionContext) -> CompiledSql:
        params: dict[str, Any] = {}
        source = self.relation(query.source)
        alias = quote_identifier(query.source_alias) if query.source_alias else None
        if query.columns:
            columns = ", ".join(self.expr(column, params) for column in query.columns)
        else:
            columns = "*"
        sql = f"SELECT {'DISTINCT ' if query.distinct else ''}{columns} FROM {source}"
        if alias:
            sql += f" AS {alias}"
        for join in query.joins:
            sql += " " + self._join(join, params, query.source_alias)
        if query.where is not None:
            sql += f" WHERE {self.expr(query.where, params)}"
        if query.group_by:
            sql += " GROUP BY " + ", ".join(quote_identifier(x) for x in query.group_by)
        if query.order_by:
            sql += " ORDER BY " + ", ".join(
                f"{quote_identifier(item.column)} {'DESC' if item.descending else 'ASC'} {'NULLS LAST' if item.nulls_last else 'NULLS FIRST'}"
                for item in query.order_by
            )
        if query.limit is not None:
            if query.limit < 0:
                raise ValueError("limit must be non-negative")
            sql += f" LIMIT {int(query.limit)}"
        if query.offset is not None:
            if query.offset < 0:
                raise ValueError("offset must be non-negative")
            sql += f" OFFSET {int(query.offset)}"
        if query.union is not None:
            other = self.query(query.union, context=context)
            params.update(dict(other.metadata.get("_bound_params") or {}))
            sql = (
                f"({sql}) {'UNION ALL' if query.union_all else 'UNION'} ({other.text})"
            )
        if query.ctes:
            ctes: list[str] = []
            for cte in query.ctes:
                cte_query = self.query(cte.query, context=context)
                params.update(dict(cte_query.metadata.get("_bound_params") or {}))
                ctes.append(f"{quote_identifier(cte.name)} AS ({cte_query.text})")
            sql = f"WITH {', '.join(ctes)} {sql}"
        statement_id = f"duckdb:{uuid4().hex}"
        return CompiledSql(
            statement_id=statement_id,
            text=sql,
            param_names=tuple(params),
            redacted_params={key: "<redacted>" for key in params},
            dialect="duckdb",
            logical_nodes=(context.step_name,),
            metadata={"_bound_params": params, "engine": context.engine},
        )

    def _join(self, join: JoinClause, params: dict[str, Any], alias: str | None) -> str:
        how = _JOINS.get(join.how)
        if how is None:
            raise ValueError(f"Unsupported DuckDB join type {join.how!r}")
        right = self.relation(join.right)
        right_alias = quote_identifier(join.right_alias) if join.right_alias else None
        sql = f"{how} {right}"
        if right_alias:
            sql += f" AS {right_alias}"
        if join.how != "cross":
            left_alias = quote_identifier(alias) if alias else None
            conditions = []
            for left, right_name in zip(join.left_keys, join.right_keys, strict=False):
                left_sql = (
                    f"{left_alias}.{quote_identifier(left)}"
                    if left_alias
                    else quote_identifier(left)
                )
                right_sql = (
                    f"{right_alias}.{quote_identifier(right_name)}"
                    if right_alias
                    else quote_identifier(right_name)
                )
                conditions.append(
                    f"{left_sql} {'IS NOT DISTINCT FROM' if join.null_safe else '='} {right_sql}"
                )
            if not conditions:
                raise ValueError("DuckDB joins require explicit key pairs")
            sql += " ON " + " AND ".join(conditions)
        return sql

    def write(self, write: SqlWrite, *, context: SqlExecutionContext) -> CompiledSql:
        if write.intent is WriteIntentKind.APPEND:
            if not isinstance(write.source, (SqlQuery, RelationRef)):
                raise ValueError("append requires a query or relation source")
            source = (
                self.query(write.source, context=context)
                if isinstance(write.source, SqlQuery)
                else CompiledSql(
                    "source",
                    f"SELECT * FROM {self.relation(write.source)}",
                    dialect="duckdb",
                )
            )
            params = dict(source.metadata.get("_bound_params") or {})
            sql = f"INSERT INTO {self.relation(write.target)} {source.text}"
        elif write.intent is WriteIntentKind.INSERT_SELECT:
            if not isinstance(write.source, (SqlQuery, RelationRef)):
                raise ValueError("insert_select requires a query or relation source")
            source = (
                self.query(write.source, context=context)
                if isinstance(write.source, SqlQuery)
                else CompiledSql(
                    "source",
                    f"SELECT * FROM {self.relation(write.source)}",
                    dialect="duckdb",
                )
            )
            params = dict(source.metadata.get("_bound_params") or {})
            sql = f"INSERT INTO {self.relation(write.target)} {source.text}"
        elif write.intent is WriteIntentKind.CREATE_TABLE_AS:
            if not isinstance(write.source, SqlQuery):
                raise ValueError("create_table_as requires a query source")
            source = self.query(write.source, context=context)
            params = dict(source.metadata.get("_bound_params") or {})
            sql = f"CREATE TABLE {self.relation(write.target)} AS {source.text}"
        elif write.intent in {WriteIntentKind.REPLACE, WriteIntentKind.SNAPSHOT}:
            if not isinstance(write.source, SqlQuery):
                raise ValueError("replace/snapshot requires a query source")
            source = self.query(write.source, context=context)
            params = dict(source.metadata.get("_bound_params") or {})
            sql = f"CREATE OR REPLACE TABLE {self.relation(write.target)} AS {source.text}"
        else:
            raise ValueError(
                f"DuckDB write intent {write.intent.value!r} is unsupported"
            )
        return CompiledSql(
            statement_id=f"duckdb:{uuid4().hex}",
            text=sql,
            param_names=tuple(params),
            redacted_params={key: "<redacted>" for key in params},
            dialect="duckdb",
            logical_nodes=(context.step_name,),
            metadata={"_bound_params": params, "engine": context.engine},
        )


def statement_digest(stmt: CompiledSql) -> str:
    payload = {
        "statement_id": stmt.statement_id,
        "text": stmt.text,
        "param_names": list(stmt.param_names),
        "dialect": stmt.dialect,
        "logical_nodes": list(stmt.logical_nodes),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
