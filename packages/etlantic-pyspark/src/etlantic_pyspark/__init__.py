"""etlantic-pyspark — PySpark reference plugin for ETLantic."""

from __future__ import annotations

from etlantic_pyspark.compiler import (
    PySparkTransformCompiler,
    create_transform_compiler,
)
from etlantic_pyspark.plugin import PySparkPlugin, create_plugin
from etlantic_pyspark.provider import LocalSparkProvider, create_provider

__version__ = "0.13.0"

__all__ = [
    "LocalSparkProvider",
    "PySparkPlugin",
    "PySparkTransformCompiler",
    "__version__",
    "create_plugin",
    "create_provider",
    "create_transform_compiler",
]
