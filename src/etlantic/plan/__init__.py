"""PipelinePlan IR package."""

from etlantic.plan.artifacts import ArtifactRef, ArtifactStrategy
from etlantic.plan.diff import PlanDiff, diff_plans, render_plan_explain_human
from etlantic.plan.explain import explain_plan
from etlantic.plan.freeze import deep_freeze
from etlantic.plan.model import PLAN_SCHEMA, PipelinePlan, validate_plan_interchange
from etlantic.plan.planner import plan_pipeline, plan_pipeline_with_report
from etlantic.plan.serialize import (
    canonical_plan_json,
    plan_fingerprint,
    plan_from_json,
    plan_to_json,
    verify_plan_fingerprint,
)
from etlantic.plan.slicing import (
    dependency_closure,
    run_one_selection,
    run_until_selection,
)

__all__ = [
    "PLAN_SCHEMA",
    "ArtifactRef",
    "ArtifactStrategy",
    "PipelinePlan",
    "PlanDiff",
    "canonical_plan_json",
    "deep_freeze",
    "dependency_closure",
    "diff_plans",
    "explain_plan",
    "plan_fingerprint",
    "plan_from_json",
    "plan_pipeline",
    "plan_pipeline_with_report",
    "plan_to_json",
    "render_plan_explain_human",
    "run_one_selection",
    "run_until_selection",
    "validate_plan_interchange",
    "verify_plan_fingerprint",
]
