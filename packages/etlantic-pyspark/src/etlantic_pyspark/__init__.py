"""etlantic-pyspark — PySpark reference plugin for ETLantic."""

from __future__ import annotations

from typing import Any

from etlantic_pyspark.plugin import PySparkPlugin, create_plugin
from etlantic_pyspark.provider import LocalSparkProvider, create_provider

__version__ = "0.21.0"

__all__ = [
    "LocalSparkProvider",
    "PySparkPlugin",
    "PySparkTransformCompiler",
    "__version__",
    "create_plugin",
    "create_provider",
    "create_transform_compiler",
]


def __getattr__(name: str) -> Any:
    """Lazy-load the portable compiler so sparkless_shim imports stay pyspark-free."""
    if name in {"PySparkTransformCompiler", "create_transform_compiler"}:
        from etlantic_pyspark.compiler import (
            PySparkTransformCompiler,
            create_transform_compiler,
        )

        exports = {
            "PySparkTransformCompiler": PySparkTransformCompiler,
            "create_transform_compiler": create_transform_compiler,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
