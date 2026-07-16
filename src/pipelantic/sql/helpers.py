"""Secret-free helpers and identifier policy utilities for SQL."""

from __future__ import annotations

import re
from typing import Any

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def is_safe_identifier(name: str) -> bool:
    """Return True when ``name`` is a simple unquoted-safe identifier."""
    return bool(_IDENT.match(name))


def require_safe_identifier(name: str) -> str:
    """Validate identifier; raise ValueError when unsafe."""
    if not is_safe_identifier(name):
        raise ValueError(f"Illegal SQL identifier: {name!r}")
    return name


def redact_params(names: tuple[str, ...] | list[str]) -> dict[str, str]:
    """Build redacted parameter metadata for plans/logs."""
    return {name: "<redacted>" for name in names}


def sqlmodel_table_to_relation(table: Any) -> tuple[Any, dict[str, Any]]:
    """Optional SQLModel table → RelationRef + schema metadata.

    Imports SQLModel only when called. Core never depends on SQLModel.
    """
    try:
        from pipelantic.sql.protocol import RelationRef
    except Exception:  # pragma: no cover
        raise

    table_args = getattr(table, "__tablename__", None)
    if not table_args:
        raise TypeError("Object is not a SQLModel/SQLAlchemy table class")
    schema = getattr(getattr(table, "__table__", None), "schema", None)
    relation = RelationRef(name=str(table_args), namespace=schema)
    columns: dict[str, Any] = {}
    table_obj = getattr(table, "__table__", None)
    if table_obj is not None:
        for col in table_obj.columns:
            columns[str(col.name)] = {
                "type": str(col.type),
                "nullable": bool(col.nullable),
            }
    return relation, {"columns": columns, "source": "sqlmodel"}
