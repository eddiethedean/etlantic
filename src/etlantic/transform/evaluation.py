# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Shared scalar expression evaluation for preview and local execution."""

from __future__ import annotations

import datetime as dt
import math
import operator
import re
from collections.abc import Callable, Mapping
from decimal import Decimal, DecimalException
from typing import Any

from etlantic.transform.portable_baseline import normalize_operator
from etlantic.transform.protocol import INVALID, MISSING


class ExpressionEvaluationError(ValueError):
    """An expression cannot be evaluated under the portable scalar policy."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


ExpressionErrorHandler = Callable[[ExpressionEvaluationError], None]


def coerce_value(value: Any, logical_type: str) -> Any:
    """Convert a scalar using the inference and portable preview policy."""
    if logical_type == "integer":
        if isinstance(value, bool):
            raise ValueError("boolean is not an integer value")
        if isinstance(value, float) and not value.is_integer():
            raise ValueError("integer conversion would lose the fractional part")
        if isinstance(value, Decimal) and value != value.to_integral_value():
            raise ValueError("integer conversion would lose the fractional part")
        return int(value)
    if logical_type == "number":
        converted = float(value)
        if not math.isfinite(converted):
            raise ValueError("number conversion produced a non-finite value")
        if isinstance(value, (Decimal, int)):
            if Decimal(str(converted)) != Decimal(value):
                raise ValueError("number conversion would lose precision")
        elif isinstance(value, str):
            try:
                original = Decimal(value.strip())
            except (ArithmeticError, ValueError):
                if not value.strip():
                    raise ValueError("invalid number spelling") from None
            else:
                if Decimal(str(converted)) != original:
                    raise ValueError("number conversion would lose precision")
        return converted
    if logical_type == "decimal":
        return value if isinstance(value, Decimal) else Decimal(str(value))
    if logical_type == "binary":
        if isinstance(value, bytes):
            return value
        if isinstance(value, str):
            return value.encode()
        return bytes(value)
    if logical_type == "boolean":
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
            raise ValueError("invalid boolean spelling")
        return bool(value)
    if logical_type == "string":
        return str(value)
    if logical_type == "date":
        return (
            value if isinstance(value, dt.date) else dt.date.fromisoformat(str(value))
        )
    if logical_type == "datetime":
        return (
            value
            if isinstance(value, dt.datetime)
            else dt.datetime.fromisoformat(str(value))
        )
    raise TypeError(f"unsupported conversion to {logical_type}")


def _issue(
    code: str,
    message: str,
    on_error: ExpressionErrorHandler | None,
    *,
    cause: Exception | None = None,
) -> None:
    issue = ExpressionEvaluationError(code, message)
    if on_error is not None:
        on_error(issue)
        return
    if cause is not None:
        raise cause
    raise issue


def _literal(node: Mapping[str, Any], on_error: ExpressionErrorHandler | None) -> Any:
    value = node.get("value")
    if not isinstance(value, Mapping) or "type" not in value:
        return (
            value.get("value")
            if isinstance(value, Mapping) and "value" in value
            else value
        )
    logical_type = str(value.get("type", "")).lower()
    raw = value.get("value")
    if logical_type == "missing":
        return MISSING
    if logical_type == "invalid":
        return INVALID
    if raw is None:
        return None
    try:
        if logical_type in {"int", "integer", "long"}:
            return int(raw)
        if logical_type in {"float", "number", "double"}:
            return float(raw)
        if logical_type in {"decimal", "numeric"}:
            return Decimal(str(raw))
        if logical_type in {"bool", "boolean"}:
            if isinstance(raw, str):
                lowered = raw.strip().lower()
                if lowered in {"true", "1", "yes"}:
                    return True
                if lowered in {"false", "0", "no"}:
                    return False
                raise ValueError("invalid boolean spelling")
            return bool(raw)
        if logical_type == "date":
            return dt.date.fromisoformat(str(raw))
        if logical_type == "datetime":
            return dt.datetime.fromisoformat(str(raw))
        if logical_type in {"binary", "bytes"}:
            return bytes.fromhex(raw) if isinstance(raw, str) else bytes(raw)
        if logical_type in {"null", "none"}:
            return None
    except (ArithmeticError, TypeError, ValueError, OverflowError) as exc:
        _issue(
            "conversion",
            f"Preview literal cannot be converted to {logical_type!r}",
            on_error,
            cause=exc,
        )
        return None
    return raw


def _sql_and(left: Any, right: Any) -> bool | None:
    if left is False or right is False:
        return False
    if left is None or right is None:
        return None
    if not isinstance(left, bool) or not isinstance(right, bool):
        raise TypeError("and operands must be boolean or null")
    return left and right


def _sql_or(left: Any, right: Any) -> bool | None:
    if left is True or right is True:
        return True
    if left is None or right is None:
        return None
    if not isinstance(left, bool) or not isinstance(right, bool):
        raise TypeError("or operands must be boolean or null")
    return left or right


def evaluate_expression(
    node: Any,
    row: Mapping[str, Any],
    params: Mapping[str, Any] | None = None,
    *,
    on_error: ExpressionErrorHandler | None = None,
) -> Any:
    """Evaluate a scalar expression with SQL null and predicate semantics.

    When ``on_error`` is supplied, unsupported expressions and runtime
    failures are reported to it and evaluate to ``None``. Without a handler,
    those failures raise so engine execution remains fail closed.
    """
    parameters = params or {}
    if not isinstance(node, Mapping):
        return node
    kind = node.get("kind")
    if kind == "fieldRef":
        target = str(node.get("target"))
        return (
            parameters.get(target)
            if node.get("scope") == "parameter"
            else row.get(target)
        )
    if kind == "literal":
        return _literal(node, on_error)
    if kind == "binary":
        left = evaluate_expression(node.get("left"), row, parameters, on_error=on_error)
        right = evaluate_expression(
            node.get("right"), row, parameters, on_error=on_error
        )
        op = normalize_operator(str(node.get("op")))
        if op == "null_safe_eq":
            return left == right
        if op in {"and", "or"}:
            try:
                return _sql_and(left, right) if op == "and" else _sql_or(left, right)
            except TypeError as exc:
                _issue(
                    "runtime",
                    f"Preview evaluation failed for operator {op!r}",
                    on_error,
                    cause=exc,
                )
                return None
        if (
            left is None
            or right is None
            or left is MISSING
            or right is MISSING
            or left is INVALID
            or right is INVALID
        ):
            return None
        operations: dict[str, Callable[[Any, Any], Any]] = {
            "add": operator.add,
            "subtract": operator.sub,
            "multiply": operator.mul,
            "divide": operator.truediv,
            "modulo": operator.mod,
            "eq": operator.eq,
            "not_eq": operator.ne,
            "lt": operator.lt,
            "lte": operator.le,
            "gt": operator.gt,
            "gte": operator.ge,
        }
        if op == "in":
            return (
                left in right
                if isinstance(right, (list, tuple, set, frozenset))
                else False
            )
        operation = operations.get(op)
        if operation is None:
            _issue("unsupported", f"unsupported binary operator: {op}", on_error)
            return None
        try:
            return operation(left, right)
        except (
            TypeError,
            ValueError,
            OverflowError,
            ArithmeticError,
            DecimalException,
        ) as exc:
            _issue(
                "runtime",
                f"Preview evaluation failed for operator {op!r}",
                on_error,
                cause=exc,
            )
            return None
    if kind == "unary":
        value = evaluate_expression(
            node.get("expr", node.get("operand")), row, parameters, on_error=on_error
        )
        op = normalize_operator(str(node.get("op")))
        if op == "not":
            if value is None or value is MISSING or value is INVALID:
                return None
            if not isinstance(value, bool):
                _issue(
                    "runtime",
                    "Preview evaluation failed for operator 'not'",
                    on_error,
                    cause=TypeError("not operand must be boolean or null"),
                )
                return None
            return not value
        if op == "negate":
            if value is None or value is MISSING or value is INVALID:
                return None
            try:
                return -value
            except (
                TypeError,
                ValueError,
                OverflowError,
                ArithmeticError,
                DecimalException,
            ) as exc:
                _issue(
                    "runtime",
                    "Preview evaluation failed for operator 'negate'",
                    on_error,
                    cause=exc,
                )
                return None
        _issue("unsupported", f"unsupported unary operator: {op}", on_error)
        return None
    if kind == "call":
        callee = str(node.get("callee"))
        args = [
            evaluate_expression(item, row, parameters, on_error=on_error)
            for item in node.get("args", ())
        ]
        name = callee.removeprefix("dtcs:")
        null_aware = {
            "coalesce",
            "if_null",
            "is_null",
            "is_not_null",
            "case_when",
            "null_if",
            "is_missing",
            "is_invalid",
        }
        if name not in null_aware and any(value is None for value in args):
            return None
        try:
            if name == "is_null" and args:
                return args[0] is None
            if name == "is_not_null" and args:
                return args[0] is not None
            if name == "is_missing" and args:
                return args[0] is MISSING
            if name == "is_invalid" and args:
                return args[0] is INVALID
            if name == "coalesce" and args:
                return next((value for value in args if value is not None), None)
            if name == "if_null" and len(args) >= 2:
                return args[1] if args[0] is None else args[0]
            if name == "null_if" and len(args) >= 2:
                return None if args[0] == args[1] else args[0]
            if name == "case_when" and args:
                for index in range(0, max(0, len(args) - 1), 2):
                    if args[index] is True:
                        return args[index + 1]
                return args[-1]
            if name in {"cast", "try_cast"} and args:
                target = str(args[1] if len(args) > 1 else "string").lower()
                aliases = {
                    "int": "integer",
                    "long": "integer",
                    "float": "number",
                    "double": "number",
                    "numeric": "decimal",
                    "bool": "boolean",
                    "str": "string",
                    "bytes": "binary",
                }
                target = aliases.get(target, target)
                try:
                    return coerce_value(args[0], target)
                except (
                    TypeError,
                    ValueError,
                    OverflowError,
                    ArithmeticError,
                    DecimalException,
                ) as exc:
                    if name == "try_cast":
                        return None
                    _issue(
                        "conversion",
                        f"Preview value cannot be safely converted to {target!r}",
                        on_error,
                        cause=exc,
                    )
                    return None
            if name in {"to_integer", "to_decimal", "to_string"} and args:
                target = {
                    "to_integer": "integer",
                    "to_decimal": "decimal",
                    "to_string": "string",
                }[name]
                try:
                    return coerce_value(args[0], target)
                except (
                    TypeError,
                    ValueError,
                    OverflowError,
                    ArithmeticError,
                    DecimalException,
                ) as exc:
                    _issue(
                        "conversion",
                        f"Preview value cannot be safely converted to {target!r}",
                        on_error,
                        cause=exc,
                    )
                    return None
            if name == "lower" and args:
                return str(args[0]).lower()
            if name == "upper" and args:
                return str(args[0]).upper()
            if name == "concat":
                return "".join(str(value) for value in args)
            if name == "concat_ws" and args:
                if args[0] is None:
                    return None
                return str(args[0]).join(
                    str(value) for value in args[1:] if value is not None
                )
            if name in {"substr", "substring"} and args:
                start = int(args[1]) if len(args) > 1 else 0
                length = int(args[2]) if len(args) > 2 else None
                return (
                    str(args[0])[start:]
                    if length is None
                    else str(args[0])[start : start + length]
                )
            if name == "replace" and len(args) >= 3:
                return str(args[0]).replace(str(args[1]), str(args[2]))
            if name == "contains" and len(args) >= 2:
                return args[1] in args[0]
            if name == "in" and args:
                return args[0] in args[1:]
            if name == "starts_with" and len(args) >= 2:
                return str(args[0]).startswith(str(args[1]))
            if name == "ends_with" and len(args) >= 2:
                return str(args[0]).endswith(str(args[1]))
            if name == "regex_extract" and len(args) >= 2:
                match = re.search(str(args[1]), str(args[0]))
                if match is None:
                    return None
                group = int(args[2]) if len(args) > 2 and args[2] is not None else 0
                return match.group(group)
            if name == "regex_replace" and len(args) >= 3:
                return re.sub(str(args[1]), str(args[2]), str(args[0]))
            if name in {"trim", "ltrim", "rtrim", "normalize_whitespace"} and args:
                value = str(args[0])
                if name == "ltrim":
                    return value.lstrip()
                if name == "rtrim":
                    return value.rstrip()
                return (
                    " ".join(value.split())
                    if name == "normalize_whitespace"
                    else value.strip()
                )
            if name == "length" and args:
                return len(args[0])
            if name == "abs" and args:
                return abs(args[0])
            if name == "round" and args:
                return round(args[0], int(args[1]) if len(args) > 1 else 0)
            if name == "floor" and args:
                return math.floor(args[0])
            if name == "ceil" and args:
                return math.ceil(args[0])
            if name == "power" and len(args) >= 2:
                return pow(args[0], args[1])
            if name == "sqrt" and args:
                return math.sqrt(args[0])
            if name in {"least", "greatest"} and args:
                return min(args) if name == "least" else max(args)
            if name == "current_date":
                return dt.date.today()
            if name == "current_timestamp":
                return dt.datetime.now(dt.UTC)
        except (
            TypeError,
            ValueError,
            OverflowError,
            ArithmeticError,
            DecimalException,
            re.error,
            IndexError,
        ) as exc:
            _issue(
                "runtime",
                f"Preview evaluation failed for expression {callee!r}",
                on_error,
                cause=exc,
            )
            return None
        if name in {
            "sum",
            "average",
            "min",
            "max",
            "count",
            "count_all",
            "count_distinct",
        }:
            _issue(
                "unsupported",
                f"aggregate function is not valid in scalar expression: {callee}",
                on_error,
            )
            return None
        _issue(
            "unsupported",
            f"Preview evaluator does not support expression {callee!r}",
            on_error,
        )
        return None
    _issue("unsupported", f"unsupported expression kind: {kind}", on_error)
    return None


__all__ = ["ExpressionEvaluationError", "coerce_value", "evaluate_expression"]
