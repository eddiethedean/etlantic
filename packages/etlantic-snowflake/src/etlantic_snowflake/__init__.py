"""Experimental Snowflake connector package for ETLantic."""

from __future__ import annotations

__version__ = "0.47.0"

from etlantic_snowflake.connectors import (
    SnowflakeSinkConnector,
    SnowflakeSourceConnector,
    SnowflakeStorageConnector,
    create_sink,
    create_source,
    create_storage,
)
from etlantic_snowflake.fake import FakeSnowflakeConnection, snowflake_sdk_available

__all__ = [
    "FakeSnowflakeConnection",
    "SnowflakeSinkConnector",
    "SnowflakeSourceConnector",
    "SnowflakeStorageConnector",
    "__version__",
    "create_sink",
    "create_source",
    "create_storage",
    "snowflake_sdk_available",
]
