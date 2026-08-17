"""Fake-only Kafka connector tests (no broker, no librdkafka)."""

from __future__ import annotations

import os

import anyio
import pytest
from etlantic_kafka import FakeKafka, create_sink, create_source, live_bootstrap

from etlantic.connectors.protocol import SinkConnector, SourceConnector

pytestmark = pytest.mark.kafka


def test_factories_and_protocols() -> None:
    source = create_source()
    sink = create_sink()
    assert isinstance(source, SourceConnector)
    assert isinstance(sink, SinkConnector)
    assert source.info().maturity.value == "experimental"
    assert "source.stream" in source.info().capabilities
    assert "sink.exactly_once" in sink.info().capabilities


def test_fake_produce_fetch_and_outage() -> None:
    broker = FakeKafka(partitions=2)
    broker.produce(0, {"id": "a"})
    assert broker.fetch(0, 0) == [{"id": "a"}]
    broker.inject_outage(True)
    with pytest.raises(ConnectionError):
        broker.fetch(0, 0)
    gen = broker.rebalance()
    assert gen == 1


def test_txn_commit_and_abort() -> None:
    broker = FakeKafka(partitions=1)
    broker.begin_txn("t1")
    broker.produce(0, {"id": "x"}, txn="t1")
    assert broker.fetch(0, 0) == []
    broker.commit_txn("t1")
    assert broker.fetch(0, 0) == [{"id": "x"}]
    broker.begin_txn("t2")
    broker.produce(0, {"id": "y"}, txn="t2")
    broker.abort_txn("t2")
    assert [r["id"] for r in broker.fetch(0, 0)] == ["x"]


def test_sink_commit_source_read_without_payloads_in_plan() -> None:
    broker = FakeKafka()
    sink = create_sink()
    sink._broker = broker
    source = create_source()
    source._broker = broker
    binding = {"topic": "events"}

    async def _run() -> tuple[object, object]:
        plan = await sink.plan_write(binding=binding, context={})
        assert "payload" not in plan.to_dict() if hasattr(plan, "to_dict") else True
        session = await sink.begin_write(plan=plan, binding=binding, context={})
        await sink.write_batch(session, {"value_id": "r1"}, context={})
        receipt = await sink.commit(session, context={})
        src_plan = await source.plan_read(binding=binding, context={})
        batches = [
            b
            async for b in source.read_batches(
                plan=src_plan, binding=binding, context={}
            )
        ]
        return receipt.status, list(batches[0].records)

    status, records = anyio.run(_run)
    assert status == "committed"
    assert records == [{"value_id": "r1"}]


def test_overlapping_sink_sessions_keep_distinct_records() -> None:
    broker = FakeKafka(partitions=1)
    sink = create_sink()
    sink._broker = broker

    async def _run() -> tuple[str, str, list[dict[str, object]]]:
        plan = await sink.plan_write(binding={"topic": "events"}, context={})
        session_a = await sink.begin_write(
            plan=plan, binding={"topic": "events"}, context={}
        )
        await sink.write_batch(session_a, {"id": "A"}, context={})
        session_b = await sink.begin_write(
            plan=plan, binding={"topic": "events"}, context={}
        )
        await sink.write_batch(session_b, {"id": "B"}, context={})
        rec_a = await sink.commit(session_a, context={})
        rec_b = await sink.commit(session_b, context={})
        assert rec_a.status == "committed"
        assert rec_b.status == "committed"
        assert session_a.session_id != session_b.session_id
        return session_a.session_id, session_b.session_id, list(broker.fetch(0, 0))

    _id_a, _id_b, records = anyio.run(_run)
    assert {row["id"] for row in records} == {"A", "B"}


def test_live_broker_skipped_unless_env() -> None:
    if live_bootstrap():
        pytest.skip("live Kafka opt-in is Experimental and not part of default CI")
    assert os.environ.get("ETLANTIC_KAFKA_BOOTSTRAP") in (None, "")
