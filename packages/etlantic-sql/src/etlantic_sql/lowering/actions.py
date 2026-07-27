"""Lower DTCS kernel/relational actions onto SqlQuery IR."""

from __future__ import annotations

from typing import Any

from etlantic.sql.protocol import (
    AliasedExpr,
    ColumnRef,
    JoinClause,
    OrderByItem,
    RelationRef,
    SqlQuery,
)
from etlantic_sql.lowering.expr import lower_agg_expr, lower_expr

KERNEL_ACTIONS = frozenset(
    {
        "dtcs:filter",
        "dtcs:project",
        "dtcs:with_fields",
        "dtcs:drop_fields",
        "dtcs:rename_fields",
    }
)

RELATIONAL_ACTIONS = frozenset(
    {
        "dtcs:join",
        "dtcs:union",
        "dtcs:aggregate",
        "dtcs:sort",
        "dtcs:distinct",
        "dtcs:deduplicate",
        "dtcs:limit",
    }
)

CLAIMED_ACTIONS = KERNEL_ACTIONS | RELATIONAL_ACTIONS

_JOIN_TYPES = frozenset(
    {"inner", "left", "right", "full", "semi", "anti", "cross", "outer"}
)
_COLLISION_POLICIES = frozenset({"fail"})
_UNION_MODES = frozenset({"byName", "byPosition"})


def apply_action_to_query(
    source: RelationRef,
    columns: list[str],
    action: dict[str, Any],
    *,
    parameters: dict[str, Any],
    relations: dict[str, RelationRef],
    relation_columns: dict[str, list[str]],
) -> tuple[SqlQuery, list[str]]:
    """Lower one action into a SqlQuery over ``source``.

    Returns the query and the resulting output column names.
    """
    kind = action.get("kind") or {}
    name = kind.get("action")
    params = kind.get("parameters") or {}
    alias = source.name

    if name == "dtcs:filter":
        predicate = lower_expr(params["predicate"], parameters=parameters)
        query = SqlQuery(
            source=source,
            source_alias=alias,
            columns=tuple(ColumnRef(c) for c in columns),
            where=predicate,
            metadata={"action": name},
        )
        return query, list(columns)

    if name == "dtcs:project":
        fields = params.get("fields") or []
        exprs: list[Any] = []
        out_cols: list[str] = []
        for field in fields:
            if isinstance(field, str):
                exprs.append(ColumnRef(field))
                out_cols.append(field)
            elif isinstance(field, dict):
                if "expression" in field:
                    col_alias = field.get("name")
                    if not col_alias:
                        raise ValueError(
                            "dtcs:project expression fields require a name alias"
                        )
                    exprs.append(
                        AliasedExpr(
                            expr=lower_expr(field["expression"], parameters=parameters),
                            alias=str(col_alias),
                        )
                    )
                    out_cols.append(str(col_alias))
                elif "name" in field:
                    exprs.append(ColumnRef(str(field["name"])))
                    out_cols.append(str(field["name"]))
            else:
                raise ValueError(f"Unsupported project field {field!r}")
        query = SqlQuery(
            source=source,
            source_alias=alias,
            columns=tuple(exprs),
            metadata={"action": name},
        )
        return query, out_cols

    if name == "dtcs:with_fields":
        exprs: list[Any] = [ColumnRef(c) for c in columns]
        out_cols = list(columns)
        for item in params.get("assignments") or []:
            if item.get("window") is not None:
                raise ValueError(
                    "dtcs:with_fields window specs are not supported by the "
                    "SQL relational compiler"
                )
            col_name = str(item["name"])
            exprs.append(
                AliasedExpr(
                    expr=lower_expr(item["expression"], parameters=parameters),
                    alias=col_name,
                )
            )
            if col_name not in out_cols:
                out_cols.append(col_name)
            else:
                # Replace existing projection of same name: rebuild without prior.
                exprs = [e for e in exprs[:-1] if not _is_col(e, col_name)]
                exprs.append(
                    AliasedExpr(
                        expr=lower_expr(item["expression"], parameters=parameters),
                        alias=col_name,
                    )
                )
        query = SqlQuery(
            source=source,
            source_alias=alias,
            columns=tuple(exprs),
            metadata={"action": name},
        )
        return query, out_cols

    if name == "dtcs:drop_fields":
        drop = {str(n) for n in (params.get("fields") or params.get("names") or [])}
        out_cols = [c for c in columns if c not in drop]
        query = SqlQuery(
            source=source,
            source_alias=alias,
            columns=tuple(ColumnRef(c) for c in out_cols),
            metadata={"action": name},
        )
        return query, out_cols

    if name == "dtcs:rename_fields":
        mapping = params.get("mapping") or {}
        if isinstance(mapping, list):
            rename = {
                str(item["from"]): str(item["to"])
                for item in mapping
                if isinstance(item, dict)
            }
        else:
            rename = {str(k): str(v) for k, v in dict(mapping).items()}
        exprs = []
        out_cols = []
        for c in columns:
            new_name = rename.get(c, c)
            if new_name == c:
                exprs.append(ColumnRef(c))
            else:
                exprs.append(AliasedExpr(expr=ColumnRef(c), alias=new_name))
            out_cols.append(new_name)
        query = SqlQuery(
            source=source,
            source_alias=alias,
            columns=tuple(exprs),
            metadata={"action": name},
        )
        return query, out_cols

    if name == "dtcs:join":
        return _apply_join(
            source,
            columns,
            params,
            parameters=parameters,
            relations=relations,
            relation_columns=relation_columns,
        )

    if name == "dtcs:union":
        return _apply_union(
            source,
            columns,
            params,
            relations=relations,
            relation_columns=relation_columns,
        )

    if name == "dtcs:aggregate":
        return _apply_aggregate(source, params, parameters=parameters)

    if name == "dtcs:sort":
        return _apply_sort(source, columns, params)

    if name == "dtcs:distinct":
        query = SqlQuery(
            source=source,
            source_alias=alias,
            columns=tuple(ColumnRef(c) for c in columns),
            distinct=True,
            metadata={"action": name},
        )
        return query, list(columns)

    if name == "dtcs:deduplicate":
        keys = params.get("keys") or params.get("subset") or []
        # Full-row DISTINCT is correct only when keys are empty (all columns).
        # Keyed dedupe needs DISTINCT ON / ROW_NUMBER; fail closed until then.
        if keys:
            key_list = [str(k) for k in keys]
            raise ValueError(
                "dtcs:deduplicate with keys/subset is not implemented by the "
                "SQL reference compiler; omit keys for full-row DISTINCT or use "
                f"a dataframe engine. keys={key_list!r}"
            )
        query = SqlQuery(
            source=source,
            source_alias=alias,
            columns=tuple(ColumnRef(c) for c in columns),
            distinct=True,
            metadata={"action": name},
        )
        return query, list(columns)

    if name == "dtcs:limit":
        n = int(params.get("count") if "count" in params else params.get("n", 0))
        query = SqlQuery(
            source=source,
            source_alias=alias,
            columns=tuple(ColumnRef(c) for c in columns),
            limit=n,
            metadata={"action": name},
        )
        return query, list(columns)

    raise ValueError(f"Unsupported action {name!r}")


def _is_col(expr: Any, name: str) -> bool:
    if isinstance(expr, ColumnRef):
        return expr.column == name
    if isinstance(expr, AliasedExpr):
        return expr.alias == name
    return False


def _as_key_list(key: Any) -> list[str]:
    if key is None:
        return []
    if isinstance(key, str):
        return [key]
    return [str(k) for k in key]


def _apply_join(
    left: RelationRef,
    left_cols: list[str],
    params: dict[str, Any],
    *,
    parameters: dict[str, Any],
    relations: dict[str, RelationRef],
    relation_columns: dict[str, list[str]],
) -> tuple[SqlQuery, list[str]]:
    how = str(params.get("type") or "inner")
    if how == "outer":
        how = "full"
    if how not in _JOIN_TYPES:
        raise ValueError(f"Unsupported join type {how!r}")
    right_id = params.get("right")
    if right_id not in relations:
        raise KeyError(f"Missing join right frame {right_id!r}")
    right = relations[right_id]
    right_cols = list(relation_columns.get(str(right_id), []))
    collision = str(params.get("collisionPolicy") or "fail")
    if collision not in _COLLISION_POLICIES:
        raise ValueError(f"Unsupported collisionPolicy {collision!r}")
    null_safe = bool(params.get("nullSafe") or False)
    left_set = set(left_cols)
    right_set = set(right_cols)

    if how == "cross":
        overlap = left_set & right_set
        if collision == "fail" and overlap:
            raise ValueError(
                f"Join column collision under fail policy: {sorted(overlap)}"
            )
        out_cols = list(left_cols) + [c for c in right_cols if c not in left_set]
        join = JoinClause(
            right=right, how="cross", right_alias=right.name, null_safe=null_safe
        )
        cols = tuple(ColumnRef(c, relation=left.name) for c in left_cols) + tuple(
            ColumnRef(c, relation=right.name) for c in right_cols if c not in left_set
        )
        query = SqlQuery(
            source=left,
            source_alias=left.name,
            columns=cols,
            joins=(join,),
            metadata={"action": "dtcs:join"},
        )
        return query, out_cols

    left_on = _as_key_list(params.get("leftKey"))
    right_on = _as_key_list(params.get("rightKey"))
    if params.get("predicate") is not None and not left_on:
        raise ValueError("Predicate joins are not supported by the SQL compiler")
    if not left_on or not right_on:
        raise ValueError("Join requires leftKey/rightKey")

    key_overlap = set(left_on) | set(right_on)
    non_key_overlap = (left_set & right_set) - key_overlap
    if how not in {"semi", "anti"} and collision == "fail" and non_key_overlap:
        raise ValueError(
            f"Join column collision under fail policy: {sorted(non_key_overlap)}"
        )

    join = JoinClause(
        right=right,
        how=how,
        left_keys=tuple(left_on),
        right_keys=tuple(right_on),
        right_alias=right.name,
        null_safe=null_safe,
    )
    if how in {"semi", "anti"}:
        out_cols = list(left_cols)
        cols = tuple(ColumnRef(c, relation=left.name) for c in left_cols)
    else:
        out_cols = list(left_cols)
        col_exprs: list[Any] = [ColumnRef(c, relation=left.name) for c in left_cols]
        for c in right_cols:
            if c in key_overlap or c in left_set:
                continue
            col_exprs.append(ColumnRef(c, relation=right.name))
            out_cols.append(c)
        cols = tuple(col_exprs)
    query = SqlQuery(
        source=left,
        source_alias=left.name,
        columns=cols,
        joins=(join,),
        metadata={"action": "dtcs:join"},
    )
    return query, out_cols


def _apply_union(
    left: RelationRef,
    left_cols: list[str],
    params: dict[str, Any],
    *,
    relations: dict[str, RelationRef],
    relation_columns: dict[str, list[str]],
) -> tuple[SqlQuery, list[str]]:
    other_id = params.get("other")
    if other_id not in relations:
        raise KeyError(f"Missing union other frame {other_id!r}")
    other = relations[other_id]
    other_cols = list(relation_columns.get(str(other_id), []))
    mode = str(params.get("mode") or "byPosition")
    if mode not in _UNION_MODES:
        raise ValueError(f"Unsupported union mode {mode!r}")
    allow_missing = bool(params.get("allowMissingColumns") or False)
    if mode == "byPosition":
        if allow_missing:
            raise ValueError(
                "allowMissingColumns is not supported for byPosition unions"
            )
        if len(left_cols) != len(other_cols):
            raise ValueError("byPosition union requires equal column counts")
        right_proj = [
            AliasedExpr(expr=ColumnRef(other_cols[i]), alias=left_cols[i])
            for i in range(len(left_cols))
        ]
    else:
        if not allow_missing and set(left_cols) != set(other_cols):
            raise ValueError(
                "byName union without allowMissingColumns requires matching "
                f"column names; left={sorted(left_cols)} other={sorted(other_cols)}"
            )
        right_proj = [ColumnRef(c) for c in left_cols]
        if allow_missing:
            # Missing columns become NULL — represent via AliasedExpr Literal null.
            from etlantic.sql.protocol import LiteralExpr

            right_proj = []
            for c in left_cols:
                if c in other_cols:
                    right_proj.append(ColumnRef(c))
                else:
                    right_proj.append(
                        AliasedExpr(expr=LiteralExpr(value=None), alias=c)
                    )

    left_q = SqlQuery(
        source=left,
        source_alias=left.name,
        columns=tuple(ColumnRef(c) for c in left_cols),
    )
    right_q = SqlQuery(
        source=other,
        source_alias=other.name,
        columns=tuple(right_proj),
    )
    query = SqlQuery(
        source=left,
        source_alias=left.name,
        columns=tuple(ColumnRef(c) for c in left_cols),
        union=right_q,
        union_all=True,
        metadata={"action": "dtcs:union", "mode": mode},
    )
    # Encode as left UNION ALL right by nesting: compile_query handles union field
    # but needs the main select to be left_q. Rebuild properly:
    query = SqlQuery(
        source=left_q.source,
        source_alias=left.name,
        columns=left_q.columns,
        union=right_q,
        union_all=True,
        metadata={"action": "dtcs:union", "mode": mode},
    )
    return query, list(left_cols)


def _apply_aggregate(
    source: RelationRef,
    params: dict[str, Any],
    *,
    parameters: dict[str, Any],
) -> tuple[SqlQuery, list[str]]:
    group_by = [str(k) for k in (params.get("groupBy") or [])]
    aggregates = params.get("aggregates") or []
    cols: list[Any] = [ColumnRef(c) for c in group_by]
    out_cols = list(group_by)
    for item in aggregates:
        alias = str(item["name"])
        cols.append(
            AliasedExpr(
                expr=lower_agg_expr(item["expression"], parameters=parameters),
                alias=alias,
            )
        )
        out_cols.append(alias)
    query = SqlQuery(
        source=source,
        source_alias=source.name,
        columns=tuple(cols),
        group_by=tuple(group_by),
        metadata={"action": "dtcs:aggregate"},
    )
    return query, out_cols


def _apply_sort(
    source: RelationRef,
    columns: list[str],
    params: dict[str, Any],
) -> tuple[SqlQuery, list[str]]:
    keys = params.get("keys") or params.get("by") or []
    order: list[OrderByItem] = []
    for key in keys:
        if isinstance(key, str):
            order.append(OrderByItem(column=key))
            continue
        if isinstance(key, dict):
            name = key.get("column") or key.get("name") or key.get("field")
            if name is None and isinstance(key.get("expression"), dict):
                expr = key["expression"]
                if expr.get("kind") == "fieldRef":
                    name = expr.get("target")
            if name is None:
                raise ValueError(f"Unsupported sort key {key!r}")
            direction = str(key.get("direction") or "asc").lower()
            nulls = str(key.get("nulls") or key.get("nullPlacement") or "last").lower()
            order.append(
                OrderByItem(
                    column=str(name),
                    descending=direction in {"desc", "descending"},
                    nulls_last=nulls != "first",
                )
            )
            continue
        raise ValueError(f"Unsupported sort key {key!r}")
    query = SqlQuery(
        source=source,
        source_alias=source.name,
        columns=tuple(ColumnRef(c) for c in columns),
        order_by=tuple(order),
        metadata={"action": "dtcs:sort"},
    )
    return query, list(columns)
