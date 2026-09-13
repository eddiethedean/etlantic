"""DuckDB plugin for ETLantic's public SQL and transform protocols."""

from __future__ import annotations

from etlantic_duckdb.frame import DuckDBFrame
from etlantic_duckdb.plugin import DuckDBSqlPlugin, create_plugin
from etlantic_duckdb.transform_compiler import (
    DuckDBTransformCompiler,
    create_transform_compiler,
)

__version__ = "0.52.0"

__all__ = [
    "DuckDBFrame",
    "DuckDBSqlPlugin",
    "DuckDBTransformCompiler",
    "__version__",
    "create_plugin",
    "create_transform_compiler",
]
