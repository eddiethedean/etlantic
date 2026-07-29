"""0.33 SQL pipeline-builder differential corpus classifications."""

from __future__ import annotations

import pytest

from etlantic.testing import (
    default_sql_builder_fixtures,
    run_sql_builder_differential_suite,
)


@pytest.mark.medallantic
def test_sql_builder_differential_suite_0_33() -> None:
    fixtures = default_sql_builder_fixtures()
    assert fixtures, "expected in-tree sql_pipeline_builder fixtures"
    classifications = {f.classification for f in fixtures}
    assert "equivalent" in classifications
    assert "plugin_dependent" in classifications
    assert "intentionally_rejected" in classifications
    results = run_sql_builder_differential_suite(fixtures)
    assert all(r.ok for r in results)
    assert {r.fixture_id for r in results} == {f.fixture_id for f in fixtures}
