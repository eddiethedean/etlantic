"""Multi-phase validation tests."""

from __future__ import annotations

import pytest

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    Transformation,
)
from etlantic.capabilities import PluginCapabilities
from etlantic.policy import STRICT_POLICY
from etlantic.profile import Profile
from etlantic.registry import PlanningContext, PluginDescriptor, RegistryBundle


class Item(Data):
    id: int


class Pass(Transformation):
    items: Input[Item]
    result: Output[Item]
    rejected: Output[Item] = Output(Item).as_invalid()


@Pass.implementation("local")
def _pass_local(items):  # type: ignore[no-untyped-def]
    return items


class GoodPipeline(Pipeline):
    raw: Extract[Item] = Extract(asset="in")
    step = Pass.step(items=raw)
    out: Load[Item] = Load(input=step.result, asset="out")


class BadInvalidWire(Pipeline):
    raw: Extract[Item] = Extract(asset="in")
    step = Pass.step(items=raw)
    out: Load[Item] = Load(input=step.rejected, asset="out")


class UnboundPipeline(Pipeline):
    raw: Extract[Item] = Extract(asset="missing_binding")
    step = Pass.step(items=raw)
    out: Load[Item] = Load(input=step.result, asset="also_missing")


class NoImplTransform(Transformation):
    items: Input[Item]
    result: Output[Item]


class NoImplPipeline(Pipeline):
    raw: Extract[Item] = Extract(asset="in")
    step = NoImplTransform.step(items=raw)
    out: Load[Item] = Load(input=step.result, asset="out")


class ChildPipeline(Pipeline):
    raw: Extract[Item] = Extract(asset="child_in")
    step = Pass.step(items=raw)
    out: Load[Item] = Load(input=step.result, asset="child_out")


class ParentWithChild(Pipeline):
    raw: Extract[Item] = Extract(asset="in")
    child = ChildPipeline.subpipeline(raw=raw)
    out: Load[Item] = Load(input=child.out, asset="out")


def test_validation_phases_present() -> None:
    report = GoodPipeline.validate()
    assert report.valid
    assert report.phases == (
        "structural",
        "reference",
        "semantic",
        "policy",
        "capability",
        "plugin_discovery",
        "plugin_trust",
    )


def test_invalid_output_cannot_feed_consumer() -> None:
    report = BadInvalidWire.validate()
    assert any(d.code == "PMPIPE220" for d in report.errors)


def test_capability_fail_closed_unsupported_dataframe() -> None:
    registry = RegistryBundle()
    registry.register_plugin(
        PluginDescriptor(
            name="limited",
            kind="dataframe",
            engine="limited",
            capabilities=PluginCapabilities(engine="limited", dataframe=False),
        )
    )
    context = PlanningContext.create(
        profile=Profile(name="limited", dataframe_engine="limited"),
        registry=registry,
        required_capabilities=["dataframe"],
    )
    codes = GoodPipeline.validate(context=context).codes()
    assert "PMPLAN402" in codes
    assert "PMPLAN401" not in codes


def test_capability_missing_engine_is_plan401() -> None:
    context = PlanningContext.create(
        profile=Profile(name="ghost", dataframe_engine="does-not-exist"),
        registry=RegistryBundle(),
        required_capabilities=["dataframe"],
    )
    assert "PMPLAN401" in GoodPipeline.validate(context=context).codes()


def test_strict_policy_requires_bindings() -> None:
    report = UnboundPipeline.validate(policy=STRICT_POLICY)
    assert any(d.code == "PMPLAN201" for d in report.errors)


def test_strict_policy_requires_implementations() -> None:
    report = NoImplPipeline.validate(
        policy=STRICT_POLICY,
        profile=Profile(
            name="strict-local",
            assets={"in": "x", "out": "y"},
            validation_policy="strict",
        ),
    )
    assert any(d.code == "PMPLAN301" for d in report.errors)


def test_subpipeline_inherits_parent_strict_bindings() -> None:
    # Parent provides bindings for its own ports but not child_in/child_out.
    profile = Profile(
        name="parent",
        assets={"in": "src", "out": "dst"},
        validation_policy="strict",
    )
    report = ParentWithChild.validate(profile=profile, policy=STRICT_POLICY)
    assert any(d.code == "PMPLAN201" for d in report.errors)
    assert any("child_in" in d.message or "child" in d.path for d in report.errors)


def test_planning_discovery_diagnostics_surface_in_validate() -> None:
    """Plugin discovery diagnostics from PlanningContext appear in validate output."""
    from importlib.metadata import distribution

    from etlantic.profile import production_profile

    try:
        distribution("etlantic-polars")
    except Exception:
        pytest.skip("etlantic-polars not installed")

    profile = production_profile(
        plugin_allowlist={},
        dataframe_engine="polars",
        assets={"in": "x", "out": "y"},
    )
    report = GoodPipeline.validate(profile=profile)
    discovery = [d for d in report.diagnostics if d.phase == "plugin_discovery"]
    assert discovery, "expected plugin_discovery phase diagnostics"
    assert any(d.code == "PMPLUG401" for d in discovery)
