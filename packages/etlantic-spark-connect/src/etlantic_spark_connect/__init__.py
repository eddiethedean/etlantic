"""Experimental Spark Connect provider for ETLantic (fake by default)."""

from __future__ import annotations

__version__ = "0.47.0"

from etlantic_spark_connect.provider import (
    FakeSparkConnectProvider,
    create_provider,
    live_configured,
)

__all__ = [
    "FakeSparkConnectProvider",
    "__version__",
    "create_provider",
    "live_configured",
]
