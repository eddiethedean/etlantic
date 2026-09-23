# pyright: reportPrivateUsage=false
"""Staged plan builder facade."""

from __future__ import annotations

from typing import Any

from etlantic.plan.model import PipelinePlan
from etlantic.registry import PlanningContext


class PlanBuilder:
    """Orchestrate plan construction stages behind a single entry point."""

    def build(
        self,
        pipeline_cls: type[Any],
        context: PlanningContext,
        *,
        selection: dict[str, Any] | None = None,
    ) -> PipelinePlan:
        from etlantic.plan.planner import _build_plan

        return _build_plan(
            pipeline_cls, context, selection=selection or context.selection
        )


def build_plan(
    pipeline_cls: type[Any],
    context: PlanningContext,
    *,
    selection: dict[str, Any] | None = None,
) -> PipelinePlan:
    return PlanBuilder().build(pipeline_cls, context, selection=selection)
