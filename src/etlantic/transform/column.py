"""Immutable symbolic column expressions for portable authoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from etlantic.exceptions import ModelDefinitionError
from etlantic.transform.protocol import (
    PROFILE_COMPLEX_TYPES,
    PROFILE_COMPLEX_VALUES,
    PROFILE_CONVERSION,
)


def _reject_bool(op: str) -> None:
    msg = (
        f"Python boolean {op!r} is not supported on ColumnExpr; "
        "use & | ~ for portable boolean expressions"
    )
    raise ModelDefinitionError(msg)


@dataclass(frozen=True, slots=True)
class ColumnExpr:
    """Symbolic column or scalar expression that lowers to a DTCS structured node."""

    node: dict[str, Any]
    path: str = ""
    functions: frozenset[str] = field(default_factory=frozenset)
    profiles: frozenset[str] = field(default_factory=frozenset)
    alias_name: str | None = None
    sort_direction: str | None = None  # asc | desc
    nulls: str | None = None  # first | last
    window: Any | None = None

    def _binary(
        self, op: str, other: Any, *, function: str | None = None
    ) -> ColumnExpr:
        right = coerce_column(other)
        functions = self.functions | right.functions
        profiles = self.profiles | right.profiles
        if function:
            functions = functions | {function}
        return ColumnExpr(
            node={"kind": "binary", "op": op, "left": self.node, "right": right.node},
            path=f"({self.path} {op} {right.path})" if self.path else op,
            functions=functions,
            profiles=profiles,
        )

    def _unary(self, op: str) -> ColumnExpr:
        return ColumnExpr(
            node={"kind": "unary", "op": op, "expr": self.node},
            path=f"{op}({self.path})",
            functions=self.functions,
            profiles=self.profiles,
        )

    def _call(
        self, callee: str, *args: Any, profiles: frozenset[str] | None = None
    ) -> ColumnExpr:
        cols = [coerce_column(a) for a in args]
        functions = self.functions | frozenset({callee})
        for col in cols:
            functions |= col.functions
        req_profiles = self.profiles
        for col in cols:
            req_profiles |= col.profiles
        if profiles:
            req_profiles |= profiles
        return ColumnExpr(
            node={
                "kind": "call",
                "callee": callee,
                "args": [self.node, *[c.node for c in cols]],
            },
            path=f"{callee}({self.path})",
            functions=functions,
            profiles=req_profiles,
        )

    # comparisons
    def __eq__(self, other: object) -> ColumnExpr:  # type: ignore[override]
        return self._binary("eq", other)

    def __ne__(self, other: object) -> ColumnExpr:  # type: ignore[override]
        return self._binary("not_eq", other)

    def __lt__(self, other: object) -> ColumnExpr:
        return self._binary("lt", other)

    def __le__(self, other: object) -> ColumnExpr:
        return self._binary("lte", other)

    def __gt__(self, other: object) -> ColumnExpr:
        return self._binary("gt", other)

    def __ge__(self, other: object) -> ColumnExpr:
        return self._binary("gte", other)

    def eqNullSafe(self, other: Any) -> ColumnExpr:
        """Null-safe equality (`dtcs:null_safe_eq`)."""
        return self._binary("null_safe_eq", other)

    # arithmetic
    def __add__(self, other: Any) -> ColumnExpr:
        return self._binary("add", other)

    def __radd__(self, other: Any) -> ColumnExpr:
        return coerce_column(other)._binary("add", self)

    def __sub__(self, other: Any) -> ColumnExpr:
        return self._binary("subtract", other)

    def __rsub__(self, other: Any) -> ColumnExpr:
        return coerce_column(other)._binary("subtract", self)

    def __mul__(self, other: Any) -> ColumnExpr:
        return self._binary("multiply", other)

    def __rmul__(self, other: Any) -> ColumnExpr:
        return coerce_column(other)._binary("multiply", self)

    def __truediv__(self, other: Any) -> ColumnExpr:
        return self._binary("divide", other)

    def __rtruediv__(self, other: Any) -> ColumnExpr:
        return coerce_column(other)._binary("divide", self)

    def __mod__(self, other: Any) -> ColumnExpr:
        return self._binary("modulo", other)

    def __rmod__(self, other: Any) -> ColumnExpr:
        return coerce_column(other)._binary("modulo", self)

    def __neg__(self) -> ColumnExpr:
        return self._unary("negate")

    # boolean
    def __and__(self, other: Any) -> ColumnExpr:
        return self._binary("and", other)

    def __rand__(self, other: Any) -> ColumnExpr:
        return coerce_column(other)._binary("and", self)

    def __or__(self, other: Any) -> ColumnExpr:
        return self._binary("or", other)

    def __ror__(self, other: Any) -> ColumnExpr:
        return coerce_column(other)._binary("or", self)

    def __invert__(self) -> ColumnExpr:
        return self._unary("not")

    def __bool__(self) -> bool:
        _reject_bool("__bool__")
        return False

    def alias(self, name: str) -> ColumnExpr:
        """Attach an output field name for projection / with_fields."""
        return ColumnExpr(
            node=self.node,
            path=self.path,
            functions=self.functions,
            profiles=self.profiles,
            alias_name=name,
            sort_direction=self.sort_direction,
            nulls=self.nulls,
            window=self.window,
        )

    def cast(self, data_type: str) -> ColumnExpr:
        """Strict conversion requiring the conversion profile when not try_cast."""
        return ColumnExpr(
            node={
                "kind": "call",
                "callee": "dtcs:cast",
                "args": [
                    self.node,
                    {
                        "kind": "literal",
                        "value": {"type": "string", "value": data_type},
                    },
                ],
            },
            path=f"cast({self.path})",
            functions=self.functions | {"dtcs:cast"},
            profiles=self.profiles | {PROFILE_CONVERSION},
        )

    def isNull(self) -> ColumnExpr:
        return ColumnExpr(
            node={"kind": "call", "callee": "dtcs:is_null", "args": [self.node]},
            path=f"is_null({self.path})",
            functions=self.functions | {"dtcs:is_null"},
            profiles=self.profiles,
        )

    def isNotNull(self) -> ColumnExpr:
        return ~self.isNull()

    def isMissing(self) -> ColumnExpr:
        return ColumnExpr(
            node={"kind": "call", "callee": "dtcs:is_missing", "args": [self.node]},
            path=f"is_missing({self.path})",
            functions=self.functions | {"dtcs:is_missing"},
            profiles=self.profiles,
        )

    def isInvalid(self) -> ColumnExpr:
        return ColumnExpr(
            node={"kind": "call", "callee": "dtcs:is_invalid", "args": [self.node]},
            path=f"is_invalid({self.path})",
            functions=self.functions | {"dtcs:is_invalid"},
            profiles=self.profiles,
        )

    def isin(self, *values: Any) -> ColumnExpr:
        args = [coerce_column(v).node for v in values]
        return ColumnExpr(
            node={"kind": "call", "callee": "dtcs:in", "args": [self.node, *args]},
            path=f"in({self.path})",
            functions=self.functions | {"dtcs:in"},
            profiles=self.profiles,
        )

    def between(self, lower: Any, upper: Any) -> ColumnExpr:
        left = coerce_column(lower)
        right = coerce_column(upper)
        return ColumnExpr(
            node={
                "kind": "call",
                "callee": "dtcs:between",
                "args": [self.node, left.node, right.node],
            },
            path=f"between({self.path})",
            functions=self.functions
            | left.functions
            | right.functions
            | {"dtcs:between"},
            profiles=self.profiles | left.profiles | right.profiles,
        )

    def asc(self) -> ColumnExpr:
        return ColumnExpr(
            node=self.node,
            path=self.path,
            functions=self.functions,
            profiles=self.profiles,
            alias_name=self.alias_name,
            sort_direction="asc",
            nulls=self.nulls,
        )

    def desc(self) -> ColumnExpr:
        return ColumnExpr(
            node=self.node,
            path=self.path,
            functions=self.functions,
            profiles=self.profiles,
            alias_name=self.alias_name,
            sort_direction="desc",
            nulls=self.nulls,
        )

    def asc_nulls_first(self) -> ColumnExpr:
        return ColumnExpr(
            node=self.node,
            path=self.path,
            functions=self.functions,
            profiles=self.profiles,
            alias_name=self.alias_name,
            sort_direction="asc",
            nulls="first",
        )

    def desc_nulls_last(self) -> ColumnExpr:
        return ColumnExpr(
            node=self.node,
            path=self.path,
            functions=self.functions,
            profiles=self.profiles,
            alias_name=self.alias_name,
            sort_direction="desc",
            nulls="last",
        )

    def getField(self, name: str) -> ColumnExpr:
        return ColumnExpr(
            node={
                "kind": "call",
                "callee": "dtcs:field",
                "args": [
                    self.node,
                    {"kind": "literal", "value": {"type": "string", "value": name}},
                ],
            },
            path=f"field({self.path},{name})",
            functions=self.functions | {"dtcs:field"},
            profiles=self.profiles | {PROFILE_COMPLEX_VALUES, PROFILE_COMPLEX_TYPES},
        )

    def __getitem__(self, key: Any) -> ColumnExpr:
        k = coerce_column(key)
        return ColumnExpr(
            node={"kind": "call", "callee": "dtcs:index", "args": [self.node, k.node]},
            path=f"index({self.path})",
            functions=self.functions | k.functions | {"dtcs:index"},
            profiles=self.profiles
            | k.profiles
            | {PROFILE_COMPLEX_VALUES, PROFILE_COMPLEX_TYPES},
        )

    def over(self, window: Any) -> ColumnExpr:
        """Attach a window specification for analytic functions."""
        return ColumnExpr(
            node=self.node,
            path=self.path,
            functions=self.functions,
            profiles=self.profiles | getattr(window, "profiles", frozenset()),
            alias_name=self.alias_name,
            sort_direction=self.sort_direction,
            nulls=self.nulls,
            window=window,
        )

    def contains(self, other: Any) -> ColumnExpr:
        return self._call("dtcs:contains", other)

    def startswith(self, other: Any) -> ColumnExpr:
        return self._call("dtcs:starts_with", other)

    def endswith(self, other: Any) -> ColumnExpr:
        return self._call("dtcs:ends_with", other)


def literal_node(value: Any) -> dict[str, Any]:
    """Build a DTCS literal node from a Python scalar or sentinel."""
    from etlantic.transform.protocol import MISSING, Invalid, Missing

    if value is None:
        return {"kind": "literal", "value": {"type": "null", "value": None}}
    if isinstance(value, Missing) or value is MISSING:
        return {"kind": "literal", "value": {"type": "missing", "value": None}}
    if isinstance(value, Invalid):
        node: dict[str, Any] = {
            "kind": "literal",
            "value": {"type": "invalid", "value": None},
        }
        if value.reason is not None:
            node["value"]["reason"] = value.reason
        return node
    if isinstance(value, bool):
        return {"kind": "literal", "value": {"type": "boolean", "value": value}}
    if isinstance(value, int) and not isinstance(value, bool):
        return {"kind": "literal", "value": {"type": "integer", "value": value}}
    if isinstance(value, float):
        return {"kind": "literal", "value": {"type": "decimal", "value": str(value)}}
    if isinstance(value, str):
        return {"kind": "literal", "value": {"type": "string", "value": value}}
    msg = f"Unsupported portable literal type: {type(value)!r}"
    raise ModelDefinitionError(msg)


def coerce_column(value: Any) -> ColumnExpr:
    """Coerce a Python value or ColumnExpr into a ColumnExpr."""
    if isinstance(value, ColumnExpr):
        return value
    if isinstance(value, ParameterRef):
        return ColumnExpr(
            node={"kind": "fieldRef", "target": value.name, "scope": "parameter"},
            path=f"param:{value.name}",
        )
    return ColumnExpr(node=literal_node(value), path=repr(value))


@dataclass(frozen=True, slots=True)
class ParameterRef:
    """Symbolic reference to a transformation Parameter port."""

    name: str


def with_column_assignment(name: str, col: ColumnExpr) -> dict[str, Any]:
    """Build a with_fields assignment, including window metadata when present."""
    assignment: dict[str, Any] = {"name": name, "expression": col.node}
    if col.window is not None:
        window = col.window
        if hasattr(window, "to_dict"):
            assignment["window"] = window.to_dict()
        else:
            assignment["window"] = window
    return assignment
