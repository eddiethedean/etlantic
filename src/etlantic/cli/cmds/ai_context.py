"""etlantic context — bounded redacted context bundles."""

from __future__ import annotations

import typer

from etlantic.agents.context import assemble_context_bundle
from etlantic.cli import exit_codes as ec
from etlantic.cli.context import get_cli_context
from etlantic.cli.output import emit_payload


def register_context_commands(app: typer.Typer) -> None:
    context_app = typer.Typer(help="Bounded redacted context bundles for agents.")
    app.add_typer(context_app, name="context")

    @context_app.command("bundle")
    def context_bundle_cmd(
        ctx: typer.Context,
        target: str = typer.Argument(..., help="module:Class, path.py:Class, or JSON"),
        profile: str | None = typer.Option(None, "--profile", "-p"),
        fmt: str = typer.Option("json", "--format"),
        max_bytes: int = typer.Option(262144, "--max-bytes"),
        max_nodes: int = typer.Option(256, "--max-nodes"),
    ) -> None:
        """Assemble a read-only context bundle. Never executes the pipeline."""
        cli = get_cli_context(ctx)
        pipeline = cli.load_target(target)
        resolved = profile or "development"
        bundle = assemble_context_bundle(
            pipeline,
            profile=resolved,
            budgets={"max_bytes": max_bytes, "max_nodes": max_nodes},
        )
        payload = bundle.to_dict()
        emit_payload(payload, fmt=fmt)
        if not bundle.ok:
            raise typer.Exit(ec.INVALID_MODEL)
