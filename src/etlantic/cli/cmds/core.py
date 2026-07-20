"""Core CLI command registrations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from etlantic.cli import exit_codes as ec
from etlantic.cli.context import CliContext, get_cli_context
from etlantic.cli.output import emit_payload, emit_validation_report
from etlantic.cli.target import build_selection
from etlantic.exceptions import PipelineExecutionError
from etlantic.plan.diff import diff_plans, render_plan_explain_human
from etlantic.plan.explain import explain_plan
from etlantic.plan.planner import plan_pipeline_with_report
from etlantic.plan.serialize import plan_to_json
from etlantic.registry import PlanningContext
from etlantic.reports.file_store import FileReportStore, compare_reports
from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.request import RunIntent, RunRequest, RunSelection


def register_core_commands(
    app: typer.Typer,
    plan_app: typer.Typer,
    report_app: typer.Typer,
) -> None:
    """Register validate, inspect, plan, run, and report commands."""

    @app.command("validate")
    def validate_cmd(
        ctx: typer.Context,
        target: str = typer.Argument(..., help="module:Class or path.py:Class"),
        profile: str | None = typer.Option(None, "--profile", "-p"),
        fmt: str = typer.Option("human", "--format", help="human, json, or sarif"),
        allow_adhoc_profile: bool = typer.Option(
            False,
            "--allow-adhoc-profile",
            help="Allow unknown bare profile names.",
        ),
    ) -> None:
        """Validate a pipeline without executing it."""
        cli = get_cli_context(ctx)
        resolved, _source = cli.resolve_profile(
            profile, allow_adhoc_profile=allow_adhoc_profile
        )
        cli.ensure_plugins(resolved)
        pipeline_cls = cli.load_target(target)
        context = PlanningContext.create(
            profile=resolved,
            registry=cli.runtime.registry,
            allow_adhoc_profile=allow_adhoc_profile,
        )
        report = pipeline_cls.validate(context=context)
        emit_validation_report(
            report,
            fmt=fmt,
            prefix=pipeline_cls.__name__,
            verbose=cli.globals.verbose,
            quiet=cli.globals.quiet,
        )
        raise typer.Exit(ec.SUCCESS if report.valid else ec.INVALID_MODEL)

    @app.command("inspect")
    def inspect_cmd(
        ctx: typer.Context,
        target: str = typer.Argument(..., help="module:Class or path.py:Class"),
        fmt: str = typer.Option("human", "--format"),
    ) -> None:
        """Inspect a pipeline logical graph."""
        cli = get_cli_context(ctx)
        pipeline_cls = cli.load_target(target)
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
        emit_payload(payload, fmt=fmt, quiet=cli.globals.quiet)

    @app.command("run")
    def run_cmd(
        ctx: typer.Context,
        target: str = typer.Argument(..., help="module:Class or path.py:Class"),
        profile: str | None = typer.Option(None, "--profile", "-p"),
        fmt: str = typer.Option("text", "--format", help="text, json, or html"),
        run_one: str | None = typer.Option(None, "--run-one"),
        run_until: str | None = typer.Option(None, "--run-until"),
        intent: str = typer.Option("standard", "--intent"),
        no_write: bool = typer.Option(False, "--no-write"),
        preview: bool = typer.Option(
            False, "--preview", help="Show mutation scope only."
        ),
        allow_adhoc_profile: bool = typer.Option(
            False,
            "--allow-adhoc-profile",
            help="Allow unknown bare profile names.",
        ),
    ) -> None:
        """Execute a pipeline locally and emit a run report."""
        cli = get_cli_context(ctx)
        resolved, source = cli.resolve_profile(
            profile, allow_adhoc_profile=allow_adhoc_profile
        )
        write_intent = "no_write" if no_write else "execute_and_persist"
        if preview or (fmt == "human" and not cli.globals.quiet):
            cli.emit_mutation_preamble(
                command="run",
                target=target,
                profile=resolved,
                profile_source=source,
                write_intent=write_intent,
                preview=preview,
                fmt=fmt if preview else "human",
            )
        if preview:
            raise typer.Exit(ec.SUCCESS)
        cli.ensure_plugins(resolved)
        pipeline_cls = cli.load_target(target)
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
        paths = cli.workspace()
        try:
            report = pipeline_cls.run(
                profile=resolved,
                request=request,
                runtime=cli.runtime,
                workspace=str(paths.artifacts),
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
            raise typer.Exit(ec.EXECUTION_FAILURE) from exc
        if fmt == "json":
            typer.echo(report.to_json())
        elif fmt == "html":
            typer.echo(report.to_html())
        else:
            typer.echo(report.to_text())
        code = ec.SUCCESS if report.status.value == "succeeded" else ec.PARTIAL_RUN
        if report.status.value == "failed":
            code = ec.EXECUTION_FAILURE
        raise typer.Exit(code)

    def _plan_and_emit(
        cli: CliContext,
        target: str,
        *,
        profile: str | None,
        fmt: str,
        run_one: str | None,
        run_until: str | None,
        nodes: str | None,
        explain: bool,
        allow_adhoc_profile: bool,
    ) -> None:
        resolved, _source = cli.resolve_profile(
            profile, allow_adhoc_profile=allow_adhoc_profile
        )
        cli.ensure_plugins(resolved)
        pipeline_cls = cli.load_target(target)
        selection = build_selection(run_one=run_one, run_until=run_until, nodes=nodes)
        context = PlanningContext.create(
            profile=resolved,
            registry=cli.runtime.registry,
            allow_adhoc_profile=allow_adhoc_profile,
        )
        plan, report = plan_pipeline_with_report(
            pipeline_cls, context=context, selection=selection
        )
        if plan is None:
            emit_validation_report(
                report,
                fmt=fmt if fmt != "json" else "human",
                prefix="Planning failed",
                verbose=cli.globals.verbose,
                quiet=cli.globals.quiet,
            )
            raise typer.Exit(ec.PLANNING_FAILURE)
        if explain:
            payload = explain_plan(plan)
            if fmt == "human":
                typer.echo(render_plan_explain_human(payload))
            else:
                emit_payload(payload, fmt=fmt, quiet=cli.globals.quiet)
            return
        if fmt == "json":
            typer.echo(plan_to_json(plan), nl=False)
        else:
            typer.echo(f"plan_id={plan.plan_id}")
            typer.echo(f"fingerprint={plan.fingerprint}")
            typer.echo(f"profile={plan.profile_name}")
            typer.echo(f"nodes={len(plan.logical_graph.nodes)}")

    @plan_app.command("_default", hidden=True)
    def plan_default_cmd(
        ctx: typer.Context,
        target: str = typer.Argument(..., help="module:Class or path.py:Class"),
        profile: str | None = typer.Option(None, "--profile", "-p"),
        fmt: str = typer.Option("json", "--format"),
        run_one: str | None = typer.Option(None, "--run-one"),
        run_until: str | None = typer.Option(None, "--run-until"),
        nodes: str | None = typer.Option(None, "--nodes"),
        explain: bool = typer.Option(False, "--explain"),
        allow_adhoc_profile: bool = typer.Option(False, "--allow-adhoc-profile"),
    ) -> None:
        """Resolve a deterministic PipelinePlan."""
        _plan_and_emit(
            get_cli_context(ctx),
            target,
            profile=profile,
            fmt=fmt,
            run_one=run_one,
            run_until=run_until,
            nodes=nodes,
            explain=explain,
            allow_adhoc_profile=allow_adhoc_profile,
        )

    @plan_app.command("explain")
    def plan_explain_cmd(
        ctx: typer.Context,
        target: str = typer.Argument(..., help="module:Class or path.py:Class"),
        profile: str | None = typer.Option(None, "--profile", "-p"),
        fmt: str = typer.Option("json", "--format"),
        run_one: str | None = typer.Option(None, "--run-one"),
        run_until: str | None = typer.Option(None, "--run-until"),
        nodes: str | None = typer.Option(None, "--nodes"),
        allow_adhoc_profile: bool = typer.Option(False, "--allow-adhoc-profile"),
    ) -> None:
        """Emit a structured explanation of a resolved PipelinePlan."""
        _plan_and_emit(
            get_cli_context(ctx),
            target,
            profile=profile,
            fmt=fmt,
            run_one=run_one,
            run_until=run_until,
            nodes=nodes,
            explain=True,
            allow_adhoc_profile=allow_adhoc_profile,
        )

    @plan_app.command("diff")
    def plan_diff_cmd(
        ctx: typer.Context,
        left: str = typer.Argument(..., help="Left target or plan JSON path"),
        right: str = typer.Argument(..., help="Right target or plan JSON path"),
        profile: str | None = typer.Option(None, "--profile", "-p"),
        fmt: str = typer.Option("json", "--format"),
        allow_adhoc_profile: bool = typer.Option(False, "--allow-adhoc-profile"),
    ) -> None:
        """Compare two resolved plans structurally."""
        cli = get_cli_context(ctx)

        def _load_plan(ref: str) -> Any:
            path = Path(ref)
            if path.suffix == ".json" and path.exists():
                from etlantic.plan.model import PipelinePlan

                return PipelinePlan.from_dict(
                    json.loads(path.read_text(encoding="utf-8"))
                )
            resolved, _ = cli.resolve_profile(
                profile, allow_adhoc_profile=allow_adhoc_profile
            )
            cli.ensure_plugins(resolved)
            context = PlanningContext.create(
                profile=resolved,
                registry=cli.runtime.registry,
                allow_adhoc_profile=allow_adhoc_profile,
            )
            plan, report = plan_pipeline_with_report(
                cli.load_target(ref), context=context
            )
            if plan is None:
                raise typer.BadParameter(
                    f"Planning failed for {ref}: "
                    + "; ".join(d.message for d in report.errors)
                )
            return plan

        diff = diff_plans(_load_plan(left), _load_plan(right))
        emit_payload(diff.to_dict(), fmt=fmt, quiet=cli.globals.quiet)
        raise typer.Exit(ec.SUCCESS if diff.equal else ec.BREAKING_CHANGE)

    def _resolve_report(
        cli: CliContext, ref: str, store: str | None
    ) -> PipelineRunReport:
        path = Path(ref)
        if path.suffix == ".json" and path.exists():
            return PipelineRunReport.from_dict(
                json.loads(path.read_text(encoding="utf-8"))
            )
        store_root = Path(store) if store else cli.workspace().reports
        if not cli.globals.ephemeral:
            report = FileReportStore(store_root).get(ref)
            if report is not None:
                return report
        report = cli.runtime.reports.get(ref)
        if report is None:
            raise typer.BadParameter(f"Unknown report reference: {ref}")
        return report

    @report_app.command("list")
    def report_list_cmd(
        ctx: typer.Context,
        pipeline_id: str | None = typer.Option(None, "--pipeline-id"),
        limit: int | None = typer.Option(20, "--limit"),
        store: str | None = typer.Option(None, "--store"),
        fmt: str = typer.Option("human", "--format"),
    ) -> None:
        """List durable run reports."""
        cli = get_cli_context(ctx)
        store_root = Path(store) if store else cli.workspace().reports
        file_store = FileReportStore(store_root)
        reports = file_store.list(pipeline_id=pipeline_id, limit=limit)
        payload = {
            "reports": [
                {
                    "run_id": r.run_id,
                    "pipeline_id": r.pipeline_id,
                    "status": r.status.value,
                }
                for r in reports
            ]
        }
        emit_payload(payload, fmt=fmt, quiet=cli.globals.quiet)

    @report_app.command("show")
    def report_show_cmd(
        ctx: typer.Context,
        run_id: str = typer.Argument(..., help="Run id"),
        store: str | None = typer.Option(None, "--store"),
        fmt: str = typer.Option("text", "--format"),
    ) -> None:
        """Show a previously recorded run report."""
        cli = get_cli_context(ctx)
        report = _resolve_report(cli, run_id, store)
        if fmt == "json":
            typer.echo(report.to_json())
        elif fmt == "html":
            typer.echo(report.to_html())
        else:
            typer.echo(report.to_text())

    @report_app.command("export")
    def report_export_cmd(
        ctx: typer.Context,
        run_id: str = typer.Argument(..., help="Run id"),
        output: str = typer.Option("report.json", "--output", "-o"),
        store: str | None = typer.Option(None, "--store"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        """Export a run report to a file."""
        cli = get_cli_context(ctx)
        report = _resolve_report(cli, run_id, store)
        path = Path(output)
        if fmt == "html":
            path.write_text(report.to_html(), encoding="utf-8")
        elif fmt == "text":
            path.write_text(report.to_text(), encoding="utf-8")
        else:
            path.write_text(report.to_json(), encoding="utf-8")
        if not cli.globals.quiet:
            typer.echo(f"Wrote {path}")

    @report_app.command("compare")
    def report_compare_cmd(
        ctx: typer.Context,
        left: str = typer.Argument(..., help="Left run id or JSON path"),
        right: str = typer.Argument(..., help="Right run id or JSON path"),
        store: str | None = typer.Option(None, "--store"),
        fmt: str = typer.Option("json", "--format"),
    ) -> None:
        """Compare two run reports."""
        cli = get_cli_context(ctx)
        payload = compare_reports(
            _resolve_report(cli, left, store),
            _resolve_report(cli, right, store),
        )
        emit_payload(payload, fmt=fmt, quiet=cli.globals.quiet)
