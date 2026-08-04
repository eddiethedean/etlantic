"""CLI: etlantic erasure plan|status (CP4 governed erasure)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import typer

from etlantic.cli import exit_codes as ec
from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    MemoryErasureProvider,
    MemoryErasureStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.erasure_models import (
    ErasurePlan,
    ErasurePlanStep,
    ErasureReport,
    ErasureRequest,
    ErasureStepResult,
)


def _ctx_from_options(
    *,
    tenant: str,
    workspace: str,
    subject: str,
    environment: str,
) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject, issuer="cli"),
        tenant=TenantRef(tenant),
        workspace=WorkspaceRef(tenant, workspace),
        environment=EnvironmentRef(environment),
        security_domain=SecurityDomain("cli"),
    )


def _dump_store(store: MemoryErasureStore) -> dict[str, Any]:
    return {
        "schema": "etlantic.cli.erasure_store/1",
        "requests": [r.to_dict() for r in store._requests.values()],
        "plans": [p.to_dict() for p in store._plans.values()],
        "reports": [r.to_dict() for r in store._reports.values()],
        "plan_by_request": {
            f"{t}|{w}|{rid}": pid for (t, w, rid), pid in store._plan_by_request.items()
        },
        "idempotency": {
            f"{t}|{w}|{k}": rid for (t, w, k), rid in store._idempotency.items()
        },
    }


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _store_from_path(path: Path | None) -> MemoryErasureStore:
    store = MemoryErasureStore()
    if path is None or not path.exists():
        return store
    payload = json.loads(path.read_text(encoding="utf-8"))
    for item in payload.get("requests") or []:
        key = (
            str(item["tenant_id"]),
            str(item["workspace_id"]),
            str(item["request_id"]),
        )
        store._requests[key] = ErasureRequest(
            request_id=str(item["request_id"]),
            tenant_id=str(item["tenant_id"]),
            workspace_id=str(item["workspace_id"]),
            subject_key_fingerprint=str(item["subject_key_fingerprint"]),
            field_paths=tuple(item.get("field_paths") or ()),
            legal_hold=bool(item.get("legal_hold")),
            status=item.get("status") or "pending",
            created_at=_parse_dt(item["created_at"])
            if item.get("created_at")
            else datetime.now(),
            metadata=dict(item.get("metadata") or {}),
        )
    for item in payload.get("plans") or []:
        steps = tuple(
            ErasurePlanStep(
                step_id=str(s["step_id"]),
                provider_id=str(s["provider_id"]),
                action=s["action"],
                field_paths=tuple(s.get("field_paths") or ()),
                supported=bool(s.get("supported")),
                reason=s.get("reason"),
            )
            for s in item.get("steps") or ()
        )
        plan = ErasurePlan(
            plan_id=str(item["plan_id"]),
            request_id=str(item["request_id"]),
            steps=steps,
            created_at=_parse_dt(item["created_at"])
            if item.get("created_at")
            else datetime.now(),
        )
        # Plans are scoped by request tenant/workspace from matching request.
        req = next(
            (r for r in store._requests.values() if r.request_id == plan.request_id),
            None,
        )
        tenant = req.tenant_id if req else "default"
        workspace = req.workspace_id if req else "default"
        store._plans[(tenant, workspace, plan.plan_id)] = plan
    for item in payload.get("reports") or []:
        results = tuple(
            ErasureStepResult(
                step_id=str(r["step_id"]),
                provider_id=str(r["provider_id"]),
                status=r["status"],
                proof_fingerprint=r.get("proof_fingerprint"),
                reason=r.get("reason"),
            )
            for r in item.get("results") or ()
        )
        report = ErasureReport(
            report_id=str(item["report_id"]),
            request_id=str(item["request_id"]),
            plan_id=str(item["plan_id"]),
            status=item["status"],
            results=results,
            reconciled=bool(item.get("reconciled")),
            created_at=_parse_dt(item["created_at"])
            if item.get("created_at")
            else datetime.now(),
            metadata=dict(item.get("metadata") or {}),
        )
        req = next(
            (r for r in store._requests.values() if r.request_id == report.request_id),
            None,
        )
        tenant = req.tenant_id if req else "default"
        workspace = req.workspace_id if req else "default"
        store._reports[(tenant, workspace, report.report_id)] = report
    for key, pid in dict(payload.get("plan_by_request") or {}).items():
        t, w, rid = str(key).split("|", 2)
        store._plan_by_request[(t, w, rid)] = str(pid)
    for key, rid in dict(payload.get("idempotency") or {}).items():
        t, w, k = str(key).split("|", 2)
        store._idempotency[(t, w, k)] = str(rid)
    return store


def _write_store(path: Path, store: MemoryErasureStore) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_dump_store(store), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def register_erasure_commands(app: typer.Typer) -> None:
    """Attach ``erasure`` subcommands to the root CLI."""

    erasure_app = typer.Typer(help="Governed data-subject erasure operations (CP4).")
    app.add_typer(erasure_app, name="erasure")

    @erasure_app.command("plan")
    def erasure_plan_cmd(
        subject_key_fingerprint: str = typer.Option(
            ...,
            "--subject-key-fingerprint",
            help="Fingerprint of the subject key (never raw subject values).",
        ),
        field_path: list[str] = typer.Option(
            ...,
            "--field",
            help="Field path to include (repeatable).",
        ),
        tenant: str = typer.Option("default", "--tenant"),
        workspace: str = typer.Option("default", "--workspace"),
        environment: str = typer.Option("dev", "--environment"),
        legal_hold: bool = typer.Option(False, "--legal-hold"),
        provider: list[str] = typer.Option(
            ["local"],
            "--provider",
            help="Erasure provider ids (memory reference).",
        ),
        store_path: Path | None = typer.Option(
            None,
            "--store",
            help="Optional JSON scratch store path (written for status reload).",
        ),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        """Create an erasure request and lineage-derived plan."""
        ctx = _ctx_from_options(
            tenant=tenant,
            workspace=workspace,
            subject="cli",
            environment=environment,
        )
        store = _store_from_path(store_path)
        req = store.create_request(
            ctx,
            subject_key_fingerprint=subject_key_fingerprint,
            field_paths=field_path,
            legal_hold=legal_hold,
        )
        providers = [MemoryErasureProvider(provider_id=p) for p in provider]
        try:
            plan = store.plan(ctx, request_id=req.request_id, providers=providers)
        except Exception as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(ec.VALIDATION_FAILED) from exc
        # Reload request (status may have advanced to planned/blocked).
        req = store.get_request(ctx, request_id=req.request_id)
        if store_path is not None:
            _write_store(store_path, store)
        payload: dict[str, Any] = {
            "request": req.to_dict(),
            "plan": plan.to_dict(),
        }
        if fmt != "json":
            typer.echo(
                f"erasure request {req.request_id} status={req.status} "
                f"plan={plan.plan_id} steps={len(plan.steps)}"
            )
        else:
            typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        if req.status == "blocked":
            raise typer.Exit(ec.VALIDATION_FAILED)

    @erasure_app.command("status")
    def erasure_status_cmd(
        request_id: str = typer.Argument(..., help="Erasure request id"),
        store_path: Path | None = typer.Option(
            None,
            "--store",
            help="JSON scratch store written by a prior ``erasure plan --store``.",
        ),
        tenant: str = typer.Option("default", "--tenant"),
        workspace: str = typer.Option("default", "--workspace"),
        environment: str = typer.Option("dev", "--environment"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        """Show erasure request status (local memory/scratch store)."""
        ctx = _ctx_from_options(
            tenant=tenant,
            workspace=workspace,
            subject="cli",
            environment=environment,
        )
        store = _store_from_path(store_path)
        try:
            req = store.get_request(ctx, request_id=request_id)
        except Exception as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(ec.VALIDATION_FAILED) from exc
        if fmt != "json":
            typer.echo(f"{req.request_id} status={req.status} hold={req.legal_hold}")
        else:
            typer.echo(json.dumps(req.to_dict(), indent=2, sort_keys=True))


__all__ = ["register_erasure_commands"]
