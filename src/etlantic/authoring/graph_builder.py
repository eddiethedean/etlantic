# pyright: reportPrivateUsage=false
"""Pipeline graph construction (internal refactor surface)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from etlantic.model import LogicalGraph
    from etlantic.pipeline import Pipeline


def build_logical_graph(cls: type[Pipeline]) -> LogicalGraph:
    """Build the logical graph for a pipeline class."""
    from etlantic.pipeline import _build_logical_graph

    return _build_logical_graph(cls)
