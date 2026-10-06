# pyright: reportPrivateUsage=false, reportUnusedFunction=false
"""etlantic profile — validate, show, diff, and migrate profiles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import typer

from etlantic.cli import exit_codes as ec
from etlantic.cli.context import get_cli_context
from etlantic.cli.output import emit_payload
from etlantic.profile import Profile, load_profile, resolve_profile


def _schema_path(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / name


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads(_schema_path(name).read_text(encoding="utf-8"))


def _resolve_profile_arg(
    ref: str,
    *,
    allow_adhoc_profile: bool,
    start: Path | None = None,
) -> tuple[Profile, Path | None]:
    path = Path(ref)
    if path.suffix == ".json" and path.is_file():
        return (
            load_profile(path),
            path,
        )
    root = start or Path.cwd()
    profiles_candidate = root / "profiles" / f"{ref}.json"
    if profiles_candidate.is_file():
        return (
            load_profile(profiles_candidate),
            profiles_candidate,
        )
    return (
        resolve_profile(ref, allow_adhoc_profile=allow_adhoc_profile),
        None,
    )


def _validate_profile_semantics(profile: Profile, root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if profile.security_mode == "production" and not profile.plugin_allowlist:
        from etlantic.plugin_trust import empty_production_allowlist_message

        findings.append(
            {
                "code": "PMCFG200",
                "severity": "error",
                "message": empty_production_allowlist_message(profile.name),
            }
        )
    for asset, descriptor in profile.assets.items():
        if "://" in descriptor:
            location = descriptor.split("://", 1)[1]
            path = (root / location).resolve()
            if descriptor.startswith(("json://", "csv://")) and not path.is_file():
                findings.append(
                    {
                        "code": "PMCFG201",
                        "severity": "warning",
                        "message": f"Asset {asset!r} location not found: {path}",
                    }
                )
    return findings


def register_profile_commands(app: typer.Typer) -> None:
    profile_app = typer.Typer(help="Profile validation and inspection.")
    app.add_typer(profile_app, name="profile")

    @profile_app.command("validate")
    def profile_validate_cmd(
        ctx: typer.Context,
        ref: str = typer.Argument(..., help="Profile path or name"),
        fmt: str = typer.Option("human", "--format"),
        allow_adhoc_profile: bool = typer.Option(False, "--allow-adhoc-profile"),
    ) -> None:
        """Validate a profile document."""
        cli = get_cli_context(ctx)
        schema = _load_schema("profile.schema.json")
        path = Path(ref)
        raw: dict[str, Any]
        if path.suffix == ".json" and path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
        else:
            profile, _ = _resolve_profile_arg(
                ref,
                allow_adhoc_profile=allow_adhoc_profile,
                start=cli.workspace().root,
            )
            raw = profile.to_dict()
        errors: list[str] = []
        try:
            jsonschema.validate(raw, schema)
        except jsonschema.ValidationError as exc:
            errors.append(str(exc.message))
        try:
            profile = Profile.from_dict(raw)
        except Exception as exc:
            errors.append(str(exc))
            emit_payload({"valid": False, "errors": errors}, fmt=fmt)
            raise typer.Exit(ec.INVALID_MODEL) from exc
        semantics = _validate_profile_semantics(profile, cli.workspace().root)
        trust_error = any(
            s["severity"] == "error"
            and (
                s["code"] in {"PMCFG200", "PMPLUG401"}
                or str(s.get("code", "")).startswith("PMPLUG")
            )
            for s in semantics
        )
        valid = not errors and not any(s["severity"] == "error" for s in semantics)
        payload = {"valid": valid, "errors": errors, "findings": semantics}
        if fmt == "json":
            emit_payload(payload, fmt="json")
        else:
            typer.echo(f"profile: {'valid' if valid else 'invalid'}")
            for err in errors:
                typer.echo(f"  error: {err}")
            for finding in semantics:
                typer.echo(
                    f"  [{finding['severity']}] {finding['code']}: {finding['message']}"
                )
        if valid:
            raise typer.Exit(ec.SUCCESS)
        raise typer.Exit(ec.TRUST_FAILURE if trust_error else ec.INVALID_MODEL)

    @profile_app.command("show")
    def profile_show_cmd(
        ctx: typer.Context,
        ref: str = typer.Argument(..., help="Profile path or name"),
        fmt: str = typer.Option("json", "--format"),
        allow_adhoc_profile: bool = typer.Option(False, "--allow-adhoc-profile"),
    ) -> None:
        """Show a redacted profile document."""
        cli = get_cli_context(ctx)
        profile, _ = _resolve_profile_arg(
            ref,
            allow_adhoc_profile=allow_adhoc_profile,
            start=cli.workspace().root,
        )
        emit_payload(profile.to_dict(), fmt=fmt, quiet=cli.globals.quiet)

    @profile_app.command("diff")
    def profile_diff_cmd(
        ctx: typer.Context,
        left: str = typer.Argument(...),
        right: str = typer.Argument(...),
        fmt: str = typer.Option("json", "--format"),
        allow_adhoc_profile: bool = typer.Option(False, "--allow-adhoc-profile"),
    ) -> None:
        """Diff two profiles."""
        cli = get_cli_context(ctx)
        left_profile, _ = _resolve_profile_arg(
            left,
            allow_adhoc_profile=allow_adhoc_profile,
            start=cli.workspace().root,
        )
        right_profile, _ = _resolve_profile_arg(
            right,
            allow_adhoc_profile=allow_adhoc_profile,
            start=cli.workspace().root,
        )
        left_data = left_profile.to_dict()
        right_data = right_profile.to_dict()
        changed: dict[str, Any] = {}
        keys = sorted(set(left_data) | set(right_data))
        for key in keys:
            if left_data.get(key) != right_data.get(key):
                changed[key] = {
                    "left": left_data.get(key),
                    "right": right_data.get(key),
                }
        breaking = any(
            key in {"security_mode", "plugin_allowlist", "assets", "dataframe_engine"}
            for key in changed
        )
        payload = {
            "equal": not changed,
            "breaking": breaking,
            "changed": changed,
        }
        emit_payload(payload, fmt=fmt, quiet=cli.globals.quiet)
        raise typer.Exit(ec.SUCCESS if not breaking else ec.BREAKING_CHANGE)
