"""Complex-value constructors and accessors."""

from __future__ import annotations

from typing import Any

from etlantic.transform import functions as F
from etlantic.transform.column import ColumnExpr


def array(*values: Any) -> ColumnExpr:
    return F.array(*values)


def create_map(*values: Any) -> ColumnExpr:
    return F.create_map(*values)


def struct(*values: Any) -> ColumnExpr:
    return F.struct(*values)


def size(value: Any) -> ColumnExpr:
    return F.size(value)


def element_at(value: Any, key: Any) -> ColumnExpr:
    return F.element_at(value, key)
