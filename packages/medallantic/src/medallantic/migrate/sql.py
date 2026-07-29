"""SQL pipeline-builder IR migration namespace (``medallantic.migrate.sql``)."""

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
    write_mode_from_sparkforge,
    write_mode_metadata,
)
from medallantic.ir import (
    LayerKind,
    SparkForgePipelineSpec,
    SparkForgeStepSpec,
    StepKind,
)
from medallantic.migrate.sql_live import (
    LiveBridgeError,
    from_sql_pipeline_builder,
    sql_pipeline_builder_available,
)
from medallantic.reports import adapt_run_result, report_to_sparkforge_explain

__all__ = [
    "COMPATIBILITY_MATRIX",
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
    "enrich_plan",
    "from_sql_pipeline_builder",
    "report_to_sparkforge_explain",
    "spec_to_document",
    "sql_pipeline_builder_available",
    "write_mode_from_sparkforge",
    "write_mode_metadata",
]
