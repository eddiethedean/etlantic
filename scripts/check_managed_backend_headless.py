#!/usr/bin/env python3
"""Qualify the installed core + SQLModel wheels without FastAPI installed."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Connection, ExecutionContext


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core-wheel", type=Path, required=True)
    parser.add_argument("--sqlmodel-wheel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if importlib.util.find_spec("fastapi") is not None:
        raise SystemExit("FastAPI must be absent from the isolated qualification env")

    from sqlalchemy import event

    import etlantic
    from etlantic.control_plane import (
        ControlPlaneContext,
        EnvironmentRef,
        MemoryAuthorizer,
        Principal,
        ScheduleSpec,
        SecurityDomain,
        TenantRef,
        WorkspaceRef,
    )
    from etlantic.service import ScheduleApplicationService
    from etlantic_sqlmodel import (
        SQLModelBackendConfig,
        apply_migrations,
        create_managed_backend,
        create_sqlite_engine,
    )
    from etlantic_sqlmodel import (
        __version__ as sqlmodel_version,
    )

    context = ControlPlaneContext(
        principal=Principal(subject="release-check", issuer="etlantic-release"),
        tenant=TenantRef(tenant_id="release-tenant"),
        workspace=WorkspaceRef(
            tenant_id="release-tenant", workspace_id="release-workspace"
        ),
        environment=EnvironmentRef(name="release-check"),
        security_domain=SecurityDomain(domain_id="release-check"),
    )
    engine = create_sqlite_engine("sqlite://")
    apply_migrations(engine)
    startup_statements: list[str] = []
    startup_commits: list[bool] = []

    def capture_statement(
        _conn: Connection,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: ExecutionContext,
        _many: bool,
    ) -> None:
        startup_statements.append(statement.lstrip().split(None, 1)[0].upper())

    def capture_commit(_conn: Connection) -> None:
        startup_commits.append(True)

    event.listen(engine, "before_cursor_execute", capture_statement)
    event.listen(engine, "commit", capture_commit)
    authorizer = MemoryAuthorizer()
    authorizer.grant(context, "schedule.write")
    authorizer.grant(context, "schedule.read")
    backend = create_managed_backend(
        SQLModelBackendConfig(store_id="release-headless"),
        authorizer=authorizer,
        engine=engine,
    )
    event.remove(engine, "before_cursor_execute", capture_statement)
    event.remove(engine, "commit", capture_commit)
    if any(
        statement in {"CREATE", "ALTER", "INSERT", "UPDATE", "DELETE"}
        for statement in startup_statements
    ):
        raise AssertionError(
            f"backend startup performed schema or data writes: {startup_statements}"
        )
    if startup_commits:
        raise AssertionError("backend startup committed a transaction")
    if backend.engine is not engine or backend.owns_engine:
        raise AssertionError("injected engine ownership was not preserved")

    scheduler = backend.create_scheduler(owner_id="release-scheduler")
    run_worker = backend.create_execution_host(owner_id="release-run-worker")
    action_worker = backend.create_action_execution_host(
        worker_id="release-action-worker"
    )
    if scheduler.tick(context) != 0:
        raise AssertionError("empty schedule store unexpectedly dispatched work")
    run_worker.tick(context)
    action_worker.tick(context)
    role_statuses = {
        "scheduler": scheduler.status().to_dict(),
        "run_worker": run_worker.status().to_dict(),
        "action_worker": action_worker.status().to_dict(),
    }
    if set(role_statuses) != {"scheduler", "run_worker", "action_worker"}:
        raise AssertionError("managed role factory did not construct all roles")
    _backend_schedule_service = backend.schedule_service
    schedule_service = ScheduleApplicationService(
        authorizer=authorizer,
        schedule_store=backend.schedule_store,
    )
    if schedule_service.schedule_store is not backend.schedule_store:
        raise AssertionError("schedule service did not use the shared schedule store")
    schedule = schedule_service.create(
        context,
        "release-pipeline",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
    )
    if schedule_service.get(context, schedule.schedule_id) != schedule:
        raise AssertionError("headless schedule service failed authorized readback")

    for role in (scheduler, run_worker, action_worker):
        role.request_drain()
        if role.status().admission not in {"draining", "stopped"}:
            raise AssertionError("role drain request was not observed")
    backend.close()
    backend.close()
    with engine.connect() as connection:
        connection.exec_driver_sql("SELECT 1")
    engine.dispose()

    evidence = {
        "schema": "etlantic.phase_0_57.headless_wheels/1",
        "status": "passed",
        "observed_at": datetime.now(UTC).isoformat(),
        "source_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "python": sys.version,
        "platform": platform.platform(),
        "etlantic_version": etlantic.__version__,
        "sqlmodel_version": sqlmodel_version,
        "versions_aligned": etlantic.__version__ == sqlmodel_version,
        "fastapi_installed": False,
        "core_wheel": {
            "name": args.core_wheel.name,
            "sha256": _sha256(args.core_wheel),
        },
        "sqlmodel_wheel": {
            "name": args.sqlmodel_wheel.name,
            "sha256": _sha256(args.sqlmodel_wheel),
        },
        "observations": [
            "migrated in-memory SQLite provider schema",
            "constructed shared managed backend without FastAPI",
            "constructed scheduler, run-worker, and action-worker roles",
            "ticked all three roles and inspected local status",
            "schedule service reused the backend schedule store",
            "created and read an authorized schedule through the headless service",
            "drained roles and closed backend idempotently",
        ],
        "role_statuses": role_statuses,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"headless managed backend qualification passed: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
