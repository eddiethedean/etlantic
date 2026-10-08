"""Release acceptance tests for provider-owned read-only schema inspection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection, Engine, ExecutionContext

from etlantic_sqlmodel import (
    SchemaCompatibility,
    inspect_schema,
    schema_requirements,
)
from etlantic_sqlmodel.migrations import VERSIONS, upgrade

pytestmark = pytest.mark.sqlmodel


def test_requirements_are_provider_owned_and_immutable() -> None:
    requirements = schema_requirements()
    assert requirements.provider == "etlantic-sqlmodel"
    assert requirements.schema == "etlantic_sqlmodel.schema_requirements/2"
    assert requirements.required_version == VERSIONS[-1]
    assert {item.name for item in requirements.objects}
    field = "required_version"
    with pytest.raises((AttributeError, TypeError)):
        setattr(requirements, field, "forged")


def test_public_inspection_classifies_fresh_compatible_and_behind_schemas(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'schema-states.db'}")
    try:
        fresh = inspect_schema(engine)
        assert fresh.compatibility is SchemaCompatibility.FRESH
        assert fresh.reason_code == "schema_not_initialized"

        assert upgrade(engine, target=VERSIONS[0]) == VERSIONS[0]
        behind = inspect_schema(engine)
        assert behind.compatibility is SchemaCompatibility.BEHIND
        assert behind.reason_code == "schema_upgrade_required"

        assert upgrade(engine) == VERSIONS[-1]
        compatible = inspect_schema(engine)
        assert compatible.compatibility is SchemaCompatibility.COMPATIBLE
        assert compatible.compatible
    finally:
        engine.dispose()


def test_current_version_with_missing_required_object_is_corrupt(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'missing-object.db'}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE etlantic_sqlmodel_schema_version "
                    "(id INTEGER PRIMARY KEY CHECK (id = 1), version VARCHAR(64) NOT NULL)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO etlantic_sqlmodel_schema_version (id, version) "
                    "VALUES (1, :version)"
                ),
                {"version": VERSIONS[-1]},
            )
        result = inspect_schema(engine)
        assert result.compatibility is SchemaCompatibility.PARTIAL_OR_CORRUPT
        assert result.reason_code == "required_schema_object_missing"
        assert result.missing_objects
        assert not result.compatible
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("ddl", "reason"),
    [
        (
            "CREATE TABLE cp_definitions (id INTEGER PRIMARY KEY)",
            "version_marker_missing_from_existing_schema",
        ),
        (
            "CREATE TABLE etlantic_sqlmodel_schema_version (id INTEGER PRIMARY KEY, version VARCHAR(64) NOT NULL); "
            "INSERT INTO etlantic_sqlmodel_schema_version (id, version) VALUES (1, '999_future')",
            "version_not_recognized_by_provider",
        ),
        (
            "CREATE TABLE etlantic_sqlmodel_schema_version (id INTEGER PRIMARY KEY, version VARCHAR(64) NOT NULL)",
            "version_marker_row_malformed",
        ),
    ],
)
def test_partial_unknown_and_corrupt_markers_fail_closed(
    tmp_path: Path, ddl: str, reason: str
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'bad-schema.db'}")
    try:
        with engine.begin() as connection:
            for statement in ddl.split(";"):
                connection.execute(text(statement))
        result = inspect_schema(engine)
        assert result.compatibility in {
            SchemaCompatibility.PARTIAL_OR_CORRUPT,
            SchemaCompatibility.UNKNOWN_OR_AHEAD,
        }
        assert result.reason_code == reason
        assert not result.compatible
    finally:
        engine.dispose()


def test_inspection_performs_no_ddl_or_explicit_commit(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'read-only.db'}")
    try:
        upgrade(engine)
        statements: list[str] = []
        commits: list[bool] = []

        def capture_statement(
            _conn: Connection,
            _cursor: Any,
            statement: str,
            _parameters: Any,
            _context: ExecutionContext,
            _many: bool,
        ) -> None:
            statements.append(statement.lstrip().split(None, 1)[0].upper())

        def capture_commit(_conn: Connection) -> None:
            commits.append(True)

        event.listen(engine, "before_cursor_execute", capture_statement)
        event.listen(engine, "commit", capture_commit)
        result = inspect_schema(engine)
        event.remove(engine, "before_cursor_execute", capture_statement)
        event.remove(engine, "commit", capture_commit)

        assert result.compatibility is SchemaCompatibility.COMPATIBLE
        assert statements
        assert all(
            statement not in {"CREATE", "ALTER", "INSERT", "UPDATE", "DELETE"}
            for statement in statements
        )
        assert commits == []
    finally:
        engine.dispose()


def test_unreachable_database_returns_safe_reason_code(tmp_path: Path) -> None:
    engine: Engine = create_engine(f"sqlite:///{tmp_path / 'missing' / 'db.sqlite'}")
    try:
        result = inspect_schema(engine)
        assert result.compatibility is SchemaCompatibility.UNREACHABLE
        assert result.reason_code == "schema_inspection_failed"
        assert str(tmp_path) not in str(result.to_dict())
    finally:
        engine.dispose()
