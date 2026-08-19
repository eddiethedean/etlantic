"""etlantic proposal — validate untrusted AI proposals (no apply)."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from etlantic.agents.proposal import Proposal, validate_proposal
from etlantic.cli import exit_codes as ec
from etlantic.cli.context import get_cli_context
from etlantic.cli.output import emit_payload


def register_proposal_commands(app: typer.Typer) -> None:
    proposal_app = typer.Typer(
        help="Validate untrusted AI proposals. Does not apply files or submit runs."
    )
    app.add_typer(proposal_app, name="proposal")

    @proposal_app.command("validate")
    def proposal_validate_cmd(
        ctx: typer.Context,
        proposal_path: Path = typer.Argument(
            ..., help="Path to an etlantic.proposal/1 JSON document"
        ),
        target: str | None = typer.Option(
            None,
            "--target",
            help="Optional pipeline to validate against (no execution).",
        ),
        profile: str | None = typer.Option(None, "--profile", "-p"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        """Run the deterministic sandbox. Never mutates files or calls approvals."""
        raw = json.loads(proposal_path.read_text(encoding="utf-8"))
        proposal = Proposal.from_dict(raw)
        pipeline = None
        if target:
            pipeline = get_cli_context(ctx).load_target(target)
        result = validate_proposal(
            proposal, pipeline=pipeline, profile=profile or "development"
        )
        emit_payload(result.to_dict(), fmt=fmt)
        if not result.ok:
            raise typer.Exit(ec.INVALID_MODEL)
