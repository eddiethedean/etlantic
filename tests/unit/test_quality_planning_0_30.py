"""Tests for quality-gate planning (0.30 WP2)."""

from __future__ import annotations

import pytest

from etlantic import Data, Extract, Load, Pipeline, plan_pipeline
from etlantic.capabilities import PluginCapabilities
from etlantic.exceptions import PipelineValidationError
from etlantic.profile import Profile
from etlantic.quality.gate import make_quality_gate
from etlantic.quality.model import QualityRuleset, rule_not_null, rule_regex
from etlantic.registry import PlanningContext, PluginDescriptor, builtin_stub_registry


class Item(Data):
    id: int
    email: str | None = None


Gate = make_quality_gate(
    Item,
    QualityRuleset(rules=(rule_not_null("id"), rule_regex("email", r".+@.+"))),
    name="ItemGate",
)


class QualityPipeline(Pipeline):
    raw: Extract[Item] = Extract(asset="in")
    gate = Gate.step(rows=raw)
    out: Load[Item] = Load(input=gate.result, asset="out")


def _context(
    *,
    extras: frozenset[str] = frozenset(),
    invalid_row_separation: bool = True,
) -> PlanningContext:
    registry = builtin_stub_registry()
    caps = PluginCapabilities(
        engine="polars",
        dataframe=True,
        eager=True,
        lazy=True,
        invalid_row_separation=invalid_row_separation,
        extras=extras,
    )
    registry.register_plugin(
        PluginDescriptor(
            name="etlantic-polars",
            kind="dataframe",
            version="0.30.0",
            engine="polars",
            capabilities=caps,
        )
    )
    return PlanningContext(
        profile=Profile(name="dev", dataframe_engine="polars"),
        registry=registry,
        required_capabilities=["dataframe", "eager"],
    )


def test_plan_includes_quality_metadata() -> None:
    extras = frozenset({"quality.not_null", "quality.regex"})
    plan = plan_pipeline(QualityPipeline, context=_context(extras=extras))
    quality = plan.metadata.get("etlantic.quality") or {}
    assert quality.get("validation_cost", 0) >= 1
    gates = quality.get("gates") or []
    assert len(gates) == 1
    assert "quality.not_null" in gates[0]["required_capabilities"]
    assert any(
        b.reason == "validation_boundary" for b in plan.materialization_boundaries
    )


def test_unsupported_quality_rule_fails_closed() -> None:
    with pytest.raises(PipelineValidationError) as exc_info:
        plan_pipeline(
            QualityPipeline,
            context=_context(extras=frozenset({"quality.not_null"})),
        )
    codes = {d.code for d in exc_info.value.report.diagnostics}
    assert "PMPLAN421" in codes


def test_missing_row_separation_fails_closed() -> None:
    with pytest.raises(PipelineValidationError) as exc_info:
        plan_pipeline(
            QualityPipeline,
            context=_context(
                extras=frozenset({"quality.not_null", "quality.regex"}),
                invalid_row_separation=False,
            ),
        )
    codes = {d.code for d in exc_info.value.report.diagnostics}
    assert "PMPLAN420" in codes


def _non_dataframe_quality_context(engine: str, *, kind: str) -> PlanningContext:
    registry = builtin_stub_registry()
    caps = PluginCapabilities(
        engine=engine,
        dataframe=False,
        sql=engine == "sql",
        spark=engine in {"spark", "pyspark"},
        invalid_row_separation=False,
        extras=frozenset({engine}),
    )
    registry.register_plugin(
        PluginDescriptor(
            name=f"etlantic-{engine}",
            kind=kind,
            version="0.30.0",
            engine=engine,
            capabilities=caps,
        )
    )
    profile_kwargs: dict = {"name": "dev"}
    if engine == "sql":
        profile_kwargs["sql_engine"] = "sql"
    else:
        profile_kwargs["spark_engine"] = engine
    return PlanningContext(
        profile=Profile(**profile_kwargs),
        registry=registry,
        required_capabilities=[],
    )


@pytest.mark.parametrize(
    ("engine", "kind"),
    [("sql", "sql"), ("pyspark", "spark"), ("spark", "spark")],
)
def test_sql_spark_quality_gates_fail_with_pmplan42x_not_302(
    engine: str, kind: str
) -> None:
    with pytest.raises(PipelineValidationError) as exc_info:
        plan_pipeline(
            QualityPipeline,
            context=_non_dataframe_quality_context(engine, kind=kind),
        )
    codes = {d.code for d in exc_info.value.report.diagnostics}
    assert "PMPLAN302" not in codes
    assert "PMPLAN420" in codes or "PMPLAN421" in codes


def test_plan_recomputes_stale_quality_fingerprint() -> None:
    extras = frozenset({"quality.not_null", "quality.regex"})
    # Corrupt embedded fingerprint on the transform class metadata.

    raw = dict(Gate.__quality_expression__)
    raw["fingerprint"] = "0" * 64
    Gate.__quality_expression__ = raw
    plan = plan_pipeline(QualityPipeline, context=_context(extras=extras))
    gate_meta = (plan.metadata.get("etlantic.quality") or {})["gates"][0]
    assert gate_meta["fingerprint"] != "0" * 64
    # restore for other tests
    from etlantic.quality.serialize import quality_fingerprint, quality_from_dict

    expr = quality_from_dict(raw, verify=False, recompute_fingerprint=True)
    Gate.__quality_expression__ = {**raw, "fingerprint": quality_fingerprint(expr)}
