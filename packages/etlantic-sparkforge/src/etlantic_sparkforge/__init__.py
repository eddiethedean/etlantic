"""etlantic-sparkforge — SparkForge → ETLantic migration adapter."""

from __future__ import annotations

from etlantic_sparkforge.adapt import (
    AdaptationResult,
    AdaptedRow,
    AdapterError,
    adapt_pipeline,
    adapt_profile,
    adapt_validation_policy,
    enrich_plan,
)
from etlantic_sparkforge.compat import (
    COMPATIBILITY_MATRIX,
    assert_delta_capabilities,
    retry_policy_from_sparkforge,
    write_mode_from_sparkforge,
    write_mode_metadata,
)
from etlantic_sparkforge.ir import (
    LayerKind,
    SparkForgePipelineSpec,
    SparkForgeStepSpec,
    StepKind,
)
from etlantic_sparkforge.reports import adapt_run_result, report_to_sparkforge_explain
from etlantic_sparkforge.runtime_map import (
    bind_debug_session,
    debug_request_from_sparkforge,
    intent_from_sparkforge,
    selection_from_sparkforge,
)

__version__ = "0.14.0"

__all__ = [
    "COMPATIBILITY_MATRIX",
    "AdaptationResult",
    "AdaptedRow",
    "AdapterError",
    "LayerKind",
    "SparkForgePipelineSpec",
    "SparkForgeStepSpec",
    "StepKind",
    "__version__",
    "adapt_pipeline",
    "adapt_profile",
    "adapt_run_result",
    "adapt_validation_policy",
    "assert_delta_capabilities",
    "bind_debug_session",
    "debug_request_from_sparkforge",
    "enrich_plan",
    "intent_from_sparkforge",
    "report_to_sparkforge_explain",
    "retry_policy_from_sparkforge",
    "selection_from_sparkforge",
    "write_mode_from_sparkforge",
    "write_mode_metadata",
]
