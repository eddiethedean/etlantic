"""Fake Snowflake connector tests (no network / SDK)."""

from __future__ import annotations

import anyio
from etlantic_snowflake import FakeSnowflakeConnection, create_sink, create_source

from etlantic.connectors.protocol import SinkConnector, SourceConnector


def test_autocommit_off_and_query_id_evidence() -> None:
    conn = FakeSnowflakeConnection()
    assert conn.autocommit is False
    sink = create_sink()
    sink.connection = conn
    source = create_source()
    source.connection = conn
    binding = {
        "config": {
            "database": "DB",
            "schema": "PUBLIC",
            "table": "ORDERS",
            "mode": "append",
        }
    }

    async def _run() -> None:
        plan = await sink.plan_write(binding=binding, context={})
        session = await sink.begin_write(plan=plan, binding=binding, context={})
        assert session.metadata.get("autocommit") is False
        await sink.write_batch(session, [{"id": 1, "amt": 10}], context={})
        receipt = await sink.commit(session, context={})
        assert receipt.status == "committed"
        assert receipt.publication_id
        assert receipt.publication_id.startswith("sfqid-")
        assert receipt.metadata["query_id"] == receipt.publication_id
        assert receipt.metadata["autocommit"] is False

        src_plan = await source.plan_read(binding=binding, context={})
        batches = [
            b
            async for b in source.read_batches(
                plan=src_plan, binding=binding, context={}
            )
        ]
        assert list(batches[0].records) == [{"id": 1, "amt": 10}]

    anyio.run(_run)


def test_abort_rolls_back_transaction() -> None:
    conn = FakeSnowflakeConnection()
    sink = create_sink()
    sink.connection = conn
    binding = {"config": {"table": "T", "mode": "append"}}

    async def _run() -> None:
        plan = await sink.plan_write(binding=binding, context={})
        session = await sink.begin_write(plan=plan, binding=binding, context={})
        await sink.write_batch(session, [{"id": 9}], context={})
        await sink.prepare(session, context={})
        receipt = await sink.abort(session, context={})
        assert receipt.status == "rolled_back"
        assert conn.tables.get("T", []) == []

    anyio.run(_run)


def test_reconcile_by_query_id() -> None:
    conn = FakeSnowflakeConnection()
    sink = create_sink()
    sink.connection = conn
    binding = {"config": {"table": "T", "mode": "overwrite"}}

    async def _run() -> None:
        plan = await sink.plan_write(binding=binding, context={})
        session = await sink.begin_write(plan=plan, binding=binding, context={})
        await sink.write_batch(session, [{"id": 1}], context={})
        receipt = await sink.commit(session, context={})
        result = await sink.reconcile(receipt, context={})
        assert result.status == "committed"
        assert result.publication_id == receipt.publication_id

    anyio.run(_run)


def test_protocols() -> None:
    assert isinstance(create_source(), SourceConnector)
    assert isinstance(create_sink(), SinkConnector)
