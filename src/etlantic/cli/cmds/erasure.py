"""CLI: etlantic erasure plan|status (CP4 governed erasure)."""

from __future__ import annotations

import json
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


def _store_from_path(path: Path | None) -> MemoryErasureStore:
    store = MemoryErasureStore()
    if path is None or not path.exists():
        return store
    payload = json.loads(path.read_text(encoding="utf-8"))
    # Minimal reload: requests only (local CLI scratch).
    for item in payload.get("requests") or []:
        ctx = _ctx_from_options(
            tenant=item["tenant_id"],
            workspace=item["workspace_id"],
            subject="cli",
            environment="dev",
        )
        store.create_request(
            ctx,
            subject_key_fingerprint=item["subject_key_fingerprint"],
            field_paths=item.get("field_paths") or (),
            legal_hold=bool(item.get("legal_hold")),
            request_id=item["request_id"],
        )
    return store


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
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        """Create an erasure request and lineage-derived plan."""
        ctx = _ctx_from_options(
            tenant=tenant,
            workspace=workspace,
            subject="cli",
            environment=environment,
        )
        store = MemoryErasureStore()
        req = store.create_request(
            ctx,
            subject_key_fingerprint=subject_key_fingerprint,
            field_paths=field_path,
            legal_hold=legal_hold,
        )
        providers = [MemoryErasureProvider(provider_id=p) for p in provider]
        try:
            plan = store.plan(ctx, request_id=req.request_id, providers=providers)
        except Exception as exc:  # noqa: BLE001
            typer.echo(str(exc), err=True)
            raise typer.Exit(ec.VALIDATION_FAILED) from exc
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
            help="Optional JSON scratch store from a prior plan export.",
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
        except Exception as exc:  # noqa: BLE001
            typer.echo(str(exc), err=True)
            raise typer.Exit(ec.VALIDATION_FAILED) from exc
        if fmt != "json":
            typer.echo(f"{req.request_id} status={req.status} hold={req.legal_hold}")
        else:
            typer.echo(json.dumps(req.to_dict(), indent=2, sort_keys=True))


__all__ = ["register_erasure_commands"]
