"""SparkForge IR migration namespace (``medallantic.migrate.sparkforge``)."""

from __future__ import annotations

from medallantic.adapt import (
    AdaptationResult,
    AdaptedRow,
    AdapterError,
    adapt_pipeline,
    adapt_profile,
    adapt_validation_policy,
    enrich_plan,
    spec_to_document,
)
from medallantic.compat import (
    COMPATIBILITY_MATRIX,
    DELTA_CAPABILITY_MAP,
    assert_delta_capabilities,
    retry_policy_from_sparkforge,
    write_mode_from_sparkforge,
    write_mode_metadata,
)
from medallantic.ir import (
    LayerKind,
    SparkForgePipelineSpec,
    SparkForgeStepSpec,
    StepKind,
)
from medallantic.migrate.sparkforge_live import (
    LiveBridgeError,
    from_pipeline_builder,
    sparkforge_available,
)
from medallantic.reports import adapt_run_result, report_to_sparkforge_explain
from medallantic.runtime_map import (
    bind_debug_session,
    debug_request_from_sparkforge,
    intent_from_sparkforge,
    invalidation_from_sparkforge,
    selection_from_sparkforge,
)

__all__ = [
    "COMPATIBILITY_MATRIX",
    "DELTA_CAPABILITY_MAP",
    "AdaptationResult",
    "AdaptedRow",
    "AdapterError",
    "LayerKind",
    "LiveBridgeError",
    "SparkForgePipelineSpec",
    "SparkForgeStepSpec",
    "StepKind",
    "adapt_pipeline",
    "adapt_profile",
    "adapt_run_result",
    "adapt_validation_policy",
    "assert_delta_capabilities",
    "bind_debug_session",
    "debug_request_from_sparkforge",
    "enrich_plan",
    "from_pipeline_builder",
    "intent_from_sparkforge",
    "invalidation_from_sparkforge",
    "report_to_sparkforge_explain",
    "retry_policy_from_sparkforge",
    "selection_from_sparkforge",
    "sparkforge_available",
    "spec_to_document",
    "write_mode_from_sparkforge",
    "write_mode_metadata",
]
