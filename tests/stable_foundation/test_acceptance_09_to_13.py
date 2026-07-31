"""Stable-foundation acceptance items 9-13 (lifecycle, trust, portable, medallantic)."""

from __future__ import annotations

from typing import Annotated

import pytest
from examples.memory_customers import CustomerPipeline

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
    SecretRef,
    Transformation,
)
from etlantic.lifecycle.callbacks import FailureAction
from etlantic.lifecycle.resources import Inject
from etlantic.outbound import OutboundPolicy, evaluate_outbound_url
from etlantic.plan import plan_pipeline, plan_to_json
from etlantic.profile import Profile, production_profile
from etlantic.registry import PlanningContext
from etlantic.runtime.logging import redact_message, redact_value
from etlantic.runtime.state import RunStatus
from etlantic.testing import (
    default_sparkforge_fixtures,
    run_conformance_suite,
    run_lifecycle_conformance_suite,
    run_portable_transform_conformance_suite,
    run_production_conformance_suite,
    run_sparkforge_differential_suite,
)


class _Sf09Row(Data):
    id: int


class _Sf09WithResource(Transformation):
    rows: Input[_Sf09Row]
    result: Output[_Sf09Row]


@_Sf09WithResource.implementation("local")
def _sf09_with_resource_local(
    rows: list[_Sf09Row],
    db: Annotated[object, Inject("db")],
) -> list[_Sf09Row]:
    assert db == {"ok": True}
    return list(rows)


class _Sf09ResourcePipeline(Pipeline):
    raw: Extract[_Sf09Row] = Extract(asset="rows")
    step = _Sf09WithResource.step(rows=raw)
    out: Load[_Sf09Row] = Load(input=step.result, asset="out")


class _Sf09Boom(Transformation):
    rows: Input[_Sf09Row]
    result: Output[_Sf09Row]


@_Sf09Boom.implementation("local")
def _sf09_boom_local(rows: list[_Sf09Row]) -> list[_Sf09Row]:
    raise RuntimeError("sf09-boom")


class _Sf09BoomPipeline(Pipeline):
    raw: Extract[_Sf09Row] = Extract(asset="rows")
    step = _Sf09Boom.step(rows=raw)
    out: Load[_Sf09Row] = Load(input=step.result, asset="out")


def test_sf_09_lifecycle_middleware_resource_callback_outbound_logging_redaction() -> (
    None
):
    """Item 9: lifecycle, middleware, resource, callback, outbound, logging, redaction."""
    results = run_lifecycle_conformance_suite()
    assert results

    order: list[str] = []

    async def mw(ctx, call_next):  # type: ignore[no-untyped-def]
        order.append("before")
        out = await call_next()
        order.append("after")
        return out

    cleaned: list[str] = []
    failed_callbacks: list[str] = []

    def provide_db():
        class _CM:
            def __enter__(self):
                return {"ok": True}

            def __exit__(self, *args):
                cleaned.append("done")
                return False

        return _CM()

    runtime = PipelineRuntime()
    runtime.add_run_middleware(mw, name="sf09")
    runtime.override_resource("db", provide_db)
    runtime.callbacks.on_step_failed(
        lambda _ctx: failed_callbacks.append("step_failed") or FailureAction.CONTINUE
    )
    runtime.memory.seed("rows", [_Sf09Row(id=1)])
    report = _Sf09ResourcePipeline.run(profile="development", runtime=runtime)
    assert report.status is RunStatus.SUCCEEDED
    assert order == ["before", "after"]
    assert cleaned == ["done"]

    boom_runtime = PipelineRuntime()
    boom_runtime.callbacks.on_step_failed(
        lambda _ctx: failed_callbacks.append("step_failed") or FailureAction.CONTINUE
    )
    boom_runtime.memory.seed("rows", [_Sf09Row(id=1)])
    boom_report = _Sf09BoomPipeline.run(profile="development", runtime=boom_runtime)
    assert boom_report.status is RunStatus.PARTIAL
    # CONTINUE soft-skips the boom step and still schedules dependents; the
    # load then fails without artifacts and also emits step_failed.
    assert failed_callbacks == ["step_failed", "step_failed"]

    decision = evaluate_outbound_url(
        "https://evil.example/hook",
        OutboundPolicy(allowed_hosts=("api.example.com",)),
    )
    assert not decision.allowed

    assert "password=***" in redact_message("failed password=hunter2 for user")
    assert "hunter2" not in redact_message("token=hunter2")
    assert redact_value({"password": "x", "ok": 1})["password"] == "***"


def test_sf_10_plugin_conformance_and_production_trust_policy() -> None:
    """Item 10: plugin conformance + production trust-policy enforcement."""
    from etlantic.plugin_lifecycle import authorize_plugins, discover_entry_points

    empty = production_profile(plugin_allowlist={})
    empty_result = run_production_conformance_suite(empty)
    assert not empty_result.passed
    assert any("allowlist" in f.lower() for f in empty_result.failures)

    discovered, _ = discover_entry_points("etlantic.dataframe_plugins")
    if discovered:
        authorized, diags, _events = authorize_plugins(discovered, empty)
        assert authorized == []
        assert any(d.code.startswith("PMPLUG") for d in diags)

    pytest.importorskip("polars")
    from etlantic_polars import create_plugin

    run_conformance_suite(
        create_plugin(),
        engine="polars",
        sample_rows=[{"id": 1}],
        contract_type=None,
    )

    ok = production_profile(plugin_allowlist={"etlantic-polars": "==0.37.0"})
    assert run_production_conformance_suite(ok).passed


def test_sf_11_security_boundary_preserved_through_planning() -> None:
    """Item 11: security-boundary preservation through planning/optimization."""
    profile = Profile(
        name="sf-secrets",
        resources={"db": "warehouse"},
        secrets={
            "db": SecretRef(provider="env-secrets", name="db", key="password"),
        },
    )
    plan = plan_pipeline(
        CustomerPipeline, context=PlanningContext.create(profile=profile)
    )
    secret_ref = plan.resource_refs["secret:db"]
    assert secret_ref["key"] == "password"
    assert "value" not in secret_ref
    blob = plan_to_json(plan).lower()
    assert "hunter" not in blob
    assert "secret_value" not in blob
    dumped = str(plan.to_dict()).lower()
    assert "password" in dumped  # key name ok
    assert "secret-value" not in dumped


@pytest.mark.medallantic
def test_sf_12_sparkforge_medallantic_pipeline_on_etlantic() -> None:
    """Item 12: representative SparkForge/Medallantic corpus on ETLantic."""
    pytest.importorskip("medallantic")
    fixtures = default_sparkforge_fixtures()
    assert fixtures, "expected in-tree sparkforge fixtures"
    results = run_sparkforge_differential_suite(fixtures)
    assert all(r.ok for r in results)


def test_sf_13_portable_definition_multi_engine_intersection() -> None:
    """Item 13: one portable definition across advertised engine intersection."""
    from tests.testing.test_testing_foundation_0_37 import _run_portable_projection

    engines: list[str] = []
    rows_by_engine: dict[str, list[dict]] = {}
    for engine, deps in (
        ("polars", ("polars", "etlantic_polars")),
        ("pandas", ("pandas", "etlantic_pandas")),
        ("sql", ("sqlalchemy", "etlantic_sql")),
        ("pyspark", ("sparkless", "etlantic_pyspark")),
    ):
        missing = False
        for dep in deps:
            try:
                __import__(dep)
            except ImportError:
                missing = True
                break
        if missing:
            continue
        engines.append(engine)
        rows_by_engine[engine] = _run_portable_projection(engine)

    if not engines:
        pytest.skip("no portable transform engines installed")

    expected = [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Grace"}]
    for engine in engines:
        assert rows_by_engine[engine] == expected, engine
    first = rows_by_engine[engines[0]]
    for engine in engines[1:]:
        assert rows_by_engine[engine] == first

    if "polars" in engines:
        from etlantic_polars import create_transform_compiler

        run_portable_transform_conformance_suite(create_transform_compiler())
