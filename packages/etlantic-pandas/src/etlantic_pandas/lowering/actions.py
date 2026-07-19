"""Lower DTCS kernel and relational actions onto Pandas DataFrames."""

from __future__ import annotations

from typing import Any

import pandas as pd

from etlantic_pandas.lowering.expr import lower_agg_expr, lower_expr

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


def _index_neutral(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with a default RangeIndex (index is never semantic)."""
    out = frame.copy(deep=False)
    out = out.reset_index(drop=True)
    return out


def apply_action(
    frame: pd.DataFrame,
    action: dict[str, Any],
    *,
    parameters: dict[str, Any],
    frames: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Apply one semantic action to a Pandas DataFrame."""
    kind = action.get("kind") or {}
    name = kind.get("action")
    params = kind.get("parameters") or {}
    frame = _index_neutral(frame)
    if name == "dtcs:filter":
        predicate = lower_expr(params["predicate"], parameters=parameters)(frame)
        mask = predicate.fillna(False).astype(bool)
        return _index_neutral(frame.loc[mask])
    if name == "dtcs:project":
        fields = params.get("fields") or []
        cols: dict[str, Any] = {}
        order: list[str] = []
        for field in fields:
            if isinstance(field, str):
                cols[field] = frame[field]
                order.append(field)
            elif isinstance(field, dict):
                if "expression" in field:
                    alias = field.get("name")
                    if not alias:
                        raise ValueError(
                            "dtcs:project expression fields require a name alias"
                        )
                    alias_s = str(alias)
                    cols[alias_s] = lower_expr(
                        field["expression"], parameters=parameters
                    )(frame)
                    order.append(alias_s)
                elif "name" in field:
                    col = str(field["name"])
                    cols[col] = frame[col]
                    order.append(col)
            else:
                raise ValueError(f"Unsupported project field {field!r}")
        return _index_neutral(pd.DataFrame(cols, index=frame.index)[order])
    if name == "dtcs:with_fields":
        out = frame.copy(deep=False)
        for item in params.get("assignments") or []:
            if item.get("window") is not None:
                raise ValueError(
                    "dtcs:with_fields window specs are not supported by the "
                    "Pandas relational compiler"
                )
            col_name = str(item["name"])
            out[col_name] = lower_expr(item["expression"], parameters=parameters)(out)
        return _index_neutral(out)
    if name == "dtcs:drop_fields":
        names = [str(n) for n in (params.get("fields") or params.get("names") or [])]
        return _index_neutral(frame.drop(columns=names))
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
        return _index_neutral(frame.rename(columns=rename))
    if name == "dtcs:join":
        return _apply_join(frame, params, frames=frames or {}, parameters=parameters)
    if name == "dtcs:union":
        return _apply_union(frame, params, frames=frames or {})
    if name == "dtcs:aggregate":
        return _apply_aggregate(frame, params, parameters=parameters)
    if name == "dtcs:sort":
        return _apply_sort(frame, params)
    if name == "dtcs:distinct":
        return _index_neutral(frame.drop_duplicates(keep="first"))
    if name == "dtcs:deduplicate":
        keys = params.get("keys") or params.get("subset") or []
        subset = [str(k) for k in keys] if keys else None
        return _index_neutral(frame.drop_duplicates(subset=subset, keep="first"))
    if name == "dtcs:limit":
        n = int(params.get("count") if "count" in params else params.get("n", 0))
        return _index_neutral(frame.head(n))
    raise ValueError(f"Unsupported action {name!r}")


def _apply_join(
    left: pd.DataFrame,
    params: dict[str, Any],
    *,
    frames: dict[str, Any],
    parameters: dict[str, Any],
) -> pd.DataFrame:
    del parameters  # key joins only in 0.14 claim matrix
    how = str(params.get("type") or "inner")
    if how == "outer":
        how = "full"
    if how not in _JOIN_TYPES:
        raise ValueError(f"Unsupported join type {how!r}")
    right_id = params.get("right")
    if right_id not in frames:
        raise KeyError(f"Missing join right frame {right_id!r}")
    right = _index_neutral(frames[right_id])
    left = _index_neutral(left)
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
        left2 = left.copy()
        right2 = right.copy()
        left2["_etlantic_cross"] = 1
        right2["_etlantic_cross"] = 1
        out = left2.merge(right2, on="_etlantic_cross", how="inner")
        return _index_neutral(out.drop(columns=["_etlantic_cross"]))

    if params.get("predicate") is not None and params.get("leftKey") is None:
        raise ValueError("Predicate joins are not supported by the Pandas compiler")

    left_on = _as_key_list(params.get("leftKey"))
    right_on = _as_key_list(params.get("rightKey"))
    if not left_on or not right_on:
        raise ValueError("Join requires leftKey/rightKey")

    key_overlap = set(left_on) | set(right_on)
    non_key_overlap = (left_cols & right_cols) - key_overlap
    if how not in {"semi", "anti"} and collision == "fail" and non_key_overlap:
        raise ValueError(
            f"Join column collision under fail policy: {sorted(non_key_overlap)}"
        )

    if how == "semi":
        merged = left.merge(
            right[right_on].drop_duplicates(),
            left_on=left_on,
            right_on=right_on,
            how="inner",
        )
        # Keep left columns only; coalesce equal-named keys.
        return _index_neutral(merged[list(left.columns)].drop_duplicates())

    if how == "anti":
        indicator = left.merge(
            right[right_on].drop_duplicates(),
            left_on=left_on,
            right_on=right_on,
            how="left",
            indicator=True,
        )
        anti = indicator[indicator["_merge"] == "left_only"]
        return _index_neutral(anti[list(left.columns)])

    pandas_how = {"full": "outer"}.get(how, how)
    if null_safe:
        left_work = left.copy()
        right_work = right.copy()
        join_left: list[str] = []
        join_right: list[str] = []
        for i, (lk, rk) in enumerate(zip(left_on, right_on, strict=True)):
            ltmp = f"__ns_l_{i}"
            rtmp = f"__ns_r_{i}"
            left_work[ltmp] = (
                left_work[lk]
                .astype("string")
                .where(left_work[lk].notna(), other="__ETLANTIC_NULL__")
            )
            right_work[rtmp] = (
                right_work[rk]
                .astype("string")
                .where(right_work[rk].notna(), other="__ETLANTIC_NULL__")
            )
            join_left.append(ltmp)
            join_right.append(rtmp)
        merged = left_work.merge(
            right_work,
            left_on=join_left,
            right_on=join_right,
            how=pandas_how,
            suffixes=("", "_right"),
        )
        merged = merged.drop(columns=join_left + join_right)
        # Drop coalesced right keys when names match.
        for lk, rk in zip(left_on, right_on, strict=True):
            if lk == rk:
                right_key = f"{rk}_right"
                if right_key in merged.columns:
                    merged = merged.drop(columns=[right_key])
            elif rk in merged.columns and rk not in left.columns:
                # Keep left key name only.
                pass
            elif rk in merged.columns and rk != lk:
                merged = merged.drop(columns=[rk])
        return _index_neutral(merged)

    if left_on == right_on:
        merged = left.merge(right, on=left_on, how=pandas_how, suffixes=("", "_right"))
        return _index_neutral(merged)

    merged = left.merge(
        right,
        left_on=left_on,
        right_on=right_on,
        how=pandas_how,
        suffixes=("", "_right"),
    )
    # Match Polars coalesce=True: keep left key names, drop right key cols.
    for lk, rk in zip(left_on, right_on, strict=True):
        if lk == rk:
            right_key = f"{rk}_right"
            if right_key in merged.columns:
                merged = merged.drop(columns=[right_key])
        elif rk in merged.columns:
            merged = merged.drop(columns=[rk])
    return _index_neutral(merged)


def _as_key_list(key: Any) -> list[str]:
    if key is None:
        return []
    if isinstance(key, str):
        return [key]
    return [str(k) for k in key]


def _apply_union(
    left: pd.DataFrame,
    params: dict[str, Any],
    *,
    frames: dict[str, Any],
) -> pd.DataFrame:
    other_id = params.get("other")
    if other_id not in frames:
        raise KeyError(f"Missing union other frame {other_id!r}")
    other = _index_neutral(frames[other_id])
    left = _index_neutral(left)
    mode = str(params.get("mode") or "byPosition")
    if mode not in _UNION_MODES:
        raise ValueError(f"Unsupported union mode {mode!r}")
    allow_missing = bool(params.get("allowMissingColumns") or False)
    if mode == "byPosition":
        if allow_missing:
            raise ValueError(
                "allowMissingColumns is not supported for byPosition unions"
            )
        if list(left.columns) != list(other.columns):
            # Align by position using left column names.
            if len(left.columns) != len(other.columns):
                raise ValueError("byPosition union requires equal column counts")
            other = other.copy()
            other.columns = list(left.columns)
        return _index_neutral(pd.concat([left, other], axis=0, ignore_index=True))
    if allow_missing:
        return _index_neutral(
            pd.concat([left, other], axis=0, ignore_index=True, sort=False)
        )
    left_cols = list(left.columns)
    other_cols = list(other.columns)
    if set(left_cols) != set(other_cols):
        raise ValueError(
            "byName union without allowMissingColumns requires matching "
            f"column names; left={sorted(left_cols)} other={sorted(other_cols)}"
        )
    return _index_neutral(
        pd.concat([left, other[left_cols]], axis=0, ignore_index=True)
    )


def _apply_aggregate(
    frame: pd.DataFrame,
    params: dict[str, Any],
    *,
    parameters: dict[str, Any],
) -> pd.DataFrame:
    group_by = [str(k) for k in (params.get("groupBy") or [])]
    aggregates = params.get("aggregates") or []
    if not group_by:
        row: dict[str, Any] = {}
        for item in aggregates:
            name = str(item["name"])
            agg_fn = lower_agg_expr(item["expression"], parameters=parameters)
            row[name] = agg_fn(frame)
        return _index_neutral(pd.DataFrame([row]))

    grouped = frame.groupby(group_by, dropna=False, sort=False)
    series_map: dict[str, pd.Series] = {}
    for item in aggregates:
        name = str(item["name"])
        agg_fn = lower_agg_expr(item["expression"], parameters=parameters)
        series_map[name] = grouped.apply(agg_fn, include_groups=False)
    out = pd.DataFrame(series_map)
    out = out.reset_index()
    return _index_neutral(out)


def _apply_sort(frame: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    keys = params.get("keys") or params.get("by") or []
    cols: list[str] = []
    ascending: list[bool] = []
    na_position = "last"
    positions: list[str] = []
    for key in keys:
        if isinstance(key, str):
            cols.append(key)
            ascending.append(True)
            positions.append("last")
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
            ascending.append(direction not in {"desc", "descending"})
            nulls = str(key.get("nulls") or key.get("nullPlacement") or "last").lower()
            positions.append("first" if nulls == "first" else "last")
            continue
        raise ValueError(f"Unsupported sort key {key!r}")
    # pandas sort_values supports a single na_position; require uniform or use last.
    if positions and len(set(positions)) == 1:
        na_position = positions[0]
    elif positions and len(set(positions)) > 1:
        # Fail closed: mixed null placement is not implemented for Pandas.
        raise ValueError(
            "Mixed null placement across sort keys is not supported by the "
            "Pandas relational compiler"
        )
    return _index_neutral(
        frame.sort_values(
            by=cols, ascending=ascending, na_position=na_position, kind="mergesort"
        )
    )
