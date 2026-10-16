"""PostgreSQL qualification for external timer mutation locking."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")

from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    MemoryScheduleStore,
    Principal,
    ScheduleSpec,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic_sqlmodel.control_plane import SQLModelScheduleStore
from etlantic_sqlmodel.migrations import upgrade

pytestmark = pytest.mark.sqlmodel


def _postgres_url() -> str:
    url = os.environ.get("ETLANTIC_SQLMODEL_TEST_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("set ETLANTIC_SQLMODEL_TEST_URL for live PostgreSQL qualification")
    return url


def _advisory_lock_id(store_id: str) -> int:
    digest = hashlib.sha256(("schedule:" + store_id).encode("utf-8")).digest()[:8]
    return int.from_bytes(digest, byteorder="big", signed=True)


def _context(store_id: str) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal("phase061-timer-test"),
        tenant=TenantRef(store_id),
        workspace=WorkspaceRef(store_id, "workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("phase061-timer-test"),
    )


def test_snapshot_query_error_releases_session_advisory_lock() -> None:
    url = _postgres_url()
    admin_engine = create_engine(url)
    schema = "phase061_timer_" + uuid.uuid4().hex
    scoped_engine = None
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))

        scoped_engine = create_engine(
            url, connect_args={"options": f"-c search_path={schema}"}
        )

        store_id = "phase061-lock-cleanup-" + uuid.uuid4().hex
        store = SQLModelScheduleStore(scoped_engine, store_id=store_id)
        ctx = _context(store_id)

        # The private schema has no schedule snapshot table, so the SELECT fails
        # after the session lock is acquired and leaves its transaction aborted.
        with (
            pytest.raises(ProgrammingError, match="cp_schedule_snapshot"),
            store.timer_mutation_lock(ctx, "missing-schedule"),
        ):
            pass

        with admin_engine.connect() as observer:
            acquired = observer.execute(
                text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
                {"lock_id": _advisory_lock_id(store_id)},
            ).scalar_one()
            observer.rollback()
        assert acquired is True
    finally:
        if scoped_engine is not None:
            scoped_engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


def test_repeatable_read_guard_reads_after_waiting_for_canonical_writer() -> None:
    url = _postgres_url()
    admin_engine = create_engine(url)
    schema = "phase061_fresh_" + uuid.uuid4().hex
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    connect_args = {"options": f"-c search_path={schema}"}
    engine = create_engine(url, connect_args=connect_args)
    rr_engine = create_engine(
        url, isolation_level="REPEATABLE READ", connect_args=connect_args
    )
    store_id = "phase061-fresh-snapshot-" + uuid.uuid4().hex
    writer: Any = None
    writer_tx: Any = None
    reader: threading.Thread | None = None
    try:
        upgrade(engine)
        ctx = _context(store_id)
        store = SQLModelScheduleStore(engine, store_id=store_id)
        start = datetime.now(UTC).replace(microsecond=0)
        active = store.create(
            ctx,
            definition_id="phase061-pipeline",
            profile_name="test",
            spec=ScheduleSpec(kind="interval", interval_seconds=60),
            schedule_id="phase061-schedule",
            timer_owner="external",
            workload_identity=Principal(
                "phase061-timer", issuer="tests", kind="workload"
            ),
            next_fire_at=(start + timedelta(seconds=60))
            .isoformat()
            .replace("+00:00", "Z"),
            timer_schedule_start_at=start.isoformat().replace("+00:00", "Z"),
            timer_binding_fingerprint="a" * 64,
        )
        lock_id = _advisory_lock_id(store_id)
        writer = engine.connect()
        writer_tx = writer.begin()
        writer.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id}
        )
        payload_json = writer.execute(
            text(
                "SELECT payload_json FROM cp_schedule_snapshot "
                "WHERE store_id = :store_id"
            ),
            {"store_id": store_id},
        ).scalar_one()
        memory = MemoryScheduleStore()
        memory.load(json.loads(payload_json))
        memory.pause(ctx, active.schedule_id)
        writer.execute(
            text(
                "UPDATE cp_schedule_snapshot SET payload_json = :payload_json, "
                "payload_version = payload_version + 1 "
                "WHERE store_id = :store_id"
            ),
            {
                "payload_json": json.dumps(memory.dump(), sort_keys=True),
                "store_id": store_id,
            },
        )

        rr_store = SQLModelScheduleStore(rr_engine, store_id=store_id)
        result: list[str | None] = []
        errors: list[BaseException] = []
        reader_started = threading.Event()

        def read_under_guard() -> None:
            reader_started.set()
            try:
                with rr_store.timer_mutation_lock(ctx, active.schedule_id) as canonical:
                    result.append(canonical.status if canonical is not None else None)
            except BaseException as exc:
                errors.append(exc)

        reader = threading.Thread(target=read_under_guard, daemon=True)
        reader.start()
        assert reader_started.wait(timeout=5)

        unsigned_lock_id = lock_id & ((1 << 64) - 1)
        class_id = unsigned_lock_id >> 32
        object_id = unsigned_lock_id & 0xFFFFFFFF
        deadline = time.monotonic() + 5
        waiting = False
        while time.monotonic() < deadline:
            with engine.connect() as observer:
                waiting = observer.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM pg_locks "
                        "WHERE locktype = 'advisory' AND NOT granted "
                        "AND database = (SELECT oid FROM pg_database "
                        "WHERE datname = current_database()) "
                        "AND classid = :class_id AND objid = :object_id "
                        "AND objsubid = 1)"
                    ),
                    {"class_id": class_id, "object_id": object_id},
                ).scalar_one()
                observer.rollback()
            if waiting:
                break
            time.sleep(0.01)
        assert waiting, "timer guard did not wait for the canonical writer"

        writer_tx.commit()
        reader.join(timeout=5)
        assert not reader.is_alive(), "timer guard did not finish after writer commit"
        assert errors == []
        assert result == ["paused"]
    finally:
        if writer_tx is not None and writer_tx.is_active:
            writer_tx.rollback()
        if reader is not None and reader.is_alive():
            reader.join(timeout=5)
        if writer is not None:
            writer.close()
        rr_engine.dispose()
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()
