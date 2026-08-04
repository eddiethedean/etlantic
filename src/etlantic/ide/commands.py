"""IDE command executor — public SDK paths only (0.44)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from etlantic.ide.protocol import DiagnosticPayload, IdeCommand, IdeResult
from etlantic.ide.trust import TrustedWorkspacePolicy, deny_untrusted


def execute_command(
    command: IdeCommand | dict[str, Any],
    *,
    policy: TrustedWorkspacePolicy | None = None,
) -> IdeResult:
    """Execute an editor command via the public validate/plan/run/report SDK.

    Import of ``module:Class`` / ``path.py:Class`` targets requires an enabled
    :class:`TrustedWorkspacePolicy` with ``allow_imports``. JSON
    ``etlantic.pipeline/1`` targets are always allowed (no user import).
    """
    if isinstance(command, dict):
        command = IdeCommand(
            name=str(command["name"]),
            arguments=dict(command.get("arguments") or {}),
        )
    policy = policy or TrustedWorkspacePolicy.disabled()
    name = command.name
    args = dict(command.arguments)
    handlers = {
        "validate": _cmd_validate,
        "plan": _cmd_plan,
        "explain": _cmd_explain,
        "generate": _cmd_generate,
        "run_selected": _cmd_run_selected,
        "report": _cmd_report,
    }
    handler = handlers.get(name)
    if handler is None:
        return IdeResult(
            name=name,
            ok=False,
            error=f"Unknown IDE command: {name}",
        )
    try:
        return handler(args, policy=policy)
    except Exception as exc:
        # Surface failures to the editor host as IdeResult errors.
        return IdeResult(name=name, ok=False, error=str(exc))


def _resolve_target(
    target: str,
    *,
    policy: TrustedWorkspacePolicy,
    operation: str,
) -> Any:
    from etlantic.ide.trust import classify_target

    kind = classify_target(target)
    if kind == "json":
        from etlantic.ide.trust import split_target

        module_part, _ = split_target(target)
        path = Path(module_part)
        if policy.enabled:
            audit = deny_untrusted(
                policy, operation=operation, target=target, require_imports=False
            )
            if not audit.allowed:
                raise PermissionError(
                    f"JSON target {target!r} requires trusted allow_roots "
                    f"({audit.reason})"
                )
        if not path.exists():
            raise PermissionError(f"JSON target not found: {path}")
        from etlantic.authoring.serialize import read_pipeline_json

        return read_pipeline_json(path)

    audit = deny_untrusted(
        policy, operation=operation, target=target, require_imports=True
    )
    if not audit.allowed or not policy.allow_imports:
        raise PermissionError(
            f"Import-based target {target!r} requires trusted workspace "
            f"({audit.reason})"
        )
    if kind in {"py_path", "module"}:
        from etlantic.cli.target import load_target

        return load_target(target)
    raise PermissionError(f"Unsupported target form for IDE command: {target!r}")


def _diagnostics_from_report(report: Any) -> tuple[DiagnosticPayload, ...]:
    return tuple(
        DiagnosticPayload.from_diagnostic(d) for d in getattr(report, "diagnostics", ())
    )


def _cmd_validate(args: dict[str, Any], *, policy: TrustedWorkspacePolicy) -> IdeResult:
    from etlantic.authoring.lifecycle import validate_pipeline_like

    target = str(args["target"])
    profile = args.get("profile", "development")
    pipeline = _resolve_target(target, policy=policy, operation="validate")
    report = validate_pipeline_like(pipeline, profile=profile)
    return IdeResult(
        name="validate",
        ok=report.valid,
        payload={"valid": report.valid, "phases": list(report.phases)},
        diagnostics=_diagnostics_from_report(report),
    )


def _cmd_plan(args: dict[str, Any], *, policy: TrustedWorkspacePolicy) -> IdeResult:
    from etlantic.authoring.definition import PipelineDefinition
    from etlantic.authoring.lifecycle import plan_pipeline_like
    from etlantic.authoring.preview import plan_preview

    target = str(args["target"])
    profile = args.get("profile", "development")
    pipeline = _resolve_target(target, policy=policy, operation="plan")
    if isinstance(pipeline, PipelineDefinition):
        plan, report = plan_preview(pipeline, profile=profile)
        if plan is None:
            return IdeResult(
                name="plan",
                ok=False,
                diagnostics=_diagnostics_from_report(report),
                error="plan preview failed validation",
            )
    else:
        plan = plan_pipeline_like(pipeline, profile=profile)
    return IdeResult(
        name="plan",
        ok=True,
        payload={
            "plan_id": plan.plan_id,
            "fingerprint": plan.fingerprint,
            "profile_name": plan.profile_name,
            "node_count": len(plan.logical_graph.nodes),
        },
    )


def _cmd_explain(args: dict[str, Any], *, policy: TrustedWorkspacePolicy) -> IdeResult:
    from etlantic.authoring.definition import PipelineDefinition
    from etlantic.authoring.lifecycle import plan_pipeline_like
    from etlantic.authoring.preview import plan_preview
    from etlantic.plan.explain import explain_plan

    target = str(args["target"])
    profile = args.get("profile", "development")
    pipeline = _resolve_target(target, policy=policy, operation="explain")
    if isinstance(pipeline, PipelineDefinition):
        plan, report = plan_preview(pipeline, profile=profile)
        if plan is None:
            return IdeResult(
                name="explain",
                ok=False,
                diagnostics=_diagnostics_from_report(report),
                error="explain requires a valid plan",
            )
    else:
        plan = plan_pipeline_like(pipeline, profile=profile)
    explanation = explain_plan(plan)
    steps = explanation.get("steps", []) if isinstance(explanation, dict) else []
    if not isinstance(steps, list):
        steps = []
    return IdeResult(
        name="explain",
        ok=True,
        payload={
            "plan_id": plan.plan_id,
            "fingerprint": plan.fingerprint,
            "explanation": explanation
            if isinstance(explanation, dict)
            else {"text": str(explanation)},
            "steps": steps,
        },
    )


def _cmd_generate(args: dict[str, Any], *, policy: TrustedWorkspacePolicy) -> IdeResult:
    # Contract generation is CLI/SDK territory; IDE hosts must not fake success.
    target = str(args.get("target", ""))
    if target:
        try:
            _resolve_target(target, policy=policy, operation="generate")
        except PermissionError as exc:
            return IdeResult(name="generate", ok=False, error=str(exc))
    return IdeResult(
        name="generate",
        ok=False,
        error=(
            "generate is not executed by the IDE command host; "
            "use `etlantic generate` or public authoring/interchange helpers"
        ),
        payload={
            "target": target,
            "output": args.get("output", "contracts"),
            "sqlmodel": bool(args.get("sqlmodel", False)),
            "supported": False,
        },
    )


def _cmd_run_selected(
    args: dict[str, Any], *, policy: TrustedWorkspacePolicy
) -> IdeResult:
    from etlantic.authoring.definition import PipelineDefinition
    from etlantic.runtime.execute import run_pipeline
    from etlantic.runtime.request import RunRequest, RunSelection

    target = str(args["target"])
    profile = args.get("profile", "development")
    pipeline = _resolve_target(target, policy=policy, operation="run_selected")
    if isinstance(pipeline, PipelineDefinition):
        raise PermissionError(
            "run_selected on JSON PipelineDefinition requires a trusted import "
            "host or compiled pipeline class"
        )
    if args.get("run_one"):
        selection = RunSelection.only(str(args["run_one"]))
    elif args.get("run_until"):
        selection = RunSelection.until(str(args["run_until"]))
    elif args.get("nodes"):
        selection = RunSelection.only(*[str(n) for n in args["nodes"]])
    else:
        selection = RunSelection.all()
    request = RunRequest(
        selection=selection,
        no_write=bool(args.get("no_write", False)),
    )
    report = run_pipeline(pipeline, profile=profile, request=request)
    status = (
        report.status.value if hasattr(report.status, "value") else str(report.status)
    )
    return IdeResult(
        name="run_selected",
        ok=status in {"succeeded", "success", "completed"},
        payload={
            "run_id": report.run_id,
            "status": status,
            "pipeline_id": getattr(report, "pipeline_id", None),
            "plan_fingerprint": getattr(report, "plan_fingerprint", None),
        },
    )


def _cmd_report(args: dict[str, Any], *, policy: TrustedWorkspacePolicy) -> IdeResult:
    del policy  # report lookup does not import user code
    from etlantic.reports.file_store import FileReportStore

    run_id = str(args["run_id"])
    store_dir = args.get("store_dir")
    store = FileReportStore(Path(store_dir) if store_dir else Path(".etlantic/reports"))
    report = store.get(run_id)
    if report is None:
        return IdeResult(name="report", ok=False, error=f"Unknown run_id: {run_id}")
    return IdeResult(
        name="report",
        ok=True,
        payload={
            "run_id": report.run_id,
            "status": str(
                report.status.value
                if hasattr(report.status, "value")
                else report.status
            ),
            "pipeline_id": getattr(report, "pipeline_id", None),
        },
    )
