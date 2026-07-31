"""WP7: curated ``import etlantic as etl`` facade identity + import budget."""

from __future__ import annotations

import subprocess
import sys

import pytest

import etlantic
import etlantic as etl


def test_curated_symbols_present() -> None:
    for name in (
        "Data",
        "Transformation",
        "Pipeline",
        "Extract",
        "Load",
        "Input",
        "Output",
        "Parameter",
        "Profile",
        "PipelineRuntime",
        "PipelinePlan",
        "plan_pipeline",
        "explain_plan",
        "ValidationReport",
        "PipelineRunReport",
        "SecretRef",
        "compile_plan",
        "__version__",
    ):
        assert name in etl.__all__
        assert getattr(etl, name) is not None


def test_lazy_namespaces_identity() -> None:
    assert "sql" not in etl.__all__  # namespaces are lazy attributes
    assert etl.sql is etlantic.sql
    assert etl.dataframe is etlantic.dataframe
    assert etl.spark is etlantic.spark
    assert etl.orchestration is etlantic.orchestration
    assert etl.secrets is etlantic.secrets
    assert etl.testing is etlantic.testing
    assert etl.viz is etlantic.viz
    assert etl.transform is etlantic.transform
    assert "sql" in dir(etl)


def test_curated_identity_across_import_styles() -> None:
    assert etl.Data is etlantic.Data
    assert etl.Pipeline is etlantic.Pipeline
    assert etl.plan_pipeline is etlantic.plan_pipeline
    assert etl.SecretRef is etlantic.secrets.SecretRef


def test_demoted_alias_removed() -> None:
    with pytest.raises(
        AttributeError, match=r"removed from the etlantic root in 0\.37\.0"
    ):
        _ = etlantic.Edge
    from etlantic.model import Edge

    assert Edge is etlantic.model.Edge


def test_import_budget_no_optional_engines() -> None:
    """Fresh subprocess: ``import etlantic as etl`` must not load optional engines."""
    script = """
import sys
import etlantic as etl
forbidden = (
    "polars",
    "pandas",
    "pyspark",
    "airflow",
    "prefect",
    "etlantic_polars",
    "etlantic_pandas",
    "etlantic_sql",
    "etlantic_pyspark",
    "etlantic_airflow",
    "etlantic_prefect",
)
loaded = [m for m in forbidden if m in sys.modules]
assert etl.Data is not None
assert not loaded, loaded
print("ok", etl.__version__, len(sys.modules))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        cwd=".",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip().startswith("ok")
