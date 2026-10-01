"""PostgreSQL failure atomicity and backup/restore qualification for CP3."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")

import sqlalchemy
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import DBAPIError

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic_sqlmodel.control_plane.durable_stores import SQLModelDurableWorkStore
from etlantic_sqlmodel.migrations import upgrade


def _context() -> ControlPlaneContext:
    scope = uuid4().hex
    tenant_id = f"backup-tenant-{scope}"
    return ControlPlaneContext(
        principal=Principal(f"backup-worker-{scope}"),
        tenant=TenantRef(tenant_id),
        workspace=WorkspaceRef(tenant_id, f"backup-workspace-{scope}"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain(f"backup-domain-{scope}"),
    )


def _database_uri(base_url: str, database: str) -> str:
    return (
        make_url(base_url).set(database=database).render_as_string(hide_password=False)
    )


def _cli_database_uri(base_url: str, database: str) -> str:
    return (
        make_url(base_url)
        .set(database=database, drivername="postgresql")
        .render_as_string(hide_password=False)
    )


def _create_database(admin: Engine, name: str) -> None:
    identifier = admin.dialect.identifier_preparer.quote(name)
    with admin.connect() as connection:
        connection.exec_driver_sql(f"CREATE DATABASE {identifier}")


def _drop_database(admin: Engine, name: str) -> None:
    identifier = admin.dialect.identifier_preparer.quote(name)
    with admin.connect() as connection:
        connection.exec_driver_sql(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (name,),
        )
        connection.exec_driver_sql(f"DROP DATABASE IF EXISTS {identifier}")


def test_postgresql_cp3_failure_atomicity_and_backup_restore(
    tmp_path: Path,
) -> None:
    base_url = os.environ.get("ETLANTIC_CP_TEST_URL")
    if not base_url:
        pytest.skip("ETLANTIC_CP_TEST_URL must point to isolated PostgreSQL")
    pg_dump = shutil.which("pg_dump")
    pg_restore = shutil.which("pg_restore")
    if not pg_dump or not pg_restore:
        pytest.skip("pg_dump and pg_restore are required for backup/restore evidence")

    url = make_url(base_url)
    admin_url = url.set(database="postgres")
    admin = sqlalchemy.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    suffix = uuid4().hex[:12]
    source_database = f"etlantic056_src_{suffix}"
    restored_database = f"etlantic056_dst_{suffix}"
    source_engine: Engine | None = None
    restored_engine: Engine | None = None
    created_databases: list[str] = []
    try:
        for database in (source_database, restored_database):
            _create_database(admin, database)
            created_databases.append(database)

        source_engine = sqlalchemy.create_engine(
            _database_uri(base_url, source_database)
        )
        assert upgrade(source_engine) == "012_bounded_event_tombstone_retention_0_56"
        store_id = f"phase056-backup-{suffix}"
        store = SQLModelDurableWorkStore(source_engine, store_id=store_id)
        ctx = _context()

        with source_engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE FUNCTION phase056_reject_outbox_insert() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected outbox failure'; "
                "END $$"
            )
            connection.exec_driver_sql(
                "CREATE TRIGGER phase056_reject_outbox BEFORE INSERT "
                "ON cp_durable_outbox_entity FOR EACH ROW "
                "EXECUTE FUNCTION phase056_reject_outbox_insert()"
            )
        with pytest.raises(DBAPIError):
            store.accept(
                ctx,
                idempotency_key="rolled-back-accept",
                operation="run.submit",
                plan_fingerprint="a" * 64,
                input_snapshot='{"schema":"phase056-test/1"}',
            )
        assert (
            store.get_submission_by_idempotency(
                ctx, idempotency_key="rolled-back-accept"
            )
            is None
        )
        with source_engine.begin() as connection:
            connection.exec_driver_sql(
                "DROP TRIGGER phase056_reject_outbox ON cp_durable_outbox_entity"
            )
            connection.exec_driver_sql("DROP FUNCTION phase056_reject_outbox_insert()")

        accepted, created = store.accept(
            ctx,
            idempotency_key="backup-accepted-run",
            operation="run.submit",
            plan_fingerprint="b" * 64,
            input_snapshot='{"schema":"phase056-test/1","accepted":true}',
        )
        assert created is True
        assert len(store.pending_outbox(ctx)) == 1

        backup = tmp_path / "phase056-control-plane.dump"
        subprocess.run(
            [
                pg_dump,
                "--format=custom",
                "--no-owner",
                "--no-acl",
                "--dbname",
                _cli_database_uri(base_url, source_database),
                "--file",
                str(backup),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        subprocess.run(
            [
                pg_restore,
                "--exit-on-error",
                "--no-owner",
                "--no-acl",
                "--dbname",
                _cli_database_uri(base_url, restored_database),
                str(backup),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )

        restored_engine = sqlalchemy.create_engine(
            _database_uri(base_url, restored_database)
        )
        restored_store = SQLModelDurableWorkStore(restored_engine, store_id=store_id)
        restored = restored_store.get_submission_by_idempotency(
            ctx, idempotency_key="backup-accepted-run"
        )
        assert restored is not None
        assert restored.submission_id == accepted.submission_id
        assert restored.input_snapshot == accepted.input_snapshot
        restored_outbox = restored_store.pending_outbox(ctx)
        assert len(restored_outbox) == 1
        assert restored_outbox[0].submission_id == accepted.submission_id
    finally:
        if restored_engine is not None:
            restored_engine.dispose()
        if source_engine is not None:
            source_engine.dispose()
        for database in reversed(created_databases):
            _drop_database(admin, database)
        admin.dispose()
