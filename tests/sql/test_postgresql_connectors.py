"""PostgreSQL connector fake tests (sqlite; no live Postgres)."""

from __future__ import annotations

import anyio

from etlantic.connectors.protocol import SinkConnector, SourceConnector
from etlantic_sql.connectors import create_sink, create_source


def test_commit_rollback_and_query_id() -> None:
    sink = create_sink()
    source = create_source()
    # Share the fake connection so source sees committed rows.
    source.connection = sink.connection
    binding = {"config": {"schema": "public", "table": "orders", "mode": "append"}}

    async def _run() -> None:
        plan = await sink.plan_write(binding=binding, context={})
        session = await sink.begin_write(plan=plan, binding=binding, context={})
        await sink.write_batch(
            session,
            [{"id": "1", "payload": "a"}, {"id": "2", "payload": "b"}],
            context={},
        )
        receipt = await sink.commit(session, context={})
        assert receipt.status == "committed"
        assert receipt.publication_id
        assert receipt.publication_id.startswith("pgqid-")

        src_plan = await source.plan_read(binding=binding, context={})
        batches = [
            b
            async for b in source.read_batches(
                plan=src_plan, binding=binding, context={}
            )
        ]
        assert {r["id"] for r in batches[0].records} == {"1", "2"}

        # Abort path leaves no new rows.
        plan2 = await sink.plan_write(
            binding={**binding, "config": {**binding["config"], "mode": "append"}},
            context={},
        )
        session2 = await sink.begin_write(plan=plan2, binding=binding, context={})
        await sink.write_batch(session2, [{"id": "3", "payload": "c"}], context={})
        await sink.prepare(session2, context={})
        aborted = await sink.abort(session2, context={})
        assert aborted.status == "rolled_back"

        batches2 = [
            b
            async for b in source.read_batches(
                plan=src_plan, binding=binding, context={}
            )
        ]
        assert {r["id"] for r in batches2[0].records} == {"1", "2"}

    anyio.run(_run)


def test_merge_upsert() -> None:
    sink = create_sink()
    binding = {"config": {"table": "items", "mode": "merge"}}

    async def _run() -> None:
        plan = await sink.plan_write(binding=binding, context={})
        s1 = await sink.begin_write(plan=plan, binding=binding, context={})
        await sink.write_batch(s1, [{"id": "a", "payload": "1"}], context={})
        await sink.commit(s1, context={})
        s2 = await sink.begin_write(plan=plan, binding=binding, context={})
        await sink.write_batch(s2, [{"id": "a", "payload": "2"}], context={})
        await sink.commit(s2, context={})
        rows = sink.connection.select("items")
        assert len(rows) == 1
        assert rows[0]["payload"] == "2"

    anyio.run(_run)


def test_protocols_and_matrix_metadata() -> None:
    assert isinstance(create_source(), SourceConnector)
    assert isinstance(create_sink(), SinkConnector)
    caps = set(create_sink().info().capabilities)
    assert "transactions" in caps
    assert "write.merge" in caps
    assert "reconciliation" in caps
