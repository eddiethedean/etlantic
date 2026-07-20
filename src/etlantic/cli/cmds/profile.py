"""etlantic profile — validate, show, diff, and migrate profiles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import typer

from etlantic.bindings import normalize_assets_map
from etlantic.cli import exit_codes as ec
from etlantic.cli.context import get_cli_context
from etlantic.cli.output import emit_payload
from etlantic.profile import Profile, load_profile, resolve_profile, write_profile


def _schema_path(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / name


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads(_schema_path(name).read_text(encoding="utf-8"))


def _resolve_profile_arg(
    ref: str,
    *,
    accept_legacy_bindings: bool,
    allow_adhoc_profile: bool,
) -> tuple[Profile, Path | None]:
    path = Path(ref)
    if path.suffix == ".json" and path.is_file():
        return Profile.from_dict(
            json.loads(path.read_text(encoding="utf-8")),
            accept_legacy_bindings=accept_legacy_bindings,
        ), path
    profiles_candidate = Path("profiles") / f"{ref}.json"
    if profiles_candidate.is_file():
        return load_profile(profiles_candidate), profiles_candidate
    return (
        resolve_profile(ref, allow_adhoc_profile=allow_adhoc_profile),
        None,
    )


def _validate_profile_semantics(profile: Profile, root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if profile.security_mode == "production" and not profile.plugin_allowlist:
        findings.append(
            {
                "code": "PMCFG200",
                "severity": "error",
                "message": "Production profile requires non-empty plugin_allowlist",
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
    profile_app = typer.Typer(help="Profile validation and migration.")
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
                accept_legacy_bindings=cli.globals.accept_legacy_bindings,
                allow_adhoc_profile=allow_adhoc_profile,
            )
            raw = profile.to_dict()
        errors: list[str] = []
        try:
            jsonschema.validate(raw, schema)
        except jsonschema.ValidationError as exc:
            errors.append(str(exc.message))
        try:
            profile = Profile.from_dict(
                raw,
                accept_legacy_bindings=cli.globals.accept_legacy_bindings,
            )
        except Exception as exc:
            errors.append(str(exc))
            emit_payload({"valid": False, "errors": errors}, fmt=fmt)
            raise typer.Exit(ec.INVALID_MODEL) from exc
        semantics = _validate_profile_semantics(profile, cli.workspace().root)
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
        raise typer.Exit(ec.SUCCESS if valid else ec.INVALID_MODEL)

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
            accept_legacy_bindings=cli.globals.accept_legacy_bindings,
            allow_adhoc_profile=allow_adhoc_profile,
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
            accept_legacy_bindings=cli.globals.accept_legacy_bindings,
            allow_adhoc_profile=allow_adhoc_profile,
        )
        right_profile, _ = _resolve_profile_arg(
            right,
            accept_legacy_bindings=cli.globals.accept_legacy_bindings,
            allow_adhoc_profile=allow_adhoc_profile,
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

    @profile_app.command("migrate")
    def profile_migrate_cmd(
        ctx: typer.Context,
        ref: str = typer.Argument(..., help="Profile JSON path"),
        dry_run: bool = typer.Option(True, "--dry-run/--write"),
        fmt: str = typer.Option("human", "--format"),
    ) -> None:
        """Migrate legacy profile JSON to 0.21 shape."""
        cli = get_cli_context(ctx)
        path = Path(ref)
        if not path.is_file():
            raise typer.BadParameter(f"Profile file not found: {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        migrated = dict(raw)
        if "bindings" in migrated and "assets" not in migrated:
            migrated["assets"] = dict(migrated.pop("bindings"))
        if "assets" in migrated:
            migrated["assets"] = normalize_assets_map(migrated["assets"])
        if "security_mode" not in migrated:
            migrated["security_mode"] = "development"
        migrated.pop("bindings", None)
        payload = {"path": str(path), "dry_run": dry_run, "profile": migrated}
        if fmt == "json":
            emit_payload(payload, fmt="json")
        else:
            typer.echo(f"migrate: {path} (dry_run={dry_run})")
        if not dry_run:
            cli.confirm_mutation(f"Write migrated profile to {path}?")
            write_profile(Profile.from_dict(migrated), path)
            if not cli.globals.quiet:
                typer.echo(f"Wrote {path}")
        raise typer.Exit(ec.SUCCESS)
