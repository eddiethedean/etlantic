"""Lower DTCS kernel and relational actions onto Spark DataFrames."""

from __future__ import annotations

from typing import Any

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from etlantic_pyspark.lowering.expr import lower_agg_expr, lower_expr

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
_COLLISION_POLICIES = frozenset({"fail", "suffix", "coalesce"})
_UNION_MODES = frozenset({"byName", "byPosition"})


def apply_action(
    frame: DataFrame,
    action: dict[str, Any],
    *,
    parameters: dict[str, Any],
    frames: dict[str, Any] | None = None,
) -> DataFrame:
    """Apply one semantic action to a Spark DataFrame."""
    kind = action.get("kind") or {}
    name = kind.get("action")
    params = kind.get("parameters") or {}
    if name == "dtcs:filter":
        return frame.filter(lower_expr(params["predicate"], parameters=parameters))
    if name == "dtcs:project":
        fields = params.get("fields") or []
        cols = []
        for field in fields:
            if isinstance(field, str):
                cols.append(F.col(field))
            elif isinstance(field, dict):
                if "expression" in field:
                    alias = field.get("name")
                    if not alias:
                        raise ValueError(
                            "dtcs:project expression fields require a name alias"
                        )
                    cols.append(
                        lower_expr(field["expression"], parameters=parameters).alias(
                            str(alias)
                        )
                    )
                elif "name" in field:
                    cols.append(F.col(str(field["name"])))
            else:
                raise ValueError(f"Unsupported project field {field!r}")
        return frame.select(*cols)
    if name == "dtcs:with_fields":
        assignments = []
        for item in params.get("assignments") or []:
            if item.get("window") is not None:
                raise ValueError(
                    "dtcs:with_fields window specs are not supported by the "
                    "PySpark relational compiler"
                )
            expr = lower_expr(item["expression"], parameters=parameters)
            assignments.append(expr.alias(str(item["name"])))
        return frame.select("*", *assignments)
    if name == "dtcs:drop_fields":
        names = [str(n) for n in (params.get("fields") or params.get("names") or [])]
        return frame.drop(*names)
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
        out = frame
        for src, dst in rename.items():
            out = out.withColumnRenamed(src, dst)
        return out
    if name == "dtcs:join":
        return _apply_join(frame, params, frames=frames or {}, parameters=parameters)
    if name == "dtcs:union":
        return _apply_union(frame, params, frames=frames or {})
    if name == "dtcs:aggregate":
        return _apply_aggregate(frame, params, parameters=parameters)
    if name == "dtcs:sort":
        return _apply_sort(frame, params)
    if name == "dtcs:distinct":
        return frame.distinct()
    if name == "dtcs:deduplicate":
        keys = params.get("keys") or params.get("subset") or []
        if keys:
            return frame.dropDuplicates([str(k) for k in keys])
        return frame.dropDuplicates()
    if name == "dtcs:limit":
        n = int(params.get("count") if "count" in params else params.get("n", 0))
        return frame.limit(n)
    raise ValueError(f"Unsupported action {name!r}")


def _apply_join(
    left: DataFrame,
    params: dict[str, Any],
    *,
    frames: dict[str, Any],
    parameters: dict[str, Any],
) -> DataFrame:
    how = str(params.get("type") or "inner")
    if how == "outer":
        how = "full"
    if how not in _JOIN_TYPES:
        raise ValueError(f"Unsupported join type {how!r}")
    right_id = params.get("right")
    if right_id not in frames:
        raise KeyError(f"Missing join right frame {right_id!r}")
    right = frames[right_id]
    collision = str(params.get("collisionPolicy") or "fail")
    if collision not in _COLLISION_POLICIES:
        raise ValueError(f"Unsupported collisionPolicy {collision!r}")
    null_safe = bool(params.get("nullSafe") or False)

    left_cols = set(left.columns)
    right_cols = set(right.columns)

    if how == "cross":
        if collision == "fail":
            overlap = left_cols & right_cols
            if overlap:
                raise ValueError(
                    f"Join column collision under fail policy: {sorted(overlap)}"
                )
        return left.crossJoin(right)

    left_on = _as_key_list(params.get("leftKey"))
    right_on = _as_key_list(params.get("rightKey"))
    if params.get("predicate") is not None and not left_on:
        raise ValueError("Predicate joins are not supported by the PySpark compiler")
    if not left_on or not right_on:
        raise ValueError("Join requires leftKey/rightKey")

    key_overlap = set(left_on) | set(right_on)
    non_key_overlap = (left_cols & right_cols) - key_overlap
    if collision == "fail" and non_key_overlap:
        raise ValueError(
            f"Join column collision under fail policy: {sorted(non_key_overlap)}"
        )

    spark_how = "fullouter" if how == "full" else how
    if null_safe:
        cond = None
        for lk, rk in zip(left_on, right_on, strict=True):
            piece = left[lk].eqNullSafe(right[rk])
            cond = piece if cond is None else (cond & piece)
        return left.join(right, on=cond, how=spark_how)
    if left_on == right_on:
        return left.join(right, on=left_on, how=spark_how)
    cond = None
    for lk, rk in zip(left_on, right_on, strict=True):
        piece = left[lk] == right[rk]
        cond = piece if cond is None else (cond & piece)
    return left.join(right, on=cond, how=spark_how)


def _as_key_list(key: Any) -> list[str]:
    if key is None:
        return []
    if isinstance(key, str):
        return [key]
    return [str(k) for k in key]


def _apply_union(
    left: DataFrame,
    params: dict[str, Any],
    *,
    frames: dict[str, Any],
) -> DataFrame:
    other_id = params.get("other")
    if other_id not in frames:
        raise KeyError(f"Missing union other frame {other_id!r}")
    other = frames[other_id]
    mode = str(params.get("mode") or "byPosition")
    if mode not in _UNION_MODES:
        raise ValueError(f"Unsupported union mode {mode!r}")
    allow_missing = bool(params.get("allowMissingColumns") or False)
    if mode == "byName":
        if allow_missing:
            # Align columns by name, filling missing with null.
            left_cols = left.columns
            right_cols = other.columns
            all_cols = list(dict.fromkeys([*left_cols, *right_cols]))
            left_sel = [
                F.col(c) if c in left_cols else F.lit(None).alias(c) for c in all_cols
            ]
            right_sel = [
                F.col(c) if c in right_cols else F.lit(None).alias(c) for c in all_cols
            ]
            return left.select(*left_sel).unionByName(other.select(*right_sel))
        return left.unionByName(other)
    return left.union(other)


def _apply_aggregate(
    frame: DataFrame,
    params: dict[str, Any],
    *,
    parameters: dict[str, Any],
) -> DataFrame:
    group_by = [str(k) for k in (params.get("groupBy") or [])]
    aggregates = params.get("aggregates") or []
    aggs = [
        lower_agg_expr(item["expression"], parameters=parameters).alias(
            str(item["name"])
        )
        for item in aggregates
    ]
    if not group_by:
        return frame.agg(*aggs)
    return frame.groupBy(*group_by).agg(*aggs)


def _apply_sort(frame: DataFrame, params: dict[str, Any]) -> DataFrame:
    keys = params.get("keys") or params.get("by") or []
    cols = []
    for key in keys:
        if isinstance(key, str):
            cols.append(F.col(key).asc_nulls_last())
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
            col = F.col(str(name))
            if direction in {"desc", "descending"}:
                cols.append(
                    col.desc_nulls_first()
                    if nulls == "first"
                    else col.desc_nulls_last()
                )
            else:
                cols.append(
                    col.asc_nulls_first() if nulls == "first" else col.asc_nulls_last()
                )
            continue
        raise ValueError(f"Unsupported sort key {key!r}")
    return frame.orderBy(*cols)
