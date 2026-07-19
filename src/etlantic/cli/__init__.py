"""ETLantic CLI (validate / plan / inspect / run / report)."""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import click
import typer
from typer.core import TyperGroup

from etlantic import __version__
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.plan.explain import explain_plan
from etlantic.plan.planner import plan_pipeline_with_report
from etlantic.plan.serialize import plan_to_json
from etlantic.profile import resolve_profile
from etlantic.registry import PlanningContext
from etlantic.runtime.request import RunIntent, RunRequest, RunSelection


class _DefaultToPlanGroup(TyperGroup):
    """Treat unknown first tokens as the default plan target (not a subcommand).

    Enables both ``etlantic plan TARGET`` and ``etlantic plan explain TARGET``
    without the callback Argument swallowing ``explain``.
    """

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

# Process-local runtime for CLI report history within a process.
_CLI_RUNTIME = PipelineRuntime()


def _load_target(target: str) -> type[Any]:
    """Load ``module.path:ClassName`` or a file path ``file.py:ClassName``."""
    if ":" not in target:
        raise typer.BadParameter("Target must be module:Class or path.py:Class")
    module_part, class_name = target.rsplit(":", 1)
    path = Path(module_part)
    if path.suffix == ".py" and path.exists():
        module_name = f"_etlantic_cli_{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise typer.BadParameter(f"Cannot import {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    else:
        module = importlib.import_module(module_part)
    try:
        return getattr(module, class_name)
    except AttributeError as exc:
        raise typer.BadParameter(
            f"Module {module_part!r} has no attribute {class_name!r}"
        ) from exc


def _emit(data: Any, *, fmt: str) -> None:
    if fmt == "json":
        typer.echo(json.dumps(data, indent=2, sort_keys=True, default=str))
    else:
        if isinstance(data, dict):
            for key, value in data.items():
                typer.echo(f"{key}: {value}")
        else:
            typer.echo(str(data))


def _build_selection(
    *,
    run_one: str | None,
    run_until: str | None,
    nodes: str | None,
) -> dict[str, Any] | None:
    if run_one and run_until:
        raise typer.BadParameter("Use only one of --run-one or --run-until.")
    selection: dict[str, Any] = {}
    if run_one:
        selection["run_one"] = run_one
    if run_until:
        selection["run_until"] = run_until
    if nodes:
        selection["nodes"] = [n.strip() for n in nodes.split(",") if n.strip()]
    return selection or None


def _plan_and_emit(
    target: str,
    *,
    profile: str,
    fmt: str,
    run_one: str | None,
    run_until: str | None,
    nodes: str | None,
    explain: bool,
) -> None:
    pipeline_cls = _load_target(target)
    selection = _build_selection(run_one=run_one, run_until=run_until, nodes=nodes)
    context = PlanningContext.create(
        profile=resolve_profile(profile),
        registry=_CLI_RUNTIME.registry,
    )
    plan, report = plan_pipeline_with_report(
        pipeline_cls, context=context, selection=selection
    )
    if plan is None:
        typer.echo("Planning failed:", err=True)
        for diagnostic in report.errors:
            typer.echo(f"  {diagnostic.code}: {diagnostic.message}", err=True)
        raise typer.Exit(1)
    if explain:
        _emit(explain_plan(plan), fmt=fmt)
        return
    if fmt == "json":
        typer.echo(plan_to_json(plan), nl=False)
    else:
        typer.echo(f"plan_id={plan.plan_id}")
        typer.echo(f"fingerprint={plan.fingerprint}")
        typer.echo(f"profile={plan.profile_name}")
        typer.echo(f"nodes={len(plan.logical_graph.nodes)}")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        help="Show version and exit.",
        is_eager=True,
    ),
) -> None:
    """ETLantic command-line interface."""
    if version:
        typer.echo(__version__)
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)


@app.command("validate")
def validate_cmd(
    target: str = typer.Argument(..., help="module:Class or path.py:Class"),
    profile: str = typer.Option("local", "--profile", "-p"),
    fmt: str = typer.Option("human", "--format", help="human, json, or sarif"),
) -> None:
    """Validate a pipeline without executing it."""
    pipeline_cls = _load_target(target)
    context = PlanningContext.create(profile=profile, registry=_CLI_RUNTIME.registry)
    report = pipeline_cls.validate(context=context)
    if fmt == "sarif":
        from etlantic.diagnostics.sarif import validation_report_to_sarif

        _emit(validation_report_to_sarif(report), fmt="json")
    elif fmt == "json":
        _emit(
            {
                "valid": report.valid,
                "phases": list(report.phases),
                "diagnostics": [
                    {
                        "code": d.code,
                        "severity": d.severity.value,
                        "message": d.message,
                        "path": list(d.path),
                        "phase": d.phase,
                    }
                    for d in report.diagnostics
                ],
            },
            fmt="json",
        )
    else:
        status = "valid" if report.valid else "invalid"
        typer.echo(f"{pipeline_cls.__name__}: {status}")
        for diagnostic in report.diagnostics:
            typer.echo(
                f"  [{diagnostic.severity.value}] {diagnostic.code}: {diagnostic.message}"
            )
    raise typer.Exit(0 if report.valid else 1)


@app.command("inspect")
def inspect_cmd(
    target: str = typer.Argument(..., help="module:Class or path.py:Class"),
    fmt: str = typer.Option("human", "--format"),
) -> None:
    """Inspect a pipeline logical graph."""
    pipeline_cls = _load_target(target)
    graph = pipeline_cls.inspect()
    payload = {
        "pipeline_id": graph.pipeline_id,
        "pipeline_name": graph.pipeline_name,
        "nodes": [
            {
                "name": n.name,
                "kind": n.kind.value,
                "binding": n.binding,
                "asset": n.binding,
                "transformation": n.transformation_name,
            }
            for n in graph.nodes
        ],
        "edges": [
            {
                "from": f"{e.producer_node}.{e.producer_port}",
                "to": f"{e.consumer_node}.{e.consumer_port}",
            }
            for e in graph.edges
        ],
    }
    if fmt == "json":
        _emit(payload, fmt="json")
    else:
        typer.echo(f"{graph.pipeline_name} ({graph.pipeline_id})")
        for node in graph.nodes:
            typer.echo(f"  - {node.kind.value}: {node.name}")


@app.command("run")
def run_cmd(
    target: str = typer.Argument(..., help="module:Class or path.py:Class"),
    profile: str = typer.Option("development", "--profile", "-p"),
    fmt: str = typer.Option("text", "--format", help="text, json, or html"),
    run_one: str | None = typer.Option(None, "--run-one"),
    run_until: str | None = typer.Option(None, "--run-until"),
    intent: str = typer.Option("standard", "--intent"),
    no_write: bool = typer.Option(False, "--no-write"),
) -> None:
    """Execute a pipeline locally and emit a run report."""
    from etlantic.exceptions import PipelineExecutionError

    pipeline_cls = _load_target(target)
    if run_one and run_until:
        raise typer.BadParameter("Use only one of --run-one or --run-until.")
    selection = RunSelection.all()
    if run_one:
        selection = RunSelection.only(run_one)
    elif run_until:
        selection = RunSelection.until(run_until)
    request = RunRequest(
        selection=selection,
        intent=RunIntent(intent),
        no_write=no_write,
    )
    try:
        report = pipeline_cls.run(
            profile=profile, request=request, runtime=_CLI_RUNTIME
        )
    except PipelineExecutionError as exc:
        report = getattr(exc, "report", None)
        if report is not None:
            if fmt == "json":
                typer.echo(report.to_json())
            elif fmt == "html":
                typer.echo(report.to_html())
            else:
                typer.echo(report.to_text())
        else:
            typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    if fmt == "json":
        typer.echo(report.to_json())
    elif fmt == "html":
        typer.echo(report.to_html())
    else:
        typer.echo(report.to_text())
    raise typer.Exit(0 if report.status.value == "succeeded" else 1)


@report_app.command("show")
def report_show_cmd(
    run_id: str = typer.Argument(..., help="Run id"),
    fmt: str = typer.Option("text", "--format"),
) -> None:
    """Show a previously recorded run report from this process."""
    report = _CLI_RUNTIME.reports.get(run_id)
    if report is None:
        typer.echo(f"Unknown run id: {run_id}", err=True)
        raise typer.Exit(1)
    if fmt == "json":
        typer.echo(report.to_json())
    elif fmt == "html":
        typer.echo(report.to_html())
    else:
        typer.echo(report.to_text())


@report_app.command("export")
def report_export_cmd(
    run_id: str = typer.Argument(..., help="Run id"),
    output: str = typer.Option("report.json", "--output", "-o"),
    fmt: str = typer.Option("json", "--format"),
) -> None:
    """Export a run report to a file."""
    report = _CLI_RUNTIME.reports.get(run_id)
    if report is None:
        typer.echo(f"Unknown run id: {run_id}", err=True)
        raise typer.Exit(1)
    path = Path(output)
    if fmt == "html":
        path.write_text(report.to_html(), encoding="utf-8")
    elif fmt == "text":
        path.write_text(report.to_text(), encoding="utf-8")
    else:
        path.write_text(report.to_json(), encoding="utf-8")
    typer.echo(f"Wrote {path}")


@plan_app.command("_default", hidden=True)
def plan_default_cmd(
    target: str = typer.Argument(..., help="module:Class or path.py:Class"),
    profile: str = typer.Option("local", "--profile", "-p"),
    fmt: str = typer.Option("json", "--format"),
    run_one: str | None = typer.Option(None, "--run-one"),
    run_until: str | None = typer.Option(None, "--run-until"),
    nodes: str | None = typer.Option(
        None, "--nodes", help="Comma-separated node names for selection"
    ),
    explain: bool = typer.Option(
        False, "--explain", help="Emit plan explain output (alias for plan explain)"
    ),
) -> None:
    """Resolve a deterministic PipelinePlan."""
    _plan_and_emit(
        target,
        profile=profile,
        fmt=fmt,
        run_one=run_one,
        run_until=run_until,
        nodes=nodes,
        explain=explain,
    )


@plan_app.command("explain")
def plan_explain_cmd(
    target: str = typer.Argument(..., help="module:Class or path.py:Class"),
    profile: str = typer.Option("local", "--profile", "-p"),
    fmt: str = typer.Option("json", "--format"),
    run_one: str | None = typer.Option(None, "--run-one"),
    run_until: str | None = typer.Option(None, "--run-until"),
    nodes: str | None = typer.Option(None, "--nodes"),
) -> None:
    """Emit a structured explanation of a resolved PipelinePlan."""
    _plan_and_emit(
        target,
        profile=profile,
        fmt=fmt,
        run_one=run_one,
        run_until=run_until,
        nodes=nodes,
        explain=True,
    )


# 0.9 command surfaces (compile / generate / diff / plugin / schema / …)
from etlantic.cli.commands import register_commands  # noqa: E402

register_commands(app, load_target=_load_target, runtime=_CLI_RUNTIME)


@report_app.command("compare")
def report_compare_cmd(
    left: str = typer.Argument(..., help="Left run id or JSON path"),
    right: str = typer.Argument(..., help="Right run id or JSON path"),
    store: str | None = typer.Option(
        None, "--store", help="File report store root (.etlantic/reports)"
    ),
    fmt: str = typer.Option("json", "--format"),
) -> None:
    """Compare two run reports (process store, file store, or JSON files)."""
    from etlantic.reports.file_store import FileReportStore, compare_reports
    from etlantic.reports.model import PipelineRunReport

    def _load(ref: str) -> Any:
        path = Path(ref)
        if path.suffix == ".json" and path.exists():
            return PipelineRunReport.from_dict(
                json.loads(path.read_text(encoding="utf-8"))
            )
        if store:
            report = FileReportStore(Path(store)).get(ref)
            if report is not None:
                return report
        report = _CLI_RUNTIME.reports.get(ref)
        if report is None:
            raise typer.BadParameter(f"Unknown report reference: {ref}")
        return report

    payload = compare_reports(_load(left), _load(right))
    _emit(payload, fmt=fmt)


def run() -> None:
    """Console script entry point."""
    app()


if __name__ == "__main__":
    run()
