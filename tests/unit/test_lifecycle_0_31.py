"""Unit tests for 0.31 lifecycle / state / write foundations."""

from __future__ import annotations

from etlantic.reliability import WriteMode, write_capability_for_mode
from etlantic.reliability_runtime import write_mode_for_request
from etlantic.runtime.incremental import (
    FileStateStore,
    IncrementalStrategy,
    MemoryStateStore,
    may_advance_state,
)
from etlantic.runtime.lifecycle_policy import (
    LifecycleAction,
    resolve_lifecycle_action,
    write_mode_for_lifecycle,
)
from etlantic.runtime.request import RunIntent, RunRequest
from etlantic.testing import run_lifecycle_conformance_suite


def test_write_mode_skip_if_exists_exists() -> None:
    assert WriteMode.SKIP_IF_EXISTS.value == "skip_if_exists"
    assert write_capability_for_mode(WriteMode.SKIP_IF_EXISTS) == "write.skip_if_exists"


def test_write_mode_for_request_intents() -> None:
    assert (
        write_mode_for_request(RunRequest(intent=RunIntent.VALIDATE))
        is WriteMode.NO_WRITE
    )
    assert (
        write_mode_for_request(RunRequest(intent=RunIntent.INCREMENTAL))
        is WriteMode.APPEND
    )
    assert (
        write_mode_for_request(RunRequest(intent=RunIntent.REFRESH))
        is WriteMode.OVERWRITE
    )
    assert (
        write_mode_for_request(
            RunRequest(intent=RunIntent.STANDARD), declared=WriteMode.MERGE
        )
        is WriteMode.MERGE
    )


def test_memory_state_store_commit_and_non_advancement() -> None:
    store = MemoryStateStore()
    store.commit("s", "1")
    assert may_advance_state(intent=RunIntent.STANDARD, no_write=False, succeeded=True)
    assert not may_advance_state(
        intent=RunIntent.VALIDATE, no_write=False, succeeded=True
    )
    t = store.commit("s", "2", reason="ok")
    assert t.from_status == "1"
    assert t.to_status == "2"
    assert store.get("s").value == "2"


def test_file_state_store_roundtrip(tmp_path) -> None:
    path = tmp_path / "state.json"
    store = FileStateStore(path)
    store.commit("wm", "2026-01-01")
    again = FileStateStore(path)
    assert again.get("wm").value == "2026-01-01"


def test_incremental_strategy_builders() -> None:
    wm = IncrementalStrategy.watermark(subject_id="orders", field="updated_at")
    assert wm.kind.value == "watermark"
    assert IncrementalStrategy.from_dict(wm.to_dict()).column == "updated_at"


def test_lifecycle_policy_actions() -> None:
    assert (
        resolve_lifecycle_action(intent=RunIntent.VALIDATE) is LifecycleAction.VALIDATE
    )
    assert write_mode_for_lifecycle(LifecycleAction.PRESERVE) is WriteMode.APPEND
    assert write_mode_for_lifecycle(LifecycleAction.REFRESH) is WriteMode.OVERWRITE


def test_lifecycle_conformance_suite() -> None:
    results = run_lifecycle_conformance_suite()
    assert results
    assert all(r["ok"] for r in results)
