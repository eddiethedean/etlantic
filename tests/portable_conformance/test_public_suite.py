"""Public portable transform conformance suite smoke tests."""

from __future__ import annotations

import pytest

from etlantic.testing import (
    portable_transform_conformance,
    run_portable_transform_conformance_suite,
)


def test_suite_passes_local() -> None:
    from etlantic.transform.local_compiler import LocalTransformCompiler

    run_portable_transform_conformance_suite(LocalTransformCompiler())


@pytest.mark.datafusion
def test_suite_passes_datafusion() -> None:
    pytest.importorskip("datafusion")
    from etlantic_datafusion import create_transform_compiler

    run_portable_transform_conformance_suite(create_transform_compiler())


@pytest.mark.datafusion
def test_datafusion_analysis_reports_native_pushdown_boundaries() -> None:
    pytest.importorskip("datafusion")
    from etlantic.transform.compiler import TransformPlanningContext
    from etlantic_datafusion import create_transform_compiler

    report = create_transform_compiler().analyze(
        {"actions": [{"kind": {"action": "dtcs:limit", "parameters": {"n": 1}}}]},
        context=TransformPlanningContext("p", "s", "profile", "datafusion"),
    )
    assert report.pushdown
    assert report.pushdown[0].outcome == "pushed_exact"
    assert report.pushdown[0].physical_effects == ("native_logical_plan",)


def test_local_unknown_operator_fails_closed() -> None:
    from etlantic.transform.compiler import TransformPlanningContext
    from etlantic.transform.local_compiler import LocalTransformCompiler

    plan = {
        "actions": [
            {
                "kind": {
                    "action": "dtcs:filter",
                    "target": "t",
                    "parameters": {
                        "predicate": {
                            "kind": "binary",
                            "op": "not-a-real-operator",
                            "left": {"kind": "fieldRef", "target": "x"},
                            "right": {
                                "kind": "literal",
                                "value": {"type": "integer", "value": 1},
                            },
                        }
                    },
                }
            }
        ]
    }
    report = LocalTransformCompiler().analyze(
        plan,
        context=TransformPlanningContext("p", "s", "profile", "local"),
    )
    assert report.supported is False
    assert any(f.requirement == "operator:not-a-real-operator" for f in report.findings)


def test_local_unknown_expression_kind_fails_closed() -> None:
    from etlantic.transform.compiler import TransformPlanningContext
    from etlantic.transform.local_compiler import LocalTransformCompiler

    plan = {
        "actions": [
            {
                "kind": {
                    "action": "dtcs:project",
                    "target": "t",
                    "parameters": {
                        "fields": [
                            {
                                "name": "x",
                                "expression": {"kind": "not-a-real-expression"},
                            }
                        ]
                    },
                }
            }
        ]
    }
    report = LocalTransformCompiler().analyze(
        plan,
        context=TransformPlanningContext("p", "s", "profile", "local"),
    )
    assert report.supported is False
    assert any(
        f.requirement == "expression_kind:not-a-real-expression"
        for f in report.findings
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


@pytest.mark.sql
def test_suite_passes_sql() -> None:
    pytest.importorskip("sqlalchemy")
    from etlantic_sql import create_transform_compiler

    run_portable_transform_conformance_suite(create_transform_compiler())


@pytest.mark.duckdb
def test_suite_passes_duckdb() -> None:
    pytest.importorskip("duckdb")
    from etlantic_duckdb import create_transform_compiler

    run_portable_transform_conformance_suite(create_transform_compiler())


def test_module_export_surface() -> None:
    assert hasattr(
        portable_transform_conformance, "run_portable_transform_conformance_suite"
    )
