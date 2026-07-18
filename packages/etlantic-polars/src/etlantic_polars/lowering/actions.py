"""Lower DTCS kernel and relational actions onto Polars frames."""

from __future__ import annotations

from typing import Any

import polars as pl

from etlantic_polars.lowering.expr import lower_agg_expr, lower_expr

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
    frame: pl.DataFrame | pl.LazyFrame,
    action: dict[str, Any],
    *,
    parameters: dict[str, Any],
    frames: dict[str, Any] | None = None,
) -> pl.DataFrame | pl.LazyFrame:
    """Apply one semantic action to a Polars frame."""
    kind = action.get("kind") or {}
    name = kind.get("action")
    params = kind.get("parameters") or {}
    if name == "dtcs:filter":
        predicate = lower_expr(params["predicate"], parameters=parameters)
        return frame.filter(predicate)
    if name == "dtcs:project":
        fields = params.get("fields") or []
        exprs: list[pl.Expr | str] = []
        for field in fields:
            if isinstance(field, str):
                exprs.append(field)
            elif isinstance(field, dict):
                if "expression" in field:
                    alias = field.get("name")
                    if not alias:
                        raise ValueError(
                            "dtcs:project expression fields require a name alias"
                        )
                    exprs.append(
                        lower_expr(field["expression"], parameters=parameters).alias(
                            str(alias)
                        )
                    )
                elif "name" in field:
                    exprs.append(str(field["name"]))
            else:
                raise ValueError(f"Unsupported project field {field!r}")
        return frame.select(exprs)
    if name == "dtcs:with_fields":
        assignments = []
        for item in params.get("assignments") or []:
            if item.get("window") is not None:
                raise ValueError(
                    "dtcs:with_fields window specs are not supported by the "
                    "Polars relational compiler"
                )
            expr = lower_expr(item["expression"], parameters=parameters)
            assignments.append(expr.alias(str(item["name"])))
        return frame.with_columns(assignments)
    if name == "dtcs:drop_fields":
        names = [str(n) for n in (params.get("fields") or params.get("names") or [])]
        return frame.drop(names)
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
        return frame.rename(rename)
    if name == "dtcs:join":
        return _apply_join(frame, params, frames=frames or {}, parameters=parameters)
    if name == "dtcs:union":
        return _apply_union(frame, params, frames=frames or {})
    if name == "dtcs:aggregate":
        return _apply_aggregate(frame, params, parameters=parameters)
    if name == "dtcs:sort":
        return _apply_sort(frame, params)
    if name == "dtcs:distinct":
        return frame.unique(maintain_order=True)
    if name == "dtcs:deduplicate":
        keys = params.get("keys") or params.get("subset") or []
        subset = [str(k) for k in keys] if keys else None
        return frame.unique(subset=subset, maintain_order=True)
    if name == "dtcs:limit":
        n = int(params.get("count") if "count" in params else params.get("n", 0))
        return frame.head(n)
    raise ValueError(f"Unsupported action {name!r}")


def _frame_columns(frame: pl.DataFrame | pl.LazyFrame) -> list[str]:
    if isinstance(frame, pl.LazyFrame):
        return list(frame.collect_schema().names())
    return list(frame.columns)


def _apply_join(
    left: pl.DataFrame | pl.LazyFrame,
    params: dict[str, Any],
    *,
    frames: dict[str, Any],
    parameters: dict[str, Any],
) -> pl.DataFrame | pl.LazyFrame:
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

    left_cols = set(_frame_columns(left))
    right_cols = set(_frame_columns(right))

    if how == "cross":
        if collision == "fail":
            overlap = left_cols & right_cols
            if overlap:
                raise ValueError(
                    f"Join column collision under fail policy: {sorted(overlap)}"
                )
        return left.join(right, how="cross")

    left_key = params.get("leftKey")
    right_key = params.get("rightKey")
    predicate = params.get("predicate")
    if predicate is not None and left_key is None:
        # Predicate joins are not claimed for 0.13 mode matrix beyond key joins.
        raise ValueError("Predicate joins are not supported by the Polars compiler")

    left_on = _as_key_list(left_key)
    right_on = _as_key_list(right_key)
    if not left_on or not right_on:
        raise ValueError("Join requires leftKey/rightKey")

    key_overlap = set(left_on) | set(right_on)
    non_key_overlap = (left_cols & right_cols) - key_overlap
    if collision == "fail" and non_key_overlap:
        raise ValueError(
            f"Join column collision under fail policy: {sorted(non_key_overlap)}"
        )

    join_kwargs: dict[str, Any] = {
        "left_on": left_on,
        "right_on": right_on,
        "how": how,
        "coalesce": True,
    }
    # Polars 1.x: nulls_equal; older builds ignore via try/except path.
    if null_safe:
        join_kwargs["nulls_equal"] = True
    try:
        return left.join(right, **join_kwargs)
    except TypeError:
        join_kwargs.pop("nulls_equal", None)
        return left.join(right, **join_kwargs)


def _as_key_list(key: Any) -> list[str]:
    if key is None:
        return []
    if isinstance(key, str):
        return [key]
    return [str(k) for k in key]


def _apply_union(
    left: pl.DataFrame | pl.LazyFrame,
    params: dict[str, Any],
    *,
    frames: dict[str, Any],
) -> pl.DataFrame | pl.LazyFrame:
    other_id = params.get("other")
    if other_id not in frames:
        raise KeyError(f"Missing union other frame {other_id!r}")
    other = frames[other_id]
    mode = str(params.get("mode") or "byPosition")
    if mode not in _UNION_MODES:
        raise ValueError(f"Unsupported union mode {mode!r}")
    allow_missing = bool(params.get("allowMissingColumns") or False)
    if mode == "byPosition":
        return pl.concat([left, other], how="vertical")
    how = "diagonal" if allow_missing else "vertical"
    return pl.concat([left, other], how=how)


def _apply_aggregate(
    frame: pl.DataFrame | pl.LazyFrame,
    params: dict[str, Any],
    *,
    parameters: dict[str, Any],
) -> pl.DataFrame | pl.LazyFrame:
    group_by = [str(k) for k in (params.get("groupBy") or [])]
    aggregates = params.get("aggregates") or []
    aggs = [
        lower_agg_expr(item["expression"], parameters=parameters).alias(
            str(item["name"])
        )
        for item in aggregates
    ]
    if not group_by:
        return frame.select(aggs)
    return frame.group_by(group_by, maintain_order=True).agg(aggs)


def _apply_sort(
    frame: pl.DataFrame | pl.LazyFrame,
    params: dict[str, Any],
) -> pl.DataFrame | pl.LazyFrame:
    keys = params.get("keys") or params.get("by") or []
    cols: list[str] = []
    descending: list[bool] = []
    nulls_last: list[bool] = []
    for key in keys:
        if isinstance(key, str):
            cols.append(key)
            descending.append(False)
            nulls_last.append(True)
            continue
        if isinstance(key, dict):
            name = key.get("column") or key.get("name") or key.get("field")
            if name is None and isinstance(key.get("expression"), dict):
                expr = key["expression"]
                if expr.get("kind") == "fieldRef":
                    name = expr.get("target")
            if name is None:
                raise ValueError(f"Unsupported sort key {key!r}")
            cols.append(str(name))
            direction = str(key.get("direction") or "asc").lower()
            descending.append(direction in {"desc", "descending"})
            nulls = str(key.get("nulls") or key.get("nullPlacement") or "last").lower()
            nulls_last.append(nulls != "first")
            continue
        raise ValueError(f"Unsupported sort key {key!r}")
    return frame.sort(cols, descending=descending, nulls_last=nulls_last)
