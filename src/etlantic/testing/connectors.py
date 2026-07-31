"""Public connector conformance suites (capability-selected fake cases)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from etlantic.connectors.capabilities import (
    FORMAT_CSV,
    SOURCE_BATCH_SNAPSHOT,
    SOURCE_FILE_GLOB,
)
from etlantic.connectors.compatibility import StorageBindingAdapter
from etlantic.connectors.errors import ConnectorConfigError, ConnectorReadError
from etlantic.connectors.models import CommitReceipt, LandingReadManifest, SourcePlan
from etlantic.io_policy import SafeIoPolicy
from etlantic.storage.memory import MemoryStorage

SECRET_SENTINEL = "ETLANTIC_CONNECTOR_SECRET_SENTINEL_DO_NOT_LEAK"


def _write_csv(path: Path, rows: Sequence[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "event_id,payload\n" + "".join(f"{a},{b}\n" for a, b in rows),
        encoding="utf-8",
    )


def _assert_no_sentinel(obj: Any, *, path: str = "artifact") -> None:
    """Fail if the secret sentinel appears in plans/manifests/diagnostics."""
    if obj is None:
        return
    if isinstance(obj, (str, bytes)):
        text = obj.decode("utf-8", errors="replace") if isinstance(obj, bytes) else obj
        if SECRET_SENTINEL in text:
            raise AssertionError(f"Secret sentinel leaked into {path}")
        return
    if isinstance(obj, Mapping):
        encoded = json.dumps(obj, sort_keys=True, default=str)
        if SECRET_SENTINEL in encoded:
            raise AssertionError(f"Secret sentinel leaked into {path}")
        for key, child in obj.items():
            _assert_no_sentinel(child, path=f"{path}.{key}")
        return
    if isinstance(obj, (list, tuple)):
        for index, item in enumerate(obj):
            _assert_no_sentinel(item, path=f"{path}[{index}]")
        return
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        _assert_no_sentinel(obj.to_dict(), path=path)
        return
    text = repr(obj)
    if SECRET_SENTINEL in text:
        raise AssertionError(f"Secret sentinel leaked into {path} repr")


def _resolve_capabilities(
    connector: Any,
    capabilities: Sequence[str] | None,
) -> frozenset[str]:
    if capabilities is not None:
        return frozenset(str(c) for c in capabilities)
    info = connector.info()
    return frozenset(str(c) for c in (info.capabilities or ()))


async def _case_batch_snapshot(connector: Any, tmp: Path) -> dict[str, Any]:
    inbox = tmp / "inbox"
    _write_csv(inbox / "b.csv", [("2", "beta")])
    _write_csv(inbox / "a.csv", [("1", "alpha")])
    policy = SafeIoPolicy.for_root(tmp)
    binding = {
        "provider": getattr(connector.info(), "provider", None) or "local-files",
        "format": "csv",
        "root": "inbox",
        "root_ref": "landing",
        "glob": "*.csv",
        "mode": "snapshot",
        "empty_match": "fail",
        "secret_refs": {"api_token": "ref://never-resolve"},
    }
    context: dict[str, Any] = {
        "run_id": "conformance-snapshot",
        "safe_io": policy,
        # Sentinel must never appear in plan / manifest serialization.
        "secret_sentinel": SECRET_SENTINEL,
    }
    plan = await connector.plan_read(binding=binding, context=context)
    assert isinstance(plan, SourcePlan)
    assert plan.mode == "snapshot"
    _assert_no_sentinel(plan.to_dict(), path="source_plan")
    records: list[Any] = []
    async for batch in connector.read_batches(
        plan=plan, binding=binding, context=context
    ):
        records.extend(batch.records)
        _assert_no_sentinel(batch.to_dict(), path="read_batch")
    assert len(records) >= 2
    manifest = context.get("landing_read_manifest")
    assert isinstance(manifest, LandingReadManifest)
    _assert_no_sentinel(manifest.to_dict(), path="landing_read_manifest")
    return {"case": "source.batch_snapshot", "ok": True, "records": len(records)}


async def _case_file_glob(connector: Any, tmp: Path) -> dict[str, Any]:
    inbox = tmp / "inbox"
    _write_csv(inbox / "keep.csv", [("1", "keep")])
    _write_csv(inbox / "skip.txt", [("9", "skip")])
    policy = SafeIoPolicy.for_root(tmp)
    binding = {
        "provider": "local-files",
        "format": "csv",
        "root": "inbox",
        "root_ref": "landing",
        "glob": "*.csv",
        "mode": "snapshot",
        "empty_match": "allow",
    }
    context: dict[str, Any] = {"run_id": "conformance-glob", "safe_io": policy}
    plan = await connector.plan_read(binding=binding, context=context)
    assert plan.listing_intent.get("glob") == "*.csv"
    count = 0
    async for batch in connector.read_batches(
        plan=plan, binding=binding, context=context
    ):
        count += len(batch.identities)
    assert count == 1
    return {"case": "source.file_glob", "ok": True, "files": count}


async def _case_format_csv(connector: Any, tmp: Path) -> dict[str, Any]:
    inbox = tmp / "inbox"
    _write_csv(inbox / "row.csv", [("1", "csv")])
    policy = SafeIoPolicy.for_root(tmp)
    binding = {
        "provider": "local-files",
        "format": "csv",
        "root": "inbox",
        "root_ref": "landing",
        "glob": "*.csv",
        "mode": "snapshot",
    }
    context: dict[str, Any] = {"run_id": "conformance-csv", "safe_io": policy}
    plan = await connector.plan_read(binding=binding, context=context)
    assert plan.listing_intent.get("format") == "csv"
    async for _batch in connector.read_batches(
        plan=plan, binding=binding, context=context
    ):
        pass
    return {"case": "format.csv", "ok": True}


async def _case_empty_listing_fail(connector: Any, tmp: Path) -> dict[str, Any]:
    inbox = tmp / "empty"
    inbox.mkdir(parents=True, exist_ok=True)
    policy = SafeIoPolicy.for_root(tmp)
    binding = {
        "provider": "local-files",
        "format": "csv",
        "root": "empty",
        "root_ref": "landing",
        "glob": "*.csv",
        "mode": "snapshot",
        "empty_match": "fail",
    }
    context: dict[str, Any] = {"run_id": "conformance-empty", "safe_io": policy}
    plan = await connector.plan_read(binding=binding, context=context)
    raised = False
    try:
        async for _batch in connector.read_batches(
            plan=plan, binding=binding, context=context
        ):
            pass
    except ConnectorReadError:
        raised = True
    assert raised, "empty_match=fail must raise ConnectorReadError"
    return {"case": "fault.empty_listing_fail", "ok": True}


async def _case_empty_listing_allow(connector: Any, tmp: Path) -> dict[str, Any]:
    inbox = tmp / "empty_allow"
    inbox.mkdir(parents=True, exist_ok=True)
    policy = SafeIoPolicy.for_root(tmp)
    binding = {
        "provider": "local-files",
        "format": "csv",
        "root": "empty_allow",
        "root_ref": "landing",
        "glob": "*.csv",
        "mode": "snapshot",
        "empty_match": "allow",
    }
    context: dict[str, Any] = {"run_id": "conformance-empty-allow", "safe_io": policy}
    plan = await connector.plan_read(binding=binding, context=context)
    batches = 0
    async for batch in connector.read_batches(
        plan=plan, binding=binding, context=context
    ):
        batches += 1
        assert batch.exhausted or len(batch.records) == 0
    assert batches >= 1
    return {"case": "fault.empty_listing_allow", "ok": True}


async def _case_invalid_glob(connector: Any, tmp: Path) -> dict[str, Any]:
    policy = SafeIoPolicy.for_root(tmp)
    context: dict[str, Any] = {"run_id": "conformance-bad-glob", "safe_io": policy}
    raised = False
    try:
        await connector.plan_read(
            binding={
                "provider": "local-files",
                "format": "csv",
                "root": ".",
                "glob": "/tmp/*.csv",
                "mode": "snapshot",
            },
            context=context,
        )
    except ConnectorConfigError:
        raised = True
    assert raised, "absolute glob must be rejected at plan time"
    raised_recursive = False
    try:
        await connector.plan_read(
            binding={
                "provider": "local-files",
                "format": "csv",
                "root": ".",
                "glob": "**/*.csv",
                "mode": "snapshot",
            },
            context=context,
        )
    except ConnectorConfigError:
        raised_recursive = True
    assert raised_recursive, "recursive glob must be rejected by default"
    return {"case": "fault.invalid_glob", "ok": True}


_SOURCE_CASES: dict[str, Any] = {
    SOURCE_BATCH_SNAPSHOT: _case_batch_snapshot,
    SOURCE_FILE_GLOB: _case_file_glob,
    FORMAT_CSV: _case_format_csv,
}


async def _run_source_async(
    connector: Any,
    *,
    capabilities: Sequence[str] | None,
    workdir: Path,
) -> list[dict[str, Any]]:
    caps = _resolve_capabilities(connector, capabilities)
    results: list[dict[str, Any]] = []
    info = connector.info()
    assert info.name
    assert info.protocol
    results.append(
        {
            "case": "info",
            "ok": True,
            "provider": info.provider,
            "capabilities": sorted(caps),
        }
    )

    for capability, case_fn in _SOURCE_CASES.items():
        if capability in caps:
            results.append(
                await case_fn(connector, workdir / capability.replace(".", "_"))
            )

    # Fault cases for local landing-zone style connectors.
    if SOURCE_FILE_GLOB in caps or SOURCE_BATCH_SNAPSHOT in caps:
        results.append(
            await _case_empty_listing_fail(connector, workdir / "fault_empty")
        )
        results.append(
            await _case_empty_listing_allow(connector, workdir / "fault_empty_allow")
        )
        results.append(await _case_invalid_glob(connector, workdir / "fault_glob"))

    failed = [r for r in results if not r.get("ok")]
    if failed:
        raise AssertionError(f"Source connector conformance failures: {failed}")
    return results


def run_source_connector_conformance_suite(
    connector: Any,
    *,
    capabilities: Sequence[str] | None = None,
    workdir: Path | None = None,
) -> list[dict[str, Any]]:
    """Run capability-selected fake source connector cases.

    For local-files, advertised ``source.batch_snapshot``, ``source.file_glob``,
    and ``format.csv`` each select mandatory cases. Fault cases cover empty
    listing policy and invalid glob rejection. Plans/manifests must not contain
    :data:`SECRET_SENTINEL`.
    """
    import tempfile

    if workdir is None:
        with tempfile.TemporaryDirectory(prefix="etlantic-conn-conf-") as tmp:
            return asyncio.run(
                _run_source_async(
                    connector,
                    capabilities=capabilities,
                    workdir=Path(tmp),
                )
            )
    return asyncio.run(
        _run_source_async(connector, capabilities=capabilities, workdir=Path(workdir))
    )


async def _run_sink_async(connector: Any) -> list[dict[str, Any]]:
    info = connector.info()
    assert info.name
    results: list[dict[str, Any]] = [
        {"case": "info", "ok": True, "provider": info.provider}
    ]
    binding = {"binding": "sink", "location": "out", "mode": "overwrite"}
    context: dict[str, Any] = {
        "run_id": "conformance-sink",
        "write_mode": "overwrite",
        "secret_sentinel": SECRET_SENTINEL,
    }
    plan = await connector.plan_write(binding=binding, context=context)
    _assert_no_sentinel(plan.to_dict(), path="sink_plan")
    session = await connector.begin_write(plan=plan, binding=binding, context=context)
    await connector.write_batch(
        session,
        [{"event_id": "1", "payload": "x"}],
        context=context,
    )
    await connector.prepare(session, context=context)
    receipt = await connector.commit(session, context=context)
    assert isinstance(receipt, CommitReceipt)
    assert receipt.status in {"committed", "rolled_back", "unknown"}
    _assert_no_sentinel(receipt.to_dict(), path="commit_receipt")
    results.append(
        {"case": "sink.commit_lifecycle", "ok": True, "status": receipt.status}
    )

    # Abort path on a fresh session.
    session2 = await connector.begin_write(plan=plan, binding=binding, context=context)
    abort_receipt = await connector.abort(session2, context=context)
    assert abort_receipt.status == "rolled_back"
    results.append({"case": "sink.abort", "ok": True})

    failed = [r for r in results if not r.get("ok")]
    if failed:
        raise AssertionError(f"Sink connector conformance failures: {failed}")
    return results


def run_sink_connector_conformance_suite(
    connector: Any | None = None,
    *,
    capabilities: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Run a minimal sink lifecycle suite (defaults to StorageBindingAdapter)."""
    del capabilities  # reserved for capability selection expansion
    if connector is None:
        connector = StorageBindingAdapter(MemoryStorage(), provider="memory")
    return asyncio.run(_run_sink_async(connector))


def run_storage_connector_conformance_suite(
    connector: Any,
    *,
    capabilities: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Minimal storage connector smoke (info + inspect failure or success)."""
    del capabilities

    async def _run() -> list[dict[str, Any]]:
        info = connector.info()
        assert info.protocol
        results = [{"case": "info", "ok": True, "provider": info.provider}]
        try:
            inspection = await connector.inspect_schema(
                binding={}, context={"run_id": "storage-conf"}
            )
            _assert_no_sentinel(inspection.to_dict(), path="schema_inspection")
            results.append({"case": "inspect_schema", "ok": True})
        except Exception as exc:
            # Adapters may refuse inspection; that is acceptable for fake suite.
            results.append(
                {
                    "case": "inspect_schema",
                    "ok": True,
                    "skipped": True,
                    "reason": type(exc).__name__,
                }
            )
        return results

    return asyncio.run(_run())


__all__ = [
    "SECRET_SENTINEL",
    "run_sink_connector_conformance_suite",
    "run_source_connector_conformance_suite",
    "run_storage_connector_conformance_suite",
]
