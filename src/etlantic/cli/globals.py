"""Root CLI global options."""

from __future__ import annotations

import os

import typer

from etlantic import __version__
from etlantic.cli.context import CliContext, GlobalCliOptions
from etlantic.cli.target import load_target
from etlantic.project import load_project


def register_global_callback(
    app: typer.Typer, ctx_holder: dict[str, CliContext]
) -> None:
    """Attach global options to the root Typer app."""

    @app.callback(invoke_without_command=True)
    def main(
        ctx: typer.Context,
        version: bool = typer.Option(
            False,
            "--version",
            help="Show version and exit.",
            is_eager=True,
        ),
        verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output."),
        quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output."),
        color: bool = typer.Option(
            True,
            "--color/--no-color",
            help="Colorized output when supported.",
        ),
        non_interactive: bool = typer.Option(
            False,
            "--non-interactive",
            help="Do not prompt for confirmation.",
        ),
        workspace: str | None = typer.Option(
            None,
            "--workspace",
            help="Project/workspace root (default: cwd or etlantic.toml parent).",
        ),
        ephemeral: bool = typer.Option(
            False,
            "--ephemeral",
            help="Use process-local stores instead of durable .etlantic/.",
        ),
        profile: str | None = typer.Option(
            None,
            "--profile",
            "-p",
            help="Default profile for commands that accept --profile.",
        ),
        accept_legacy_bindings: bool = typer.Option(
            False,
            "--accept-legacy-bindings",
            help="Allow legacy profile JSON 'bindings' key (deprecated).",
        ),
    ) -> None:
        """ETLantic command-line interface."""
        if version:
            typer.echo(__version__)
            raise typer.Exit()
        if quiet and verbose:
            raise typer.BadParameter("Use only one of --quiet or --verbose.")
        if not color or os.environ.get("NO_COLOR"):
            os.environ.setdefault("NO_COLOR", "1")
        project = load_project()
        default_profile = profile
        if default_profile is None and project is not None:
            default_profile = project.default_profile
        globals_opts = GlobalCliOptions(
            verbose=verbose,
            quiet=quiet,
            color=color,
            non_interactive=non_interactive,
            workspace=workspace,
            ephemeral=ephemeral,
            default_profile=default_profile,
            accept_legacy_bindings=accept_legacy_bindings,
        )
        cli_ctx = CliContext(load_target=load_target, globals=globals_opts)
        ctx_holder["ctx"] = cli_ctx
        ctx.obj = cli_ctx
        if ctx.invoked_subcommand is None:
            typer.echo(ctx.get_help())
            raise typer.Exit(0)
