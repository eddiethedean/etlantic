"""etlantic-sql — PostgreSQL / SQLite Tier A reference SQL execution plugin."""

from __future__ import annotations

__version__ = "0.37.0"

from etlantic_sql.plugin import PostgresSqlPlugin, create_plugin
from etlantic_sql.transform_compiler import (
    SqlTransformCompiler,
    create_transform_compiler,
)

__all__ = [
    "PostgresSqlPlugin",
    "SqlTransformCompiler",
    "__version__",
    "create_plugin",
    "create_transform_compiler",
]
