"""Implementation regressions for bounded identities and lock contention."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from etlantic import io_policy
from etlantic.plan import physical
from etlantic.plan.physical import PhysicalUnit, PhysicalUnitKind


@pytest.mark.parametrize("transfer", [False, True])
def test_streamed_identity_preserves_canonical_wire_bytes(
    monkeypatch: pytest.MonkeyPatch, transfer: bool
) -> None:
    """Generation and read-side verification borrow frozen, nested envelopes."""
    payload: dict[str, Any] = {
        "kind": "transfer" if transfer else "compute",
        "target_identity": "target:local",
        "input_contracts": [{"name": "Row", "nullable": False}],
        "output_contracts": [{"name": "Row", "nullable": True}],
        "policy": {"execution": {"mode": "batch"}},
        "retry_policy": {"mode": "none"},
        "ownership": {"logical_node": "pair"},
        "protocol_versions": {"physical_unit": "etlantic.physical_unit/1"},
    }
    metadata = {"etlantic.note": ('雪\\"\n' * 5000)}
    if transfer:
        metadata.update(
            {
                "etlantic.edge_ports": ["raw", "pair", "result", "left"],
                "etlantic.source_target": "source:local",
                "etlantic.destination_target": "target:local",
                "etlantic.handoff_contract": {"format": "arrow"},
                "etlantic.handoff_evidence": ["sha256:" + "a" * 64],
            }
        )
        payload.update(
            edge=["raw", "result", "pair", "left"],
            source=metadata["etlantic.source_target"],
            destination=metadata["etlantic.destination_target"],
            handoff_contract=metadata["etlantic.handoff_contract"],
            handoff_evidence=metadata["etlantic.handoff_evidence"],
        )
    else:
        payload.update(logical_nodes=["pair"], metadata=metadata)
    expected = (
        "unit:"
        + hashlib.sha256(
            json.dumps(
                payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
        ).hexdigest()[:24]
    )
    unit = PhysicalUnit(
        identity=expected,
        kind=PhysicalUnitKind(payload["kind"]),
        target_identity=payload["target_identity"],
        logical_nodes=() if transfer else ("pair",),
        input_contracts=tuple(payload["input_contracts"]),
        output_contracts=tuple(payload["output_contracts"]),
        policy=payload["policy"],
        retry_policy=payload["retry_policy"],
        ownership=payload["ownership"],
        protocol_versions=payload["protocol_versions"],
        metadata=metadata,
    )
    original = json.dumps

    def primitives_only(value: Any, *args: Any, **kwargs: Any) -> str:
        assert not isinstance(value, Mapping), "identity allocated an object buffer"
        return original(value, *args, **kwargs)

    def no_copy(value: Any) -> Any:
        pytest.fail("identity copied its nested envelope")

    monkeypatch.setattr(physical.json, "dumps", primitives_only)
    monkeypatch.setattr(physical, "mutable_copy", no_copy)
    if transfer:
        assert physical._generated_transfer_identity(unit) == expected
    else:
        assert physical._generated_unit_identity(unit) == expected
        assert (
            physical.generated_unit_identity(
                kind=unit.kind,
                target_identity=unit.target_identity,
                logical_nodes=unit.logical_nodes,
                input_contracts=unit.input_contracts,
                output_contracts=unit.output_contracts,
                policy=unit.policy,
                retry_policy=unit.retry_policy,
                ownership=unit.ownership,
                protocol_versions=unit.protocol_versions,
                metadata=unit.metadata,
            )
            == expected
        )


@pytest.mark.parametrize("error_type", [FileExistsError, PermissionError])
def test_lock_waits_then_acquires_after_owner_releases(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, error_type: type[OSError]
) -> None:
    """Both contention signals wait; a disappearing POSIX lock remains retryable."""
    path = tmp_path / "report.json"
    lock = io_policy._lock_path(path)
    lock.touch()
    original = io_policy.os.open
    attempts = 0
    waits = []

    def contended_once(name: str, flags: int, mode: int = 0o777) -> int:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            if error_type is FileExistsError:
                lock.unlink()
            raise error_type("another writer holds the lock")
        return original(name, flags, mode)

    def release_owner(delay: float) -> None:
        waits.append(delay)
        lock.unlink(missing_ok=True)

    monkeypatch.setattr(io_policy.os, "open", contended_once)
    monkeypatch.setattr(io_policy.time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(io_policy.time, "sleep", release_owner)
    acquired = io_policy._acquire_lock(path, timeout=1.0)
    try:
        assert acquired == lock
        assert lock.read_text() == str(io_policy.os.getpid())
        assert attempts == 2
        assert waits == [0.05]
    finally:
        io_policy._release_lock(acquired)


def test_unrelated_lock_permission_failure_propagates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "report.json"
    error = PermissionError("parent is not writable")

    def denied(*args: Any, **kwargs: Any) -> int:
        raise error

    def unexpected_wait(delay: float) -> None:
        pytest.fail("an unrelated permission failure was treated as contention")

    monkeypatch.setattr(io_policy.os, "open", denied)
    monkeypatch.setattr(io_policy.time, "sleep", unexpected_wait)
    with pytest.raises(PermissionError) as caught:
        io_policy._acquire_lock(path, timeout=1.0)
    assert caught.value is error
