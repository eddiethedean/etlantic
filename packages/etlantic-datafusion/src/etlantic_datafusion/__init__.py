"""DataFusion plugin package for ETLantic."""

from __future__ import annotations

__version__ = "0.50.1"

STREAMING_STABILITY = "stable"


def create_plugin():
    """Entry-point factory for ``etlantic.dataframe_plugins``."""
    from etlantic_datafusion.plugin import DataFusionPlugin

    return DataFusionPlugin()


def create_transform_compiler():
    """Entry-point factory for ``etlantic.transform_compilers``."""
    from etlantic_datafusion.compiler import DataFusionTransformCompiler

    return DataFusionTransformCompiler()


__all__ = [
    "STREAMING_STABILITY",
    "__version__",
    "create_plugin",
    "create_transform_compiler",
]
