# pyright: reportArgumentType=false, reportCallIssue=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
"""Live multiprocess admission qualification for the PostgreSQL CP3 store."""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime, timedelta
from multiprocessing import get_context

import pytest

pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")

from sqlalchemy import delete, select, text
from sqlalchemy.engine import Engine

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
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


def _accept_competing_intent_in_process(
    url: str, store_id: str, fingerprint: str, snapshot: str
) -> tuple[str, str, bool]:
    engine = create_engine(url, pool_pre_ping=True)
    try:
        store = SQLModelDurableWorkStore(engine, store_id=store_id)
        try:
            submission, created = store.accept(
                _context(),
                idempotency_key="concurrent-changed-intent",
                operation="run.submit",
                plan_fingerprint=fingerprint,
                input_snapshot=snapshot,
            )
        except ControlPlaneError as exc:
            return fingerprint, str(exc.status), False
        return fingerprint, submission.submission_id, created
    finally:
        engine.dispose()


def _accept_then_lose_ack_in_process(url: str, store_id: str) -> None:
    engine = create_engine(url, pool_pre_ping=True)
    try:
        store = SQLModelDurableWorkStore(engine, store_id=store_id)
        store.accept(
            _context(),
            idempotency_key="lost-accept-ack",
            operation="run.submit",
            plan_fingerprint="c" * 64,
            input_snapshot='{"intent":"committed-before-ack-loss"}',
        )
        # The store transaction has committed; failing before returning models
        # a lost process/transport acknowledgement at the acceptance boundary.
        raise RuntimeError("simulated lost acceptance acknowledgement")
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


def _accept_action_in_process(url: str, store_id: str) -> str:
    engine = create_engine(url, pool_pre_ping=True)
    try:
        record = SQLModelDurableWorkStore(engine, store_id=store_id).accept_action_job(
            _context(),
            action="connector.test",
            idempotency_key="same-action-intent",
            request={"provider": "test", "connection_id": "saved-db"},
            deadline_at=(datetime.now(UTC) + timedelta(minutes=2)).isoformat(),
        )
        return record.action_id
    finally:
        engine.dispose()


def _claim_action_in_process(
    url: str, store_id: str, worker_id: str
) -> tuple[str, int] | None:
    engine = create_engine(url, pool_pre_ping=True)
    try:
        record = SQLModelDurableWorkStore(engine, store_id=store_id).claim_action_job(
            _context(), worker_id=worker_id, lease_seconds=30
        )
        if record is None:
            return None
        return record.action_id, record.fencing_token
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
    create_cp4_tables(engine)
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
        # Do not initialize the snapshot row first: all worker processes race
        # through the store's first transaction, exercising missing-row
        # initialization as well as idempotent quota admission.
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


def test_postgresql_multiprocess_action_acceptance_and_claim_are_single() -> None:
    url = os.environ.get("ETLANTIC_CP_TEST_URL")
    if not url:
        pytest.skip(
            "set ETLANTIC_CP_TEST_URL to qualify live PostgreSQL control storage"
        )
    engine = create_engine(url, pool_pre_ping=True)
    store_id = f"phase056-actions-{uuid.uuid4().hex}"
    create_cp4_tables(engine)
    create_durable_tables(engine)
    try:
        with ProcessPoolExecutor(
            max_workers=8, mp_context=get_context("spawn")
        ) as workers:
            action_ids = list(
                workers.map(_accept_action_in_process, [url] * 8, [store_id] * 8)
            )
        assert len(set(action_ids)) == 1

        worker_ids = [f"action-worker-{index}" for index in range(8)]
        with ProcessPoolExecutor(
            max_workers=8, mp_context=get_context("spawn")
        ) as workers:
            claims = list(
                workers.map(
                    _claim_action_in_process,
                    [url] * len(worker_ids),
                    [store_id] * len(worker_ids),
                    worker_ids,
                )
            )
        winners = [
            (worker_id, claim)
            for worker_id, claim in zip(worker_ids, claims, strict=True)
            if claim is not None
        ]
        assert len(winners) == 1
        worker_id, claim = winners[0]
        assert claim is not None
        action_id, fencing_token = claim
        assert action_id == action_ids[0]

        restarted = SQLModelDurableWorkStore(engine, store_id=store_id)
        queued = restarted.get_action_job(_context(), action_id)
        assert queued.status == "running"
        assert queued.worker_id == worker_id
        assert queued.fencing_token == fencing_token
        with pytest.raises(ControlPlaneError) as cross_owner:
            restarted.get_action_job(
                ControlPlaneContext(
                    principal=Principal("other", issuer="phase056-tests"),
                    tenant=TenantRef("phase056-tenant"),
                    workspace=WorkspaceRef("phase056-tenant", "phase056-workspace"),
                    environment=EnvironmentRef("test"),
                    security_domain=SecurityDomain("phase056-test-domain"),
                ),
                action_id,
            )
        assert cross_owner.value.status == 404
    finally:
        _remove_store(engine, store_id)
        engine.dispose()


def test_postgresql_multiprocess_changed_intent_conflicts_under_one_key() -> None:
    url = os.environ.get("ETLANTIC_CP_TEST_URL")
    if not url:
        pytest.skip(
            "set ETLANTIC_CP_TEST_URL to qualify live PostgreSQL control storage"
        )
    engine = create_engine(url, pool_pre_ping=True)
    store_id = f"phase056-intent-race-{uuid.uuid4().hex}"
    create_cp4_tables(engine)
    create_durable_tables(engine)
    try:
        fingerprints = ["a" * 64] * 4 + ["b" * 64] * 4
        snapshots = ['{"intent":"a"}'] * 4 + ['{"intent":"b"}'] * 4
        with ProcessPoolExecutor(
            max_workers=8, mp_context=get_context("spawn")
        ) as workers:
            results = list(
                workers.map(
                    _accept_competing_intent_in_process,
                    [url] * 8,
                    [store_id] * 8,
                    fingerprints,
                    snapshots,
                )
            )

        accepted = [item for item in results if item[1] != "409"]
        conflicts = [item for item in results if item[1] == "409"]
        assert len(accepted) == len(conflicts) == 4
        assert len({item[0] for item in accepted}) == 1
        assert len({item[1] for item in accepted}) == 1
        assert sum(item[2] for item in accepted) == 1

        durable = SQLModelDurableWorkStore(engine, store_id=store_id)
        record = durable.get_submission_by_idempotency(
            _context(),
            idempotency_key="concurrent-changed-intent",
            operation="run.submit",
        )
        assert record is not None
        assert record.plan_fingerprint == accepted[0][0]
        assert len(durable.pending_outbox(_context())) == 1
    finally:
        _remove_store(engine, store_id)
        engine.dispose()


def test_postgresql_lost_accept_ack_recovers_the_committed_receipt() -> None:
    url = os.environ.get("ETLANTIC_CP_TEST_URL")
    if not url:
        pytest.skip(
            "set ETLANTIC_CP_TEST_URL to qualify live PostgreSQL control storage"
        )
    engine = create_engine(url, pool_pre_ping=True)
    store_id = f"phase056-lost-ack-{uuid.uuid4().hex}"
    create_cp4_tables(engine)
    create_durable_tables(engine)
    try:
        with ProcessPoolExecutor(
            max_workers=1, mp_context=get_context("spawn")
        ) as workers:
            future = workers.submit(_accept_then_lose_ack_in_process, url, store_id)
            with pytest.raises(RuntimeError, match="simulated lost acceptance"):
                future.result()

        restarted = SQLModelDurableWorkStore(engine, store_id=store_id)
        receipt, created = restarted.accept(
            _context(),
            idempotency_key="lost-accept-ack",
            operation="run.submit",
            plan_fingerprint="c" * 64,
            input_snapshot='{"intent":"committed-before-ack-loss"}',
        )
        assert not created
        assert restarted.get_submission(_context(), receipt.submission_id) == receipt
        assert len(restarted.pending_outbox(_context())) == 1
    finally:
        _remove_store(engine, store_id)
        engine.dispose()
