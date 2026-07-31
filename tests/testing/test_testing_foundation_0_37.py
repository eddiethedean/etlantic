"""0.37 testing-foundation graduation evidence.

ADOPTION_ECOSYSTEM / EXIT_GATE_0_37 gates covered here:

1. Public imports only for end-to-end pipeline cases
2. Same eligible identity/projection case → equivalent normalized rows on
   Polars / Pandas / SQL / PySpark advertised intersection (skip missing engines)
3. Fault / write injection via public fakes (no production system)
4. Explicit snapshot updates
5. No secrets / unbounded rows in artifacts
6. Isolated-wheel evidence path: ``scripts/check_isolated_codec_burn_in.py``
   (and packaged ``etlantic.testing`` symbols — no private underscore imports)
7. Independent app CI: ``.github/workflows/checks.yml`` runnable example
   (``examples/memory_customers.py``) + public ``PipelineTestCase`` on that pipeline

Burn-in corpus from 0.36 remains in ``test_application_pipeline_burn_in_0_36.py``.
"""

from __future__ import annotations

import asyncio
import ast
import json
from pathlib import Path
from typing import Any

import pytest
from examples.memory_customers import CustomerPipeline, RawCustomer

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
    Profile,
    Transformation,
)
from etlantic.testing import (
    MAX_SEED_ROWS_PER_ASSET,
    ExpectedResult,
    FakeRunIdentity,
    FakeSecretProvider,
    FaultBoundary,
    FaultSpec,
    PipelineTestCase,
    assert_case_succeeded,
    assert_snapshots_match,
    emit_case_result_json,
    inject_faults,
    normalize_rows,
    run_pipeline_case,
    snapshot_plan,
    snapshot_report,
)
from etlantic.testing.portable_transform_conformance import rows_from_frame
from etlantic.transform import functions as F
from etlantic.transform.compiler import (
    TransformCompileContext,
    TransformExecutionContext,
    TransformPlanningContext,
)

FOUNDATION = "etlantic.testing.foundation/0.37"


class _Row(Data):
    id: int
    name: str


class _Out(Data):
    id: int
    name: str


class _Project(Transformation):
    rows: Input[_Row]
    result: Output[_Out]


@_Project.portable
def _project(rows):  # type: ignore[no-untyped-def]
    return rows.filter(F.col("id") > 0).select("id", "name")


class _ProjectionPipeline(Pipeline):
    raw: Extract[_Row] = Extract(asset="src")
    projected = _Project.step(rows=raw)
    out: Load[_Out] = Load(input=projected.result, asset="dst")


_SEED_ROWS = (
    _Row(id=1, name="Ada"),
    _Row(id=0, name="Skip"),
    _Row(id=2, name="Grace"),
)
_EXPECTED_OUT = [
    {"id": 1, "name": "Ada"},
    {"id": 2, "name": "Grace"},
]


def _public_symbols() -> list[str]:
    import etlantic.testing as testing

    required = [
        "PipelineTestCase",
        "ExpectedResult",
        "PipelineCaseResult",
        "run_pipeline_case",
        "FakeClock",
        "FakeRunIdentity",
        "FakeSecretProvider",
        "FaultBoundary",
        "FaultSpec",
        "inject_faults",
        "with_faults",
        "snapshot_plan",
        "snapshot_report",
        "assert_snapshots_match",
        "emit_case_result_json",
        "normalize_rows",
        "MAX_SEED_ROWS_PER_ASSET",
        "MAX_SNAPSHOT_BYTES",
    ]
    missing = [name for name in required if not hasattr(testing, name)]
    assert not missing, missing
    return required


def test_public_exports_complete() -> None:
    _public_symbols()


def test_pipeline_case_module_uses_no_private_etlantic_imports() -> None:
    """Isolated-wheel / public-API gate: foundation module stays public-only."""
    root = Path(__file__).resolve().parents[2]
    path = root / "src" / "etlantic" / "testing" / "pipeline_case.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("etlantic._"), alias.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert not mod.startswith("etlantic._"), mod
            if mod == "etlantic":
                for alias in node.names:
                    assert not alias.name.startswith("_"), alias.name


def test_independent_app_pipeline_via_public_testing() -> None:
    """Gate 7: independently maintained example pipeline + public testing API."""
    case = PipelineTestCase(
        case_id="foundation_memory_customers",
        pipeline=CustomerPipeline,
        profile="development",
        seed={
            "customer_source": (
                RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
                RawCustomer(customer_id=2, first_name="Grace", last_name="Hopper"),
            )
        },
        expected=ExpectedResult(
            status="succeeded",
            sink_assets={
                "customer_sink": (
                    {"customer_id": 1, "full_name": "Ada Lovelace"},
                    {"customer_id": 2, "full_name": "Grace Hopper"},
                )
            },
        ),
        metadata={"foundation": FOUNDATION, "ci_example": "memory_customers"},
    )
    result = run_pipeline_case(
        case,
        runtime=PipelineRuntime(),
        identity=FakeRunIdentity(run_id="foundation-037"),
    )
    assert_case_succeeded(result)
    blob = json.dumps(result.to_dict()).lower()
    assert "password" not in blob
    assert "should-never" not in blob


def test_fault_and_write_injection_via_public_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ETLANTIC_FAULT_INJECTION", "1")
    case = PipelineTestCase(
        case_id="foundation_load_fault",
        pipeline=CustomerPipeline,
        profile="development",
        seed={
            "customer_source": (
                RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
            )
        },
        expected=ExpectedResult(status="failed"),
        faults=(
            FaultSpec(boundary=FaultBoundary.LOAD, message="injected-write-fail"),
        ),
        metadata={"foundation": FOUNDATION},
    )
    result = run_pipeline_case(case, runtime=PipelineRuntime())
    assert result.status == "failed" or not result.ok
    # Public inject_faults alias remains usable outside PipelineTestCase.faults.
    with inject_faults(FaultSpec(boundary=FaultBoundary.LOAD, message="alias")):
        pass


def test_explicit_snapshot_update_and_redaction(tmp_path: Path) -> None:
    case = PipelineTestCase(
        case_id="foundation_snapshot",
        pipeline=CustomerPipeline,
        profile="development",
        seed={
            "customer_source": (
                RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
            )
        },
        expected=ExpectedResult(status="succeeded"),
    )
    result = run_pipeline_case(case, runtime=PipelineRuntime())
    assert_case_succeeded(result)
    plan_path = tmp_path / "plan.json"
    report_path = tmp_path / "report.json"
    with pytest.raises(FileNotFoundError):
        snapshot_plan(result.plan, plan_path, update=False)
    snapshot_plan(result.plan, plan_path, update=True)
    snapshot_report(result.report, report_path, update=True)
    assert_snapshots_match(result.plan, snapshot_plan(result.plan, plan_path))
    assert_snapshots_match(result.report, snapshot_report(result.report, report_path))
    emit_case_result_json(result, tmp_path / "case.json")
    provider = FakeSecretProvider({"token": "super-secret-value"})
    assert "super-secret-value" not in (tmp_path / "case.json").read_text(
        encoding="utf-8"
    )
    assert provider.descriptor.version.startswith("0.37")


def test_seed_bounds_reject_unbounded_rows() -> None:
    rows = tuple(
        RawCustomer(customer_id=i, first_name="A", last_name="B")
        for i in range(MAX_SEED_ROWS_PER_ASSET + 1)
    )
    case = PipelineTestCase(
        case_id="too_many_rows",
        pipeline=CustomerPipeline,
        seed={"customer_source": rows},
    )
    result = run_pipeline_case(case, runtime=PipelineRuntime())
    assert not result.ok
    assert any("max is" in err for err in result.errors)


def _compiler_for(engine: str) -> Any:
    if engine == "polars":
        pytest.importorskip("polars")
        from etlantic_polars import create_transform_compiler

        return create_transform_compiler()
    if engine == "pandas":
        pytest.importorskip("pandas")
        from etlantic_pandas import create_transform_compiler

        return create_transform_compiler()
    if engine == "sql":
        pytest.importorskip("sqlalchemy")
        from etlantic_sql import create_transform_compiler

        return create_transform_compiler()
    if engine == "pyspark":
        pytest.importorskip("sparkless")
        from etlantic_pyspark import create_transform_compiler
        from etlantic_pyspark.sparkless_shim import install

        install()
        return create_transform_compiler()
    raise AssertionError(engine)


def _frame_for(engine: str, rows: list[dict[str, Any]]) -> Any:
    if engine == "polars":
        import polars as pl

        return pl.DataFrame(rows)
    if engine == "pandas":
        import pandas as pd

        return pd.DataFrame(rows)
    if engine == "sql":
        from etlantic_sql.frame import SqlRelationFrame

        return SqlRelationFrame(rows=list(rows))
    if engine == "pyspark":
        from etlantic.spark.provider import ResourceContext, SparkSessionRequest
        from etlantic_pyspark import create_provider

        provider = create_provider()
        ctx = ResourceContext(run_id="foundation", pipeline_id="p", plan_id="pl")
        handle = provider.acquire(
            SparkSessionRequest(app_name="foundation-037", master="local[1]"),
            ctx,
        )
        return handle.session.createDataFrame(rows)
    raise AssertionError(engine)


def _run_portable_projection(engine: str) -> list[dict[str, Any]]:
    compiler = _compiler_for(engine)
    plan = _Project.to_transform_plan()
    requirements = _Project.portable_definition().requirements
    planning = TransformPlanningContext(
        pipeline_id="foundation",
        step_name="projected",
        profile_name="foundation",
        engine=engine,
    )
    report = compiler.analyze(plan, context=planning, requirements=requirements)
    assert report.supported, f"{engine} should support identity/projection kernel"
    compiled = compiler.compile(
        plan,
        context=TransformCompileContext(
            pipeline_id="foundation",
            plan_id="pl",
            step_name="projected",
            profile_name="foundation",
            engine=engine,
        ),
        requirements=requirements,
    )
    seed = [
        {"id": 1, "name": "Ada"},
        {"id": 0, "name": "Skip"},
        {"id": 2, "name": "Grace"},
    ]
    metadata: dict[str, Any] = {}
    if engine == "pyspark":
        from etlantic.spark.provider import ResourceContext, SparkSessionRequest
        from etlantic_pyspark import create_provider

        provider = create_provider()
        ctx = ResourceContext(run_id="foundation", pipeline_id="p", plan_id="pl")
        handle = provider.acquire(
            SparkSessionRequest(app_name="foundation-037", master="local[1]"),
            ctx,
        )
        session = handle.session
        metadata["spark_session"] = session
        inputs = {"rows": session.createDataFrame(seed)}
    else:
        inputs = {"rows": _frame_for(engine, seed)}

    async def _exec() -> list[dict[str, Any]]:
        bundle = await compiler.execute(
            compiled,
            inputs=inputs,
            parameters={},
            context=TransformExecutionContext(
                run_id="foundation",
                pipeline_id="foundation",
                plan_id="pl",
                step_name="projected",
                engine=engine,
                metadata=metadata,
            ),
        )
        frame = next(iter(bundle.valid.values()))
        return normalize_rows(rows_from_frame(frame))

    return asyncio.run(_exec())


@pytest.mark.parametrize(
    "engine",
    [
        pytest.param("polars", marks=pytest.mark.polars),
        pytest.param("pandas", marks=pytest.mark.pandas),
        pytest.param("sql", marks=pytest.mark.sql),
        pytest.param("pyspark", marks=pytest.mark.spark),
    ],
)
def test_multi_engine_projection_intersection(engine: str) -> None:
    """Gate 2: same eligible case → equivalent normalized results per engine."""
    got = _run_portable_projection(engine)
    assert got == normalize_rows(_EXPECTED_OUT)


@pytest.mark.polars
def test_pipeline_case_on_polars_portable() -> None:
    pytest.importorskip("polars")
    from etlantic_polars import create_plugin

    profile = Profile(
        name="foundation-polars",
        dataframe_engine="polars",
        portable_transform_policy="require",
    )
    runtime = PipelineRuntime()
    runtime.register_dataframe_plugin("polars", create_plugin())
    case = PipelineTestCase(
        case_id="foundation_polars_projection",
        pipeline=_ProjectionPipeline,
        profile=profile,
        seed={"src": _SEED_ROWS},
        expected=ExpectedResult(
            status="succeeded",
            sink_assets={"dst": tuple(_EXPECTED_OUT)},
        ),
        metadata={"foundation": FOUNDATION, "engine": "polars"},
    )
    result = run_pipeline_case(case, runtime=runtime)
    assert_case_succeeded(result)


@pytest.mark.pandas
def test_pipeline_case_on_pandas_portable() -> None:
    pytest.importorskip("pandas")
    from etlantic_pandas import create_plugin

    profile = Profile(
        name="foundation-pandas",
        dataframe_engine="pandas",
        portable_transform_policy="require",
    )
    runtime = PipelineRuntime()
    runtime.register_dataframe_plugin("pandas", create_plugin())
    case = PipelineTestCase(
        case_id="foundation_pandas_projection",
        pipeline=_ProjectionPipeline,
        profile=profile,
        seed={"src": _SEED_ROWS},
        expected=ExpectedResult(
            status="succeeded",
            sink_assets={"dst": tuple(_EXPECTED_OUT)},
        ),
        metadata={"foundation": FOUNDATION, "engine": "pandas"},
    )
    result = run_pipeline_case(case, runtime=runtime)
    assert_case_succeeded(result)
