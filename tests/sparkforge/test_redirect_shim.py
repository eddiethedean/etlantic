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
