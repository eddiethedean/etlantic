"""Watch-mode CLI: revalidate on file changes without executing (0.44)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import typer

from etlantic.cli import exit_codes as ec
from etlantic.cli.context import get_cli_context
from etlantic.cli.output import emit_payload


def register_watch_command(app: typer.Typer) -> None:
    """Register ``etlantic watch``."""

    @app.command("watch")
    def watch_cmd(
        ctx: typer.Context,
        path: Path = typer.Argument(
            ...,
            exists=True,
            file_okay=False,
            dir_okay=True,
            help="Workspace root to watch",
        ),
        interval: float = typer.Option(
            1.0, "--interval", help="Polling interval in seconds"
        ),
        once: bool = typer.Option(
            False, "--once", help="Index and validate once then exit"
        ),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        """Revalidate workspace pipelines on change. Never executes pipelines."""
        cli = get_cli_context(ctx)
        from etlantic.diagnostics import Diagnostic, Severity, SourceLocation
        from etlantic.diagnostics.sarif import diagnostics_to_sarif
        from etlantic.ide.analysis import WorkspaceIndex

        index = WorkspaceIndex(root=path.resolve())
        previous: dict[str, str] = {}

        def _cycle() -> dict[str, Any]:
            stats = index.refresh()
            payloads = list(index.diagnostics_for())
            diagnostics = [d.to_dict() for d in payloads]
            fingerprint = {
                str(p): item.content_hash for p, item in index._files.items()
            }
            changed = fingerprint != previous
            previous.clear()
            previous.update(fingerprint)
            return {
                "stats": stats,
                "changed": changed,
                "diagnostics": diagnostics,
                "diagnostic_payloads": payloads,
                "symbols": len(index.symbols()),
                "executed": False,
            }

        def _emit(payload: dict[str, Any]) -> None:
            if fmt == "sarif":
                diags: list[Diagnostic] = []
                for item in payload.get("diagnostic_payloads") or []:
                    loc = item.location
                    source = None
                    if loc is not None:
                        source = SourceLocation(
                            path=str(loc.uri),
                            line=loc.line or 1,
                            column=loc.column or 0,
                        )
                    severity = {
                        "error": Severity.ERROR,
                        "warning": Severity.WARNING,
                        "info": Severity.INFO,
                        "hint": Severity.HINT,
                    }.get(str(item.severity), Severity.ERROR)
                    diags.append(
                        Diagnostic(
                            code=item.code,
                            severity=severity,
                            message=item.message,
                            source=source,
                        )
                    )
                emit_payload(
                    diagnostics_to_sarif(diags),
                    fmt="sarif",
                    quiet=cli.globals.quiet,
                )
                return
            slim = {k: v for k, v in payload.items() if k != "diagnostic_payloads"}
            emit_payload(slim, fmt=fmt, quiet=cli.globals.quiet)

        if once:
            payload = _cycle()
            _emit(payload)
            errors = [d for d in payload["diagnostics"] if d.get("severity") == "error"]
            raise typer.Exit(ec.SUCCESS if not errors else ec.INVALID_MODEL)

        typer.echo(
            f"Watching {path} (interval={interval}s). Ctrl+C to stop. Never auto-runs.",
            err=True,
        )
        try:
            while True:
                payload = _cycle()
                if payload["changed"]:
                    _emit(payload)
                time.sleep(max(interval, 0.2))
        except KeyboardInterrupt:
            raise typer.Exit(ec.SUCCESS) from None
