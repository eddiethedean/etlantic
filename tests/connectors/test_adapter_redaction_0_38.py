"""StorageBindingAdapter receipt redaction and unknown-outcome status."""

from __future__ import annotations

import anyio

from etlantic.connectors.compatibility import StorageBindingAdapter
from etlantic.storage.memory import MemoryStorage


class _BoomStorage:
    name = "boom"

    async def write(self, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("write failed")


def test_adapter_receipt_metadata_strips_secret() -> None:
    adapter = StorageBindingAdapter(MemoryStorage(), provider="memory")

    async def _run() -> None:
        plan = await adapter.plan_write(
            binding={"name": "out", "mode": "overwrite"},
            context={"run_id": "r1", "secret": "hunter2"},
        )
        session = await adapter.begin_write(
            plan=plan,
            binding={"name": "out"},
            context={"run_id": "r1", "secret": "hunter2", "write_mode": "overwrite"},
        )
        await adapter.write_batch(session, [{"id": 1}], context={"secret": "hunter2"})
        receipt = await adapter.commit(
            session,
            context={"run_id": "r1", "secret": "hunter2", "node": "sink"},
        )
        assert receipt.status == "committed"
        assert "hunter2" not in str(receipt.metadata)
        assert "secret" not in receipt.metadata
        assert receipt.metadata.get("adapter") is True
        assert receipt.metadata.get("run_id") == "r1"
        assert receipt.metadata.get("node") == "sink"
        assert receipt.metadata.get("write_mode") == "overwrite"

        plan2 = await adapter.plan_write(binding={"name": "x"}, context={})
        session2 = await adapter.begin_write(
            plan=plan2, binding={"name": "x"}, context={}
        )
        aborted = await adapter.abort(
            session2, context={"secret": "hunter2", "run_id": "abort-1"}
        )
        assert aborted.status == "rolled_back"
        assert "hunter2" not in str(aborted.metadata)
        assert "secret" not in aborted.metadata
        assert aborted.metadata.get("run_id") == "abort-1"

        recon = await adapter.reconcile(
            aborted, context={"secret": "hunter2", "run_id": "recon"}
        )
        assert "hunter2" not in str(recon.metadata)
        assert "secret" not in recon.metadata

        cleaned = await adapter.cleanup(
            aborted, context={"secret": "hunter2", "run_id": "clean"}
        )
        assert "hunter2" not in str(cleaned.metadata)
        assert "secret" not in cleaned.metadata

    anyio.run(_run)


def test_adapter_write_failure_is_unknown_not_rolled_back() -> None:
    adapter = StorageBindingAdapter(_BoomStorage(), provider="boom")  # type: ignore[arg-type]

    async def _run() -> None:
        plan = await adapter.plan_write(binding={"name": "out"}, context={})
        session = await adapter.begin_write(
            plan=plan, binding={"name": "out"}, context={"secret": "hunter2"}
        )
        await adapter.write_batch(session, [{"id": 1}], context={})
        receipt = await adapter.commit(
            session, context={"secret": "hunter2", "run_id": "fail"}
        )
        assert receipt.status == "unknown"
        assert "hunter2" not in str(receipt.metadata)
        assert "secret" not in receipt.metadata

    anyio.run(_run)


def test_adapter_abort_stays_rolled_back() -> None:
    adapter = StorageBindingAdapter(MemoryStorage(), provider="memory")

    async def _run() -> None:
        plan = await adapter.plan_write(binding={"name": "out"}, context={})
        session = await adapter.begin_write(
            plan=plan, binding={"name": "out"}, context={}
        )
        receipt = await adapter.abort(session, context={"run_id": "a1"})
        assert receipt.status == "rolled_back"

    anyio.run(_run)
