"""ETLantic CLI (validate / plan / inspect / run / report)."""

from __future__ import annotations

import click
import typer
from typer.core import TyperGroup

from etlantic.cli.cmds.core import register_core_commands
from etlantic.cli.cmds.doctor import register_doctor_command
from etlantic.cli.cmds.init import register_init_command
from etlantic.cli.cmds.profile import register_profile_commands
from etlantic.cli.commands import register_commands
from etlantic.cli.context import CliContext
from etlantic.cli.globals import register_global_callback
from etlantic.cli.target import build_selection, load_target


class _DefaultToPlanGroup(TyperGroup):
    """Treat unknown first tokens as the default plan target (not a subcommand)."""

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        if args and not args[0].startswith("-") and args[0] not in self.commands:
            args = ["_default", *args]
        return super().resolve_command(ctx, args)


app = typer.Typer(
    name="etlantic",
    help="Validate, plan, and run ETLantic pipelines.",
    no_args_is_help=True,
)
plan_app = typer.Typer(
    cls=_DefaultToPlanGroup,
    help="Resolve a deterministic PipelinePlan.",
    invoke_without_command=False,
    no_args_is_help=True,
)
report_app = typer.Typer(help="Inspect stored run reports.")

app.add_typer(plan_app, name="plan")
app.add_typer(report_app, name="report")

_CTX_HOLDER: dict[str, CliContext] = {}
register_global_callback(app, _CTX_HOLDER)
register_core_commands(app, plan_app, report_app)
register_init_command(app)
register_doctor_command(app)
register_profile_commands(app)


def _default_cli_context() -> CliContext:
    if "ctx" in _CTX_HOLDER:
        return _CTX_HOLDER["ctx"]
    return CliContext(load_target=load_target)


register_commands(app, context_factory=_default_cli_context)

# Backward-compatible exports for tests and extensions.
_build_selection = build_selection
_load_target = load_target


def run() -> None:
    """Console script entry point."""
    app()


if __name__ == "__main__":
    run()
