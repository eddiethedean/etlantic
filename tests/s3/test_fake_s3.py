"""Fake-only S3 connector tests (no network)."""

from __future__ import annotations

import anyio
from etlantic_s3 import InMemoryS3Fake, create_sink, create_source, create_storage
from etlantic_s3.fake import boto3_available

from etlantic.connectors.protocol import (
    SinkConnector,
    SourceConnector,
    StorageConnector,
)


def test_factories_and_protocols() -> None:
    source = create_source()
    sink = create_sink()
    storage = create_storage()
    assert isinstance(source, SourceConnector)
    assert isinstance(sink, SinkConnector)
    assert isinstance(storage, StorageConnector)
    assert source.info().maturity.value == "experimental"
    assert sink.info().metadata.get("commit_pointer") == "conditional"


def test_multipart_abort_discards_parts() -> None:
    fake = InMemoryS3Fake()
    upload_id = fake.create_multipart_upload(bucket="b", key="k")
    fake.upload_part(upload_id=upload_id, part_number=1, body=b"abc")
    fake.abort_multipart_upload(upload_id=upload_id)
    assert fake.multiparts[upload_id].aborted is True
    assert fake.multiparts[upload_id].parts == {}
    assert ("b", "k") not in fake.objects


def test_conditional_commit_pointer_one_winner() -> None:
    fake = InMemoryS3Fake()
    fake.put_object(bucket="b", key="data/a", body=b'[{"x":1}]')
    fake.put_object(bucket="b", key="data/b", body=b'[{"x":2}]')
    first = fake.put_commit_pointer(
        bucket="b", pointer_key="ds.commit", data_key="data/a"
    )
    second = fake.put_commit_pointer(
        bucket="b", pointer_key="ds.commit", data_key="data/b"
    )
    assert first["ok"] is True
    assert second["ok"] is False
    assert second["status"] == "precondition_failed"
    resolved = fake.get_committed_object(bucket="b", pointer_key="ds.commit")
    assert resolved is not None
    assert resolved[0] == "data/a"


def test_sink_commit_and_source_reads_pointer_only() -> None:
    backend = InMemoryS3Fake()
    sink = create_sink()
    sink.backend = backend
    source = create_source()
    source.backend = backend
    binding = {
        "config": {
            "bucket": "lake",
            "prefix": "orders",
            "pointer_key": "orders.commit",
        }
    }

    async def _run() -> list:
        plan = await sink.plan_write(binding=binding, context={})
        session = await sink.begin_write(
            plan=plan, binding=binding, context={"run_id": "r1"}
        )
        await sink.write_batch(session, [{"id": 1}], context={})
        receipt = await sink.commit(session, context={})
        assert receipt.status == "committed"
        assert receipt.publication_id == "orders.commit"

        orphan = backend.create_multipart_upload(
            bucket="lake", key="orders/data/orphan.json"
        )
        backend.upload_part(upload_id=orphan, part_number=1, body=b'[{"id":99}]')
        committed = backend.get_committed_object(
            bucket="lake", pointer_key="orders.commit"
        )
        assert committed is not None
        assert committed[0] != "orders/data/orphan.json"

        src_plan = await source.plan_read(binding=binding, context={})
        return [
            b
            async for b in source.read_batches(
                plan=src_plan, binding=binding, context={}
            )
        ]

    batches = anyio.run(_run)
    assert len(batches) == 1
    assert list(batches[0].records) == [{"id": 1}]


def test_abort_after_prepare_cleans_orphan_object() -> None:
    backend = InMemoryS3Fake()
    sink = create_sink()
    sink.backend = backend
    binding = {"config": {"bucket": "lake", "prefix": "t", "pointer_key": "t.commit"}}

    async def _run() -> None:
        plan = await sink.plan_write(binding=binding, context={})
        session = await sink.begin_write(
            plan=plan, binding=binding, context={"run_id": "r2"}
        )
        await sink.write_batch(session, [{"n": 1}], context={})
        await sink.prepare(session, context={})
        data_key = sink._sessions[session.session_id]["data_key"]
        assert ("lake", data_key) in backend.objects
        receipt = await sink.abort(session, context={})
        assert receipt.status == "rolled_back"
        assert ("lake", data_key) not in backend.objects
        assert (
            backend.get_committed_object(bucket="lake", pointer_key="t.commit") is None
        )

    anyio.run(_run)


def test_reconcile_after_lost_commit() -> None:
    backend = InMemoryS3Fake()
    sink = create_sink()
    sink.backend = backend
    # create mode keeps If-None-Match; a rival pointer makes this writer lose.
    binding = {
        "config": {
            "bucket": "b",
            "prefix": "p",
            "pointer_key": "p.commit",
            "mode": "create",
        }
    }

    async def _run() -> None:
        plan = await sink.plan_write(binding=binding, context={})
        session = await sink.begin_write(
            plan=plan, binding=binding, context={"run_id": "r3"}
        )
        await sink.write_batch(session, [{"a": 1}], context={})
        rival_key = "p/data/rival.json"
        backend.put_object(bucket="b", key=rival_key, body=b"[]")
        backend.put_commit_pointer(
            bucket="b", pointer_key="p.commit", data_key=rival_key
        )
        receipt = await sink.commit(session, context={})
        assert receipt.status == "unknown"
        result = await sink.reconcile(receipt, context={"bucket": "b"})
        assert result.status == "rolled_back"

    anyio.run(_run)


def test_boto3_probe_is_bool() -> None:
    assert isinstance(boto3_available(), bool)


def test_second_overwrite_publish_succeeds() -> None:
    backend = InMemoryS3Fake()
    sink = create_sink()
    sink.backend = backend
    binding = {
        "config": {
            "bucket": "lake",
            "prefix": "orders",
            "pointer_key": "orders.commit",
            "mode": "overwrite",
        }
    }

    async def _publish(run_id: str, rows: list) -> None:
        plan = await sink.plan_write(binding=binding, context={})
        session = await sink.begin_write(
            plan=plan, binding=binding, context={"run_id": run_id}
        )
        await sink.write_batch(session, rows, context={})
        receipt = await sink.commit(session, context={})
        assert receipt.status == "committed"

    async def _run() -> list:
        await _publish("r1", [{"id": 1}])
        await _publish("r2", [{"id": 2}, {"id": 3}])
        source = create_source()
        source.backend = backend
        src_plan = await source.plan_read(binding=binding, context={})
        batches = [
            b
            async for b in source.read_batches(
                plan=src_plan, binding=binding, context={}
            )
        ]
        return list(batches[0].records)

    assert anyio.run(_run) == [{"id": 2}, {"id": 3}]


def test_multi_batch_serializes_as_one_json_array() -> None:
    backend = InMemoryS3Fake()
    sink = create_sink()
    sink.backend = backend
    binding = {
        "config": {
            "bucket": "b",
            "prefix": "p",
            "pointer_key": "p.commit",
            "mode": "append",
        }
    }

    async def _run() -> None:
        plan = await sink.plan_write(binding=binding, context={})
        session = await sink.begin_write(
            plan=plan, binding=binding, context={"run_id": "mb"}
        )
        await sink.write_batch(session, [{"a": 1}], context={})
        await sink.write_batch(session, [{"a": 2}], context={})
        receipt = await sink.commit(session, context={})
        assert receipt.status == "committed"
        assert sink.info().metadata.get("format") == "json"
        resolved = backend.get_committed_object(bucket="b", pointer_key="p.commit")
        assert resolved is not None
        _, payload = resolved
        assert payload.decode("utf-8") == '[{"a": 1}, {"a": 2}]'

    anyio.run(_run)
