"""Lower DTCS expression nodes to Spark Column expressions."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def _F():
    from pyspark.sql import functions as F

    return F


def _binary_ops():
    return {
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
        "null_safe_eq": lambda a, b: a.eqNullSafe(b),
    }


def _unary_ops():
    return {
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


def lower_expr(node: Any, *, parameters: dict[str, Any]) -> Any:
    """Recursively lower a DTCS expression node to a Spark Column."""
    if not isinstance(node, dict):
        raise ValueError(f"Expected expression object, got {type(node)!r}")
    kind = node.get("kind")
    if kind == "fieldRef":
        scope = node.get("scope")
        target = node.get("target")
        if scope == "parameter":
            if target not in parameters:
                raise KeyError(f"Missing parameter {target!r}")
            return _F().lit(parameters[target])
        return _F().col(str(target))
    if kind == "literal":
        return _F().lit(unwrap_literal_value(node.get("value")))
    if kind == "binary":
        op = node.get("op")
        if op not in _binary_ops():
            raise ValueError(f"Unsupported binary op {op!r}")
        left = lower_expr(node["left"], parameters=parameters)
        right = lower_expr(node["right"], parameters=parameters)
        return _binary_ops()[op](left, right)
    if kind == "unary":
        op = node.get("op")
        if op not in _unary_ops():
            raise ValueError(f"Unsupported unary op {op!r}")
        operand = node.get("operand", node.get("expr"))
        if operand is None:
            raise ValueError("unary expression missing operand/expr")
        return _unary_ops()[op](lower_expr(operand, parameters=parameters))
    if kind == "call":
        return _lower_call(node, parameters=parameters)
    raise ValueError(f"Unsupported expression kind {kind!r}")


def _lower_call(node: dict[str, Any], *, parameters: dict[str, Any]) -> Any:
    callee = str(node.get("callee") or "")
    raw_args = list(node.get("args") or [])
    args = [lower_expr(a, parameters=parameters) for a in raw_args]
    if callee == "dtcs:lower":
        return _F().lower(args[0])
    if callee == "dtcs:upper":
        return _F().upper(args[0])
    if callee == "dtcs:trim":
        return _F().trim(args[0])
    if callee == "dtcs:ltrim":
        return _F().ltrim(args[0])
    if callee == "dtcs:rtrim":
        return _F().rtrim(args[0])
    if callee == "dtcs:regex_extract":
        pattern = constant_python(raw_args[1], parameters=parameters)
        group = (
            int(constant_python(raw_args[2], parameters=parameters))
            if len(raw_args) > 2
            else 0
        )
        return _F().regexp_extract(args[0], str(pattern), group)
    if callee == "dtcs:regex_replace":
        pattern = constant_python(raw_args[1], parameters=parameters)
        replacement = constant_python(raw_args[2], parameters=parameters)
        return _F().regexp_replace(args[0], str(pattern), str(replacement))
    if callee == "dtcs:split":
        pattern = constant_python(raw_args[1], parameters=parameters)
        return _F().split(args[0], str(pattern))
    if callee == "dtcs:concat":
        return _F().concat(*args)
    if callee == "dtcs:concat_ws":
        sep = constant_python(raw_args[0], parameters=parameters)
        return _F().concat_ws(str(sep), *args[1:])
    if callee == "dtcs:length":
        return _F().length(args[0])
    if callee == "dtcs:substr":
        # Portable IR is 0-based; Spark substring is 1-based.
        # PySpark < 4 accepts Python integers, not Column expressions, for
        # ``pos`` and ``len``. DTCS substring bounds are constant expressions.
        start = int(constant_python(raw_args[1], parameters=parameters)) + 1
        if len(args) == 2:
            return _F().substring(args[0], start, 2147483647)
        length = int(constant_python(raw_args[2], parameters=parameters))
        return _F().substring(args[0], start, length)
    if callee == "dtcs:replace":
        import re

        search = constant_python(raw_args[1], parameters=parameters)
        replacement = constant_python(raw_args[2], parameters=parameters)
        # Literal replace (match Polars); escape regex metacharacters.
        pattern = re.escape(str(search))
        return _F().regexp_replace(args[0], pattern, str(replacement))
    if callee == "dtcs:contains":
        needle = constant_python(raw_args[1], parameters=parameters)
        return args[0].contains(str(needle))
    if callee == "dtcs:in":
        values = [constant_python(raw, parameters=parameters) for raw in raw_args[1:]]
        return args[0].isin(*values)
    if callee == "dtcs:starts_with":
        prefix = constant_python(raw_args[1], parameters=parameters)
        return args[0].startswith(str(prefix))
    if callee == "dtcs:ends_with":
        suffix = constant_python(raw_args[1], parameters=parameters)
        return args[0].endswith(str(suffix))
    if callee == "dtcs:coalesce":
        return _F().coalesce(*args)
    if callee == "dtcs:if_null":
        return _F().when(args[0].isNull(), args[1]).otherwise(args[0])
    if callee == "dtcs:null_if":
        return _F().when(args[0] == args[1], _F().lit(None)).otherwise(args[0])
    if callee == "dtcs:is_null":
        return args[0].isNull()
    if callee == "dtcs:to_string":
        return args[0].cast("string")
    if callee == "dtcs:to_integer":
        return args[0].cast("long")
    if callee in {"dtcs:cast", "dtcs:try_cast"}:
        data_type = str(constant_python(raw_args[1], parameters=parameters))
        spark_type = _spark_dtype(data_type)
        # Spark 3.5 soft-casts invalid values to null under default ANSI-off;
        # Column.try_cast arrives in later Spark lines.
        return args[0].cast(spark_type)
    if callee == "dtcs:abs":
        return _F().abs(args[0])
    if callee == "dtcs:round":
        scale = (
            constant_python(raw_args[1], parameters=parameters)
            if len(raw_args) > 1
            else 0
        )
        return _F().round(args[0], int(scale))
    if callee == "dtcs:floor":
        return _F().floor(args[0])
    if callee == "dtcs:ceil":
        return _F().ceil(args[0])
    if callee == "dtcs:power":
        return _F().pow(args[0], args[1])
    if callee == "dtcs:sqrt":
        return _F().sqrt(args[0])
    if callee == "dtcs:least":
        return _F().least(*args)
    if callee == "dtcs:greatest":
        return _F().greatest(*args)
    if callee == "dtcs:row_number":
        if args:
            raise ValueError("dtcs:row_number does not accept arguments")
        return _F().row_number()
    if callee == "dtcs:rank":
        return _F().rank()
    if callee == "dtcs:dense_rank":
        return _F().dense_rank()
    if callee == "dtcs:lag":
        offset = (
            int(constant_python(raw_args[1], parameters=parameters))
            if len(raw_args) > 1
            else 1
        )
        if len(args) > 2:
            return _F().lag(args[0], offset, args[2])
        return _F().lag(args[0], offset)
    if callee == "dtcs:lead":
        offset = (
            int(constant_python(raw_args[1], parameters=parameters))
            if len(raw_args) > 1
            else 1
        )
        if len(args) > 2:
            return _F().lead(args[0], offset, args[2])
        return _F().lead(args[0], offset)
    if callee == "dtcs:first_value":
        return _F().first(args[0], ignorenulls=False)
    if callee == "dtcs:last_value":
        return _F().last(args[0], ignorenulls=False)
    if callee == "dtcs:array":
        return _F().array(*args)
    if callee == "dtcs:map":
        if len(args) % 2:
            raise ValueError("dtcs:map requires alternating key/value arguments")
        return _F().create_map(*args)
    if callee == "dtcs:size":
        return _F().size(args[0])
    if callee == "dtcs:object":
        if len(raw_args) % 2:
            raise ValueError("dtcs:object requires alternating key/value arguments")
        fields = []
        for index in range(0, len(raw_args), 2):
            key = constant_python(raw_args[index], parameters=parameters)
            if not isinstance(key, str):
                raise ValueError("dtcs:object keys must be string constants")
            fields.append(args[index + 1].alias(key))
        return _F().struct(*fields)
    if callee == "dtcs:field":
        field = constant_python(raw_args[1], parameters=parameters)
        if not isinstance(field, str):
            raise ValueError("dtcs:field name must be a string constant")
        return args[0].getField(field)
    if callee in {"dtcs:index", "dtcs:element_at"}:
        try:
            key = constant_python(raw_args[1], parameters=parameters)
        except (KeyError, ValueError):
            key = None
        if isinstance(key, str):
            return args[0].getField(key)
        # Spark element_at is 1-based for arrays; portable IR is 0-based.
        if isinstance(key, bool):
            raise ValueError(f"{callee} boolean index is not supported")
        if isinstance(key, int):
            return _F().element_at(args[0], int(key) + 1)
        raise ValueError(f"{callee} requires a constant string field or integer index")
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
        "dtcs:variance",
        "dtcs:stddev",
        "dtcs:corr",
    }:
        raise ValueError(
            f"Aggregate function {callee!r} is only valid inside dtcs:aggregate"
        )
    raise ValueError(f"Unsupported function {callee!r}")


def _spark_dtype(data_type: str) -> str:
    normalized = data_type.strip().lower()
    aliases = {
        "string": "string",
        "str": "string",
        "utf8": "string",
        "integer": "long",
        "int": "long",
        "int64": "long",
        "long": "long",
        "float": "double",
        "float64": "double",
        "double": "double",
        "boolean": "boolean",
        "bool": "boolean",
        "date": "date",
        "datetime": "timestamp",
        "timestamp": "timestamp",
    }
    if normalized not in aliases:
        raise ValueError(f"Unsupported cast data type {data_type!r}")
    return aliases[normalized]


def lower_agg_expr(node: Any, *, parameters: dict[str, Any]) -> Any:
    """Lower an aggregate call expression for ``dtcs:aggregate``."""
    if not isinstance(node, dict) or node.get("kind") != "call":
        raise ValueError(f"Expected aggregate call expression, got {node!r}")
    callee = str(node.get("callee") or "")
    raw_args = list(node.get("args") or [])
    args = [lower_expr(a, parameters=parameters) for a in raw_args]
    if callee == "dtcs:sum":
        return _F().sum(args[0])
    if callee == "dtcs:average":
        return _F().avg(args[0])
    if callee == "dtcs:min":
        return _F().min(args[0])
    if callee == "dtcs:max":
        return _F().max(args[0])
    if callee == "dtcs:count_all":
        return _F().count(_F().lit(1))
    if callee == "dtcs:count":
        if not args:
            return _F().count(_F().lit(1))
        return _F().count(args[0])
    if callee == "dtcs:count_distinct":
        return _F().countDistinct(args[0])
    if callee == "dtcs:variance":
        return _F().variance(args[0])
    if callee == "dtcs:stddev":
        return _F().stddev(args[0])
    if callee == "dtcs:corr":
        return _F().corr(args[0], args[1])
    raise ValueError(f"Unsupported aggregate function {callee!r}")


def _lower_case_when(node: dict[str, Any], *, parameters: dict[str, Any]) -> Any:
    args = list(node.get("args") or [])
    if not args:
        raise ValueError("case_when requires branches")
    expr: Any | None = None
    i = 0
    while i + 1 < len(args):
        cond = lower_expr(args[i], parameters=parameters)
        then = lower_expr(args[i + 1], parameters=parameters)
        branch = _F().when(cond, then)
        expr = branch if expr is None else expr.when(cond, then)
        i += 2
    if i < len(args):
        otherwise = lower_expr(args[i], parameters=parameters)
        if expr is None:
            return otherwise
        return expr.otherwise(otherwise)
    if expr is None:
        raise ValueError("empty case_when")
    return expr.otherwise(_F().lit(None))
