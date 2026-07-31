"""Stable-foundation acceptance items 14-17 (Arrow Gate A, DataFusion, plans, allowlist)."""

from __future__ import annotations

import json
from types import SimpleNamespace

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
    Profile,
    Transformation,
)
from etlantic.exceptions import ETLanticError
from etlantic.plan import plan_from_json, plan_pipeline, plan_to_json
from etlantic.plan.artifacts import artifact_identity, assert_identity_compatible
from etlantic.plan.model import PipelinePlan
from etlantic.plugin_lifecycle import authorize_plugins, discover_entry_points
from etlantic.profile import production_profile
from etlantic.registry import PlanningContext


class _Sf14Row(Data):
    value: int


class _Sf14PolarsIdentity(Transformation):
    rows: Input[_Sf14Row]
    result: Output[_Sf14Row]


class _Sf14PandasIdentity(Transformation):
    rows: Input[_Sf14Row]
    result: Output[_Sf14Row]


class _Sf14CrossEnginePipeline(Pipeline):
    raw: Extract[_Sf14Row] = Extract(asset="rows")
    polars_step = _Sf14PolarsIdentity.step(rows=raw)
    pandas_step = _Sf14PandasIdentity.step(rows=polars_step.result)
    out: Load[_Sf14Row] = Load(input=pandas_step.result, asset="out")


@pytest.mark.polars
@pytest.mark.pandas
def test_sf_14_gate_a_polars_pandas_arrow_interchange_with_diagnosed_fallback() -> None:
    """Item 14: Gate A Polars↔Pandas Arrow/interchange evidence + diagnosed fallback.

    Does NOT require PySpark/SQL Arrow or Gate B.
    """
    pytest.importorskip("pandas")
    pytest.importorskip("polars")
    etlantic_pandas = pytest.importorskip("etlantic_pandas")
    etlantic_polars = pytest.importorskip("etlantic_polars")

    from etlantic.dataframe.discovery import register_discovered_plugins
    from etlantic.interchange.tabular import InterchangeEvidence, InterchangeMechanism
    from etlantic.interchange.tabular.execute import boundary_for_input
    from etlantic.interchange.tabular.reconcile import reconcile_interchange_evidence
    from etlantic.registry import builtin_stub_registry
    from etlantic.runtime.state import RunStatus
    from etlantic.testing import run_tabular_interchange_conformance_smoke

    @_Sf14PolarsIdentity.implementation("polars")
    def _polars_identity(rows):  # type: ignore[no-untyped-def]
        return rows

    @_Sf14PandasIdentity.implementation("pandas")
    def _pandas_identity(rows):  # type: ignore[no-untyped-def]
        return rows

    polars_plugin = etlantic_polars.create_plugin()
    pandas_plugin = etlantic_pandas.create_plugin()
    run_tabular_interchange_conformance_smoke(
        polars_plugin.info.capabilities,
        pandas_plugin.info.capabilities,
    )

    plugins = {"polars": polars_plugin, "pandas": pandas_plugin}
    registry = builtin_stub_registry()
    register_discovered_plugins(registry, plugins=plugins)
    profile = Profile(
        name="sf-gate-a",
        dataframe_engine="polars",
        implementation_overrides={"pandas_step": "pandas"},
        portable_transform_policy="native",
    )
    context = PlanningContext.create(profile=profile, registry=registry)
    runtime = PipelineRuntime(registry=registry, dataframe_plugins=plugins)
    runtime.memory.seed("rows", [_Sf14Row(value=1), _Sf14Row(value=2)])

    plan = _Sf14CrossEnginePipeline.plan(profile=profile, context=context)
    descriptor = boundary_for_input(plan, "pandas_step", "rows")
    assert descriptor is not None

    report = _Sf14CrossEnginePipeline.run(
        profile=profile, context=context, runtime=runtime
    )
    assert report.status is RunStatus.SUCCEEDED
    assert [row.value for row in runtime.memory.get("out")] == [1, 2]

    pandas_step = next(s for s in report.steps if s.step_name == "pandas_step")
    dataframe_meta = pandas_step.metadata.get("dataframe") or {}
    evidence_items = (dataframe_meta.get("extras") or {}).get("interchange_evidence")
    assert evidence_items, "expected ownership/collection/copy interchange evidence"
    observed_raw = evidence_items[0]
    mechanism = InterchangeMechanism(observed_raw["mechanism"])
    arrow_or_fallback = {
        InterchangeMechanism.ARROW_C_DATA,
        InterchangeMechanism.ARROW_C_STREAM,
        InterchangeMechanism.ARROW_IPC_STREAM,
        InterchangeMechanism.ARROW_IPC_FILE,
        InterchangeMechanism.RECORDS_FALLBACK,
        InterchangeMechanism.NATIVE_FALLBACK,
        InterchangeMechanism.PARQUET_ARTIFACT,
    }
    assert mechanism in arrow_or_fallback
    if mechanism in {
        InterchangeMechanism.RECORDS_FALLBACK,
        InterchangeMechanism.NATIVE_FALLBACK,
    }:
        assert observed_raw.get("fallback_reason") or getattr(
            descriptor, "fallback_reason", None
        ), "diagnosed fallback requires a reason"
    observed = InterchangeEvidence(
        evidence_id=observed_raw["evidence_id"],
        mechanism=mechanism,
        copy_observed=observed_raw["copy_observed"],
        zero_copy_reported=observed_raw["zero_copy_reported"],
        fallback_reason=observed_raw.get("fallback_reason"),
        cleanup_status=observed_raw["cleanup_status"],
        notes=observed_raw.get("notes") or "",
    )
    assert "copy_observed" in observed_raw
    result = reconcile_interchange_evidence(descriptor, observed)
    assert result.ok


def test_sf_15_datafusion_experimental_no_foundation_obligation() -> None:
    """Item 15: DataFusion is experimental; no stable-foundation obligation."""
    try:
        import etlantic_datafusion as df_pkg
    except ImportError:
        pytest.skip(
            "etlantic-datafusion not installed — disposition: experimental / "
            "no stable-foundation compatibility obligation (item 15)"
        )

    assert getattr(df_pkg, "STREAMING_STABILITY", None) == "experimental"
    plugin = df_pkg.create_plugin()
    caps = plugin.info.capabilities
    assert "experimental" in caps.extras
    assert caps.dataframe is False
    assert caps.arrow_import is False
    assert caps.arrow_export is False
    with pytest.raises(NotImplementedError, match="experimental"):
        plugin.materialize()


def test_sf_16_reject_bad_plans_before_plugin_loading() -> None:
    """Item 16: reject mutated/corrupt/unknown-version/cross-domain plans early."""
    plan = plan_pipeline(CustomerPipeline, profile="development")

    data = json.loads(plan_to_json(plan))
    data["fingerprint"] = "0" * 64
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        plan_from_json(json.dumps(data))

    bad_schema = plan.to_dict()
    bad_schema["schema"] = "etlantic.plan/999"
    with pytest.raises(ValueError, match="Unsupported PipelinePlan schema"):
        PipelinePlan.from_dict(bad_schema)

    missing = plan.to_dict()
    del missing["schema"]
    with pytest.raises(ValueError, match="missing required 'schema'"):
        PipelinePlan.from_dict(missing)

    left = artifact_identity(
        pipeline_id="p",
        node_name="n",
        port_name="out",
        security_domain="prod",
        tenant="t1",
        environment="staging",
        authorization="prod-profile",
    )
    with pytest.raises(ETLanticError):
        assert_identity_compatible(
            left, security_domain="prod", tenant="t2", environment="staging"
        )


def test_sf_17_allowlist_authorizes_and_rejects_without_importing_entry_point() -> None:
    """Item 17: allow listed plugins; reject disallowed without loading EP."""
    from etlantic.plugin_lifecycle import DiscoveredPlugin

    discovered, _ = discover_entry_points("etlantic.dataframe_plugins")
    if not discovered:
        pytest.skip("no dataframe plugins installed")

    denied_profile = production_profile(
        plugin_allowlist={"definitely-not-installed": "==9.9.9"}
    )
    authorized, diags, events = authorize_plugins(discovered, denied_profile)
    assert authorized == []
    assert any(d.code == "PMPLUG402" for d in diags)
    assert all(e.outcome == "denied" for e in events)

    # Spy via a mutable fake entry point (stdlib EntryPoint is immutable).
    loads: list[str] = []

    def _tracking_load(name: str = "tracked") -> object:
        loads.append(name)
        raise AssertionError("disallowed plugin entry point must not be loaded")

    fake = DiscoveredPlugin(
        group="etlantic.dataframe_plugins",
        name="evil",
        target="evil:create",
        distribution_name="evil-pkg",
        distribution_version="0.0.1",
        entry_point=SimpleNamespace(
            name="evil", value="evil:create", load=_tracking_load
        ),
        engine="evil",
    )
    authorize_plugins([fake], denied_profile)
    assert loads == [], "disallowed plugins must not import/load entry points"

    package = next(
        (item.distribution_name for item in discovered if item.distribution_name),
        None,
    )
    if package is None:
        pytest.skip("no distribution metadata available")
    version = next(
        item.distribution_version
        for item in discovered
        if item.distribution_name == package
    )
    allowed_profile = production_profile(
        plugin_allowlist={str(package): f"=={version}"}
    )
    authorized_ok, diags_ok, _ = authorize_plugins(discovered, allowed_profile)
    assert authorized_ok, f"expected {package!r} to authorize; diags={diags_ok}"
