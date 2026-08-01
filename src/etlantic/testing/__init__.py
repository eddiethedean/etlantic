"""ETLantic testing helpers."""

from __future__ import annotations

from etlantic.testing.capability_truthfulness import (
    assert_capability_claims_consistent,
    assert_capability_matches_behavior,
)
from etlantic.testing.connectors import (
    SECRET_SENTINEL,
    run_sink_connector_conformance_suite,
    run_source_connector_conformance_suite,
    run_storage_connector_conformance_suite,
)
from etlantic.testing.dataframe import (
    assert_plugin_info,
    assert_roundtrip_records,
    run_conformance_suite,
)
from etlantic.testing.durable_work_conformance import (
    run_durable_work_conformance_suite,
)
from etlantic.testing.event_consumer_conformance import (
    run_event_consumer_conformance_suite,
)
from etlantic.testing.facade import (
    assert_facade_public_imports,
    run_facade_conformance_suite,
)
from etlantic.testing.faults import (
    FaultBoundary,
    FaultSpec,
    FaultTrigger,
    clear_faults,
    fault_injection_enabled,
    maybe_inject,
    maybe_inject_async,
    register_faults,
    reset_fault_counts,
    with_faults,
)
from etlantic.testing.interchange import run_tabular_interchange_conformance_smoke
from etlantic.testing.lifecycle_conformance import run_lifecycle_conformance_suite
from etlantic.testing.observability_conformance import (
    run_observability_conformance_suite,
)
from etlantic.testing.orchestrator import (
    assert_orchestrator_plugin_info,
    run_orchestrator_conformance_suite,
)
from etlantic.testing.pipeline_case import (
    MAX_SEED_ROWS_PER_ASSET,
    MAX_SNAPSHOT_BYTES,
    ExpectedResult,
    FakeClock,
    FakeRunIdentity,
    FakeSecretProvider,
    PipelineCaseResult,
    PipelineTestCase,
    assert_case_succeeded,
    assert_snapshots_match,
    emit_case_result_json,
    inject_faults,
    run_pipeline_case,
    snapshot_plan,
    snapshot_report,
)
from etlantic.testing.portable_transform_conformance import (
    normalize_rows,
    run_portable_transform_conformance_suite,
)
from etlantic.testing.production_conformance import run_production_conformance_suite
from etlantic.testing.quality_conformance import run_quality_conformance_suite
from etlantic.testing.run_history_conformance import run_run_history_conformance_suite
from etlantic.testing.scheduler import (
    assert_scheduler_plugin_info,
    run_scheduler_conformance_suite,
)
from etlantic.testing.secrets import (
    assert_missing_secret_fails,
    assert_secret_provider_info,
    run_secret_conformance_suite,
)
from etlantic.testing.spark import (
    assert_spark_plugin_info,
    run_spark_conformance_suite,
)
from etlantic.testing.sparkforge_differential import (
    SparkForgeDifferentialFixture,
    SparkForgeDifferentialResult,
    default_sparkforge_fixtures,
    run_sparkforge_differential_suite,
)
from etlantic.testing.sql import assert_sql_plugin_info, run_sql_conformance_suite
from etlantic.testing.sql_builder_differential import (
    SqlBuilderDifferentialFixture,
    SqlBuilderDifferentialResult,
    default_sql_builder_fixtures,
    run_sql_builder_differential_suite,
)
from etlantic.testing.write_semantics import (
    assert_write_intent_parity,
    run_write_semantics_parity_suite,
)

# Module alias matching documented import path.
from . import portable_transform_conformance as portable_transform_conformance

__all__ = [
    "MAX_SEED_ROWS_PER_ASSET",
    "MAX_SNAPSHOT_BYTES",
    "SECRET_SENTINEL",
    "ExpectedResult",
    "FakeClock",
    "FakeRunIdentity",
    "FakeSecretProvider",
    "FaultBoundary",
    "FaultSpec",
    "FaultTrigger",
    "PipelineCaseResult",
    "PipelineTestCase",
    "SparkForgeDifferentialFixture",
    "SparkForgeDifferentialResult",
    "SqlBuilderDifferentialFixture",
    "SqlBuilderDifferentialResult",
    "assert_capability_claims_consistent",
    "assert_capability_matches_behavior",
    "assert_case_succeeded",
    "assert_facade_public_imports",
    "assert_missing_secret_fails",
    "assert_orchestrator_plugin_info",
    "assert_plugin_info",
    "assert_roundtrip_records",
    "assert_scheduler_plugin_info",
    "assert_secret_provider_info",
    "assert_snapshots_match",
    "assert_spark_plugin_info",
    "assert_sql_plugin_info",
    "assert_write_intent_parity",
    "clear_faults",
    "default_sparkforge_fixtures",
    "default_sql_builder_fixtures",
    "emit_case_result_json",
    "fault_injection_enabled",
    "inject_faults",
    "maybe_inject",
    "maybe_inject_async",
    "normalize_rows",
    "portable_transform_conformance",
    "register_faults",
    "reset_fault_counts",
    "run_conformance_suite",
    "run_durable_work_conformance_suite",
    "run_event_consumer_conformance_suite",
    "run_facade_conformance_suite",
    "run_lifecycle_conformance_suite",
    "run_observability_conformance_suite",
    "run_orchestrator_conformance_suite",
    "run_pipeline_case",
    "run_portable_transform_conformance_suite",
    "run_production_conformance_suite",
    "run_quality_conformance_suite",
    "run_run_history_conformance_suite",
    "run_scheduler_conformance_suite",
    "run_secret_conformance_suite",
    "run_sink_connector_conformance_suite",
    "run_source_connector_conformance_suite",
    "run_spark_conformance_suite",
    "run_sparkforge_differential_suite",
    "run_sql_builder_differential_suite",
    "run_sql_conformance_suite",
    "run_storage_connector_conformance_suite",
    "run_tabular_interchange_conformance_smoke",
    "run_write_semantics_parity_suite",
    "snapshot_plan",
    "snapshot_report",
    "with_faults",
]
