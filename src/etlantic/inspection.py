"""Pipeline inspection helpers."""

from __future__ import annotations

from typing import Any

from etlantic.model import LogicalGraph


def inspect_pipeline(pipeline_cls: type[Any] | Any) -> LogicalGraph:
    """Return the immutable logical graph for a pipeline class or definition.

    Repeated calls on classes return an equivalent graph (cached on the class).
    """
    from etlantic.authoring.lifecycle import inspect_pipeline_like

    return inspect_pipeline_like(pipeline_cls)
