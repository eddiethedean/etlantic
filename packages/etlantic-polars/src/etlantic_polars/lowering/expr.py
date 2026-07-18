"""Lower DTCS expression nodes to Polars expressions."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import polars as pl

_BINARY_OPS = {
    "eq": lambda a, b: a == b,
    "neq": lambda a, b: a != b,
    "not_eq": lambda a, b: a != b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "add": lambda a, b: a + b,
    "sub": lambda a, b: a - b,
    "subtract": lambda a, b: a - b,
    "mul": lambda a, b: a * b,
    "multiply": lambda a, b: a * b,
    "div": lambda a, b: a / b,
    "divide": lambda a, b: a / b,
    "modulo": lambda a, b: a % b,
    "and": lambda a, b: a & b,
    "or": lambda a, b: a | b,
    "null_safe_eq": lambda a, b: a.eq_missing(b),
}

_UNARY_OPS = {
    "not": lambda a: ~a,
    "negate": lambda a: -a,
}


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


def constant_python(
    node: Any,
    *,
    parameters: dict[str, Any],
) -> Any:
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


def lower_expr(node: Any, *, parameters: dict[str, Any]) -> pl.Expr:
    """Recursively lower a DTCS expression node to ``pl.Expr``."""
    if not isinstance(node, dict):
        raise ValueError(f"Expected expression object, got {type(node)!r}")
    kind = node.get("kind")
    if kind == "fieldRef":
        scope = node.get("scope")
        target = node.get("target")
        if scope == "parameter":
            if target not in parameters:
                raise KeyError(f"Missing parameter {target!r}")
            return pl.lit(parameters[target])
        return pl.col(str(target))
    if kind == "literal":
        return pl.lit(unwrap_literal_value(node.get("value")))
    if kind == "binary":
        op = node.get("op")
        if op not in _BINARY_OPS:
            raise ValueError(f"Unsupported binary op {op!r}")
        left = lower_expr(node["left"], parameters=parameters)
        right = lower_expr(node["right"], parameters=parameters)
        return _BINARY_OPS[op](left, right)
    if kind == "unary":
        op = node.get("op")
        if op not in _UNARY_OPS:
            raise ValueError(f"Unsupported unary op {op!r}")
        operand = node.get("operand", node.get("expr"))
        if operand is None:
            raise ValueError("unary expression missing operand/expr")
        return _UNARY_OPS[op](lower_expr(operand, parameters=parameters))
    if kind == "call":
        return _lower_call(node, parameters=parameters)
    raise ValueError(f"Unsupported expression kind {kind!r}")


def _lower_call(node: dict[str, Any], *, parameters: dict[str, Any]) -> pl.Expr:
    callee = str(node.get("callee") or "")
    raw_args = list(node.get("args") or [])
    args = [lower_expr(a, parameters=parameters) for a in raw_args]
    if callee == "dtcs:lower":
        return args[0].str.to_lowercase()
    if callee == "dtcs:upper":
        return args[0].str.to_uppercase()
    if callee == "dtcs:concat":
        return pl.concat_str(args, separator="")
    if callee == "dtcs:concat_ws":
        sep = constant_python(raw_args[0], parameters=parameters)
        if not isinstance(sep, str):
            raise ValueError("dtcs:concat_ws separator must be a string constant")
        return pl.concat_str(args[1:], separator=sep)
    if callee == "dtcs:length":
        return args[0].str.len_chars()
    if callee == "dtcs:substr":
        if len(args) == 2:
            return args[0].str.slice(args[1])
        return args[0].str.slice(args[1], args[2])
    if callee == "dtcs:replace":
        search = constant_python(raw_args[1], parameters=parameters)
        replacement = constant_python(raw_args[2], parameters=parameters)
        return args[0].str.replace_all(str(search), str(replacement), literal=True)
    if callee == "dtcs:contains":
        needle = constant_python(raw_args[1], parameters=parameters)
        return args[0].str.contains(str(needle), literal=True)
    if callee == "dtcs:starts_with":
        prefix = constant_python(raw_args[1], parameters=parameters)
        return args[0].str.starts_with(str(prefix))
    if callee == "dtcs:ends_with":
        suffix = constant_python(raw_args[1], parameters=parameters)
        return args[0].str.ends_with(str(suffix))
    if callee == "dtcs:coalesce":
        return pl.coalesce(args)
    if callee == "dtcs:if_null":
        return pl.when(args[0].is_null()).then(args[1]).otherwise(args[0])
    if callee == "dtcs:null_if":
        return pl.when(args[0] == args[1]).then(None).otherwise(args[0])
    if callee == "dtcs:is_null":
        return args[0].is_null()
    if callee == "dtcs:abs":
        return args[0].abs()
    if callee == "dtcs:round":
        scale = constant_python(raw_args[1], parameters=parameters)
        return args[0].round(int(scale))
    if callee == "dtcs:floor":
        return args[0].floor()
    if callee == "dtcs:ceil":
        return args[0].ceil()
    if callee == "dtcs:power":
        return args[0].pow(args[1])
    if callee == "dtcs:sqrt":
        return args[0].sqrt()
    if callee == "dtcs:least":
        return pl.min_horizontal(args)
    if callee == "dtcs:greatest":
        return pl.max_horizontal(args)
    if callee == "dtcs:case_when":
        return _lower_case_when(node, parameters=parameters)
    # Aggregate callees are only valid inside dtcs:aggregate (see lower_agg_expr).
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
    # dtcs:cast is conversion-profile only; do not silently no-op.
    raise ValueError(f"Unsupported function {callee!r}")


def lower_agg_expr(node: Any, *, parameters: dict[str, Any]) -> pl.Expr:
    """Lower an aggregate call expression for ``dtcs:aggregate``."""
    if not isinstance(node, dict) or node.get("kind") != "call":
        raise ValueError(f"Expected aggregate call expression, got {node!r}")
    callee = str(node.get("callee") or "")
    raw_args = list(node.get("args") or [])
    args = [lower_expr(a, parameters=parameters) for a in raw_args]
    if callee == "dtcs:sum":
        return args[0].sum()
    if callee == "dtcs:average":
        return args[0].mean()
    if callee == "dtcs:min":
        return args[0].min()
    if callee == "dtcs:max":
        return args[0].max()
    if callee == "dtcs:count_all":
        return pl.len()
    if callee == "dtcs:count":
        if not args:
            return pl.len()
        return args[0].count()
    if callee == "dtcs:count_distinct":
        return args[0].n_unique()
    raise ValueError(f"Unsupported aggregate function {callee!r}")


def _lower_case_when(node: dict[str, Any], *, parameters: dict[str, Any]) -> pl.Expr:
    args = list(node.get("args") or [])
    if not args:
        raise ValueError("case_when requires branches")
    # DTCS case_when args are alternating when/then pairs ending with else.
    expr: pl.Expr | None = None
    i = 0
    while i + 1 < len(args):
        cond = lower_expr(args[i], parameters=parameters)
        then = lower_expr(args[i + 1], parameters=parameters)
        branch = pl.when(cond).then(then)
        expr = branch if expr is None else expr.when(cond).then(then)  # type: ignore[union-attr]
        i += 2
    if i < len(args):
        otherwise = lower_expr(args[i], parameters=parameters)
        if expr is None:
            return otherwise
        return expr.otherwise(otherwise)
    if expr is None:
        raise ValueError("empty case_when")
    return expr.otherwise(None)
