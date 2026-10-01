"""Bounded event idempotency tombstone cleanup qualification."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.memory import MemoryEventStore
from etlantic_sqlmodel.control_plane import (
    SqlModelEventStore,
    create_control_plane_tables,
    create_sqlite_engine,
)


def _ctx(tenant: str = "retention-tenant") -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="event-retention-test"),
        tenant=TenantRef(tenant_id=tenant),
        workspace=WorkspaceRef(tenant_id=tenant, workspace_id="retention-workspace"),
        environment=EnvironmentRef(name="test"),
        security_domain=SecurityDomain(domain_id="event-retention-tests"),
    )


def _expired_after(retention_seconds: int) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=retention_seconds + 5)


def test_memory_event_tombstone_pruning_is_bounded_scoped_and_allows_expired_retry() -> (
    None
):
    store = MemoryEventStore(idempotency_retention_seconds=1)
    ctx = _ctx()
    other = _ctx(tenant="other-tenant")
    for key in ("one", "two", "three"):
        store.append_once(ctx, event_key=key, kind="run.started", payload={"key": key})
    other_event = store.append_once(
        other, event_key="other", kind="run.started", payload={"key": "other"}
    )
    expired_at = _expired_after(1)

    assert store.prune_expired_idempotency(ctx, limit=2, now=expired_at) == 2
    assert store.prune_expired_idempotency(ctx, limit=2, now=expired_at) == 1
    assert store.prune_expired_idempotency(ctx, limit=2, now=expired_at) == 0
    assert (
        store.append_once(
            other, event_key="other", kind="run.started", payload={"key": "other"}
        ).event_id
        == other_event.event_id
    )

    replacement = store.append_once(
        ctx, event_key="one", kind="run.started", payload={"key": "one"}
    )
    assert replacement.sequence == 4
    assert len(store.list_after_cursor(ctx, None)) == 4


@pytest.mark.parametrize("limit", [0, -1, 1001, True, 1.5])
def test_memory_event_tombstone_pruning_rejects_invalid_batch(limit: Any) -> None:
    with pytest.raises(ValueError, match="between 1 and 1000"):
        MemoryEventStore().prune_expired_idempotency(
            _ctx(),
            limit=limit,
            now=datetime.now(UTC),
        )


def test_sqlite_event_tombstone_pruning_is_bounded_scoped_and_durable(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'event-tombstone-prune.db'}")
    create_control_plane_tables(engine)
    ctx = _ctx()
    other = _ctx(tenant="other-tenant")
    store = SqlModelEventStore(engine, idempotency_retention_seconds=1)
    for key in ("one", "two", "three"):
        store.append_once(ctx, event_key=key, kind="run.started", payload={"key": key})
    other_event = store.append_once(
        other, event_key="other", kind="run.started", payload={"key": "other"}
    )
    expired_at = _expired_after(1)

    assert store.prune_expired_idempotency(ctx, limit=2, now=expired_at) == 2
    assert store.prune_expired_idempotency(ctx, limit=2, now=expired_at) == 1
    assert store.prune_expired_idempotency(ctx, limit=2, now=expired_at) == 0
    assert (
        store.append_once(
            other, event_key="other", kind="run.started", payload={"key": "other"}
        ).event_id
        == other_event.event_id
    )

    replacement = store.append_once(
        ctx, event_key="one", kind="run.started", payload={"key": "one"}
    )
    assert replacement.sequence == 4
    assert [event.sequence for event in store.list_after_cursor(ctx, None)] == [
        1,
        2,
        3,
        4,
    ]

    restarted_engine = create_sqlite_engine(
        f"sqlite:///{tmp_path / 'event-tombstone-prune.db'}"
    )
    restarted = SqlModelEventStore(restarted_engine, idempotency_retention_seconds=1)
    assert (
        restarted.append_once(
            other, event_key="other", kind="run.started", payload={"key": "other"}
        ).event_id
        == other_event.event_id
    )
    restarted_engine.dispose()
    engine.dispose()


@pytest.mark.parametrize("limit", [0, -1, 1001, True, 1.5])
def test_sqlite_event_tombstone_pruning_rejects_invalid_batch(
    tmp_path: Path, limit: Any
) -> None:
    engine = create_sqlite_engine(
        f"sqlite:///{tmp_path / 'event-tombstone-invalid.db'}"
    )
    create_control_plane_tables(engine)
    try:
        with pytest.raises(ValueError, match="between 1 and 1000"):
            SqlModelEventStore(engine).prune_expired_idempotency(
                _ctx(),
                limit=limit,
                now=datetime.now(UTC),
            )
    finally:
        engine.dispose()
