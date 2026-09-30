"""etlantic-sql — PostgreSQL / SQLite Tier A reference SQL execution plugin."""

from __future__ import annotations

from typing import Any

__version__ = "0.55.0"


def __getattr__(name: str) -> Any:
    if name in {
        "FakePostgresConnection",
        "LivePostgresSinkConnector",
        "LivePostgresSourceConnector",
        "LivePostgresStorageConnector",
        "PostgresSinkConnector",
        "PostgresSourceConnector",
        "PostgresStorageConnector",
        "create_sink",
        "create_source",
        "create_storage",
    }:
        from etlantic_sql import connectors as _connectors

        return getattr(_connectors, name)
    if name in {"PostgresSqlPlugin", "create_plugin"}:
        from etlantic_sql.plugin import PostgresSqlPlugin, create_plugin

        return PostgresSqlPlugin if name == "PostgresSqlPlugin" else create_plugin
    if name in {"SqlTransformCompiler", "create_transform_compiler"}:
        from etlantic_sql.transform_compiler import (
            SqlTransformCompiler,
            create_transform_compiler,
        )

        return (
            SqlTransformCompiler
            if name == "SqlTransformCompiler"
            else create_transform_compiler
        )
    if name == "SQLiteTableTarget":
        from etlantic_sql.sqlite_target import SQLiteTableTarget

        return SQLiteTableTarget
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "FakePostgresConnection",
    "LivePostgresSinkConnector",
    "LivePostgresSourceConnector",
    "LivePostgresStorageConnector",
    "PostgresSinkConnector",
    "PostgresSourceConnector",
    "PostgresSqlPlugin",
    "PostgresStorageConnector",
    "SQLiteTableTarget",
    "SqlTransformCompiler",
    "__version__",
    "create_plugin",
    "create_sink",
    "create_source",
    "create_storage",
    "create_transform_compiler",
]
