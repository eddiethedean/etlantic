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
        profile: str = typer.Option("development", "--profile", "-p"),
        interval: float = typer.Option(
            1.0, "--interval", help="Polling interval in seconds"
        ),
        once: bool = typer.Option(
            False, "--once", help="Index and validate once then exit"
        ),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        """Revalidate workspace pipelines on change. Never executes pipelines."""
        del profile  # reserved for future profile-scoped watch
        cli = get_cli_context(ctx)
        from etlantic.ide.analysis import WorkspaceIndex

        index = WorkspaceIndex(root=path.resolve())
        previous: dict[str, str] = {}

        def _cycle() -> dict[str, Any]:
            stats = index.refresh()
            diagnostics = [d.to_dict() for d in index.diagnostics_for()]
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
                "symbols": len(index.symbols()),
                "executed": False,
            }

        if once:
            payload = _cycle()
            emit_payload(payload, fmt=fmt, quiet=cli.globals.quiet)
            errors = [d for d in payload["diagnostics"] if d.get("severity") == "error"]
            raise typer.Exit(ec.SUCCESS if not errors else ec.INVALID_MODEL)

        typer.echo(
            f"Watching {path} (interval={interval}s). Ctrl+C to stop. Never auto-runs.",
            err=True,
        )
        try:
            while True:
                payload = _cycle()
                if payload["changed"] or once:
                    emit_payload(payload, fmt=fmt, quiet=cli.globals.quiet)
                time.sleep(max(interval, 0.2))
        except KeyboardInterrupt:
            raise typer.Exit(ec.SUCCESS) from None
