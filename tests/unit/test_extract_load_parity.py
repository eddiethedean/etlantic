"""Semantic parity between legacy Source/Sink/binding and Extract/Load/asset."""

from __future__ import annotations

from pathlib import Path

import yaml

from etlantic import (
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    Sink,
    Source,
    Transformation,
    graphs_equivalent,
)
from etlantic.model import NodeKind
from etlantic.plan.planner import plan_pipeline
from etlantic.profile import Profile
from etlantic.registry import PlanningContext
from tests.conftest import Customer, RawCustomer
from tests.fixtures.extract_load_golden_pipeline import ExtractLoadGoldenPipeline


class Normalize(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]


def _legacy_pipeline() -> type[Pipeline]:
    class LegacyPipeline(Pipeline):
        __published_id__ = "parity-pipeline"
        __published_version__ = "0.15.0"
        raw: Source[RawCustomer] = Source(asset="raw_customers", _compat_warn=False)
        normalized = Normalize.step(customers=raw)
        out: Sink[Customer] = Sink(
            input=normalized.result, asset="curated_customers", _compat_warn=False
        )

    return LegacyPipeline


def _canonical_pipeline() -> type[Pipeline]:
    class CanonicalPipeline(Pipeline):
        __published_id__ = "parity-pipeline"
        __published_version__ = "0.15.0"
        raw: Extract[RawCustomer] = Extract(asset="raw_customers")
        normalized = Normalize.step(customers=raw)
        out: Load[Customer] = Load(input=normalized.result, asset="curated_customers")

    return CanonicalPipeline


def test_graphs_equivalent_legacy_and_canonical() -> None:
    legacy = _legacy_pipeline()
    canonical = _canonical_pipeline()
    assert graphs_equivalent(legacy.inspect(), canonical.inspect())


def test_graph_retains_source_sink_kinds_and_binding_field() -> None:
    graph = _canonical_pipeline().build_graph()
    by_name = {node.name: node for node in graph.nodes}
    assert by_name["raw"].kind is NodeKind.SOURCE
    assert by_name["raw"].kind.value == "source"
    assert by_name["raw"].binding == "raw_customers"
    assert by_name["out"].kind is NodeKind.SINK
    assert by_name["out"].kind.value == "sink"
    assert by_name["out"].binding == "curated_customers"


def test_dpcs_retains_etlantic_binding_and_interface() -> None:
    doc = ExtractLoadGoldenPipeline.to_dpcs()
    fixture = Path("tests/interchange/fixtures/extract_load_golden.dpcs.yaml")
    expected = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    assert doc["interface"] == expected["interface"]
    assert doc["interface"]["inputs"][0]["etlantic:binding"] == "raw_customers"
    assert doc["interface"]["outputs"][0]["etlantic:binding"] == "curated_customers"
    assert "Pipeline source" in doc["interface"]["inputs"][0]["purpose"]
    assert "Pipeline sink" in doc["interface"]["outputs"][0]["purpose"]
    assert doc == expected


def test_dpcs_round_trip_graph_equivalence(tmp_path: Path) -> None:
    from etlantic.interchange.bundle import load_bundle, write_contracts

    write_contracts(ExtractLoadGoldenPipeline, tmp_path)
    loaded = load_bundle(tmp_path)
    assert loaded.pipeline is not None
    assert graphs_equivalent(
        ExtractLoadGoldenPipeline.inspect(), loaded.pipeline.inspect()
    )


def test_plan_fingerprint_stable_across_profile_vocabularies() -> None:
    pipeline_cls = _canonical_pipeline()
    legacy_profile = Profile(
        name="parity",
        bindings={"raw_customers": "memory", "curated_customers": "memory"},
        _warn_legacy_bindings=False,
    )
    canonical_profile = Profile(
        name="parity",
        assets={"raw_customers": "memory", "curated_customers": "memory"},
    )
    left = plan_pipeline(
        pipeline_cls, context=PlanningContext.create(profile=legacy_profile)
    )
    right = plan_pipeline(
        pipeline_cls, context=PlanningContext.create(profile=canonical_profile)
    )
    assert left.fingerprint == right.fingerprint
    assert "assets" not in (left.profile_snapshot or {})
    assert "bindings" in (left.profile_snapshot or {})
    assert left.profile_snapshot == right.profile_snapshot


def test_plan_json_retains_binding_field_on_nodes() -> None:
    pipeline_cls = _canonical_pipeline()
    plan = plan_pipeline(
        pipeline_cls,
        context=PlanningContext.create(
            profile=Profile(
                name="parity",
                assets={"raw_customers": "memory", "curated_customers": "memory"},
            )
        ),
    )
    payload = plan.to_dict()
    nodes = {node["name"]: node for node in payload["logical_graph"]["nodes"]}
    assert nodes["raw"]["binding"] == "raw_customers"
    assert nodes["out"]["binding"] == "curated_customers"
    assert "bindings" in payload
