"""Local-files incremental ledger + commit-barrier tests."""

from __future__ import annotations

from pathlib import Path

import anyio

from etlantic import Data, Extract, Load, Pipeline, PipelineRuntime, Profile
from etlantic.connectors.checkpoint import (
    checkpoint_path_for,
    load_landing_checkpoint,
)
from etlantic.connectors.local_files import LocalFilesSourceConnector
from etlantic.connectors.models import CommitReceipt
from etlantic.io_policy import SafeIoPolicy
from etlantic.runtime.state import RunStatus


class RawEvent(Data):
    event_id: str
    payload: str


def _write_csv(path: Path, rows: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "event_id,payload\n" + "".join(f"{a},{b}\n" for a, b in rows),
        encoding="utf-8",
    )


def _landing_profile(tmp_path: Path, *, mode: str = "incremental") -> Profile:
    return Profile(
        name="dev",
        security_mode="development",
        assets={
            "landing_csv": {
                "provider": "local-files",
                "format": "csv",
                "root": "inbox",
                "root_ref": "landing",
                "glob": "*.csv",
                "mode": mode,
                "consume": "ledger",
                "checkpoint": "landing_csv_checkpoint",
            },
            "curated": "memory://curated",
        },
        safe_io={"approved_roots": [str(tmp_path)]},
    )


class LandingPipe(Pipeline):
    src = Extract[RawEvent](asset="landing_csv")
    out = Load[RawEvent](input=src, asset="curated")


def test_incremental_second_run_only_new_file(tmp_path) -> None:
    inbox = tmp_path / "inbox"
    _write_csv(inbox / "a.csv", [("1", "alpha")])

    profile = _landing_profile(tmp_path)
    runtime = PipelineRuntime()
    # Fresh connector instance per runtime is default; register explicit.
    runtime.register_source_connector("local-files", LocalFilesSourceConnector())

    report1 = LandingPipe.run(profile=profile, runtime=runtime)
    assert report1.status is RunStatus.SUCCEEDED
    assert len(runtime.memory.get("curated")) == 1

    _write_csv(inbox / "b.csv", [("2", "beta")])
    # New connector instance avoids stale lease state across runs.
    runtime.register_source_connector("local-files", LocalFilesSourceConnector())
    report2 = LandingPipe.run(profile=profile, runtime=runtime)
    assert report2.status is RunStatus.SUCCEEDED
    # Overwrite sink: only the new file's rows.
    rows = runtime.memory.get("curated")
    ids = [r.event_id if hasattr(r, "event_id") else r["event_id"] for r in rows]
    assert ids == ["2"]

    policy = SafeIoPolicy.for_root(tmp_path)
    ckpt_path = checkpoint_path_for(inbox, "landing_csv_checkpoint")
    ckpt = load_landing_checkpoint(ckpt_path, policy=policy, run_id="verify")
    assert ckpt is not None
    assert len(ckpt.committed_identities) == 2


def test_failed_load_does_not_advance_checkpoint(tmp_path) -> None:
    inbox = tmp_path / "inbox"
    _write_csv(inbox / "a.csv", [("1", "alpha")])

    class BoomStorage:
        name = "boom"

        async def read(self, **kwargs):
            return []

        async def write(self, **kwargs):
            raise RuntimeError("load failed")

    profile = Profile(
        name="dev",
        security_mode="development",
        assets={
            "landing_csv": {
                "provider": "local-files",
                "format": "csv",
                "root": "inbox",
                "root_ref": "landing",
                "glob": "*.csv",
                "mode": "incremental",
                "consume": "ledger",
                "checkpoint": "landing_csv_checkpoint",
            },
            "curated": "boom://curated",
        },
        safe_io={"approved_roots": [str(tmp_path)]},
    )
    runtime = PipelineRuntime()
    runtime.register_storage("boom", BoomStorage())  # type: ignore[arg-type]
    runtime.register_source_connector("local-files", LocalFilesSourceConnector())

    report = LandingPipe.run(profile=profile, runtime=runtime)
    assert report.status is not RunStatus.SUCCEEDED

    policy = SafeIoPolicy.for_root(tmp_path)
    ckpt_path = checkpoint_path_for(inbox, "landing_csv_checkpoint")
    ckpt = load_landing_checkpoint(ckpt_path, policy=policy, run_id="verify")
    # Missing or empty generation-0 ledger — not advanced.
    if ckpt is not None:
        assert ckpt.committed_identities == ()
        assert ckpt.generation == 0


def test_commit_receipt_barrier_unit(tmp_path) -> None:
    inbox = tmp_path / "inbox"
    _write_csv(inbox / "a.csv", [("1", "alpha")])
    connector = LocalFilesSourceConnector()
    policy = SafeIoPolicy.for_root(tmp_path)
    binding = {
        "provider": "local-files",
        "format": "csv",
        "root": "inbox",
        "root_ref": "landing",
        "glob": "*.csv",
        "mode": "incremental",
        "consume": "ledger",
        "checkpoint": "landing_csv_checkpoint",
        "config": {
            "mode": "incremental",
            "glob": "*.csv",
            "root": "inbox",
            "root_ref": "landing",
            "checkpoint": "landing_csv_checkpoint",
            "format": "csv",
        },
    }
    context: dict = {
        "run_id": "inc-1",
        "safe_io": policy,
        "contract_type": RawEvent,
        "pipeline_id": "p",
        "node": "src",
    }

    async def _run() -> None:
        plan = await connector.plan_read(binding=binding, context=context)
        records: list = []
        async for batch in connector.read_batches(
            plan=plan, binding=binding, context=context
        ):
            records.extend(batch.records)
        assert len(records) == 1
        manifest = context["landing_read_manifest"]
        await connector.propose_cursor(plan=plan, manifest=manifest, context=context)
        # Failed publication — discard, no advance.
        connector.discard_proposal()
        ckpt_path = checkpoint_path_for(inbox, "landing_csv_checkpoint")
        assert load_landing_checkpoint(ckpt_path, policy=policy) is None

        # Second attempt: commit after receipt.
        connector2 = LocalFilesSourceConnector()
        context2 = dict(context)
        plan2 = await connector2.plan_read(binding=binding, context=context2)
        async for _ in connector2.read_batches(
            plan=plan2, binding=binding, context=context2
        ):
            pass
        manifest2 = context2["landing_read_manifest"]
        await connector2.propose_cursor(
            plan=plan2, manifest=manifest2, context=context2
        )
        receipt = CommitReceipt(status="committed", publication_id="pub-1")
        await connector2.commit_ledger(
            publication_id=receipt.publication_id, context=context2
        )
        await connector2.consume_after_commit(binding=binding, context=context2)
        ckpt = load_landing_checkpoint(ckpt_path, policy=policy)
        assert ckpt is not None
        assert len(ckpt.committed_identities) == 1
        assert ckpt.generation == 1

    anyio.run(_run)
