"""ETLantic testing helpers."""

from __future__ import annotations

from etlantic.testing.capability_truthfulness import (
    assert_capability_claims_consistent,
    assert_capability_matches_behavior,
)
from etlantic.testing.dataframe import (
    assert_plugin_info,
    assert_roundtrip_records,
    run_conformance_suite,
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
    register_faults,
    reset_fault_counts,
    with_faults,
)
from etlantic.testing.interchange import run_tabular_interchange_conformance_smoke
from etlantic.testing.orchestrator import (
    assert_orchestrator_plugin_info,
    run_orchestrator_conformance_suite,
)
from etlantic.testing.portable_transform_conformance import (
    normalize_rows,
    run_portable_transform_conformance_suite,
)
from etlantic.testing.quality_conformance import run_quality_conformance_suite
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
from etlantic.testing.sql import assert_sql_plugin_info, run_sql_conformance_suite
from etlantic.testing.write_semantics import (
    assert_write_intent_parity,
    run_write_semantics_parity_suite,
)

# Module alias matching documented import path.
from . import portable_transform_conformance as portable_transform_conformance

__all__ = [
    "FaultBoundary",
    "FaultSpec",
    "FaultTrigger",
    "assert_capability_claims_consistent",
    "assert_capability_matches_behavior",
    "assert_facade_public_imports",
    "assert_missing_secret_fails",
    "assert_orchestrator_plugin_info",
    "assert_plugin_info",
    "assert_roundtrip_records",
    "assert_scheduler_plugin_info",
    "assert_secret_provider_info",
    "assert_spark_plugin_info",
    "assert_sql_plugin_info",
    "assert_write_intent_parity",
    "clear_faults",
    "fault_injection_enabled",
    "maybe_inject",
    "normalize_rows",
    "portable_transform_conformance",
    "register_faults",
    "reset_fault_counts",
    "run_conformance_suite",
    "run_facade_conformance_suite",
    "run_orchestrator_conformance_suite",
    "run_portable_transform_conformance_suite",
    "run_quality_conformance_suite",
    "run_scheduler_conformance_suite",
    "run_secret_conformance_suite",
    "run_spark_conformance_suite",
    "run_sql_conformance_suite",
    "run_tabular_interchange_conformance_smoke",
    "run_write_semantics_parity_suite",
    "with_faults",
]
