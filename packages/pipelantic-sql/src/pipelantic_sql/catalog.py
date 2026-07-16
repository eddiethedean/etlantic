"""Catalog / information_schema inspection (metadata only, no row reads)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from pipelantic.sql.helpers import require_safe_identifier
from pipelantic.sql.protocol import RelationRef
from pipelantic_sql.dialect_postgresql import quote_identifier


def inspect_relation(
    engine: Engine,
    relation: RelationRef,
    *,
    dialect: str,
) -> dict[str, Any]:
    schema = relation.namespace
    table = relation.name
    require_safe_identifier(table)
    if dialect == "postgresql":
        sql = text(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = :table
              AND (:schema IS NULL OR table_schema = :schema)
            ORDER BY ordinal_position
            """
        )
        with engine.connect() as conn:
            rows = conn.execute(sql, {"table": table, "schema": schema}).mappings()
            columns = {
                r["column_name"]: {
                    "type": r["data_type"],
                    "nullable": r["is_nullable"] == "YES",
                }
                for r in rows
            }
    else:
        with engine.connect() as conn:
            rows = conn.execute(
                text(f"PRAGMA table_info({quote_identifier(table, dialect=dialect)})")
            )
            columns = {r[1]: {"type": r[2], "nullable": not bool(r[3])} for r in rows}
    return {
        "identity": relation.qualified_name,
        "columns": columns,
        "source": "catalog",
        "dialect": dialect,
    }
