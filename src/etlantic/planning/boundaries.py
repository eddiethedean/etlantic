# pyright: reportPrivateUsage=false
"""Materialization and collection boundary stage."""

from etlantic.plan.planner import (
    _collection_boundaries,
    _materialization_boundaries,
)

__all__ = ["_collection_boundaries", "_materialization_boundaries"]
