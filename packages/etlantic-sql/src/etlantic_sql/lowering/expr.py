"""Lower DTCS expression nodes to etlantic.sql IR expressions."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from etlantic.sql.protocol import (
    BinaryExpr,
    CallExpr,
    CaseWhenExpr,
    ColumnRef,
    LiteralExpr,
    UnaryExpr,
)

_BINARY_OPS = frozenset(
    {
        "eq",
        "neq",
        "not_eq",
        "lt",
        "lte",
        "gt",
        "gte",
        "add",
        "sub",
        "subtract",
        "mul",
        "multiply",
        "div",
        "divide",
        "modulo",
        "and",
        "or",
        "null_safe_eq",
    }
)
_UNARY_OPS = frozenset({"not", "negate"})


def unwrap_literal_value(value: Any) -> Any:
    if not isinstance(value, dict) or "type" not in value:
        return value
    lit_type = str(value.get("type") or "")
    payload = value.get("value")
    if lit_type in {"null", "missing", "invalid"}:
        return None
    if lit_type == "boolean":
        return bool(payload)
    if lit_type == "integer":
        if payload is None:
            raise ValueError("integer literal requires a value")
        return int(payload)
    if lit_type == "decimal":
        if payload is None:
            raise ValueError("decimal literal requires a value")
        # JSON-authored decimal fixtures may use numeric values for ordinary
        # bounded decimals.  Exact Decimal authoring uses a string payload so
        # coefficient and scale survive serialization without a float hop.
        return Decimal(str(payload)) if isinstance(payload, str) else payload
    if lit_type == "string":
        return str(payload)
    raise ValueError(f"Unsupported DTCS literal type {lit_type!r}")


def lower_literal(value: Any) -> LiteralExpr:
    """Lower a DTCS literal with enough SQL type information for PostgreSQL.

    PostgreSQL cannot infer the type of a bound ``NULL`` or an argument to a
    polymorphic variadic function such as ``CONCAT_WS``.  The closed portable
    literal envelope already carries this information, so keep it through the
    SQL IR instead of relying on driver-specific inference.
    """
    if not isinstance(value, dict) or "type" not in value:
        return LiteralExpr(value=value)
    literal_type = str(value.get("type") or "")
    sql_type = {
        "null": "TEXT",
        "boolean": "BOOLEAN",
        # PostgreSQL's SUBSTRING/ROUND overloads use ``integer`` rather than
        # ``bigint``; the portable integer literals used by this baseline fit
        # the shared SQL ``INTEGER`` type.
        "integer": "INTEGER",
        "decimal": "NUMERIC",
        "string": "TEXT",
    }.get(literal_type)
    return LiteralExpr(value=unwrap_literal_value(value), sql_type=sql_type)


def constant_python(node: Any, *, parameters: dict[str, Any]) -> Any:
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


def lower_expr(node: Any, *, parameters: dict[str, Any]) -> Any:
    if not isinstance(node, dict):
        raise ValueError(f"Expected expression object, got {type(node)!r}")
    kind = node.get("kind")
    if kind == "fieldRef":
        scope = node.get("scope")
        target = node.get("target")
        if scope == "parameter":
            if target not in parameters:
                raise KeyError(f"Missing parameter {target!r}")
            return LiteralExpr(value=parameters[target])
        return ColumnRef(column=str(target))
    if kind == "literal":
        return lower_literal(node.get("value"))
    if kind == "binary":
        op = node.get("op")
        if op not in _BINARY_OPS:
            raise ValueError(f"Unsupported binary op {op!r}")
        return BinaryExpr(
            op=str(op),
            left=lower_expr(node["left"], parameters=parameters),
            right=lower_expr(node["right"], parameters=parameters),
        )
    if kind == "unary":
        op = node.get("op")
        if op not in _UNARY_OPS:
            raise ValueError(f"Unsupported unary op {op!r}")
        operand = node.get("operand", node.get("expr"))
        if operand is None:
            raise ValueError("unary expression missing operand/expr")
        return UnaryExpr(op=str(op), operand=lower_expr(operand, parameters=parameters))
    if kind == "call":
        return _lower_call(node, parameters=parameters)
    raise ValueError(f"Unsupported expression kind {kind!r}")


def _lower_call(node: dict[str, Any], *, parameters: dict[str, Any]) -> Any:
    callee = str(node.get("callee") or "")
    raw_args = list(node.get("args") or [])
    if callee == "dtcs:case_when":
        return _lower_case_when(node, parameters=parameters)
    # Preserve closed literal type envelopes for PostgreSQL's polymorphic
    # functions; all values still lower to bound parameters.
    if callee in {
        "dtcs:replace",
        "dtcs:contains",
        "dtcs:starts_with",
        "dtcs:ends_with",
        "dtcs:concat_ws",
        "dtcs:round",
    }:
        args: list[Any] = []
        for i, raw in enumerate(raw_args):
            if (
                (callee == "dtcs:concat_ws" and i == 0)
                or (callee == "dtcs:replace" and i in {1, 2})
                or (
                    callee in {"dtcs:contains", "dtcs:starts_with", "dtcs:ends_with"}
                    and i == 1
                )
                or (callee == "dtcs:round" and i == 1)
            ):
                args.append(lower_expr(raw, parameters=parameters))
            else:
                args.append(lower_expr(raw, parameters=parameters))
        return CallExpr(callee=callee, args=tuple(args))
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
    args = [lower_expr(a, parameters=parameters) for a in raw_args]
    return CallExpr(callee=callee, args=tuple(args))


def lower_agg_expr(node: Any, *, parameters: dict[str, Any]) -> CallExpr:
    if not isinstance(node, dict) or node.get("kind") != "call":
        raise ValueError(f"Expected aggregate call expression, got {node!r}")
    callee = str(node.get("callee") or "")
    raw_args = list(node.get("args") or [])
    if callee == "dtcs:count_all":
        return CallExpr(callee=callee, args=())
    args = [lower_expr(a, parameters=parameters) for a in raw_args]
    return CallExpr(callee=callee, args=tuple(args))


def _lower_case_when(
    node: dict[str, Any], *, parameters: dict[str, Any]
) -> CaseWhenExpr:
    args = list(node.get("args") or [])
    if not args:
        raise ValueError("case_when requires branches")
    branches: list[tuple[Any, Any]] = []
    i = 0
    while i + 1 < len(args):
        branches.append(
            (
                lower_expr(args[i], parameters=parameters),
                lower_expr(args[i + 1], parameters=parameters),
            )
        )
        i += 2
    otherwise = lower_expr(args[i], parameters=parameters) if i < len(args) else None
    return CaseWhenExpr(branches=tuple(branches), otherwise=otherwise)
