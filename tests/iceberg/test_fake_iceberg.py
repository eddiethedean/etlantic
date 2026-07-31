"""Fake Iceberg connector tests (no pyiceberg required)."""

from __future__ import annotations

import anyio
from etlantic_iceberg import FakeIcebergCatalog, create_sink, create_source

from etlantic.connectors.protocol import SinkConnector, SourceConnector


def test_snapshot_id_is_publication_identity() -> None:
    catalog = FakeIcebergCatalog()
    sink = create_sink()
    sink.catalog = catalog
    source = create_source()
    source.catalog = catalog
    binding = {"config": {"namespace": "ns", "table": "events", "mode": "append"}}

    async def _run() -> None:
        plan = await sink.plan_write(binding=binding, context={})
        session = await sink.begin_write(plan=plan, binding=binding, context={})
        await sink.write_batch(session, [{"id": 1}, {"id": 2}], context={})
        receipt = await sink.commit(session, context={})
        assert receipt.status == "committed"
        assert receipt.publication_id == "1"
        assert receipt.metadata["snapshot_id"] == 1

        src_plan = await source.plan_read(binding=binding, context={})
        batches = [
            b
            async for b in source.read_batches(
                plan=src_plan, binding=binding, context={}
            )
        ]
        assert list(batches[0].records) == [{"id": 1}, {"id": 2}]
        assert batches[0].metadata["snapshot_id"] == 1

    anyio.run(_run)


def test_abort_discards_staged_rows() -> None:
    sink = create_sink()
    binding = {"config": {"identifier": "db.t", "mode": "overwrite"}}

    async def _run() -> None:
        plan = await sink.plan_write(binding=binding, context={})
        session = await sink.begin_write(plan=plan, binding=binding, context={})
        await sink.write_batch(session, [{"x": 1}], context={})
        receipt = await sink.abort(session, context={})
        assert receipt.status == "rolled_back"
        assert sink.catalog.tables["db.t"].current_snapshot_id is None

    anyio.run(_run)


def test_protocols() -> None:
    assert isinstance(create_source(), SourceConnector)
    assert isinstance(create_sink(), SinkConnector)
    assert create_sink().info().metadata["publication_identity"] == "snapshot_id"
    assert "write.partition_replace" not in create_sink().info().capabilities


def test_abort_after_commit_does_not_rollback_published_snapshot() -> None:
    catalog = FakeIcebergCatalog()
    sink = create_sink()
    sink.catalog = catalog
    binding = {"config": {"identifier": "db.t", "mode": "append"}}

    async def _run() -> None:
        plan = await sink.plan_write(binding=binding, context={})
        session = await sink.begin_write(plan=plan, binding=binding, context={})
        await sink.write_batch(session, [{"x": 1}], context={})
        receipt = await sink.commit(session, context={})
        assert receipt.status == "committed"
        assert catalog.tables["db.t"].current_snapshot_id == 1
        abort_receipt = await sink.abort(session, context={})
        assert abort_receipt.status == "committed"
        assert catalog.tables["db.t"].current_snapshot_id == 1
        assert list(catalog.tables["db.t"].current_rows) == [{"x": 1}]

    anyio.run(_run)


def test_partition_replace_mode_rejected() -> None:
    sink = create_sink()

    async def _run() -> None:
        from etlantic.connectors.errors import ConnectorConfigError

        try:
            await sink.plan_write(
                binding={"config": {"identifier": "db.t", "mode": "partition_replace"}},
                context={},
            )
        except ConnectorConfigError as exc:
            assert exc.code == "PMCONN822"
            return
        raise AssertionError("partition_replace must be rejected")

    anyio.run(_run)
