"""etlantic doctor — read-only environment and project checks."""

from __future__ import annotations

import os
import platform
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import typer

from etlantic.cli import exit_codes as ec
from etlantic.cli.context import get_cli_context
from etlantic.cli.output import emit_payload
from etlantic.diagnostics import Severity
from etlantic.io_policy import SafeIoPolicy
from etlantic.workspace import ensure_workspace_layout


def _check(
    name: str, ok: bool, message: str, *, severity: str = "error"
) -> dict[str, Any]:
    return {"name": name, "ok": ok, "message": message, "severity": severity}


def register_doctor_command(app: typer.Typer) -> None:
    @app.command("doctor")
    def doctor_cmd(
        ctx: typer.Context,
        target: str | None = typer.Argument(None, help="Optional pipeline target"),
        profile: str | None = typer.Option(None, "--profile", "-p"),
        check_backends: bool = typer.Option(
            False,
            "--check-backends",
            help="Probe optional SQL/Spark backends when configured.",
        ),
        fmt: str = typer.Option("human", "--format"),
    ) -> None:
        """Run read-only environment, dependency, and workspace checks."""
        cli = get_cli_context(ctx)
        checks: list[dict[str, Any]] = []

        py_ok = sys.version_info >= (3, 11)
        checks.append(
            _check(
                "python_version",
                py_ok,
                f"Python {platform.python_version()} ({'ok' if py_ok else 'requires >=3.11'})",
                severity="error" if not py_ok else "info",
            )
        )

        try:
            core_version = version("etlantic")
            checks.append(
                _check("etlantic", True, f"etlantic {core_version}", severity="info")
            )
        except PackageNotFoundError:
            checks.append(
                _check(
                    "etlantic",
                    False,
                    "etlantic package not installed",
                    severity="error",
                )
            )

        try:
            resolved, source = cli.resolve_profile(profile)
            checks.append(
                _check(
                    "profile",
                    True,
                    f"Profile {resolved.name!r} from {source}",
                    severity="info",
                )
            )
        except Exception as exc:
            checks.append(_check("profile", False, str(exc), severity="error"))
            resolved = None
            source = None

        if resolved is not None:
            diags = cli.runtime.ensure_plugins_for_profile(resolved)
            errors = [d for d in diags if d.severity is Severity.ERROR]
            checks.append(
                _check(
                    "plugins",
                    not errors,
                    "Plugin authorization ok"
                    if not errors
                    else "; ".join(f"{d.code}: {d.message}" for d in errors),
                    severity="error" if errors else "info",
                )
            )
            for plugin_name in resolved.plugin_allowlist:
                try:
                    version(plugin_name)
                    checks.append(
                        _check(
                            f"plugin:{plugin_name}",
                            True,
                            f"{plugin_name} installed",
                            severity="info",
                        )
                    )
                except PackageNotFoundError:
                    checks.append(
                        _check(
                            f"plugin:{plugin_name}",
                            False,
                            f"{plugin_name} listed in allowlist but not installed",
                            severity="warning",
                        )
                    )

        paths = cli.workspace()
        try:
            ensure_workspace_layout(paths)
            SafeIoPolicy.for_root(paths.reports)
            checks.append(
                _check(
                    "workspace",
                    True,
                    f"Workspace {paths.root} (reports={paths.reports})",
                    severity="info",
                )
            )
            for label, directory in (
                ("reports", paths.reports),
                ("artifacts", paths.artifacts),
            ):
                writable = directory.exists() and os.access(directory, os.W_OK)
                checks.append(
                    _check(
                        f"workspace:{label}",
                        writable,
                        f"{label} directory writable at {directory}",
                        severity="error" if not writable else "info",
                    )
                )
        except Exception as exc:
            checks.append(_check("workspace", False, str(exc), severity="error"))

        if resolved is not None and resolved.safe_io:
            for root_path in resolved.safe_io.get("approved_roots") or []:
                path = Path(str(root_path))
                checks.append(
                    _check(
                        f"safe_io:{path}",
                        path.is_dir(),
                        f"approved root exists: {path}",
                        severity="warning" if not path.is_dir() else "info",
                    )
                )

        if target:
            try:
                pipeline_cls = cli.load_target(target)
                checks.append(
                    _check(
                        "target",
                        True,
                        f"Loaded target {pipeline_cls.__name__}",
                        severity="info",
                    )
                )
            except Exception as exc:
                checks.append(_check("target", False, str(exc), severity="error"))

        if check_backends and resolved is not None:
            if resolved.sql_engine:
                try:
                    __import__("etlantic_sql")
                    checks.append(
                        _check(
                            "backend:sql",
                            True,
                            "etlantic-sql import ok",
                            severity="info",
                        )
                    )
                except ImportError:
                    checks.append(
                        _check(
                            "backend:sql",
                            False,
                            "sql_engine configured but etlantic-sql not installed",
                            severity="warning",
                        )
                    )
            if resolved.spark_engine:
                try:
                    __import__("etlantic_pyspark")
                    checks.append(
                        _check(
                            "backend:spark",
                            True,
                            "etlantic-pyspark import ok",
                            severity="info",
                        )
                    )
                except ImportError:
                    checks.append(
                        _check(
                            "backend:spark",
                            False,
                            "spark_engine configured but etlantic-pyspark not installed",
                            severity="warning",
                        )
                    )

        ok = all(c["ok"] or c["severity"] != "error" for c in checks)
        payload = {"ok": ok, "checks": checks}
        if fmt == "json":
            emit_payload(payload, fmt="json", quiet=cli.globals.quiet)
        else:
            typer.echo("ETLantic doctor")
            for item in checks:
                status = "ok" if item["ok"] else item["severity"]
                typer.echo(f"  [{status}] {item['name']}: {item['message']}")
        raise typer.Exit(ec.SUCCESS if ok else ec.ENVIRONMENT_FAILURE)
