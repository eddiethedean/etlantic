"""Compile, generate, and diff CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from etlantic.cli.cmds.context import emit_payload, report_to_payload
from etlantic.cli.context import CliContext, get_cli_context
from etlantic.diagnostics.sarif import validation_report_to_sarif
from etlantic.interchange.bundle import write_contracts
from etlantic.interchange.diff import (
    diff_data_contracts,
    diff_pipelines,
    diff_transformations,
)
from etlantic.orchestration.compile import OrchestrationCompilationError, compile_plan
from etlantic.plan.planner import plan_pipeline_with_report
from etlantic.registry import PlanningContext


def register_compile_commands(app: typer.Typer, context_factory: Any) -> None:
    def _cli(ctx: typer.Context) -> CliContext:
        try:
            return get_cli_context(ctx)
        except RuntimeError:
            return context_factory()

    @app.command("compile")
    def compile_cmd(
        ctx: typer.Context,
        target: str = typer.Argument(..., help="module:Class or path.py:Class"),
        orch_target: str = typer.Option("airflow", "--target", "-t"),
        output: str = typer.Option("dags", "--output", "-o"),
        profile: str = typer.Option("local", "--profile", "-p"),
        allow_adhoc_profile: bool = typer.Option(
            False,
            "--allow-adhoc-profile",
            help="Allow unknown bare profile names (fail-closed by default).",
        ),
        fmt: str = typer.Option("json", "--format"),
        preview: bool = typer.Option(False, "--preview"),
    ) -> None:
        """Compile a planned pipeline to an external orchestrator artifact."""
        cli = _cli(ctx)
        pipeline_cls = cli.load_target(target)
        resolved, source = cli.resolve_profile(
            profile, allow_adhoc_profile=allow_adhoc_profile
        )
        cli.emit_mutation_preamble(
            command="compile",
            target=target,
            profile=resolved,
            profile_source=source,
            write_intent=f"write artifacts to {output}",
            preview=preview,
            fmt=fmt if preview else "human",
        )
        if preview:
            raise typer.Exit(0)
        diags = cli.runtime.ensure_plugins_for_profile(resolved)
        from etlantic.diagnostics import Severity

        errors = [d for d in diags if d.severity is Severity.ERROR]
        if errors:
            emit_payload(
                {
                    "ok": False,
                    "diagnostics": [
                        {
                            "code": d.code,
                            "severity": d.severity.value,
                            "message": d.message,
                        }
                        for d in errors
                    ],
                },
                fmt=fmt,
            )
            raise typer.Exit(1)
        context = PlanningContext.create(
            profile=resolved, registry=cli.runtime.registry
        )
        plan, report = plan_pipeline_with_report(pipeline_cls, context=context)
        if plan is None:
            payload = report_to_payload(report)
            if fmt == "sarif":
                emit_payload(validation_report_to_sarif(report), fmt="json")
            else:
                emit_payload(payload, fmt=fmt)
            raise typer.Exit(1)
        try:
            artifact = compile_plan(
                plan,
                target=orch_target,
                profile=resolved,
                allow_adhoc_profile=allow_adhoc_profile,
            )
        except OrchestrationCompilationError as exc:
            emit_payload(
                {
                    "ok": False,
                    "error": str(exc),
                    "diagnostics": [d.to_dict() for d in exc.diagnostics],
                },
                fmt=fmt,
            )
            raise typer.Exit(1) from exc
        out = Path(output)
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{artifact.dag_id}.py"
        written = artifact.write(path)
        emit_payload(
            {
                "ok": True,
                "target": orch_target,
                "plan_id": plan.plan_id,
                "dag_id": artifact.dag_id,
                "output": str(written),
            },
            fmt=fmt,
        )

    @app.command("generate")
    def generate_cmd(
        ctx: typer.Context,
        target: str = typer.Argument(..., help="module:Class or path.py:Class"),
        output: str = typer.Option("contracts", "--output", "-o"),
        fmt: str = typer.Option("json", "--format"),
        sqlmodel: bool = typer.Option(
            False,
            "--sqlmodel",
            help="Also emit SQLModel stubs (requires etlantic-sqlmodel)",
        ),
    ) -> None:
        """Generate ODCS/DTCS/DPCS contract bundles for a pipeline."""
        cli = _cli(ctx)
        pipeline_cls = cli.load_target(target)
        bundle = write_contracts(pipeline_cls, output)
        payload: dict[str, Any] = {
            "ok": True,
            "pipeline_id": bundle.pipeline_id,
            "root": str(bundle.root) if bundle.root else None,
            "paths": {k: str(v) for k, v in bundle.paths.items()},
            "data_contracts": sorted(bundle.data_contracts),
            "transformations": sorted(bundle.transformations),
        }
        if sqlmodel:
            try:
                from etlantic_sqlmodel import (
                    contract_to_sqlmodel_source,  # type: ignore
                )
            except ImportError as exc:
                emit_payload(
                    {
                        "ok": False,
                        "error": "etlantic-sqlmodel is required for --sqlmodel",
                    },
                    fmt=fmt,
                )
                raise typer.Exit(1) from exc
            stubs: dict[str, str] = {}
            out = Path(output) / "sqlmodel"
            out.mkdir(parents=True, exist_ok=True)
            for name, contract in bundle.data_contracts.items():
                source = contract_to_sqlmodel_source(contract, table_name=name)
                path = out / f"{name}.py"
                path.write_text(source, encoding="utf-8")
                stubs[name] = str(path)
            payload["sqlmodel"] = stubs
        emit_payload(payload, fmt=fmt)

    @app.command("diff")
    def diff_cmd(
        ctx: typer.Context,
        previous: str = typer.Argument(
            ..., help="Previous artifact (module:Class or path)"
        ),
        current: str = typer.Argument(
            ..., help="Current artifact (module:Class or path)"
        ),
        kind: str = typer.Option(
            "auto", "--kind", help="auto|data|pipeline|transformation"
        ),
        fmt: str = typer.Option("json", "--format", help="human|json|sarif"),
    ) -> None:
        """Diff contracts or pipelines and emit diagnostics."""
        cli = _cli(ctx)

        def _load_side(target: str) -> Any:
            path = Path(target)
            if path.exists() and path.is_file():
                return path
            return cli.load_target(target)

        def _sniff_kind(path: Path) -> str:
            name = path.name.lower()
            if "odcs" in name:
                return "data"
            if "dtcs" in name or "transform" in name:
                return "transformation"
            if "dpcs" in name or "pipeline" in name:
                return "pipeline"
            try:
                head = path.read_text(encoding="utf-8")[:800].lower()
            except OSError:
                return "pipeline"
            if "odcs" in head or "datacontract" in head.replace(" ", ""):
                return "data"
            if "dtcs" in head or "transform-plan" in head:
                return "transformation"
            return "pipeline"

        errors: list[str] = []
        prev_obj: Any = None
        curr_obj: Any = None
        try:
            prev_obj = _load_side(previous)
        except Exception as exc:
            errors.append(f"previous ({previous}): {exc}")
        try:
            curr_obj = _load_side(current)
        except Exception as exc:
            errors.append(f"current ({current}): {exc}")
        if errors:
            emit_payload({"ok": False, "error": "; ".join(errors)}, fmt=fmt)
            raise typer.Exit(1)

        if kind == "auto":
            if isinstance(prev_obj, Path):
                resolved_kind = _sniff_kind(prev_obj)
            elif isinstance(curr_obj, Path):
                resolved_kind = _sniff_kind(curr_obj)
            else:
                resolved_kind = "pipeline"
        else:
            resolved_kind = kind

        if resolved_kind == "data":
            report = diff_data_contracts(prev_obj, curr_obj)
        elif resolved_kind == "transformation":
            report = diff_transformations(prev_obj, curr_obj)
        else:
            report = diff_pipelines(prev_obj, curr_obj)

        if fmt == "sarif":
            emit_payload(validation_report_to_sarif(report), fmt="json")
        else:
            emit_payload(report_to_payload(report), fmt=fmt)
        raise typer.Exit(0 if report.valid else 1)
