"""Smoke tests for the etlantic-sparkforge → medallantic redirect shim."""

from __future__ import annotations

import warnings

import pytest


@pytest.mark.medallantic
def test_sparkforge_shim_reexports_medallantic() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        import etlantic_sparkforge as sf

    assert sf.adapt_pipeline is not None
    assert sf.SparkForgePipelineSpec is not None
    deprecated = [
        w
        for w in caught
        if issubclass(w.category, DeprecationWarning)
        and "medallantic" in str(w.message).lower()
    ]
    assert len(deprecated) >= 1


@pytest.mark.medallantic
def test_sparkforge_shim_submodules() -> None:
    import etlantic_sparkforge.adapt as adapt
    import etlantic_sparkforge.compat as compat
    import etlantic_sparkforge.ir as ir
    import etlantic_sparkforge.reports as reports
    import etlantic_sparkforge.runtime_map as runtime_map

    assert adapt.adapt_pipeline is not None
    assert ir.SparkForgePipelineSpec is not None
    assert compat.write_mode_from_sparkforge is not None
    assert reports.adapt_run_result is not None
    assert runtime_map.intent_from_sparkforge is not None
