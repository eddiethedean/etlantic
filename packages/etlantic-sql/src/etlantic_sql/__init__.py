"""etlantic-sql — PostgreSQL reference SQL execution plugin."""

from __future__ import annotations

__version__ = "0.13.0"

from etlantic_sql.plugin import PostgresSqlPlugin, create_plugin

__all__ = ["PostgresSqlPlugin", "__version__", "create_plugin"]
