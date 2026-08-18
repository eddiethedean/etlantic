"""CLI: etlantic schedule / scheduler / worker."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import typer

from etlantic.cli.cmds.context import emit_payload
from etlantic.control_plane.durable_memory import MemoryDurableWorkStore
from etlantic.control_plane.models import (
    ControlPlaneContext,
    EnvironmentRef,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.schedule_clock import next_fire_after
from etlantic.control_plane.schedule_memory import MemoryScheduleStore
from etlantic.control_plane.schedule_models import ScheduleSpec
from etlantic.control_plane.schedule_trust import validate_schedule_runtime
from etlantic.profile import resolve_profile
from etlantic.runtime.execution_host import ExecutionHost
from etlantic.runtime.scheduler_service import SchedulerService


def _ctx(*, tenant: str, workspace: str, principal: str) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(principal, issuer="cli"),
        tenant=TenantRef(tenant),
        workspace=WorkspaceRef(tenant, workspace),
        environment=EnvironmentRef("cli"),
        security_domain=SecurityDomain("cli"),
    )


def _load_schedule_store(path: Path) -> MemoryScheduleStore:
    store = MemoryScheduleStore()
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            store.load(data)
    return store


def _save_schedule_store(path: Path, store: MemoryScheduleStore) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(store.dump(), indent=2, sort_keys=True), encoding="utf-8"
    )


def register_schedule_commands(app: typer.Typer) -> None:
    """Attach schedule authoring and scheduler/worker serve commands."""
    schedule_app = typer.Typer(help="Create and inspect secret-free schedules.")
    scheduler_app = typer.Typer(help="Run the timer-leadership scheduler process.")
    worker_app = typer.Typer(help="Run the execution-host worker process.")
    app.add_typer(schedule_app, name="schedule")
    app.add_typer(scheduler_app, name="scheduler")
    app.add_typer(worker_app, name="worker")

    @schedule_app.command("create")
    def schedule_create(
        store: Path = typer.Option(..., "--store"),
        definition_id: str = typer.Option(..., "--definition-id"),
        interval: int | None = typer.Option(None, "--interval"),
        cron: str | None = typer.Option(None, "--cron"),
        timezone: str = typer.Option("UTC", "--timezone"),
        tenant: str = typer.Option("default", "--tenant"),
        workspace: str = typer.Option("default", "--workspace"),
        principal: str = typer.Option("cli", "--principal"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        """Create an interval or 5-field cron schedule (no secrets)."""
        if (interval is None) == (cron is None):
            raise typer.BadParameter("provide exactly one of --interval or --cron")
        spec = (
            ScheduleSpec(kind="interval", interval_seconds=interval, timezone=timezone)
            if interval is not None
            else ScheduleSpec(kind="cron", cron=cron, timezone=timezone)
        )
        from datetime import datetime as dt

        nxt = next_fire_after(spec, after=dt.now(UTC))
        mem = _load_schedule_store(store)
        rec = mem.create(
            _ctx(tenant=tenant, workspace=workspace, principal=principal),
            definition_id=definition_id,
            profile_name="cli",
            spec=spec,
            next_fire_at=nxt.isoformat().replace("+00:00", "Z") if nxt else None,
        )
        _save_schedule_store(store, mem)
        emit_payload(rec.to_dict(), fmt=fmt)

    @schedule_app.command("list")
    def schedule_list(
        store: Path = typer.Option(..., "--store"),
        tenant: str = typer.Option("default", "--tenant"),
        workspace: str = typer.Option("default", "--workspace"),
        principal: str = typer.Option("cli", "--principal"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        mem = _load_schedule_store(store)
        items = [
            rec.to_dict()
            for rec in mem.list_schedules(
                _ctx(tenant=tenant, workspace=workspace, principal=principal)
            )
        ]
        emit_payload({"schedules": items}, fmt=fmt)

    @schedule_app.command("inspect")
    def schedule_inspect(
        schedule_id: str,
        store: Path = typer.Option(..., "--store"),
        tenant: str = typer.Option("default", "--tenant"),
        workspace: str = typer.Option("default", "--workspace"),
        principal: str = typer.Option("cli", "--principal"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        mem = _load_schedule_store(store)
        rec = mem.get(
            _ctx(tenant=tenant, workspace=workspace, principal=principal),
            schedule_id,
        )
        emit_payload(rec.to_dict(), fmt=fmt)

    @schedule_app.command("pause")
    def schedule_pause(
        schedule_id: str,
        store: Path = typer.Option(..., "--store"),
        tenant: str = typer.Option("default", "--tenant"),
        workspace: str = typer.Option("default", "--workspace"),
        principal: str = typer.Option("cli", "--principal"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        mem = _load_schedule_store(store)
        rec = mem.pause(
            _ctx(tenant=tenant, workspace=workspace, principal=principal),
            schedule_id,
        )
        _save_schedule_store(store, mem)
        emit_payload(rec.to_dict(), fmt=fmt)

    @schedule_app.command("resume")
    def schedule_resume(
        schedule_id: str,
        store: Path = typer.Option(..., "--store"),
        tenant: str = typer.Option("default", "--tenant"),
        workspace: str = typer.Option("default", "--workspace"),
        principal: str = typer.Option("cli", "--principal"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        mem = _load_schedule_store(store)
        rec = mem.resume(
            _ctx(tenant=tenant, workspace=workspace, principal=principal),
            schedule_id,
        )
        _save_schedule_store(store, mem)
        emit_payload(rec.to_dict(), fmt=fmt)

    @schedule_app.command("delete")
    def schedule_delete(
        schedule_id: str,
        store: Path = typer.Option(..., "--store"),
        tenant: str = typer.Option("default", "--tenant"),
        workspace: str = typer.Option("default", "--workspace"),
        principal: str = typer.Option("cli", "--principal"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        mem = _load_schedule_store(store)
        rec = mem.delete(
            _ctx(tenant=tenant, workspace=workspace, principal=principal),
            schedule_id,
        )
        _save_schedule_store(store, mem)
        emit_payload(rec.to_dict(), fmt=fmt)

    @schedule_app.command("preview")
    def schedule_preview(
        schedule_id: str,
        store: Path = typer.Option(..., "--store"),
        tenant: str = typer.Option("default", "--tenant"),
        workspace: str = typer.Option("default", "--workspace"),
        principal: str = typer.Option("cli", "--principal"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        mem = _load_schedule_store(store)
        rec = mem.get(
            _ctx(tenant=tenant, workspace=workspace, principal=principal),
            schedule_id,
        )
        after = datetime.now(UTC)
        nxt = next_fire_after(rec.spec, after=after)
        emit_payload(
            {
                "schedule_id": rec.schedule_id,
                "next_fire_at": nxt.isoformat().replace("+00:00", "Z") if nxt else None,
            },
            fmt=fmt,
        )

    @schedule_app.command("trigger")
    def schedule_trigger(
        schedule_id: str,
        store: Path = typer.Option(..., "--store"),
        tenant: str = typer.Option("default", "--tenant"),
        workspace: str = typer.Option("default", "--workspace"),
        principal: str = typer.Option("cli", "--principal"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        mem = _load_schedule_store(store)
        ctx = _ctx(tenant=tenant, workspace=workspace, principal=principal)
        rec = mem.get(ctx, schedule_id)
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        firing, created = mem.claim_firing(
            ctx,
            schedule_id=rec.schedule_id,
            revision_id=rec.revision_id,
            nominal_fire_time=now,
            owner_id="cli-trigger",
            fencing_token=0,
            plan_fingerprint="cli-manual",
            require_leader_lease=False,
        )
        _save_schedule_store(store, mem)
        emit_payload({**firing.to_dict(), "created": created}, fmt=fmt)

    @scheduler_app.command("serve")
    def scheduler_serve(
        store: Path = typer.Option(..., "--store"),
        tenant: str = typer.Option("default", "--tenant"),
        workspace: str = typer.Option("default", "--workspace"),
        principal: str = typer.Option("cli", "--principal"),
        profile: str = typer.Option("development", "--profile"),
        once: bool = typer.Option(False, "--once"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        """Run one due-timer scan (--once) or poll until interrupted."""
        mem = _load_schedule_store(store)
        resolved = resolve_profile(profile, allow_adhoc_profile=True)
        validate_schedule_runtime(resolved, mem)
        durable = MemoryDurableWorkStore()
        service = SchedulerService(
            mem,
            durable=durable,
            owner_id="cli-scheduler",
            profile=resolved,
        )
        ctx = _ctx(tenant=tenant, workspace=workspace, principal=principal)
        claimed = service.tick(ctx)
        _save_schedule_store(store, mem)
        emit_payload({"claimed": claimed, "ready": service.ready()}, fmt=fmt)
        if not once:
            raise typer.Exit(0)

    @worker_app.command("serve")
    def worker_serve(
        once: bool = typer.Option(True, "--once"),
        tenant: str = typer.Option("default", "--tenant"),
        workspace: str = typer.Option("default", "--workspace"),
        principal: str = typer.Option("cli", "--principal"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        """Poll durable outbox. Default is a single tick (no FastAPI)."""
        host = ExecutionHost(MemoryDurableWorkStore())
        processed = host.tick(
            _ctx(tenant=tenant, workspace=workspace, principal=principal)
        )
        emit_payload({"processed": processed, "once": once}, fmt=fmt)
