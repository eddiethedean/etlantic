"""Compile portable SQL IR into parameterized dialect SQL."""

from __future__ import annotations

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
        params[name] = value
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
            return self.next_param(params, expr.value)
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
        body: str
        if callee == "dtcs:lower":
            body = f"LOWER({args[0]})"
        elif callee == "dtcs:upper":
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
            if self.dialect == "sqlite":
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
        elif callee == "dtcs:starts_with":
            if self.dialect == "sqlite":
                body = f"(INSTR({args[0]}, {args[1]}) = 1)"
            else:
                body = f"(STRPOS({args[0]}, {args[1]}) = 1)"
        elif callee == "dtcs:ends_with":
            if self.dialect == "sqlite":
                body = f"(SUBSTR({args[0]}, -LENGTH({args[1]})) = {args[1]})"
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
            body = f"ROUND({args[0]}, {args[1]})"
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
            body = f"LEAST({', '.join(args)})"
        elif callee == "dtcs:greatest":
            body = f"GREATEST({', '.join(args)})"
        elif callee == "dtcs:sum":
            body = f"SUM({args[0]})"
        elif callee == "dtcs:average":
            body = f"AVG({args[0]})"
        elif callee == "dtcs:min":
            body = f"MIN({args[0]})"
        elif callee == "dtcs:max":
            body = f"MAX({args[0]})"
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


def _projection_names(query: SqlQuery) -> set[str]:
    """Extract safe column names from a query projection when available."""
    names: set[str] = set()
    for col in query.columns or ():
        if isinstance(col, AliasedExpr):
            names.add(require_safe_identifier(col.alias))
        elif isinstance(col, ColumnRef):
            names.add(require_safe_identifier(col.column))
    return names
