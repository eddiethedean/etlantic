"""Lifecycle conformance suite for run intents, state, and write modes (0.31)."""

from __future__ import annotations

from typing import Any

from etlantic.reliability import WriteMode
from etlantic.reliability_runtime import write_mode_for_request
from etlantic.runtime.incremental import MemoryStateStore, may_advance_state
from etlantic.runtime.request import RunIntent, RunRequest


def run_lifecycle_conformance_suite() -> list[dict[str, Any]]:
    """Exercise portable lifecycle invariants independent of engine plugins."""
    results: list[dict[str, Any]] = []

    # VALIDATE / no_write never mutate.
    validate_req = RunRequest(intent=RunIntent.VALIDATE)
    results.append(
        {
            "case": "validate_no_write",
            "write_mode": write_mode_for_request(validate_req).value,
            "ok": write_mode_for_request(validate_req) is WriteMode.NO_WRITE,
        }
    )

    # Intent defaults.
    for intent, expected in (
        (RunIntent.INITIALIZE, WriteMode.OVERWRITE),
        (RunIntent.REFRESH, WriteMode.OVERWRITE),
        (RunIntent.INCREMENTAL, WriteMode.APPEND),
        (RunIntent.STANDARD, WriteMode.OVERWRITE),
    ):
        mode = write_mode_for_request(RunRequest(intent=intent))
        results.append(
            {
                "case": f"intent_default_{intent.value}",
                "write_mode": mode.value,
                "ok": mode is expected,
            }
        )

    # Declared sink intent wins over STANDARD default.
    declared = write_mode_for_request(
        RunRequest(intent=RunIntent.STANDARD),
        declared=WriteMode.APPEND,
    )
    results.append(
        {
            "case": "declared_overrides_standard",
            "write_mode": declared.value,
            "ok": declared is WriteMode.APPEND,
        }
    )

    # State advancement rules.
    store = MemoryStateStore()
    store.commit("orders", "100", reason="seed")
    assert may_advance_state(
        intent=RunIntent.INCREMENTAL, no_write=False, succeeded=True
    )
    assert not may_advance_state(
        intent=RunIntent.VALIDATE, no_write=False, succeeded=True
    )
    assert not may_advance_state(
        intent=RunIntent.INCREMENTAL, no_write=True, succeeded=True
    )
    assert not may_advance_state(
        intent=RunIntent.INCREMENTAL, no_write=False, succeeded=False
    )
    before = store.get("orders")
    if not may_advance_state(intent=RunIntent.VALIDATE, no_write=True, succeeded=True):
        # VALIDATE must leave committed state untouched.
        after = store.get("orders")
        results.append(
            {
                "case": "validate_does_not_advance_state",
                "ok": before is not None
                and after is not None
                and before.value == after.value == "100",
            }
        )
    transition = store.commit("orders", "200", reason="materialized:out")
    results.append(
        {
            "case": "commit_after_materialization",
            "ok": transition.to_status == "200" and store.get("orders").value == "200",
        }
    )

    failed = [r for r in results if not r.get("ok")]
    if failed:
        raise AssertionError(f"Lifecycle conformance failures: {failed}")
    return results
