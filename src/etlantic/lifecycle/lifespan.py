# pyright: reportDeprecated=false
"""Lifespan scope helpers for runtime / run / execution-region."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from etlantic.lifecycle.runtime import PipelineRuntime


@asynccontextmanager
async def run_lifespan(runtime: PipelineRuntime, run_id: str) -> AsyncIterator[None]:
    """Scope resources for a single pipeline run."""
    async with runtime.resources.scope("run", run_id):
        yield


@asynccontextmanager
async def region_lifespan(
    runtime: PipelineRuntime, region_id: str
) -> AsyncIterator[None]:
    """Scope resources for an execution region."""
    async with runtime.resources.scope("execution_region", region_id):
        yield
