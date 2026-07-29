"""Medallantic — engine-agnostic medallion pipelines built on ETLantic."""

from __future__ import annotations

from medallantic.adapt import (
    AdaptationResult,
    AdaptedRow,
    AdapterError,
    adapt_pipeline,
    adapt_profile,
    adapt_validation_policy,
    enrich_plan,
)
from medallantic.authoring import Bronze, Gold, MedallionPipeline, Silver, from_document
from medallantic.builder import MedallionBuilder
from medallantic.compat import (
    COMPATIBILITY_MATRIX,
    assert_delta_capabilities,
    retry_policy_from_sparkforge,
    write_mode_from_sparkforge,
    write_mode_metadata,
)
from medallantic.diagnostics import (
    MDL100_EMPTY,
    MDL101_DUPLICATE_NAME,
    MDL102_CYCLE,
    MDL103_UNKNOWN_SOURCE,
    MDL104_MISSING_SOURCE,
    MDL105_BAD_WRITE_MODE,
    MDL106_UNKNOWN_KIND,
    MDL107_UNKNOWN_LAYER,
    MDL110_RULES_INVALID,
    MDL110_RULES_UNENFORCED,
    MDL111_TRANSFORM_PASSTHROUGH,
    MDL120_ACCEPT_RATE,
)
from medallantic.ir import (
    LayerKind,
    SparkForgePipelineSpec,
    SparkForgeStepSpec,
    StepKind,
)
from medallantic.lower import (
    LoweringError,
    LoweringResult,
    MedallionRow,
    lower_document,
)
from medallantic.explain import explain_medallion_plan
from medallantic.lifecycle_views import (
    enrich_lifecycle_event,
    group_events_by_layer,
    layer_run_summary,
)
from medallantic.profiles import (
    medallion_development_profile,
    medallion_production_profile,
    medallion_test_profile,
)
from medallantic.reports import (
    adapt_run_result,
    enforce_accept_rates,
    evaluate_accept_rates,
    report_to_sparkforge_explain,
)
from medallantic.rules import RuleDSLError, parse_rules_shorthand
from medallantic.runtime_map import (
    bind_debug_session,
    debug_request_from_sparkforge,
    intent_from_sparkforge,
    selection_from_sparkforge,
)
from medallantic.schema import MedallionDocument, MedallionStep

__version__ = "0.34.0"

__all__ = [
    "COMPATIBILITY_MATRIX",
    "MDL100_EMPTY",
    "MDL101_DUPLICATE_NAME",
    "MDL102_CYCLE",
    "MDL103_UNKNOWN_SOURCE",
    "MDL104_MISSING_SOURCE",
    "MDL105_BAD_WRITE_MODE",
    "MDL106_UNKNOWN_KIND",
    "MDL107_UNKNOWN_LAYER",
    "MDL110_RULES_INVALID",
    "MDL110_RULES_UNENFORCED",
    "MDL111_TRANSFORM_PASSTHROUGH",
    "MDL120_ACCEPT_RATE",
    "AdaptationResult",
    "AdaptedRow",
    "AdapterError",
    "Bronze",
    "Gold",
    "LayerKind",
    "LoweringError",
    "LoweringResult",
    "MedallionBuilder",
    "MedallionDocument",
    "MedallionPipeline",
    "MedallionRow",
    "MedallionStep",
    "RuleDSLError",
    "Silver",
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
    "enforce_accept_rates",
    "enrich_lifecycle_event",
    "enrich_plan",
    "evaluate_accept_rates",
    "explain_medallion_plan",
    "from_document",
    "group_events_by_layer",
    "intent_from_sparkforge",
    "layer_run_summary",
    "lower_document",
    "medallion_development_profile",
    "medallion_production_profile",
    "medallion_test_profile",
    "parse_rules_shorthand",
    "report_to_sparkforge_explain",
    "retry_policy_from_sparkforge",
    "selection_from_sparkforge",
    "write_mode_from_sparkforge",
    "write_mode_metadata",
]
