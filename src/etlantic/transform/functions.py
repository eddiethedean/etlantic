"""PySpark-inspired `functions as F` catalog for portable authoring."""

from __future__ import annotations

from typing import Any

from etlantic.exceptions import ModelDefinitionError
from etlantic.transform.column import ColumnExpr, coerce_column
from etlantic.transform.protocol import (
    PROFILE_COMPLEX_TYPES,
    PROFILE_COMPLEX_VALUES,
    PROFILE_CONVERSION,
    PROFILE_NONDETERMINISTIC,
    PROFILE_STATISTICS,
    PROFILE_STRING_ADVANCED,
    PROFILE_TEMPORAL_IANA,
    PROFILE_WINDOW_V1,
    PROFILE_WINDOW_V2,
    RELATIONAL_PROFILE_V1,
)


def col(name: str) -> ColumnExpr:
    """Reference a field by name."""
    return ColumnExpr(
        node={"kind": "fieldRef", "target": name},
        path=name,
    )


def lit(value: Any) -> ColumnExpr:
    """Create a bounded literal column."""
    return coerce_column(value)


def _call(
    callee: str,
    *args: Any,
    profiles: frozenset[str] | set[str] | None = None,
) -> ColumnExpr:
    cols = [coerce_column(a) for a in args]
    functions = frozenset({callee}).union(*(c.functions for c in cols))
    req = frozenset(profiles or ())
    req = req.union(*(c.profiles for c in cols))
    return ColumnExpr(
        node={"kind": "call", "callee": callee, "args": [c.node for c in cols]},
        path=f"{callee}(...)",
        functions=functions,
        profiles=req,
    )


class _WhenBuilder:
    def __init__(self, branches: list[tuple[ColumnExpr, ColumnExpr]]) -> None:
        self._branches = branches

    def when(self, condition: Any, value: Any) -> _WhenBuilder:
        return _WhenBuilder(
            [*self._branches, (coerce_column(condition), coerce_column(value))]
        )

    def otherwise(self, value: Any) -> ColumnExpr:
        else_col = coerce_column(value)
        args: list[dict[str, Any]] = []
        functions = else_col.functions | {"dtcs:case_when"}
        profiles = else_col.profiles
        for cond, val in self._branches:
            args.extend([cond.node, val.node])
            functions |= cond.functions | val.functions
            profiles |= cond.profiles | val.profiles
        args.append(else_col.node)
        return ColumnExpr(
            node={"kind": "call", "callee": "dtcs:case_when", "args": args},
            path="case_when",
            functions=functions,
            profiles=profiles,
        )


def when(condition: Any, value: Any) -> _WhenBuilder:
    return _WhenBuilder([(coerce_column(condition), coerce_column(value))])


def coalesce(*values: Any) -> ColumnExpr:
    return _call("dtcs:coalesce", *values)


def if_null(value: Any, fallback: Any) -> ColumnExpr:
    return _call("dtcs:if_null", value, fallback)


def null_if(left: Any, right: Any) -> ColumnExpr:
    return _call("dtcs:null_if", left, right)


def try_cast(value: Any, data_type: str) -> ColumnExpr:
    return _call(
        "dtcs:try_cast",
        value,
        lit(data_type),
        profiles={PROFILE_CONVERSION},
    )


def cast(value: Any, data_type: str) -> ColumnExpr:
    return coerce_column(value).cast(data_type)


def is_null(value: Any) -> ColumnExpr:
    return coerce_column(value).isNull()


def is_missing(value: Any) -> ColumnExpr:
    return coerce_column(value).isMissing()


def is_invalid(value: Any) -> ColumnExpr:
    return coerce_column(value).isInvalid()


# strings (kernel)
def lower(value: Any) -> ColumnExpr:
    return _call("dtcs:lower", value)


def upper(value: Any) -> ColumnExpr:
    return _call("dtcs:upper", value)


def concat(*values: Any) -> ColumnExpr:
    if len(values) < 2:
        raise ModelDefinitionError("concat requires at least two arguments")
    return _call("dtcs:concat", *values)


def concat_ws(sep: Any, *values: Any) -> ColumnExpr:
    return _call("dtcs:concat_ws", sep, *values)


def substring(value: Any, start: Any, length: Any | None = None) -> ColumnExpr:
    if length is None:
        return _call("dtcs:substr", value, start)
    return _call("dtcs:substr", value, start, length)


def replace(value: Any, search: Any, replacement: Any) -> ColumnExpr:
    return _call("dtcs:replace", value, search, replacement)


def length(value: Any) -> ColumnExpr:
    return _call("dtcs:length", value)


def contains(value: Any, other: Any) -> ColumnExpr:
    return coerce_column(value).contains(other)


# string-advanced
def trim(value: Any) -> ColumnExpr:
    return _call("dtcs:trim", value, profiles={PROFILE_STRING_ADVANCED})


def ltrim(value: Any) -> ColumnExpr:
    return _call("dtcs:ltrim", value, profiles={PROFILE_STRING_ADVANCED})


def rtrim(value: Any) -> ColumnExpr:
    return _call("dtcs:rtrim", value, profiles={PROFILE_STRING_ADVANCED})


def normalize_whitespace(value: Any) -> ColumnExpr:
    return _call("dtcs:normalize_whitespace", value, profiles={PROFILE_STRING_ADVANCED})


def split(value: Any, pattern: Any) -> ColumnExpr:
    return _call("dtcs:split", value, pattern, profiles={PROFILE_STRING_ADVANCED})


def regexp_extract(value: Any, pattern: Any, group: Any = 0) -> ColumnExpr:
    return _call(
        "dtcs:regex_extract",
        value,
        pattern,
        group,
        profiles={PROFILE_STRING_ADVANCED},
    )


def regexp_replace(value: Any, pattern: Any, replacement: Any) -> ColumnExpr:
    return _call(
        "dtcs:regex_replace",
        value,
        pattern,
        replacement,
        profiles={PROFILE_STRING_ADVANCED},
    )


# numeric
def abs(value: Any) -> ColumnExpr:
    return _call("dtcs:abs", value)


def round(value: Any, scale: Any = 0) -> ColumnExpr:
    return _call("dtcs:round", value, scale)


def floor(value: Any) -> ColumnExpr:
    return _call("dtcs:floor", value)


def ceil(value: Any) -> ColumnExpr:
    return _call("dtcs:ceil", value)


def pow(value: Any, exp: Any) -> ColumnExpr:
    return _call("dtcs:power", value, exp)


power = pow


def sqrt(value: Any) -> ColumnExpr:
    return _call("dtcs:sqrt", value)


def least(*values: Any) -> ColumnExpr:
    return _call("dtcs:least", *values)


def greatest(*values: Any) -> ColumnExpr:
    return _call("dtcs:greatest", *values)


def to_string(value: Any) -> ColumnExpr:
    return _call("dtcs:to_string", value, profiles={PROFILE_CONVERSION})


def to_integer(value: Any) -> ColumnExpr:
    return _call("dtcs:to_integer", value, profiles={PROFILE_CONVERSION})


def to_decimal(value: Any) -> ColumnExpr:
    return _call("dtcs:to_decimal", value, profiles={PROFILE_CONVERSION})


# aggregates
def _agg(callee: str, *args: Any, profiles: set[str] | None = None) -> ColumnExpr:
    req = {RELATIONAL_PROFILE_V1}
    if profiles:
        req |= profiles
    return _call(callee, *args, profiles=req)


def count_all() -> ColumnExpr:
    return ColumnExpr(
        node={"kind": "call", "callee": "dtcs:count_all", "args": []},
        path="count_all",
        functions=frozenset({"dtcs:count_all"}),
        profiles=frozenset({RELATIONAL_PROFILE_V1}),
    )


def count(value: Any = None) -> ColumnExpr:
    if value is None or value == "*":
        return count_all()
    return _agg("dtcs:count", value)


def count_distinct(value: Any) -> ColumnExpr:
    return _agg("dtcs:count_distinct", value)


def sum(value: Any) -> ColumnExpr:
    return _agg("dtcs:sum", value)


def avg(value: Any) -> ColumnExpr:
    return _agg("dtcs:average", value)


average = avg


def min(value: Any) -> ColumnExpr:
    return _agg("dtcs:min", value)


def max(value: Any) -> ColumnExpr:
    return _agg("dtcs:max", value)


def stddev(value: Any) -> ColumnExpr:
    return _agg("dtcs:stddev", value, profiles={PROFILE_STATISTICS})


def variance(value: Any) -> ColumnExpr:
    return _agg("dtcs:variance", value, profiles={PROFILE_STATISTICS})


def corr(left: Any, right: Any) -> ColumnExpr:
    return _agg("dtcs:corr", left, right, profiles={PROFILE_STATISTICS})


# temporal
def current_date() -> ColumnExpr:
    return _call("dtcs:current_date")


def current_timestamp() -> ColumnExpr:
    return _call("dtcs:current_timestamp")


def date_add(value: Any, amount: Any, unit: str = "day") -> ColumnExpr:
    return _call("dtcs:date_add", value, amount, lit(unit))


def date_sub(value: Any, amount: Any, unit: str = "day") -> ColumnExpr:
    amt = coerce_column(amount)
    neg = ColumnExpr(
        node={"kind": "unary", "op": "negate", "expr": amt.node},
        path=f"-{amt.path}",
        functions=amt.functions,
        profiles=amt.profiles,
    )
    return date_add(value, neg, unit=unit)


def datediff(end: Any, start: Any, unit: str = "day") -> ColumnExpr:
    return _call("dtcs:date_diff", end, start, lit(unit))


def date_trunc(unit: str, value: Any) -> ColumnExpr:
    return _call("dtcs:date_trunc", lit(unit), value)


def year(value: Any) -> ColumnExpr:
    return _call("dtcs:extract", lit("year"), value)


def month(value: Any) -> ColumnExpr:
    return _call("dtcs:extract", lit("month"), value)


def dayofmonth(value: Any) -> ColumnExpr:
    return _call("dtcs:extract", lit("day"), value)


def hour(value: Any) -> ColumnExpr:
    return _call("dtcs:extract", lit("hour"), value)


def at_timezone(value: Any, tz: Any) -> ColumnExpr:
    return _call("dtcs:at_timezone", value, tz)


def at_iana_timezone(value: Any, tz: Any) -> ColumnExpr:
    return _call("dtcs:at_iana_timezone", value, tz, profiles={PROFILE_TEMPORAL_IANA})


# window analytics
def _window_fn(callee: str, *args: Any) -> ColumnExpr:
    return _call(callee, *args, profiles={PROFILE_WINDOW_V1, PROFILE_WINDOW_V2})


def row_number() -> ColumnExpr:
    return _window_fn("dtcs:row_number")


def rank() -> ColumnExpr:
    return _window_fn("dtcs:rank")


def dense_rank() -> ColumnExpr:
    return _window_fn("dtcs:dense_rank")


def lag(value: Any, offset: Any = 1, default: Any | None = None) -> ColumnExpr:
    if default is None:
        return _window_fn("dtcs:lag", value, offset)
    return _window_fn("dtcs:lag", value, offset, default)


def lead(value: Any, offset: Any = 1, default: Any | None = None) -> ColumnExpr:
    if default is None:
        return _window_fn("dtcs:lead", value, offset)
    return _window_fn("dtcs:lead", value, offset, default)


def first_value(value: Any) -> ColumnExpr:
    return _window_fn("dtcs:first_value", value)


def last_value(value: Any) -> ColumnExpr:
    return _window_fn("dtcs:last_value", value)


def ntile(n: Any) -> ColumnExpr:
    return _call("dtcs:ntile", n, profiles={PROFILE_WINDOW_V2})


def percent_rank() -> ColumnExpr:
    return _call("dtcs:percent_rank", profiles={PROFILE_WINDOW_V2})


# complex
def element_at(value: Any, key: Any) -> ColumnExpr:
    return _call(
        "dtcs:element_at",
        value,
        key,
        profiles={PROFILE_COMPLEX_VALUES, PROFILE_COMPLEX_TYPES},
    )


def size(value: Any) -> ColumnExpr:
    return _call("dtcs:size", value, profiles={PROFILE_COMPLEX_VALUES})


def array(*values: Any) -> ColumnExpr:
    return _call("dtcs:array", *values, profiles={PROFILE_COMPLEX_VALUES})


def create_map(*values: Any) -> ColumnExpr:
    return _call("dtcs:map", *values, profiles={PROFILE_COMPLEX_VALUES})


def struct(*values: Any) -> ColumnExpr:
    return _call("dtcs:object", *values, profiles={PROFILE_COMPLEX_VALUES})


# nondeterministic
def rand(seed: Any | None = None) -> ColumnExpr:
    if seed is None:
        return _call("dtcs:rand", profiles={PROFILE_NONDETERMINISTIC})
    return _call("dtcs:rand", seed, profiles={PROFILE_NONDETERMINISTIC})


def uuid() -> ColumnExpr:
    return _call("dtcs:uuid", profiles={PROFILE_NONDETERMINISTIC})


def expr(sql: str) -> ColumnExpr:
    """Permanently excluded raw SQL authoring escape."""
    raise ModelDefinitionError(
        "F.expr(...) raw SQL is excluded from portable definitions (PMXFORM101)"
    )
