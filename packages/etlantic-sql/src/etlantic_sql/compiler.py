"""Compile portable SQL IR into parameterized dialect SQL."""

from __future__ import annotations

import sys
import unicodedata
from decimal import Decimal
from functools import lru_cache
from typing import Any
from uuid import uuid4

from etlantic.sql.helpers import require_safe_identifier
from etlantic.sql.protocol import (
    AliasedExpr,
    AtomicPublicationStrategy,
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
from etlantic_sql.dialect_postgresql import quote_identifier

_BINARY_SQL = {
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

_JOIN_SQL = {
    "inner": "INNER JOIN",
    "left": "LEFT JOIN",
    "right": "RIGHT JOIN",
    "full": "FULL OUTER JOIN",
    "outer": "FULL OUTER JOIN",
    "cross": "CROSS JOIN",
    "semi": "LEFT SEMI JOIN",  # rewritten below for PostgreSQL
    "anti": "LEFT ANTI JOIN",
}


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
        # sqlite's DB-API adapter does not bind Decimal instances.  Keep the
        # exact decimal spelling as text; SQLite's NUMERIC affinity otherwise
        # coerces it through binary floating point before the query runs.
        params[name] = (
            str(value)
            if self.dialect == "sqlite" and isinstance(value, Decimal)
            else value
        )
        return f":{name}"

    def compile_expr(
        self, expr: Any, *, params: dict[str, Any], relation_sql: str
    ) -> str:
        if isinstance(expr, ColumnRef):
            col = self.quote(require_safe_identifier(expr.column))
            if expr.relation:
                return f"{self.quote(require_safe_identifier(expr.relation))}.{col}"
            return col
        if isinstance(expr, str):
            return self.quote(require_safe_identifier(expr))
        if isinstance(expr, LiteralExpr):
            parameter = self.next_param(params, expr.value)
            if self.dialect == "sqlite" and expr.sql_type == "NUMERIC":
                # SQLite has no exact decimal storage class.  Preserve the
                # canonical coefficient/scale as a bound text value; callers
                # that require numeric evaluation must use a backend with a
                # native NUMERIC implementation.
                return parameter
            if expr.sql_type:
                return f"CAST({parameter} AS {expr.sql_type})"
            return parameter
        if isinstance(expr, BinaryExpr):
            op = str(expr.op)
            if op == "null_safe_eq":
                left = self.compile_expr(
                    expr.left, params=params, relation_sql=relation_sql
                )
                right = self.compile_expr(
                    expr.right, params=params, relation_sql=relation_sql
                )
                if self.dialect == "sqlite":
                    return (
                        f"(({left} = {right}) OR ({left} IS NULL AND {right} IS NULL))"
                    )
                return f"({left} IS NOT DISTINCT FROM {right})"
            if op not in _BINARY_SQL:
                raise ValueError(f"Unsupported SQL binary op {op!r}")
            left = self.compile_expr(
                expr.left, params=params, relation_sql=relation_sql
            )
            right = self.compile_expr(
                expr.right, params=params, relation_sql=relation_sql
            )
            sql_op = _BINARY_SQL[op]
            if sql_op in {"AND", "OR"}:
                return f"({left} {sql_op} {right})"
            return f"({left} {sql_op} {right})"
        if isinstance(expr, UnaryExpr):
            operand = self.compile_expr(
                expr.operand, params=params, relation_sql=relation_sql
            )
            if expr.op == "not":
                return f"(NOT {operand})"
            if expr.op == "negate":
                return f"(-{operand})"
            raise ValueError(f"Unsupported SQL unary op {expr.op!r}")
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
                return f"{body} AS {self.quote(require_safe_identifier(expr.alias))}"
            return body
        if isinstance(expr, AliasedExpr):
            inner = self.compile_expr(
                expr.expr, params=params, relation_sql=relation_sql
            )
            return f"{inner} AS {self.quote(require_safe_identifier(expr.alias))}"
        if isinstance(expr, CallExpr):
            return self._compile_call(expr, params=params, relation_sql=relation_sql)
        if isinstance(expr, CaseWhenExpr):
            parts = ["CASE"]
            for when, then in expr.branches:
                parts.append(
                    "WHEN "
                    + self.compile_expr(when, params=params, relation_sql=relation_sql)
                    + " THEN "
                    + self.compile_expr(then, params=params, relation_sql=relation_sql)
                )
            if expr.otherwise is not None:
                parts.append(
                    "ELSE "
                    + self.compile_expr(
                        expr.otherwise, params=params, relation_sql=relation_sql
                    )
                )
            parts.append("END")
            return " ".join(parts)
        raise ValueError(f"Unsupported SQL expression: {type(expr)!r}")

    def _compile_call(
        self, expr: CallExpr, *, params: dict[str, Any], relation_sql: str
    ) -> str:
        callee = expr.callee
        args = [
            self.compile_expr(a, params=params, relation_sql=relation_sql)
            for a in expr.args
        ]
        if callee in {"dtcs:least", "dtcs:greatest"}:
            # PostgreSQL rejects LEAST/GREATEST when a typed NULL (TEXT) is
            # mixed with a numeric literal.  Re-type only literal NULLs to
            # the first concrete literal's SQL type; dynamic expressions
            # remain untouched and are checked by the backend schema.
            fallback_type = next(
                (
                    arg.sql_type
                    for arg in expr.args
                    if isinstance(arg, LiteralExpr)
                    and arg.value is not None
                    and arg.sql_type
                ),
                None,
            )
            if fallback_type:
                for index, arg in enumerate(expr.args):
                    if isinstance(arg, LiteralExpr) and arg.value is None:
                        args[index] = args[index].replace(
                            " AS TEXT)", f" AS {fallback_type})", 1
                        )
        body: str
        if callee == "dtcs:lower":
            if self.dialect == "sqlite":
                body = f"ETLANTIC_UNICODE_LOWER({args[0]})"
            elif self.dialect == "postgresql":
                body = _postgres_unicode_case(args[0], mode="lower")
            else:
                body = f"LOWER({args[0]})"
        elif callee == "dtcs:upper":
            if self.dialect == "sqlite":
                body = f"ETLANTIC_UNICODE_UPPER({args[0]})"
            elif self.dialect == "postgresql":
                body = _postgres_unicode_case(args[0], mode="upper")
            else:
                body = f"UPPER({args[0]})"
        elif callee == "dtcs:concat":
            body = " || ".join(args) if args else "''"
        elif callee == "dtcs:concat_ws":
            if not args:
                raise ValueError("dtcs:concat_ws requires a separator")
            sep = args[0]
            if self.dialect == "sqlite":
                # SQLite has no CONCAT_WS; fold with || and separator literals.
                pieces: list[str] = []
                for i, part in enumerate(args[1:]):
                    if i:
                        pieces.append(sep)
                    pieces.append(part)
                body = " || ".join(pieces) if pieces else "''"
            else:
                body = f"CONCAT_WS({sep}, {', '.join(args[1:])})"
        elif callee == "dtcs:length":
            body = (
                f"LENGTH({args[0]})"
                if self.dialect == "sqlite"
                else f"CHAR_LENGTH({args[0]})"
            )
        elif callee == "dtcs:substr":
            # DTCS / Polars use 0-based start; SQL SUBSTRING/substr is 1-based.
            # A NULL bound must propagate as a typed NULL rather than being
            # used in ``TEXT + INTEGER`` arithmetic (PostgreSQL cannot resolve
            # that expression even though the surrounding result is NULL).
            if any(
                isinstance(argument, LiteralExpr) and argument.value is None
                for argument in expr.args[1:]
            ):
                body = "CAST(NULL AS TEXT)"
            elif self.dialect == "sqlite":
                if len(args) == 2:
                    body = f"SUBSTR({args[0]}, ({args[1]}) + 1)"
                else:
                    body = f"SUBSTR({args[0]}, ({args[1]}) + 1, {args[2]})"
            elif len(args) == 2:
                body = f"SUBSTRING({args[0]} FROM (({args[1]}) + 1))"
            else:
                body = f"SUBSTRING({args[0]} FROM (({args[1]}) + 1) FOR {args[2]})"
        elif callee == "dtcs:replace":
            body = f"REPLACE({args[0]}, {args[1]}, {args[2]})"
        elif callee == "dtcs:contains":
            if self.dialect == "sqlite":
                body = f"(INSTR({args[0]}, {args[1]}) > 0)"
            else:
                body = f"(STRPOS({args[0]}, {args[1]}) > 0)"
        elif callee == "dtcs:in":
            if len(args) < 2:
                raise ValueError("dtcs:in requires a value and at least one candidate")
            body = f"({args[0]} IN ({', '.join(args[1:])}))"
        elif callee == "dtcs:starts_with":
            if self.dialect == "sqlite":
                body = f"(INSTR({args[0]}, {args[1]}) = 1)"
            else:
                body = f"(STRPOS({args[0]}, {args[1]}) = 1)"
        elif callee == "dtcs:ends_with":
            if self.dialect == "sqlite":
                body = (
                    f"(CASE WHEN LENGTH({args[1]}) = 0 THEN TRUE "
                    f"ELSE SUBSTR({args[0]}, -LENGTH({args[1]})) = {args[1]} END)"
                )
            else:
                body = f"(RIGHT({args[0]}, CHAR_LENGTH({args[1]})) = {args[1]})"
        elif callee == "dtcs:coalesce":
            body = f"COALESCE({', '.join(args)})"
        elif callee == "dtcs:if_null":
            body = f"COALESCE({args[0]}, {args[1]})"
        elif callee == "dtcs:null_if":
            body = f"NULLIF({args[0]}, {args[1]})"
        elif callee == "dtcs:is_null":
            body = f"({args[0]} IS NULL)"
        elif callee == "dtcs:abs":
            body = f"ABS({args[0]})"
        elif callee == "dtcs:round":
            value = args[0]
            places = args[1] if len(args) > 1 else "0"
            factor = f"POWER(10.0, {places})"
            scaled = f"(({value}) * ({factor}))"
            magnitude = f"ABS({scaled})"
            integral = f"FLOOR({magnitude})"
            fraction = f"(({magnitude}) - ({integral}))"
            # ``FLOOR`` over a floating column is ``double precision`` on
            # PostgreSQL, while MOD's integer/numeric overloads do not accept
            # that type.  Cast the integral component explicitly so the same
            # parity test is valid for literals, NUMERIC columns, and floats.
            parity = f"MOD(CAST({integral} AS NUMERIC), 2)"
            rounded_magnitude = (
                f"CASE WHEN {fraction} < 0.5 THEN {integral} "
                f"WHEN {fraction} > 0.5 THEN ({integral}) + 1 "
                f"WHEN {parity} = 0 THEN {integral} "
                f"ELSE ({integral}) + 1 END"
            )
            sign = f"CASE WHEN {scaled} < 0 THEN -1.0 ELSE 1.0 END"
            body = f"(({sign}) * ({rounded_magnitude}) / ({factor}))"
        elif callee == "dtcs:floor":
            body = f"FLOOR({args[0]})"
        elif callee == "dtcs:ceil":
            body = (
                f"CEIL({args[0]})"
                if self.dialect == "sqlite"
                else f"CEILING({args[0]})"
            )
        elif callee == "dtcs:power":
            body = f"POWER({args[0]}, {args[1]})"
        elif callee == "dtcs:sqrt":
            body = f"SQRT({args[0]})"
        elif callee == "dtcs:least":
            if self.dialect == "sqlite":
                if not args:
                    raise ValueError("dtcs:least requires at least one argument")
                body = args[0]
                for candidate in args[1:]:
                    body = f"(CASE WHEN {body} <= {candidate} THEN {body} ELSE {candidate} END)"
            else:
                body = f"LEAST({', '.join(args)})"
        elif callee == "dtcs:greatest":
            if self.dialect == "sqlite":
                if not args:
                    raise ValueError("dtcs:greatest requires at least one argument")
                body = args[0]
                for candidate in args[1:]:
                    body = f"(CASE WHEN {body} >= {candidate} THEN {body} ELSE {candidate} END)"
            else:
                body = f"GREATEST({', '.join(args)})"
        elif callee == "dtcs:sum":
            body = f"SUM({args[0]})"
        elif callee == "dtcs:decimal_sum":
            body = f"ETLANTIC_DECIMAL_SUM({args[0]})"
        elif callee == "dtcs:average":
            # PostgreSQL returns NUMERIC for AVG(integer), while the portable
            # baseline normalizes average to the common floating result used
            # by the local, dataframe, and SQLite compilers.
            average = f"AVG({args[0]})"
            body = (
                f"CAST({average} AS DOUBLE PRECISION)"
                if self.dialect == "postgresql"
                else average
            )
        elif callee == "dtcs:decimal_average":
            body = f"ETLANTIC_DECIMAL_AVERAGE({args[0]})"
        elif callee == "dtcs:min":
            body = f"MIN({args[0]})"
        elif callee == "dtcs:decimal_min":
            body = f"ETLANTIC_DECIMAL_MIN({args[0]})"
        elif callee == "dtcs:max":
            body = f"MAX({args[0]})"
        elif callee == "dtcs:decimal_max":
            body = f"ETLANTIC_DECIMAL_MAX({args[0]})"
        elif callee == "dtcs:count_all":
            body = "COUNT(*)"
        elif callee == "dtcs:count":
            body = f"COUNT({args[0]})" if args else "COUNT(*)"
        elif callee == "dtcs:count_distinct":
            body = f"COUNT(DISTINCT {args[0]})"
        elif callee == "dtcs:case_when":
            raise ValueError("dtcs:case_when must be lowered to CaseWhenExpr")
        else:
            raise ValueError(f"Unsupported SQL function {callee!r}")
        if (
            callee
            not in {
                "dtcs:coalesce",
                "dtcs:if_null",
                "dtcs:null_if",
                "dtcs:is_null",
                "dtcs:case_when",
                "dtcs:sum",
                "dtcs:decimal_sum",
                "dtcs:average",
                "dtcs:decimal_average",
                "dtcs:min",
                "dtcs:decimal_min",
                "dtcs:max",
                "dtcs:decimal_max",
                "dtcs:count",
                "dtcs:count_all",
                "dtcs:count_distinct",
            }
            and args
        ):
            null_check = " OR ".join(f"({arg} IS NULL)" for arg in args)
            body = f"CASE WHEN {null_check} THEN NULL ELSE {body} END"
        if expr.alias:
            return f"{body} AS {self.quote(require_safe_identifier(expr.alias))}"
        return body

    def _compile_join(
        self, join: JoinClause, *, params: dict[str, Any], left_alias: str
    ) -> str:
        how = join.how.lower()
        right_sql = self.qid(join.right)
        right_alias = join.right_alias or join.right.name
        right_alias_q = self.quote(require_safe_identifier(right_alias))
        left_alias_q = self.quote(require_safe_identifier(left_alias))
        if how == "cross":
            return f"CROSS JOIN {right_sql} AS {right_alias_q}"
        if how in {"semi", "anti"}:
            # Emulate via EXISTS / NOT EXISTS for PostgreSQL / SQLite.
            if not join.left_keys or not join.right_keys:
                raise ValueError(f"{how} join requires keys")
            preds = []
            for lk, rk in zip(join.left_keys, join.right_keys, strict=True):
                left_c = f"{left_alias_q}.{self.quote(require_safe_identifier(lk))}"
                right_c = f"{right_alias_q}.{self.quote(require_safe_identifier(rk))}"
                if join.null_safe:
                    preds.append(f"({left_c} IS NOT DISTINCT FROM {right_c})")
                else:
                    preds.append(f"({left_c} = {right_c})")
            exists = "EXISTS" if how == "semi" else "NOT EXISTS"
            # Caller wraps WHERE; return marker consumed by compile_query.
            return f"__{how}__|{right_sql}|{right_alias}|{' AND '.join(preds)}|{exists}"
        join_kw = _JOIN_SQL.get(how)
        if join_kw is None or how in {"semi", "anti"}:
            raise ValueError(f"Unsupported join type {how!r}")
        if not join.left_keys or not join.right_keys:
            raise ValueError("Join requires left/right keys")
        preds = []
        for lk, rk in zip(join.left_keys, join.right_keys, strict=True):
            left_c = f"{left_alias_q}.{self.quote(require_safe_identifier(lk))}"
            right_c = f"{right_alias_q}.{self.quote(require_safe_identifier(rk))}"
            if join.null_safe:
                preds.append(f"({left_c} IS NOT DISTINCT FROM {right_c})")
            else:
                preds.append(f"({left_c} = {right_c})")
        return f"{join_kw} {right_sql} AS {right_alias_q} ON {' AND '.join(preds)}"

    def compile_query(
        self,
        query: SqlQuery,
        *,
        context: SqlExecutionContext,
        _inner: bool = False,
    ) -> CompiledSql:
        params: dict[str, Any] = {}
        cte_sql = ""
        if query.ctes and not _inner:
            parts = []
            for cte in query.ctes:
                compiled = self.compile_query(cte.query, context=context, _inner=True)
                bound = dict(compiled.metadata.get("_bound_params") or {})
                params.update(bound)
                parts.append(
                    f"{self.quote(require_safe_identifier(cte.name))} AS ({compiled.text})"
                )
            cte_sql = "WITH " + ", ".join(parts) + " "

        source_sql = self.qid(query.source)
        left_alias = query.source_alias or query.source.name
        left_alias_q = self.quote(require_safe_identifier(left_alias))
        needs_alias = bool(query.source_alias or query.joins)
        from_sql = f"{source_sql} AS {left_alias_q}" if needs_alias else source_sql

        semi_anti_filters: list[str] = []
        for join in query.joins:
            rendered = self._compile_join(join, params=params, left_alias=left_alias)
            if rendered.startswith("__semi__") or rendered.startswith("__anti__"):
                _, right_sql, right_alias, pred, exists = rendered.split("|", 4)
                right_alias_q = self.quote(require_safe_identifier(right_alias))
                semi_anti_filters.append(
                    f"{exists} (SELECT 1 FROM {right_sql} AS {right_alias_q} WHERE {pred})"
                )
            else:
                from_sql += " " + rendered

        if query.columns:
            cols = ", ".join(
                self.compile_expr(c, params=params, relation_sql=source_sql)
                for c in query.columns
            )
        else:
            cols = f"{left_alias_q}.*" if needs_alias else "*"
        distinct = "DISTINCT " if query.distinct else ""
        sql = f"SELECT {distinct}{cols} FROM {from_sql}"
        where_parts: list[str] = []
        if query.where is not None:
            where_parts.append(
                self.compile_expr(query.where, params=params, relation_sql=source_sql)
            )
        where_parts.extend(semi_anti_filters)
        if where_parts:
            sql += " WHERE " + " AND ".join(f"({p})" for p in where_parts)
        if query.group_by:
            sql += " GROUP BY " + ", ".join(
                self.quote(require_safe_identifier(c)) for c in query.group_by
            )
        if query.order_by:
            order_bits = []
            for item in query.order_by:
                col = self.quote(require_safe_identifier(item.column))
                direction = "DESC" if item.descending else "ASC"
                nulls = "NULLS LAST" if item.nulls_last else "NULLS FIRST"
                order_bits.append(f"{col} {direction} {nulls}")
            sql += " ORDER BY " + ", ".join(order_bits)
        if query.limit is not None:
            sql += f" LIMIT {int(query.limit)}"
        if query.offset is not None:
            sql += f" OFFSET {int(query.offset)}"
        if query.union is not None:
            union_kw = "UNION ALL" if query.union_all else "UNION"
            other = self.compile_query(query.union, context=context, _inner=True)
            bound = dict(other.metadata.get("_bound_params") or {})
            # Remap other params to avoid collisions.
            remapped = other.text
            for old_name, value in bound.items():
                new_name = self.next_param(params, value).removeprefix(":")
                remapped = remapped.replace(f":{old_name}", f":{new_name}")
            if self.dialect == "sqlite":
                # SQLite rejects parenthesized SELECT operands in CREATE TABLE
                # AS statements; the unparenthesized UNION is equivalent here.
                sql = f"{sql} {union_kw} {remapped}"
            else:
                sql = f"({sql}) {union_kw} ({remapped})"
        if not _inner:
            sql = cte_sql + sql
        return CompiledSql(
            statement_id=f"stmt:{context.step_name}:{uuid4().hex[:8]}",
            text=sql,
            param_names=tuple(params.keys()),
            redacted_params={k: "<redacted>" for k in params},
            dialect=self.dialect,
            logical_nodes=(context.step_name,),
            metadata={
                "_bound_params": params,
                "logical_attribution": dict(query.metadata),
            },
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
            return CompiledSql(
                statement_id=f"replace:{context.step_name}:{uuid4().hex[:8]}",
                text=create,
                param_names=tuple(bound.keys()),
                redacted_params={k: "<redacted>" for k in bound},
                dialect=self.dialect,
                logical_nodes=(context.step_name,),
                metadata={
                    "_bound_params": bound,
                    "intent": write.intent.value,
                    "staging": staging.to_dict(),
                    "target": write.target.to_dict(),
                    "needs_publish_swap": True,
                },
            )
        if write.intent is WriteIntentKind.MERGE:
            if not self.supports_merge or self.dialect != "postgresql":
                raise ValueError(
                    "MERGE / upsert requires PostgreSQL with sql_merge "
                    "advertised; fail closed before mutation"
                )
            if not write.merge_keys:
                raise ValueError(
                    "MERGE requires non-empty merge_keys; fail closed before mutation"
                )
            keys = [require_safe_identifier(k) for k in write.merge_keys]
            key_set = set(keys)
            update_cols: list[str] = [
                require_safe_identifier(str(c))
                for c in (
                    write.metadata.get("update_columns")
                    or write.metadata.get("columns")
                    or ()
                )
                if str(c) not in key_set
            ]
            if isinstance(write.source, SqlQuery):
                compiled = self.compile_query(write.source, context=context)
                source_sql = compiled.text
                bound = dict(compiled.metadata.get("_bound_params") or {})
                if not update_cols:
                    update_cols = sorted(_projection_names(write.source) - key_set)
            elif isinstance(write.source, RelationRef):
                source_sql = f"SELECT * FROM {self.qid(write.source)}"
                bound = {}
            else:
                raise ValueError("MERGE requires a source query or relation")
            if not update_cols:
                insert_ignore = bool(
                    write.metadata.get("insert_ignore")
                    or write.metadata.get("on_conflict") == "do_nothing"
                )
                if not insert_ignore:
                    raise ValueError(
                        "MERGE/upsert requires update_columns (or a source query "
                        "with non-key projections); refuse silent DO NOTHING"
                    )
            conflict = ", ".join(self.quote(k) for k in keys)
            if update_cols:
                sets = ", ".join(
                    f"{self.quote(c)}=EXCLUDED.{self.quote(c)}" for c in update_cols
                )
                conflict_action = f"DO UPDATE SET {sets}"
            else:
                conflict_action = "DO NOTHING"
            sql = (
                f"INSERT INTO {target} {source_sql} "
                f"ON CONFLICT ({conflict}) {conflict_action}"
            )
            return CompiledSql(
                statement_id=f"merge:{context.step_name}:{uuid4().hex[:8]}",
                text=sql,
                param_names=tuple(bound.keys()),
                redacted_params={k: "<redacted>" for k in bound},
                dialect=self.dialect,
                logical_nodes=(context.step_name,),
                metadata={
                    "_bound_params": bound,
                    "intent": write.intent.value,
                    "merge_keys": list(keys),
                    "update_columns": list(update_cols),
                },
            )
        raise ValueError(f"Unsupported write intent: {write.intent}")


@lru_cache(maxsize=2)
def _unicode_expansions(mode: str) -> tuple[tuple[str, str], ...]:
    """Return the host Unicode database's full one-codepoint case expansions."""
    if mode not in {"lower", "upper"}:
        raise ValueError(f"Unsupported Unicode case mode {mode!r}")
    expansions: list[tuple[str, str]] = []
    for codepoint in range(sys.maxunicode + 1):
        char = chr(codepoint)
        mapped = getattr(char, mode)()
        if len(mapped) != 1:
            expansions.append((char, mapped))
    return tuple(expansions)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _unicode_regex_class(codepoints: list[int]) -> str:
    """Return a compact PostgreSQL regex class for Unicode code points."""
    ranges: list[tuple[int, int]] = []
    if codepoints:
        start = previous = codepoints[0]
        for codepoint in codepoints[1:]:
            if codepoint == previous + 1:
                previous = codepoint
                continue
            ranges.append((start, previous))
            start = previous = codepoint
        ranges.append((start, previous))

    def escaped(codepoint: int) -> str:
        char = chr(codepoint)
        return "\\" + char if char in {"\\", "]", "-", "^"} else char

    parts = [
        escaped(start) if start == end else f"{escaped(start)}-{escaped(end)}"
        for start, end in ranges
    ]
    return "[" + "".join(parts) + "]"


@lru_cache(maxsize=1)
def _postgres_case_ignorable_class() -> str:
    """Return a PostgreSQL regex class for Unicode Case_Ignorable code points.

    PostgreSQL's POSIX ``alpha`` class is not sufficient for Unicode default
    casing context: punctuation such as a hyphen must stop a sigma context,
    while combining marks, modifier characters, and the punctuation listed by
    Unicode's ``Case_Ignorable`` property must be skipped.  Python's Unicode
    database is available at compile time, so encode the category-based subset
    and the assigned punctuation exceptions as compact character ranges in the
    generated SQL.
    """

    # Python's stdlib exposes General_Category but not the derived
    # Case_Ignorable property. Keep the assigned punctuation exceptions
    # explicit so PostgreSQL's final-sigma context matches default Unicode
    # casing (including separators such as ':' and '.').
    case_ignorable_punctuation = {
        0x27,
        0x2E,
        0x3A,
        0xB7,
        0x387,
        0x55F,
        0x5F4,
        0x2018,
        0x2019,
        0x2024,
        0x2027,
        0xFE13,
        0xFE52,
        0xFE55,
        0xFF07,
        0xFF0E,
        0xFF1A,
    }
    codepoints = [
        codepoint
        for codepoint in range(sys.maxunicode + 1)
        if unicodedata.category(chr(codepoint)) in {"Mn", "Me", "Cf", "Lm", "Sk"}
        or codepoint in case_ignorable_punctuation
    ]
    return _unicode_regex_class(codepoints)


@lru_cache(maxsize=1)
def _postgres_cased_class() -> str:
    """Return a locale-independent regex class for Unicode ``Cased`` code points.

    PostgreSQL's ``UPPER``/``LOWER`` functions are locale-sensitive.  They
    must not decide whether a neighboring character is cased because that
    would make final-sigma lowering vary with the database locale or build
    architecture.  Python's Unicode predicates provide the compile-time
    Unicode default property used to generate this literal class.
    """
    codepoints = [
        codepoint
        for codepoint in range(sys.maxunicode + 1)
        if unicodedata.category(chr(codepoint)) in {"Lu", "Ll", "Lt"}
        or chr(codepoint).isupper()
        or chr(codepoint).islower()
    ]
    return _unicode_regex_class(codepoints)


def _postgres_unicode_case(value: str, *, mode: str) -> str:
    """Compile full default Unicode casing for PostgreSQL relation plans.

    PostgreSQL 16 applies simple mappings and omits expansions such as
    ``ß`` → ``SS`` and ``İ`` → ``i`` plus combining dot. Splitting the value
    into code points keeps execution in SQL while applying the full mapping.
    Lowercase sigma additionally needs the default context-sensitive final form.
    """
    simple = mode.upper()
    clauses = [
        f"WHEN etlantic_chars.ch = {_sql_literal(source)} THEN {_sql_literal(mapped)}"
        for source, mapped in _unicode_expansions(mode)
    ]
    if mode == "lower":
        text = f"CAST({value} AS TEXT)"
        ignorable = _postgres_case_ignorable_class()
        cased = _postgres_cased_class()
        prefix = (
            f"REGEXP_REPLACE(SUBSTRING({text} FROM 1 FOR "
            "CAST(etlantic_chars.ordinality - 1 AS INTEGER)), "
            f"{_sql_literal(ignorable + '+$')}"
            ", '')"
        )
        suffix = (
            f"REGEXP_REPLACE(SUBSTRING({text} FROM "
            "CAST(etlantic_chars.ordinality + 1 AS INTEGER)), "
            f"{_sql_literal('^' + ignorable + '+')}"
            ", '')"
        )
        clauses.append(
            "WHEN etlantic_chars.ch = 'Σ' "
            f"AND LENGTH({prefix}) > 0 "
            f"AND RIGHT({prefix}, 1) ~ {_sql_literal(cased)} "
            f"AND (LENGTH({suffix}) = 0 OR "
            f"LEFT({suffix}, 1) !~ {_sql_literal(cased)}) "
            "THEN 'ς'"
        )
    cases = " ".join(clauses)
    return (
        "(SELECT COALESCE(STRING_AGG(CASE "
        f"{cases} ELSE {simple}(etlantic_chars.ch) END, '' "
        "ORDER BY etlantic_chars.ordinality), '') "
        f"FROM REGEXP_SPLIT_TO_TABLE(CAST({value} AS TEXT), '') WITH ORDINALITY "
        "AS etlantic_chars(ch, ordinality))"
    )


def _projection_names(query: SqlQuery) -> set[str]:
    """Extract safe column names from a query projection when available."""
    names: set[str] = set()
    for col in query.columns or ():
        if isinstance(col, AliasedExpr):
            names.add(require_safe_identifier(col.alias))
        elif isinstance(col, ColumnRef):
            names.add(require_safe_identifier(col.column))
    return names
