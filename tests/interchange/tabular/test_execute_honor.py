# pyright: reportArgumentType=false, reportMissingParameterType=false, reportMissingTypeArgument=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false
"""Runtime honors the mechanism selected on a cross-engine boundary."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

import pytest

from etlantic.capabilities import PluginCapabilities
from etlantic.dataframe.arrow import to_arrow_table_strict
from etlantic.dataframe.protocol import (
    DataframeMetrics,
    DataframeOutputBundle,
    ValidationDecision,
)
from etlantic.interchange.tabular import (
    SCHEMA,
    CopyEligibility,
    InterchangeDescriptor,
    InterchangeMechanism,
)
from etlantic.interchange.tabular.execute import boundary_for_input
from etlantic.model import Edge, LogicalGraph, Node, NodeKind, PortSpec
from etlantic.plan.model import PLAN_SCHEMA, PipelinePlan
from etlantic.plan.regions import MaterializationBoundary
from etlantic.runtime.dataframe_exec import execute_dataframe_step
from etlantic.testing import run_tabular_interchange_conformance_smoke
from etlantic.transformation import ImplementationRecord


def _descriptor(
    mechanism: InterchangeMechanism = InterchangeMechanism.RECORDS_FALLBACK,
) -> InterchangeDescriptor:
    return InterchangeDescriptor(
        schema=SCHEMA,
        mechanism=mechanism,
        producer_engine="producer",
        consumer_engine="consumer",
        producer_caps=(mechanism.value,),
        consumer_caps=(mechanism.value,),
        schema_fingerprint="a" * 64,
        ownership="copied",
        batching="collected",
        collection=True,
        copy_eligibility=CopyEligibility.COPY_REQUIRED,
        fallback_reason="test" if "fallback" in mechanism.value else None,
        evidence_refs=(),
    )


def _plan(descriptor: InterchangeDescriptor) -> PipelinePlan:
    graph = LogicalGraph(
        pipeline_id="pipeline:test",
        pipeline_name="Test",
        nodes=(
            Node(name="producer", kind=NodeKind.STEP, identity="producer"),
            Node(name="consumer", kind=NodeKind.STEP, identity="consumer"),
        ),
        edges=(
            Edge(
                producer_node="producer",
                producer_port="result",
                consumer_node="consumer",
                consumer_port="rows",
            ),
        ),
    )
    boundary = MaterializationBoundary(
        identity="boundary:test",
        producer_node="producer",
        producer_port="result",
        reason="cross_engine",
        metadata={
            "consumer_node": "consumer",
            "consumer_port": "rows",
            "interchange": descriptor.to_dict(),
        },
    )
    return PipelinePlan(
        schema=PLAN_SCHEMA,
        plan_id="plan:test",
        pipeline_id=graph.pipeline_id,
        pipeline_name=graph.pipeline_name,
        profile_name="test",
        fingerprint="test",
        logical_graph=graph,
        materialization_boundaries=(boundary,),
    )


class _Plugin:
    seen_interchange: InterchangeDescriptor | None = None

    def materialize_input(self, value: Any, **kwargs: Any) -> Any:
        self.seen_interchange = kwargs["context"].interchange
        return value

    def validate_frame(self, value: Any, **kwargs: Any) -> tuple[Any, Any, list, None]:
        return value, ValidationDecision.SKIPPED, [], None

    def invoke(self, *, callable_: Any, inputs: Any, parameters: Any, context: Any):
        return callable_(**inputs)

    def normalize_output(self, result: Any, **kwargs: Any) -> DataframeOutputBundle:
        return DataframeOutputBundle(
            valid={"result": result},
            metrics=DataframeMetrics(),
        )

    def collect_if_needed(self, value: Any, **kwargs: Any) -> Any:
        return value

    def ensure_ownership(self, value: Any, **kwargs: Any) -> Any:
        return value

    def row_count(self, value: Any) -> int | None:
        return len(value) if isinstance(value, list) else None


def test_boundary_for_input_matches_consumer_metadata_and_edge() -> None:
    descriptor = _descriptor()
    plan = _plan(descriptor)

    assert boundary_for_input(plan, "consumer", "rows") == descriptor
    assert boundary_for_input(plan, "consumer", "missing") is None


def test_public_conformance_smoke_round_trips_descriptor(monkeypatch) -> None:
    monkeypatch.setattr("etlantic.testing.interchange.arrow_available", lambda: False)
    mechanisms = frozenset({"native_fallback", "records_fallback"})

    descriptor = run_tabular_interchange_conformance_smoke(
        PluginCapabilities(engine="producer", interchange_mechanisms=mechanisms),
        PluginCapabilities(engine="consumer", interchange_mechanisms=mechanisms),
    )

    assert descriptor.mechanism is InterchangeMechanism.NATIVE_FALLBACK
    assert descriptor.fallback_reason == "pyarrow_unavailable"


def test_strict_arrow_conversion_does_not_swallow_export_failure() -> None:
    pytest.importorskip("pyarrow")

    class BrokenExport:
        def to_arrow(self):
            raise ValueError("broken export")

    with pytest.raises(TypeError, match="broken export"):
        to_arrow_table_strict(BrokenExport())


def test_execute_passes_descriptor_and_records_conversion_metrics() -> None:
    descriptor = _descriptor(InterchangeMechanism.NATIVE_FALLBACK)
    plan = _plan(descriptor)
    plugin = _Plugin()

    def identity(rows: list[dict[str, int]]) -> list[dict[str, int]]:
        return rows

    impl = ImplementationRecord(
        engine="consumer",
        identity="identity",
        callable=identity,
        is_async=False,
        signature=inspect.signature(identity),
    )
    node = Node(
        name="consumer",
        kind=NodeKind.STEP,
        identity="consumer",
        inputs=(
            PortSpec(
                name="rows",
                direction="input",
                contract_type=None,
                contract_id=None,
            ),
        ),
        outputs=(
            PortSpec(
                name="result",
                direction="output",
                contract_type=None,
                contract_id=None,
            ),
        ),
    )

    bundle = asyncio.run(
        execute_dataframe_step(
            plugin=plugin,
            impl=impl,
            node=node,
            inputs={"rows": [{"value": 1}]},
            params={},
            plan=plan,
            run_id="run:test",
            attempt=1,
        )
    )

    assert plugin.seen_interchange == descriptor
    assert bundle.metrics.converted is True
    assert bundle.metrics.conversion_kind == "native_fallback"
