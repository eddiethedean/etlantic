"""0.32 SparkForge differential corpus classifications."""

from __future__ import annotations

import pytest

from etlantic.testing import (
    default_sparkforge_fixtures,
    run_sparkforge_differential_suite,
)


@pytest.mark.medallantic
def test_sparkforge_differential_suite_0_32() -> None:
    fixtures = default_sparkforge_fixtures()
    assert fixtures, "expected in-tree sparkforge fixtures"
    classifications = {f.classification for f in fixtures}
    assert "equivalent" in classifications
    assert "plugin_dependent" in classifications
    assert "intentionally_rejected" in classifications
    results = run_sparkforge_differential_suite(fixtures)
    assert all(r.ok for r in results)
    assert {r.fixture_id for r in results} == {f.fixture_id for f in fixtures}
