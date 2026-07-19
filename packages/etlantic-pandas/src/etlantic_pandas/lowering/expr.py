"""Lower DTCS expression nodes to Pandas Series producers."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

ExprFn = Callable[[pd.DataFrame], pd.Series]


def unwrap_literal_value(value: Any) -> Any:
    """Unwrap DTCS typed literal payloads to Python scalars."""
    if not isinstance(value, dict) or "type" not in value:
        return value
    lit_type = str(value.get("type") or "")
    payload = value.get("value")
    if lit_type in {"null", "missing", "invalid"}:
        return None
    if lit_type == "boolean":
        return bool(payload)
    if lit_type == "integer":
        return int(payload)
    if lit_type == "decimal":
        return Decimal(str(payload))
    if lit_type == "string":
        return str(payload)
    raise ValueError(f"Unsupported DTCS literal type {lit_type!r}")


def constant_python(node: Any, *, parameters: dict[str, Any]) -> Any:
    """Extract a Python constant from a literal or parameter fieldRef."""
    if not isinstance(node, dict):
        raise ValueError(f"Expected constant expression object, got {type(node)!r}")
    kind = node.get("kind")
    if kind == "literal":
        return unwrap_literal_value(node.get("value"))
    if kind == "fieldRef" and node.get("scope") == "parameter":
        target = node.get("target")
        if target not in parameters:
            raise KeyError(f"Missing parameter {target!r}")
        return parameters[target]
    raise ValueError(f"Expected constant literal/parameter, got kind={kind!r}")


def _lit(df: pd.DataFrame, value: Any) -> pd.Series:
    return pd.Series([value] * len(df), index=df.index)


def lower_expr(node: Any, *, parameters: dict[str, Any]) -> ExprFn:
    """Recursively lower a DTCS expression node to a Series producer."""
    if not isinstance(node, dict):
        raise ValueError(f"Expected expression object, got {type(node)!r}")
    kind = node.get("kind")
    if kind == "fieldRef":
        scope = node.get("scope")
        target = node.get("target")
        if scope == "parameter":
            if target not in parameters:
                raise KeyError(f"Missing parameter {target!r}")
            value = parameters[target]
            return lambda df, v=value: _lit(df, v)
        col = str(target)
        return lambda df, c=col: df[c]
    if kind == "literal":
        value = unwrap_literal_value(node.get("value"))
        return lambda df, v=value: _lit(df, v)
    if kind == "binary":
        op = node.get("op")
        left_fn = lower_expr(node["left"], parameters=parameters)
        right_fn = lower_expr(node["right"], parameters=parameters)
        return _binary(op, left_fn, right_fn)
    if kind == "unary":
        op = node.get("op")
        operand = node.get("operand", node.get("expr"))
        if operand is None:
            raise ValueError("unary expression missing operand/expr")
        operand_fn = lower_expr(operand, parameters=parameters)
        return _unary(op, operand_fn)
    if kind == "call":
        return _lower_call(node, parameters=parameters)
    raise ValueError(f"Unsupported expression kind {kind!r}")


def _binary(op: str, left_fn: ExprFn, right_fn: ExprFn) -> ExprFn:
    if op == "eq":
        return lambda df: left_fn(df) == right_fn(df)
    if op in {"neq", "not_eq"}:
        return lambda df: left_fn(df) != right_fn(df)
    if op == "lt":
        return lambda df: left_fn(df) < right_fn(df)
    if op == "lte":
        return lambda df: left_fn(df) <= right_fn(df)
    if op == "gt":
        return lambda df: left_fn(df) > right_fn(df)
    if op == "gte":
        return lambda df: left_fn(df) >= right_fn(df)
    if op == "add":
        return lambda df: left_fn(df) + right_fn(df)
    if op in {"sub", "subtract"}:
        return lambda df: left_fn(df) - right_fn(df)
    if op in {"mul", "multiply"}:
        return lambda df: left_fn(df) * right_fn(df)
    if op in {"div", "divide"}:
        return lambda df: left_fn(df) / right_fn(df)
    if op == "modulo":
        return lambda df: left_fn(df) % right_fn(df)
    if op == "and":
        return lambda df: left_fn(df) & right_fn(df)
    if op == "or":
        return lambda df: left_fn(df) | right_fn(df)
    if op == "null_safe_eq":

        def _null_safe(df: pd.DataFrame) -> pd.Series:
            left = left_fn(df)
            right = right_fn(df)
            both_null = left.isna() & right.isna()
            both_eq = (left == right) & left.notna() & right.notna()
            return both_null | both_eq

        return _null_safe
    raise ValueError(f"Unsupported binary op {op!r}")


def _unary(op: str, operand_fn: ExprFn) -> ExprFn:
    if op == "not":
        return lambda df: ~operand_fn(df)
    if op == "negate":
        return lambda df: -operand_fn(df)
    raise ValueError(f"Unsupported unary op {op!r}")


def _lower_call(node: dict[str, Any], *, parameters: dict[str, Any]) -> ExprFn:
    callee = str(node.get("callee") or "")
    raw_args = list(node.get("args") or [])
    arg_fns = [lower_expr(a, parameters=parameters) for a in raw_args]
    if callee == "dtcs:lower":
        return lambda df: arg_fns[0](df).astype("string").str.lower()
    if callee == "dtcs:upper":
        return lambda df: arg_fns[0](df).astype("string").str.upper()
    if callee == "dtcs:concat":

        def _concat(df: pd.DataFrame) -> pd.Series:
            parts = [arg_fns[i](df).astype("string") for i in range(len(arg_fns))]
            out = parts[0]
            for part in parts[1:]:
                out = out + part
            return out

        return _concat
    if callee == "dtcs:concat_ws":
        sep = constant_python(raw_args[0], parameters=parameters)
        if not isinstance(sep, str):
            raise ValueError("dtcs:concat_ws separator must be a string constant")

        def _concat_ws(df: pd.DataFrame) -> pd.Series:
            parts = [arg_fns[i](df).astype("string") for i in range(1, len(arg_fns))]
            if not parts:
                return _lit(df, "")
            out = parts[0]
            for part in parts[1:]:
                out = out + sep + part
            return out

        return _concat_ws
    if callee == "dtcs:length":
        return lambda df: arg_fns[0](df).astype("string").str.len()
    if callee == "dtcs:substr":
        # Portable IR is 0-based; pandas str.slice is also 0-based.
        if len(arg_fns) == 2:
            return lambda df: (
                arg_fns[0](df)
                .astype("string")
                .str.slice(start=int(arg_fns[1](df).iloc[0]) if len(df) else 0)
            )

        def _substr(df: pd.DataFrame) -> pd.Series:
            start = arg_fns[1](df)
            length = arg_fns[2](df)
            # Vectorized when start/length are constants; otherwise row-wise.
            if start.nunique(dropna=False) == 1 and length.nunique(dropna=False) == 1:
                s = int(start.iloc[0]) if len(df) else 0
                n = int(length.iloc[0]) if len(df) else 0
                return arg_fns[0](df).astype("string").str.slice(s, s + n)
            text = arg_fns[0](df).astype("string")
            return pd.Series(
                [
                    None if pd.isna(t) else str(t)[int(s) : int(s) + int(n)]
                    for t, s, n in zip(text, start, length, strict=True)
                ],
                index=df.index,
            )

        return _substr
    if callee == "dtcs:replace":
        search = constant_python(raw_args[1], parameters=parameters)
        replacement = constant_python(raw_args[2], parameters=parameters)
        return lambda df: (
            arg_fns[0](df)
            .astype("string")
            .str.replace(str(search), str(replacement), regex=False)
        )
    if callee == "dtcs:contains":
        needle = constant_python(raw_args[1], parameters=parameters)
        return lambda df: (
            arg_fns[0](df)
            .astype("string")
            .str.contains(str(needle), regex=False, na=False)
        )
    if callee == "dtcs:starts_with":
        prefix = constant_python(raw_args[1], parameters=parameters)
        return lambda df: (
            arg_fns[0](df).astype("string").str.startswith(str(prefix), na=False)
        )
    if callee == "dtcs:ends_with":
        suffix = constant_python(raw_args[1], parameters=parameters)
        return lambda df: (
            arg_fns[0](df).astype("string").str.endswith(str(suffix), na=False)
        )
    if callee == "dtcs:coalesce":

        def _coalesce(df: pd.DataFrame) -> pd.Series:
            out = arg_fns[0](df)
            for fn in arg_fns[1:]:
                nxt = fn(df)
                out = out.where(out.notna(), nxt)
            return out

        return _coalesce
    if callee == "dtcs:if_null":
        return lambda df: arg_fns[0](df).where(arg_fns[0](df).notna(), arg_fns[1](df))
    if callee == "dtcs:null_if":
        return lambda df: arg_fns[0](df).where(
            arg_fns[0](df) != arg_fns[1](df), other=np.nan
        )
    if callee == "dtcs:is_null":
        return lambda df: arg_fns[0](df).isna()
    if callee == "dtcs:abs":
        return lambda df: arg_fns[0](df).abs()
    if callee == "dtcs:round":
        scale = constant_python(raw_args[1], parameters=parameters)
        return lambda df: arg_fns[0](df).round(int(scale))
    if callee == "dtcs:floor":
        return lambda df: np.floor(arg_fns[0](df).astype("float64"))
    if callee == "dtcs:ceil":
        return lambda df: np.ceil(arg_fns[0](df).astype("float64"))
    if callee == "dtcs:power":
        return lambda df: np.power(arg_fns[0](df).astype("float64"), arg_fns[1](df))
    if callee == "dtcs:sqrt":
        return lambda df: np.sqrt(arg_fns[0](df).astype("float64"))
    if callee == "dtcs:least":

        def _least(df: pd.DataFrame) -> pd.Series:
            stacked = pd.concat([fn(df) for fn in arg_fns], axis=1)
            return stacked.min(axis=1)

        return _least
    if callee == "dtcs:greatest":

        def _greatest(df: pd.DataFrame) -> pd.Series:
            stacked = pd.concat([fn(df) for fn in arg_fns], axis=1)
            return stacked.max(axis=1)

        return _greatest
    if callee == "dtcs:case_when":
        return _lower_case_when(node, parameters=parameters)
    if callee in {
        "dtcs:sum",
        "dtcs:average",
        "dtcs:min",
        "dtcs:max",
        "dtcs:count",
        "dtcs:count_all",
        "dtcs:count_distinct",
    }:
        raise ValueError(
            f"Aggregate function {callee!r} is only valid inside dtcs:aggregate"
        )
    raise ValueError(f"Unsupported function {callee!r}")


def lower_agg_expr(
    node: Any, *, parameters: dict[str, Any]
) -> Callable[[pd.Series | pd.DataFrame], Any]:
    """Lower an aggregate call for ``dtcs:aggregate`` over a Series/DataFrame."""
    if not isinstance(node, dict) or node.get("kind") != "call":
        raise ValueError(f"Expected aggregate call expression, got {node!r}")
    callee = str(node.get("callee") or "")
    raw_args = list(node.get("args") or [])
    arg_fns = [lower_expr(a, parameters=parameters) for a in raw_args]

    def _apply(frame: pd.Series | pd.DataFrame) -> Any:
        # When grouped, pandas passes a Series/DataFrame subgroup.
        if isinstance(frame, pd.Series):
            df = frame.to_frame(name=frame.name or "value")
        else:
            df = frame
        if callee == "dtcs:sum":
            return arg_fns[0](df).sum(min_count=1)
        if callee == "dtcs:average":
            return arg_fns[0](df).mean()
        if callee == "dtcs:min":
            return arg_fns[0](df).min()
        if callee == "dtcs:max":
            return arg_fns[0](df).max()
        if callee == "dtcs:count_all":
            return len(df)
        if callee == "dtcs:count":
            if not arg_fns:
                return len(df)
            return arg_fns[0](df).count()
        if callee == "dtcs:count_distinct":
            return arg_fns[0](df).nunique(dropna=True)
        raise ValueError(f"Unsupported aggregate function {callee!r}")

    return _apply


def _lower_case_when(node: dict[str, Any], *, parameters: dict[str, Any]) -> ExprFn:
    args = list(node.get("args") or [])
    if not args:
        raise ValueError("case_when requires branches")
    pairs: list[tuple[ExprFn, ExprFn]] = []
    i = 0
    while i + 1 < len(args):
        pairs.append(
            (
                lower_expr(args[i], parameters=parameters),
                lower_expr(args[i + 1], parameters=parameters),
            )
        )
        i += 2
    else_fn = (
        lower_expr(args[i], parameters=parameters)
        if i < len(args)
        else (lambda df: _lit(df, None))
    )

    def _case(df: pd.DataFrame) -> pd.Series:
        out = else_fn(df)
        # Apply from last branch to first so earlier branches win.
        for cond_fn, then_fn in reversed(pairs):
            cond = cond_fn(df).fillna(False).astype(bool)
            out = then_fn(df).where(cond, out)
        return out

    return _case
