"""etlantic-pyspark — PySpark reference plugin for ETLantic 0.7."""

from __future__ import annotations

from etlantic_pyspark.plugin import PySparkPlugin, create_plugin
from etlantic_pyspark.provider import LocalSparkProvider, create_provider

__version__ = "0.11.0"

__all__ = [
    "LocalSparkProvider",
    "PySparkPlugin",
    "__version__",
    "create_plugin",
    "create_provider",
]
