"""Experimental DataFusion plugin package (stub; not production-ready in 0.20.0)."""

from __future__ import annotations

__version__ = "0.21.0"

STREAMING_STABILITY = "experimental"


def create_plugin():
    """Entry-point factory for ``etlantic.dataframe_plugins`` (experimental stub)."""
    from etlantic_datafusion.plugin import DataFusionPlugin

    return DataFusionPlugin()


def create_transform_compiler():
    """Entry-point factory for ``etlantic.transform_compilers`` (experimental stub)."""
    from etlantic_datafusion.compiler import DataFusionTransformCompiler

    return DataFusionTransformCompiler()


__all__ = [
    "STREAMING_STABILITY",
    "__version__",
    "create_plugin",
    "create_transform_compiler",
]
