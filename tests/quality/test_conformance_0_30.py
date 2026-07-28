"""Portable quality conformance and engine fail-closed tests."""

from __future__ import annotations

import pytest

from etlantic import Data, Extract, Load, Pipeline, plan_pipeline
from etlantic.capabilities import PluginCapabilities
from etlantic.exceptions import PipelineValidationError
from etlantic.profile import Profile
from etlantic.quality.gate import make_quality_gate
from etlantic.quality.model import (
    PORTABLE_QUALITY_CAPABILITIES,
    QualityRuleset,
    rule_not_null,
)
from etlantic.registry import PlanningContext, PluginDescriptor, builtin_stub_registry
from etlantic.testing.quality_conformance import run_quality_conformance_suite


def test_portable_quality_conformance_suite() -> None:
    results = run_quality_conformance_suite()
    assert {r["capability"] for r in results} == set(PORTABLE_QUALITY_CAPABILITIES)


class Row(Data):
    id: int


Gate = make_quality_gate(
    Row,
    QualityRuleset(rules=(rule_not_null("id"),)),
    name="RowGate",
)


class GatePipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="in")
    gate = Gate.step(rows=raw)
    out: Load[Row] = Load(input=gate.result, asset="out")


def _dataframe_context(
    engine: str,
    *,
    extras: frozenset[str],
    invalid_row_separation: bool = True,
) -> PlanningContext:
    registry = builtin_stub_registry()
    caps = PluginCapabilities(
        engine=engine,
        dataframe=True,
        eager=True,
        lazy=engine == "polars",
        invalid_row_separation=invalid_row_separation,
        extras=extras,
    )
    registry.register_plugin(
        PluginDescriptor(
            name=f"etlantic-{engine}",
            kind="dataframe",
            version="0.30.0",
            engine=engine,
            capabilities=caps,
        )
    )
    return PlanningContext(
        profile=Profile(name="dev", dataframe_engine=engine),
        registry=registry,
        required_capabilities=["dataframe", "eager"],
    )


@pytest.mark.parametrize("engine", ["polars", "pandas"])
def test_unadvertised_quality_rules_fail_closed(engine: str) -> None:
    """Engines that do not advertise quality.* must fail at plan time."""
    with pytest.raises(PipelineValidationError) as exc:
        plan_pipeline(
            GatePipeline,
            context=_dataframe_context(
                engine,
                extras=frozenset({engine}),
                invalid_row_separation=True,
            ),
        )
    assert "PMPLAN421" in {d.code for d in exc.value.report.diagnostics}


def test_polars_with_quality_caps_plans() -> None:
    plan = plan_pipeline(
        GatePipeline,
        context=_dataframe_context(
            "polars",
            extras=frozenset({"polars"}) | PORTABLE_QUALITY_CAPABILITIES,
        ),
    )
    assert (plan.metadata.get("etlantic.quality") or {}).get("gates")


def test_polars_pandas_frame_gate_paths() -> None:
    pytest.importorskip("polars")
    pytest.importorskip("pandas")
    import pandas as pd
    import polars as pl

    from etlantic.quality.gate import make_quality_gate
    from etlantic.quality.model import QualityRuleset, rule_not_null

    GateCls = make_quality_gate(
        Row,
        QualityRuleset(rules=(rule_not_null("id"),)),
        name="FrameGate",
    )
    impls = GateCls.implementations()
    polars_fn = impls["polars"].callable
    pandas_fn = impls["pandas"].callable
    frame = pl.DataFrame({"id": [1, None]})
    out = polars_fn(frame)
    assert out["result"].height == 1
    assert out["rejected"].height == 1
    pdf = pd.DataFrame({"id": [1, None]})
    out_pd = pandas_fn(pdf)
    assert len(out_pd["result"]) == 1
    assert len(out_pd["rejected"]) == 1
