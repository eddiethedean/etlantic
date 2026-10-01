"""etlantic-sql — PostgreSQL / SQLite Tier A reference SQL execution plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .action_handlers import create_action_handlers as create_action_handlers
    from .connectors import (
        FakePostgresConnection as FakePostgresConnection,
    )
    from .connectors import (
        LivePostgresSinkConnector as LivePostgresSinkConnector,
    )
    from .connectors import (
        LivePostgresSourceConnector as LivePostgresSourceConnector,
    )
    from .connectors import (
        LivePostgresStorageConnector as LivePostgresStorageConnector,
    )
    from .connectors import PostgresSinkConnector as PostgresSinkConnector
    from .connectors import PostgresSourceConnector as PostgresSourceConnector
    from .connectors import PostgresStorageConnector as PostgresStorageConnector
    from .connectors import create_sink as create_sink
    from .connectors import create_source as create_source
    from .connectors import create_storage as create_storage
    from .plugin import PostgresSqlPlugin as PostgresSqlPlugin
    from .plugin import create_plugin as create_plugin
    from .sqlite_target import SQLiteTableTarget as SQLiteTableTarget
    from .transform_compiler import (
        SqlTransformCompiler as SqlTransformCompiler,
    )
    from .transform_compiler import (
        create_transform_compiler as create_transform_compiler,
    )

__version__ = "0.55.0"


def __getattr__(name: str) -> Any:
    if name == "create_action_handlers":
        from etlantic_sql.action_handlers import create_action_handlers

        return create_action_handlers
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
    "create_action_handlers",
    "create_plugin",
    "create_sink",
    "create_source",
    "create_storage",
    "create_transform_compiler",
]
