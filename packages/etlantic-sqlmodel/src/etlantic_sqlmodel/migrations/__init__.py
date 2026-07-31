"""Lightweight versioned migrations for etlantic-sqlmodel control-plane tables.

Production must apply these migrations (or an equivalent Alembic chain). Do
**not** treat ``SQLModel.metadata.create_all`` / ``create_control_plane_tables``
/ ``create_registry_tables`` as the sole production schema path.
"""

from __future__ import annotations

from collections.abc import Sequence
from importlib import import_module
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

VERSIONS: Sequence[str] = ("001_registry_cp2",)


def _load(version: str) -> Any:
    return import_module(f"etlantic_sqlmodel.migrations.versions.{version}")


def current_version(engine: Engine) -> str | None:
    """Return the applied migration version, or ``None`` on a fresh database."""
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS etlantic_sqlmodel_schema_version ("
                "id INTEGER PRIMARY KEY CHECK (id = 1), "
                "version VARCHAR(64) NOT NULL"
                ")"
            )
        )
        conn.commit()
        row = conn.execute(
            text("SELECT version FROM etlantic_sqlmodel_schema_version WHERE id = 1")
        ).fetchone()
        return None if row is None else str(row[0])


def _set_version(engine: Engine, version: str | None) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS etlantic_sqlmodel_schema_version ("
                "id INTEGER PRIMARY KEY CHECK (id = 1), "
                "version VARCHAR(64) NOT NULL"
                ")"
            )
        )
        if version is None:
            conn.execute(text("DELETE FROM etlantic_sqlmodel_schema_version"))
        else:
            conn.execute(text("DELETE FROM etlantic_sqlmodel_schema_version"))
            conn.execute(
                text(
                    "INSERT INTO etlantic_sqlmodel_schema_version (id, version) "
                    "VALUES (1, :version)"
                ),
                {"version": version},
            )


def upgrade(engine: Engine, *, target: str | None = None) -> str | None:
    """Apply pending migrations up to ``target`` (default: latest)."""
    current = current_version(engine)
    dest = target or VERSIONS[-1]
    if dest not in VERSIONS:
        raise ValueError(f"Unknown migration target: {dest!r}")
    start = 0 if current is None else VERSIONS.index(current) + 1
    end = VERSIONS.index(dest) + 1
    applied = current
    for version in VERSIONS[start:end]:
        module = _load(version)
        module.upgrade(engine)
        _set_version(engine, version)
        applied = version
    return applied


def downgrade(engine: Engine, *, target: str | None = None) -> str | None:
    """Roll back migrations down to ``target`` (``None`` = empty schema)."""
    current = current_version(engine)
    if current is None:
        return None
    if target is not None and target not in VERSIONS and target != "":
        raise ValueError(f"Unknown migration target: {target!r}")
    start = VERSIONS.index(current)
    stop = -1 if target in (None, "") else VERSIONS.index(target)
    for version in reversed(VERSIONS[stop + 1 : start + 1]):
        module = _load(version)
        module.downgrade(engine)
    new_version = None if stop < 0 else VERSIONS[stop]
    _set_version(engine, new_version)
    return new_version


def apply_migrations(engine: Engine) -> str | None:
    """Upgrade to the latest migration (SQLite-friendly for tests)."""
    return upgrade(engine)


__all__ = [
    "VERSIONS",
    "apply_migrations",
    "current_version",
    "downgrade",
    "upgrade",
]
