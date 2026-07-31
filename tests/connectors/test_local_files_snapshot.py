"""Local-files snapshot mode tests."""

from __future__ import annotations

import anyio
import pytest

from etlantic import Data, Extract, Load, Pipeline, PipelineRuntime, Profile
from etlantic.connectors.errors import ConnectorConfigError
from etlantic.connectors.local_files import LocalFilesSourceConnector
from etlantic.connectors.models import LandingReadManifest
from etlantic.io_policy import SafeIoPolicy
from etlantic.runtime.state import RunStatus


class RawEvent(Data):
    event_id: str
    payload: str


def _write_csv(path, rows: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "event_id,payload\n" + "".join(f"{a},{b}\n" for a, b in rows),
        encoding="utf-8",
    )


def test_local_files_snapshot_two_csvs(tmp_path) -> None:
    inbox = tmp_path / "inbox"
    _write_csv(inbox / "b.csv", [("2", "beta")])
    _write_csv(inbox / "a.csv", [("1", "alpha")])

    connector = LocalFilesSourceConnector()
    policy = SafeIoPolicy.for_root(tmp_path)
    binding = {
        "provider": "local-files",
        "format": "csv",
        "root": "inbox",
        "root_ref": "landing",
        "glob": "*.csv",
        "mode": "snapshot",
        "empty_match": "fail",
    }
    context: dict = {
        "run_id": "snap-1",
        "safe_io": policy,
        "contract_type": RawEvent,
    }

    async def _run() -> list:
        plan = await connector.plan_read(binding=binding, context=context)
        assert plan.mode == "snapshot"
        assert "root_ref" in plan.listing_intent
        records: list = []
        async for batch in connector.read_batches(
            plan=plan, binding=binding, context=context
        ):
            records.extend(batch.records)
        return records

    records = anyio.run(_run)
    assert len(records) == 2
    # Deterministic path order: a.csv then b.csv
    ids = [r.event_id if hasattr(r, "event_id") else r["event_id"] for r in records]
    assert ids == ["1", "2"]
    manifest = context.get("landing_read_manifest")
    assert isinstance(manifest, LandingReadManifest)
    assert manifest.file_count == 2
    assert manifest.root_ref == "landing"


def test_local_files_snapshot_pipeline(tmp_path) -> None:
    inbox = tmp_path / "inbox"
    _write_csv(inbox / "a.csv", [("1", "alpha")])
    _write_csv(inbox / "b.csv", [("2", "beta")])

    class LandingPipe(Pipeline):
        src = Extract[RawEvent](asset="landing_csv")
        out = Load[RawEvent](input=src, asset="curated")

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
                "mode": "snapshot",
            },
            "curated": "memory://curated",
        },
        safe_io={"approved_roots": [str(tmp_path)]},
    )
    runtime = PipelineRuntime()
    report = LandingPipe.run(profile=profile, runtime=runtime)
    assert report.status is RunStatus.SUCCEEDED
    rows = runtime.memory.get("curated")
    assert len(rows) == 2


def test_reject_absolute_and_recursive_glob(tmp_path) -> None:
    connector = LocalFilesSourceConnector()
    policy = SafeIoPolicy.for_root(tmp_path)

    async def _run() -> None:
        with pytest.raises(ConnectorConfigError, match="Absolute glob"):
            await connector.plan_read(
                binding={
                    "provider": "local-files",
                    "root": ".",
                    "glob": "/tmp/*.csv",
                    "mode": "snapshot",
                },
                context={"safe_io": policy, "run_id": "t"},
            )
        with pytest.raises(ConnectorConfigError, match="Recursive glob"):
            await connector.plan_read(
                binding={
                    "provider": "local-files",
                    "root": ".",
                    "glob": "**/*.csv",
                    "mode": "snapshot",
                },
                context={"safe_io": policy, "run_id": "t"},
            )

    anyio.run(_run)


def test_rename_done_preserves_nested_relative_paths(tmp_path) -> None:
    """Nested files with the same basename must not collide under .done/."""
    inbox = tmp_path / "inbox"
    _write_csv(inbox / "a" / "events.csv", [("1", "alpha")])
    _write_csv(inbox / "b" / "events.csv", [("2", "beta")])
    connector = LocalFilesSourceConnector(allow_recursive_glob=True)
    policy = SafeIoPolicy.for_root(tmp_path)
    binding = {
        "provider": "local-files",
        "format": "csv",
        "root": "inbox",
        "root_ref": "landing",
        "glob": "*/*.csv",
        "mode": "snapshot",
        "consume": "rename_done",
        "empty_match": "fail",
    }
    context: dict = {"run_id": "rename-nested", "safe_io": policy}

    async def _run() -> None:
        plan = await connector.plan_read(binding=binding, context=context)
        async for _ in connector.read_batches(
            plan=plan, binding=binding, context=context
        ):
            pass
        receipt = await connector.consume_after_commit(binding=binding, context=context)
        assert receipt.status == "completed"
        assert (inbox / ".done" / "a" / "events.csv").is_file()
        assert (inbox / ".done" / "b" / "events.csv").is_file()
        assert not (inbox / "a" / "events.csv").exists()
        assert not (inbox / "b" / "events.csv").exists()

    anyio.run(_run)
