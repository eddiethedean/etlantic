# pyright: reportArgumentType=false, reportCallIssue=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
"""Live multiprocess admission qualification for the PostgreSQL CP3 store."""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context

import pytest

pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")

from sqlalchemy import delete, select, text
from sqlalchemy.engine import Engine

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic_sqlmodel.control_plane.cp4_stores import (
    SQLModelQuotaProvider,
    create_cp4_tables,
)
from etlantic_sqlmodel.control_plane.durable_stores import (
    SQLModelDurableWorkStore,
    create_durable_tables,
)
from etlantic_sqlmodel.control_plane.models import (
    DurableOutboxEntityRow,
    DurableSnapshotRow,
    DurableSubmissionEntityRow,
)
from sqlmodel import Session, create_engine

pytestmark = pytest.mark.sqlmodel


def _context() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal("phase056-worker", issuer="phase056-tests"),
        tenant=TenantRef("phase056-tenant"),
        workspace=WorkspaceRef("phase056-tenant", "phase056-workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("phase056-test-domain"),
    )


def _accept_in_process(url: str, store_id: str) -> tuple[str, bool]:
    engine = create_engine(url, pool_pre_ping=True)
    try:
        store = SQLModelDurableWorkStore(engine, store_id=store_id)
        submission, created = store.accept(
            _context(),
            idempotency_key="concurrent-same-intent",
            operation="run.submit",
            plan_fingerprint="a" * 64,
            input_snapshot='{"intent":"same"}',
        )
        return submission.submission_id, created
    finally:
        engine.dispose()


def _admit_quota_in_process(url: str, store_id: str) -> tuple[str, int]:
    engine = create_engine(url, pool_pre_ping=True)
    try:
        decision = SQLModelQuotaProvider(engine, store_id=store_id).admit(
            _context(),
            resource="concurrency",
            idempotency_key="same-submission-digest",
        )
        return decision.effect, decision.used
    finally:
        engine.dispose()


def _remove_store(engine: Engine, store_id: str) -> None:
    with Session(engine) as session, session.begin():
        session.exec(
            delete(DurableOutboxEntityRow).where(
                DurableOutboxEntityRow.store_id == store_id
            )
        )
        session.exec(
            delete(DurableSubmissionEntityRow).where(
                DurableSubmissionEntityRow.store_id == store_id
            )
        )
        session.exec(
            delete(DurableSnapshotRow).where(DurableSnapshotRow.store_id == store_id)
        )
        session.connection().execute(
            text(
                "DELETE FROM cp_cp4_governance_snapshot "
                "WHERE store_id = :store_id AND kind = 'quotas'"
            ),
            {"store_id": store_id},
        )


def test_postgresql_multiprocess_accept_is_single_and_restart_visible() -> None:
    url = os.environ.get("ETLANTIC_CP_TEST_URL")
    if not url:
        pytest.skip(
            "set ETLANTIC_CP_TEST_URL to qualify live PostgreSQL control storage"
        )
    engine = create_engine(url, pool_pre_ping=True)
    store_id = f"phase056-{uuid.uuid4().hex}"
    create_durable_tables(engine)
    try:
        with ProcessPoolExecutor(
            max_workers=8, mp_context=get_context("spawn")
        ) as workers:
            results = list(
                workers.map(
                    _accept_in_process,
                    [url] * 8,
                    [store_id] * 8,
                )
            )

        submission_ids = {submission_id for submission_id, _created in results}
        assert len(submission_ids) == 1
        assert sum(created for _submission_id, created in results) == 1

        # A new store object in the parent process reads the committed receipt,
        # submission and outbox written by the independent worker processes.
        restarted = SQLModelDurableWorkStore(engine, store_id=store_id)
        record = restarted.get_submission_by_idempotency(
            _context(), idempotency_key="concurrent-same-intent"
        )
        assert record is not None
        assert record.submission_id == next(iter(submission_ids))
        assert len(restarted.pending_outbox(_context())) == 1
        with Session(engine) as session:
            assert (
                len(
                    session.exec(
                        select(DurableSubmissionEntityRow).where(
                            DurableSubmissionEntityRow.store_id == store_id
                        )
                    ).all()
                )
                == 1
            )
            assert (
                len(
                    session.exec(
                        select(DurableOutboxEntityRow).where(
                            DurableOutboxEntityRow.store_id == store_id
                        )
                    ).all()
                )
                == 1
            )
    finally:
        _remove_store(engine, store_id)
        engine.dispose()


def test_postgresql_multiprocess_quota_idempotency_is_single_and_restart_visible() -> (
    None
):
    url = os.environ.get("ETLANTIC_CP_TEST_URL")
    if not url:
        pytest.skip(
            "set ETLANTIC_CP_TEST_URL to qualify live PostgreSQL control storage"
        )
    engine = create_engine(url, pool_pre_ping=True)
    store_id = f"phase056-quota-{uuid.uuid4().hex}"
    create_cp4_tables(engine)
    try:
        quota = SQLModelQuotaProvider(engine, store_id=store_id)
        quota.set_suspended(_context(), suspended=False)
        with ProcessPoolExecutor(
            max_workers=8, mp_context=get_context("spawn")
        ) as workers:
            results = list(
                workers.map(_admit_quota_in_process, [url] * 8, [store_id] * 8)
            )

        assert set(results) == {("allow", 1)}
        reopened = SQLModelQuotaProvider(engine, store_id=store_id)
        assert reopened.get_state(_context()).usage["concurrency"] == 1
    finally:
        _remove_store(engine, store_id)
        engine.dispose()
