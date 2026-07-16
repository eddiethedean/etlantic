"""Conformance kit smoke tests for installed dataframe plugins."""

from __future__ import annotations

import pytest

from pipelantic.testing import run_conformance_suite

pytest.importorskip("polars")
pytest.importorskip("pandas")


@pytest.mark.polars
def test_polars_conformance() -> None:
    from pipelantic_polars import create_plugin

    run_conformance_suite(
        create_plugin(),
        engine="polars",
        sample_rows=[{"customer_id": 1, "full_name": "Ada"}],
    )


@pytest.mark.pandas
def test_pandas_conformance() -> None:
    from pipelantic_pandas import create_plugin

    run_conformance_suite(
        create_plugin(),
        engine="pandas",
        sample_rows=[{"customer_id": 1, "full_name": "Ada"}],
    )
