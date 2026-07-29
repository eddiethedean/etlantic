"""Catalog / information_schema inspection (metadata only, no row reads)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import MetaData, inspect, text
from sqlalchemy.engine import Engine

from etlantic.diagnostics import Diagnostic, Severity
from etlantic.sql.helpers import require_safe_identifier
from etlantic.sql.protocol import RelationRef
from etlantic_sql.dialect_postgresql import quote_identifier


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


def create_table_from_model(
    engine: Engine,
    model: Any,
    *,
    dialect: str,
    checkfirst: bool = True,
) -> dict[str, Any]:
    """Create a physical table from SQLModel / SQLAlchemy Table metadata.

    Never reads source rows. Returns secret-free catalog metadata.
    """
    table = getattr(model, "__table__", None)
    if table is None:
        raise TypeError(
            "Expected a SQLModel table class or object with __table__ metadata"
        )
    name = str(table.name)
    require_safe_identifier(name)
    metadata = MetaData()
    table.to_metadata(metadata)
    metadata.create_all(
        engine, tables=[metadata.tables[table.key]], checkfirst=checkfirst
    )
    relation = RelationRef(name=name, namespace=getattr(table, "schema", None))
    inspected = inspect_relation(engine, relation, dialect=dialect)
    pk = [c.name for c in table.primary_key.columns]
    return {
        **inspected,
        "created": True,
        "primary_key": pk,
        "source": "model_ddl",
    }


def validate_primary_keys(
    engine: Engine,
    relation: RelationRef,
    *,
    expected_keys: Sequence[str],
    dialect: str,
) -> dict[str, Any]:
    """Validate primary-key columns against catalog metadata; fail closed."""
    expected = [require_safe_identifier(str(k)) for k in expected_keys]
    if not expected:
        raise ValueError("expected_keys must be non-empty for primary-key validation")

    actual: list[str] = []
    diagnostics: list[dict[str, Any]] = []
    inspector = inspect(engine)
    schema = relation.namespace
    table = relation.name
    require_safe_identifier(table)
    try:
        pk = inspector.get_pk_constraint(table, schema=schema)
        actual = [str(c) for c in (pk.get("constrained_columns") or [])]
    except Exception as exc:
        diagnostics.append(
            {
                "code": "PMSQL430",
                "severity": "error",
                "message": f"Unable to inspect primary key for {relation.qualified_name}: {exc}",
            }
        )
        return {
            "ok": False,
            "identity": relation.qualified_name,
            "expected": expected,
            "actual": actual,
            "dialect": dialect,
            "diagnostics": diagnostics,
        }

    if list(actual) != list(expected):
        diagnostics.append(
            {
                "code": "PMSQL431",
                "severity": "error",
                "message": (
                    f"Primary key mismatch for {relation.qualified_name}: "
                    f"expected {expected!r}, catalog has {actual!r}"
                ),
            }
        )
        return {
            "ok": False,
            "identity": relation.qualified_name,
            "expected": expected,
            "actual": actual,
            "dialect": dialect,
            "diagnostics": diagnostics,
        }
    return {
        "ok": True,
        "identity": relation.qualified_name,
        "expected": expected,
        "actual": actual,
        "dialect": dialect,
        "diagnostics": [],
    }


def pk_validation_diagnostics(
    result: MappingLike,
) -> list[Diagnostic]:
    """Convert validate_primary_keys result into Diagnostic objects."""
    out: list[Diagnostic] = []
    for item in result.get("diagnostics") or ():
        out.append(
            Diagnostic(
                code=str(item.get("code") or "PMSQL431"),
                severity=Severity.ERROR,
                message=str(item.get("message") or "primary key validation failed"),
                phase="sql_catalog",
            )
        )
    return out


# Local alias to avoid importing Mapping only for typing in signature above.
from collections.abc import Mapping as MappingLike  # noqa: E402
