# pyright: reportAttributeAccessIssue=false, reportMissingTypeStubs=false, reportUnknownArgumentType=false, reportUnknownVariableType=false
"""Conformance kit smoke tests for installed dataframe plugins."""

from __future__ import annotations

import pytest

from etlantic.testing import run_conformance_suite


@pytest.mark.polars
def test_polars_conformance() -> None:
    pytest.importorskip("polars")
    from etlantic_polars import create_plugin

    run_conformance_suite(
        create_plugin(),
        engine="polars",
        sample_rows=[{"customer_id": 1, "full_name": "Ada"}],
    )


@pytest.mark.pandas
def test_pandas_conformance() -> None:
    pytest.importorskip("pandas")
    from etlantic_pandas import create_plugin

    run_conformance_suite(
        create_plugin(),
        engine="pandas",
        sample_rows=[{"customer_id": 1, "full_name": "Ada"}],
    )
