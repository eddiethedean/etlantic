"""Production conformance resilience tests for 0.34."""

from __future__ import annotations

from etlantic.profile import production_profile
from etlantic.testing.production_conformance import run_production_conformance_suite


def test_production_profile_requires_allowlist() -> None:
    result = run_production_conformance_suite(production_profile())
    assert not result.passed
    assert any("allowlist" in msg for msg in result.failures)


def test_production_profile_with_allowlist_passes() -> None:
    profile = production_profile(
        plugin_allowlist={"etlantic-polars": "==0.34.0"},
        assets={"in": "json", "out": "json"},
    )
    result = run_production_conformance_suite(profile)
    assert result.passed
