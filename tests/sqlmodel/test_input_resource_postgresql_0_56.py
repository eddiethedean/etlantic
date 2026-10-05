"""PostgreSQL isolation and lease/retention race tests for input resources."""

from __future__ import annotations

import hashlib
import multiprocessing
import os
import uuid
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("etlantic_sqlmodel")
pytest.importorskip("psycopg")
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateSchema, DropSchema

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.input_resources import InputResourceReference
from etlantic_sqlmodel.control_plane import SqlModelInputResourceStore
from etlantic_sqlmodel.migrations import upgrade


def _race_operation(
    operation: str,
    database_url: str,
    schema: str,
    context_values: Mapping[str, str],
    reference_values: Mapping[str, Any],
    lease_id: str,
    retain_until: str,
    cleanup_at: str,
    first_operation: str | None,
    barrier: Any,
    first_operation_done: Any,
    results: Any,
) -> None:
    """Run one side of a lease/delete race in an independent process."""
    engine = create_engine(
        database_url,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    try:
        ctx = ControlPlaneContext(
            principal=Principal(context_values["owner_id"], kind="workload"),
            tenant=TenantRef(context_values["tenant_id"]),
            workspace=WorkspaceRef(
                context_values["tenant_id"], context_values["workspace_id"]
            ),
            environment=EnvironmentRef(context_values["environment"]),
            security_domain=SecurityDomain(context_values["security_domain"]),
            resource_owner_id=context_values["owner_id"],
        )
        reference = InputResourceReference.from_dict(reference_values)
        store = SqlModelInputResourceStore(engine)
        barrier.wait(timeout=20)
        try:
            if (
                first_operation is not None
                and operation != first_operation
                and not first_operation_done.wait(timeout=20)
            ):
                raise TimeoutError("first PostgreSQL race operation did not finish")
            if operation == "lease":
                try:
                    store.acquire_lease(
                        ctx,
                        reference,
                        lease_id=lease_id,
                        retain_until=datetime.fromisoformat(
                            retain_until.replace("Z", "+00:00")
                        ),
                    )
                except ControlPlaneError as exc:
                    results.put((operation, "missing", exc.status))
                else:
                    results.put((operation, "acquired", None))
                return
            if operation == "cleanup":
                outcome = store.cleanup(
                    ctx,
                    now=datetime.fromisoformat(cleanup_at.replace("Z", "+00:00")),
                    limit=1,
                )
                results.put(
                    (
                        operation,
                        outcome.deleted_upload_ids,
                        outcome.remaining_candidates,
                    )
                )
                return
            raise ValueError(f"unsupported test operation: {operation}")
        finally:
            if operation == first_operation:
                first_operation_done.set()
    finally:
        engine.dispose()


@pytest.fixture
def postgres_input_resources() -> Iterator[tuple[str, str, Engine]]:
    database_url = os.environ.get("ETLANTIC_SQLMODEL_TEST_URL")
    if not database_url:
        pytest.skip("ETLANTIC_SQLMODEL_TEST_URL is not configured")
    schema = f"etlantic_input_resources_{uuid.uuid4().hex}"
    admin_engine = create_engine(database_url)
    engine: Engine | None = None
    try:
        with admin_engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        engine = create_engine(
            database_url,
            connect_args={"options": f"-csearch_path={schema}"},
        )
        assert upgrade(engine) == "014_cp1_complete_principal_idempotency_0_56"
        yield database_url, schema, engine
    finally:
        if engine is not None:
            engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin_engine.dispose()


def _context() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal("pg-upload-owner", kind="workload"),
        tenant=TenantRef("pg-upload-tenant"),
        workspace=WorkspaceRef("pg-upload-tenant", "pg-upload-workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("pg-upload-domain"),
        resource_owner_id="pg-upload-owner",
    )


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def test_postgres_multiprocess_lease_and_cleanup_race_is_linearizable(
    postgres_input_resources: tuple[str, str, Engine],
) -> None:
    database_url, schema, engine = postgres_input_resources
    ctx = _context()
    store = SqlModelInputResourceStore(engine)
    process_context = multiprocessing.get_context("spawn")
    context_values = {
        "owner_id": ctx.resource_owner_id or "",
        "tenant_id": ctx.tenant.tenant_id,
        "workspace_id": ctx.workspace.workspace_id,
        "environment": ctx.environment.name,
        "security_domain": ctx.security_domain.domain_id,
    }
    content = b"id,value\n1,retained\n"

    for iteration in range(6):
        staged = store.stage(
            ctx,
            content,
            media_type="text/csv",
            format="csv",
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        reference = store.finalize(
            ctx,
            staged.upload_id,
            expected_sha256=hashlib.sha256(content).hexdigest(),
            expected_byte_length=len(content),
        )
        future = datetime.now(UTC) + timedelta(days=2)
        first_operation = (
            "lease" if iteration == 0 else "cleanup" if iteration == 1 else None
        )
        barrier = process_context.Barrier(2)
        first_operation_done = process_context.Event()
        results = process_context.Queue()
        arguments = (
            database_url,
            schema,
            context_values,
            reference.to_dict(),
            f"accepted-submission-{iteration}",
            _iso(future + timedelta(days=1)),
            _iso(future),
            first_operation,
            barrier,
            first_operation_done,
            results,
        )
        processes = [
            process_context.Process(
                target=_race_operation,
                args=(operation, *arguments),
            )
            for operation in ("lease", "cleanup")
        ]
        try:
            for process in processes:
                process.start()
            for process in processes:
                process.join(timeout=30)
            for process in processes:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
                    pytest.fail("input-resource race worker exceeded its deadline")
                assert process.exitcode == 0
            outcomes = {
                item[0]: item[1:]
                for item in (results.get(timeout=5) for _ in processes)
            }
        finally:
            results.close()
            results.join_thread()

        lease_status = outcomes["lease"][0]
        deleted_ids = outcomes["cleanup"][0]
        if lease_status == "acquired":
            assert reference.resource_id not in deleted_ids
            assert store.read(ctx, reference, now=future) == content
        else:
            assert outcomes["lease"][1] == 404
            assert deleted_ids == (reference.resource_id,)
            with pytest.raises(ControlPlaneError) as missing:
                store.read(ctx, reference, now=future)
            assert missing.value.status == 404
        if first_operation == "lease":
            assert lease_status == "acquired"
        elif first_operation == "cleanup":
            assert lease_status == "missing"
