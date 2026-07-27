"""Incremental structural validate / plan preview (no execution)."""

from __future__ import annotations

from typing import Any

from etlantic.authoring.definition import PipelineDefinition
from etlantic.authoring.lifecycle import validate_pipeline_like
from etlantic.diagnostics import ValidationReport
from etlantic.exceptions import PipelineValidationError
from etlantic.plan.model import PipelinePlan
from etlantic.registry import PlanningContext


def structural_validate_preview(
    defn: PipelineDefinition,
    *,
    profile: str | Any | None = "development",
) -> ValidationReport:
    """Validate structure without resolving secrets or executing."""
    return validate_pipeline_like(defn, profile=profile)


def plan_preview(
    defn: PipelineDefinition,
    *,
    profile: str | Any | None = "development",
    context: PlanningContext | None = None,
) -> tuple[PipelinePlan | None, ValidationReport]:
    """Plan preview that never executes and does not resolve secrets.

    Uses the normal planner after structural validation. Plugin imports follow
    profile discovery already performed for planning contexts.
    """
    from etlantic.authoring.lifecycle import plan_pipeline_like

    report = structural_validate_preview(defn, profile=profile)
    if report.has_errors:
        return None, report
    try:
        plan = plan_pipeline_like(defn, context=context, profile=profile)
    except PipelineValidationError as exc:
        return None, exc.report if exc.report is not None else report
    return plan, report
