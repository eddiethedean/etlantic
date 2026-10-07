"""SQLModel durability and takeover for managed preparation operations."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    MemoryAuthorizer,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.runtime.action_execution_host import ActionExecutionHost
from etlantic_sqlmodel.control_plane import (
    SQLModelDurableWorkStore,
    create_sqlite_engine,
)
from etlantic_sqlmodel.migrations import upgrade

pytestmark = pytest.mark.sqlmodel


def test_preparation_operation_survives_store_restart_and_expired_lease(
    tmp_path: Any,
) -> None:
    database = tmp_path / "preparation.sqlite"
    url = f"sqlite:///{database}"
    store_id = "phase056-preparation-recovery"
    ctx = ControlPlaneContext(
        principal=Principal("preparation-owner"),
        tenant=TenantRef("preparation-tenant"),
        workspace=WorkspaceRef("preparation-tenant", "preparation-workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("preparation-domain"),
    )
    first_engine = create_sqlite_engine(url)
    upgrade(first_engine)
    first_store = SQLModelDurableWorkStore(first_engine, store_id=store_id)
    request = {
        "definition_id": "pipe",
        "revision_selector": "current",
        "profile_name": "development",
        "run_request": {"intent": "standard"},
        "definition_revision_id": "revision-1",
    }
    accepted = first_store.accept_action_job(
        ctx,
        action="run.prepare",
        idempotency_key="preparation-restart",
        request=request,
        deadline_at=(datetime.now(UTC) + timedelta(minutes=2))
        .isoformat()
        .replace("+00:00", "Z"),
    )
    stale_lease = first_store.claim_action_job(
        ctx,
        worker_id="terminated-worker",
        lease_seconds=1,
        now=datetime.now(UTC) - timedelta(seconds=10),
    )
    assert stale_lease is not None
    assert stale_lease.action_id == accepted.action_id
    assert stale_lease.phase == "preparing"
    first_engine.dispose()

    second_engine = create_sqlite_engine(url)
    second_store = SQLModelDurableWorkStore(second_engine, store_id=store_id)
    try:
        recovered = second_store.get_action_job_by_idempotency(
            ctx, action="run.prepare", idempotency_key="preparation-restart"
        )
        assert recovered is not None
        assert recovered.action_id == accepted.action_id
        assert recovered.status == "running"
        assert json.loads(recovered.request_json) == request

        authorizer = MemoryAuthorizer()
        authorizer.grant(ctx, "run.submit")

        async def resume(
            _action_ctx: ControlPlaneContext, operation_request: Mapping[str, Any]
        ) -> dict[str, Any]:
            return {
                "operation_id": operation_request["_operation_id"],
                "revision_id": operation_request["definition_revision_id"],
            }

        worker = ActionExecutionHost(
            second_store,
            handlers={"run.prepare": resume},
            authorizer=authorizer,
            worker_id="restarted-worker",
            lease_seconds=10,
        )
        assert worker.tick(ctx) == 1
        completed = second_store.get_action_job(ctx, accepted.action_id)
        assert completed.status == "succeeded"
        assert completed.attempt == 2
        assert completed.fencing_token == 2
        assert completed.to_dict()["result"] == {
            "operation_id": accepted.action_id,
            "revision_id": "revision-1",
        }
    finally:
        second_engine.dispose()
