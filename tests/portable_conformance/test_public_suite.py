"""Public portable transform conformance suite smoke tests."""

from __future__ import annotations

import pytest

from etlantic.testing import (
    portable_transform_conformance,
    run_portable_transform_conformance_suite,
)


@pytest.mark.polars
def test_suite_passes_polars() -> None:
    pytest.importorskip("polars")
    from etlantic_polars import create_transform_compiler

    run_portable_transform_conformance_suite(create_transform_compiler())


@pytest.mark.pandas
def test_suite_passes_pandas() -> None:
    pytest.importorskip("pandas")
    from etlantic_pandas import create_transform_compiler

    run_portable_transform_conformance_suite(create_transform_compiler())


@pytest.mark.spark
def test_suite_passes_pyspark() -> None:
    pytest.importorskip("sparkless")
    from etlantic_pyspark import create_transform_compiler

    run_portable_transform_conformance_suite(create_transform_compiler())


def test_module_export_surface() -> None:
    assert hasattr(
        portable_transform_conformance, "run_portable_transform_conformance_suite"
    )
