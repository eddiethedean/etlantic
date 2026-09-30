"""Managed execution rejects connector writes to a consumed source resource."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

import pytest

from etlantic import Data, Extract, Load, Pipeline, PipelineRuntime, Profile
from etlantic.connectors.models import (
    CommitReceipt,
    ConnectorInfo,
    ReadBatch,
    SinkPlan,
    SourcePlan,
    WriteSession,
)
from etlantic.connectors.protocol import SINK_PROTOCOL, SOURCE_PROTOCOL
from etlantic.registry import BindingDescriptor, PlanningContext
from etlantic.runtime.state import RunStatus

PROVIDER = "resource-overlap-test"


class Row(Data):
    id: str


class Transfer(Pipeline):
    raw = Extract[Row](asset="source")
    output = Load[Row](input=raw, asset="sink")


class Source:
    def __init__(self, identities: tuple[str, ...] | None) -> None:
        self.identities = identities

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name=PROVIDER,
            provider=PROVIDER,
            protocol=SOURCE_PROTOCOL,
        )

    async def resource_identities(
        self, *, binding: Mapping[str, Any], context: Mapping[str, Any]
    ) -> tuple[str, ...]:
        del binding, context
        return self.identities or ()

    async def plan_read(
        self, *, binding: Mapping[str, Any], context: Mapping[str, Any]
    ) -> SourcePlan:
        del context
        return SourcePlan(provider=PROVIDER, root_ref=str(binding.get("location")))

    async def read_batches(
        self,
        *,
        plan: SourcePlan,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> AsyncIterator[ReadBatch]:
        del plan, binding, context
        yield ReadBatch(records=({"id": "1"},), exhausted=True)

    async def propose_cursor(
        self, *, plan: SourcePlan, manifest: Any, context: Mapping[str, Any]
    ) -> None:
        del plan, manifest, context
        return None


class Sink:
    def __init__(self, identities: tuple[str, ...] | None) -> None:
        self.identities = identities
        self.begin_calls = 0

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name=PROVIDER,
            provider=PROVIDER,
            protocol=SINK_PROTOCOL,
        )

    async def resource_identities(
        self, *, binding: Mapping[str, Any], context: Mapping[str, Any]
    ) -> tuple[str, ...]:
        del binding, context
        return self.identities or ()

    async def plan_write(
        self, *, binding: Mapping[str, Any], context: Mapping[str, Any]
    ) -> SinkPlan:
        del context
        return SinkPlan(provider=PROVIDER, write_mode="append", root_ref=str(binding.get("location")))

    async def begin_write(
        self,
        *,
        plan: SinkPlan,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> WriteSession:
        del plan, binding, context
        self.begin_calls += 1
        return WriteSession(session_id="session-1", provider=PROVIDER)

    async def write_batch(
        self, session: WriteSession, batch: Any, *, context: Mapping[str, Any]
    ) -> None:
        del session, batch, context

    async def prepare(self, session: WriteSession, *, context: Mapping[str, Any]) -> None:
        del session, context

    async def commit(
        self, session: WriteSession, *, context: Mapping[str, Any]
    ) -> CommitReceipt:
        del context
        return CommitReceipt(status="committed", session_id=session.session_id)

    async def abort(
        self, session: WriteSession, *, context: Mapping[str, Any]
    ) -> CommitReceipt:
        del context
        return CommitReceipt(status="rolled_back", session_id=session.session_id)

    async def reconcile(
        self, receipt: CommitReceipt, *, context: Mapping[str, Any]
    ) -> Any:
        del context
        return receipt

    async def cleanup(
        self, receipt: CommitReceipt, *, context: Mapping[str, Any]
    ) -> Any:
        del receipt, context
        return None


def _run_transfer(
    source_identities: tuple[str, ...] | None,
    sink_identities: tuple[str, ...] | None,
) -> tuple[Any, Sink]:
    profile = Profile(name="dev", security_mode="development")
    planning = PlanningContext.create(profile=profile)
    planning.registry.register_binding(
        BindingDescriptor(
            binding="source",
            provider=PROVIDER,
            location="source-alias",
            kind="source",
        )
    )
    planning.registry.register_binding(
        BindingDescriptor(
            binding="sink",
            provider=PROVIDER,
            location="sink-alias",
            kind="sink",
        )
    )
    runtime = PipelineRuntime()
    source = Source(source_identities)
    if source_identities is None:
        source.__dict__["resource_identities"] = None
    runtime.register_source_connector(PROVIDER, source)
    sink = Sink(sink_identities)
    runtime.register_sink_connector(PROVIDER, sink)
    return Transfer.run(profile=profile, runtime=runtime, context=planning), sink


def test_managed_connector_write_rejects_same_resolved_resource() -> None:
    report, sink = _run_transfer(("opaque-source-and-target",), ("opaque-source-and-target",))

    assert report.status is RunStatus.PARTIAL
    assert sink.begin_calls == 0
    assert any(item.code == "PMEXEC435" for item in report.diagnostics)
    assert "opaque-source-and-target" not in report.to_json()


def test_managed_connector_write_requires_identity_for_same_provider() -> None:
    report, sink = _run_transfer(None, ("opaque-target",))

    assert report.status is RunStatus.PARTIAL
    assert sink.begin_calls == 0
    assert any(item.code == "PMEXEC435" for item in report.diagnostics)


@pytest.mark.parametrize(
    ("source_identities", "sink_identities"),
    [(("opaque-source",), ("opaque-target",)), (("source", "alias"), ("target",))],
)
def test_managed_connector_write_allows_proven_disjoint_resources(
    source_identities: tuple[str, ...], sink_identities: tuple[str, ...]
) -> None:
    report, sink = _run_transfer(source_identities, sink_identities)

    assert report.status is RunStatus.SUCCEEDED
    assert sink.begin_calls == 1
