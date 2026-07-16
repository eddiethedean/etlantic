"""Authoring helpers for portable SQL IR."""

from __future__ import annotations

from typing import Any

from pipelantic.sql.protocol import (
    AliasedExpr,
    ColumnRef,
    ConcatExpr,
    LiteralExpr,
    RelationRef,
    SqlParameter,
    SqlQuery,
    TrustedSqlFragment,
)


def col(name: str, relation: str | None = None) -> ColumnRef:
    """Column reference."""
    return ColumnRef(column=name, relation=relation)


def lit(value: Any, *, sql_type: str | None = None) -> LiteralExpr:
    """Literal that will be bound as a parameter."""
    return LiteralExpr(value=value, sql_type=sql_type)


def alias(expr: Any, name: str) -> AliasedExpr:
    """Alias a projection expression."""
    return AliasedExpr(expr=expr, alias=name)


def concat(*parts: Any, separator: str = " ", as_: str | None = None) -> ConcatExpr:
    """Concatenate string parts (columns or literals)."""
    return ConcatExpr(parts=tuple(parts), separator=separator, alias=as_)


def select(
    *columns: Any,
    source: RelationRef | str,
    where: Any | None = None,
    limit: int | None = None,
    distinct: bool = False,
    parameters: tuple[SqlParameter, ...] = (),
) -> SqlQuery:
    """Build a portable select query."""
    rel = source if isinstance(source, RelationRef) else RelationRef.parse(source)
    return SqlQuery(
        source=rel,
        columns=tuple(columns),
        where=where,
        limit=limit,
        distinct=distinct,
        parameters=parameters,
    )


def trusted_sql(
    text: str,
    *,
    param_names: tuple[str, ...] = (),
    allowed: bool = False,
) -> TrustedSqlFragment:
    """Trusted SQL fragment; ``allowed`` must be True under profile policy."""
    return TrustedSqlFragment(text=text, param_names=param_names, allowed=allowed)
