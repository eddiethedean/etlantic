"""ETLantic testing helpers."""

from __future__ import annotations

from etlantic.testing.dataframe import (
    assert_plugin_info,
    assert_roundtrip_records,
    run_conformance_suite,
)
from etlantic.testing.orchestrator import (
    assert_orchestrator_plugin_info,
    run_orchestrator_conformance_suite,
)
from etlantic.testing.portable_transform_conformance import (
    normalize_rows,
    run_portable_transform_conformance_suite,
)
from etlantic.testing.secrets import (
    assert_missing_secret_fails,
    assert_secret_provider_info,
    run_secret_conformance_suite,
)
from etlantic.testing.sql import assert_sql_plugin_info, run_sql_conformance_suite
from etlantic.testing.write_semantics import (
    assert_write_intent_parity,
    run_write_semantics_parity_suite,
)

# Module alias matching documented import path.
from . import portable_transform_conformance as portable_transform_conformance

__all__ = [
    "assert_missing_secret_fails",
    "assert_orchestrator_plugin_info",
    "assert_plugin_info",
    "assert_roundtrip_records",
    "assert_secret_provider_info",
    "assert_sql_plugin_info",
    "assert_write_intent_parity",
    "normalize_rows",
    "portable_transform_conformance",
    "run_conformance_suite",
    "run_orchestrator_conformance_suite",
    "run_portable_transform_conformance_suite",
    "run_secret_conformance_suite",
    "run_sql_conformance_suite",
    "run_write_semantics_parity_suite",
]
