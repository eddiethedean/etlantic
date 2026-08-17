"""CLI: etlantic stream dead-letters inspect | redrive plan | schemas check."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from etlantic.cli import exit_codes as ec
from etlantic.cli.cmds.context import emit_payload
from etlantic.profile import Profile, resolve_profile
from etlantic.streaming.envelope import FORBIDDEN_ENVELOPE_KEYS
from etlantic.streaming.errors import RecordErrorPolicy
from etlantic.streaming.registry import (
    CompatibilityMode,
    InMemorySchemaRegistry,
    SchemaFormat,
)
from etlantic.streaming.trust import registry_adapter_allowed


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise typer.BadParameter("JSON root must be an object")
    return data


def _contains_payload(data: Any) -> bool:
    if isinstance(data, dict):
        if {str(k).lower() for k in data} & FORBIDDEN_ENVELOPE_KEYS:
            return True
        return any(_contains_payload(v) for v in data.values())
    if isinstance(data, list):
        return any(_contains_payload(item) for item in data)
    return False


def register_stream_commands(app: typer.Typer) -> None:
    """Attach metadata-only ``etlantic stream`` commands."""
    stream_app = typer.Typer(help="Streaming dead-letter and schema-registry ops.")
    dlq_app = typer.Typer(help="Dead-letter inspect (identifiers only).")
    redrive_app = typer.Typer(help="Idempotent redrive plans.")
    schemas_app = typer.Typer(help="Schema-registry identity checks.")
    app.add_typer(stream_app, name="stream")
    stream_app.add_typer(dlq_app, name="dead-letters")
    stream_app.add_typer(redrive_app, name="redrive")
    stream_app.add_typer(schemas_app, name="schemas")

    @dlq_app.command("inspect")
    def dead_letters_inspect(
        store: Path = typer.Option(..., "--store", exists=True, readable=True),
        principal: str = typer.Option(..., "--principal"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        """Inspect dead-letter identifiers (never payloads)."""
        data = _load_json(store)
        if _contains_payload(data):
            raise typer.Exit(ec.INVALID_MODEL)
        auth = str(data.get("authorization_identity") or "")
        if principal != auth:
            raise typer.Exit(ec.TRUST_FAILURE)
        items = []
        for item in data.get("items") or []:
            if not isinstance(item, dict):
                continue
            items.append(
                {"identity": item.get("identity"), "envelope": item.get("envelope")}
            )
        emit_payload(
            {"schema": "etlantic.streaming.dlq-inspect/1", "items": items},
            fmt=fmt,
        )

    @redrive_app.command("plan")
    def redrive_plan_cmd(
        store: Path = typer.Option(..., "--store", exists=True, readable=True),
        identity: str = typer.Option(..., "--identity"),
        principal: str = typer.Option(..., "--principal"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        """Emit an idempotent redrive plan (identifiers + provenance only)."""
        data = _load_json(store)
        if _contains_payload(data):
            raise typer.Exit(ec.INVALID_MODEL)
        auth = str(data.get("authorization_identity") or "")
        if principal != auth:
            raise typer.Exit(ec.TRUST_FAILURE)
        known = {
            str(item.get("identity"))
            for item in (data.get("items") or [])
            if isinstance(item, dict)
        }
        if identity not in known:
            raise typer.Exit(ec.INVALID_MODEL)
        previously = identity in {str(x) for x in (data.get("redrive_ids") or [])}
        emit_payload(
            {
                "schema": "etlantic.streaming.redrive-plan/1",
                "identity": identity,
                "idempotent": True,
                "already_redriven": previously,
                "provenance": {
                    "store": str(store),
                    "authorization_identity": auth,
                },
            },
            fmt=fmt,
        )

    @schemas_app.command("check")
    def schemas_check(
        subject: str = typer.Option(..., "--subject"),
        fingerprint: str = typer.Option(..., "--fingerprint"),
        schema_format: str = typer.Option("json_schema", "--schema-format"),
        profile: str | None = typer.Option(None, "--profile", "-p"),
        adapter: str | None = typer.Option(None, "--adapter"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        """Check schema-registry compatibility using identity fingerprints."""
        resolved: Profile = (
            resolve_profile(profile, allow_adhoc_profile=True)
            if profile is not None
            else Profile(name="development", security_mode="development")
        )
        if adapter:
            ok, diag = registry_adapter_allowed(resolved, adapter)
            if not ok:
                emit_payload(
                    {
                        "ok": False,
                        "diagnostic": getattr(diag, "code", "PMREG140"),
                    },
                    fmt=fmt,
                )
                raise typer.Exit(ec.TRUST_FAILURE)
        registry = InMemorySchemaRegistry()
        try:
            registry.register(
                subject,
                fingerprint,
                format=SchemaFormat(schema_format),
                compatibility=CompatibilityMode.BACKWARD,
            )
            compatible = registry.check_compatibility(subject, fingerprint)
        except (LookupError, ValueError) as exc:
            emit_payload({"ok": False, "error": str(exc)}, fmt=fmt)
            raise typer.Exit(ec.INVALID_MODEL) from exc
        emit_payload(
            {
                "schema": "etlantic.streaming.schema-check/1",
                "ok": compatible,
                "subject": subject,
                "fingerprint": fingerprint,
                "record_error_policy": RecordErrorPolicy().to_dict(),
            },
            fmt=fmt,
        )
