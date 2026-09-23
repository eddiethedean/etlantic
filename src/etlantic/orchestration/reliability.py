# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Retry-safety and reliability mapping for orchestration compilation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from etlantic.orchestration.protocol import (
    CompilationDiagnostic,
    CompiledTask,
    ExecutionIntent,
    TaskRetryPolicy,
)
from etlantic.plan.model import PipelinePlan
from etlantic.reliability import RetrySafetyDeclaration


def _retry_declarations(plan: PipelinePlan) -> dict[str, RetrySafetyDeclaration]:
    raw = plan.intents.get("retry_safety") or plan.metadata.get("retry_safety") or {}
    out: dict[str, RetrySafetyDeclaration] = {}
    if isinstance(raw, Mapping):
        for key, value in raw.items():
            if isinstance(value, RetrySafetyDeclaration):
                out[str(key)] = value
            elif isinstance(value, Mapping):
                out[str(key)] = RetrySafetyDeclaration(
                    subject_id=str(value.get("subject_id") or key),
                    safe=bool(value.get("safe", False)),
                    max_attempts=value.get("max_attempts"),
                    metadata=dict(value.get("metadata") or {}),
                )
    return out


def _write_intent_for(plan: PipelinePlan, node_name: str) -> str | None:
    intents = plan.intents.get("write_intents") or {}
    if isinstance(intents, Mapping) and node_name in intents:
        value = intents[node_name]
        if isinstance(value, Mapping):
            return str(value.get("intent") or value.get("kind") or "")
        return str(value)
    return None


def _is_safe_write_intent(intent: str | None) -> bool:
    if intent is None:
        # Pure transforms / sources default to retry-safe when declared attempts > 0.
        return True
    safe = {
        "append",
        "insert_select",
        "overwrite",
        "replace",
        "merge",
        "upsert",
        "idempotent",
        "transactional",
        "compensatable",
    }
    unsafe = {"unsafe", "non_idempotent", "append_only_unsafe"}
    lowered = intent.lower()
    if lowered in unsafe:
        return False
    return lowered in safe


def resolve_task_retry(
    *,
    node_name: str,
    node_kind: str,
    plan: PipelinePlan,
    execution: ExecutionIntent,
    declarations: Mapping[str, RetrySafetyDeclaration] | None = None,
) -> tuple[int, TaskRetryPolicy, list[CompilationDiagnostic]]:
    """Map profile retry intent to a safe per-task policy.

    Unsafe sinks with requested retries produce ``PMORCH310`` and force retries
    off (or reject when ``strict`` metadata asks).
    """
    diagnostics: list[CompilationDiagnostic] = []
    decls = declarations if declarations is not None else _retry_declarations(plan)
    requested = max(0, int(execution.retries))
    if plan.execution_settings.get("retry_max_attempts") is not None:
        requested = max(
            requested, max(0, int(plan.execution_settings["retry_max_attempts"]) - 1)
        )

    decl = decls.get(node_name)
    write_intent = _write_intent_for(plan, node_name)
    safe = True
    if decl is not None:
        safe = bool(decl.safe)
    elif node_kind == "sink":
        safe = _is_safe_write_intent(write_intent)

    if requested <= 0:
        return 0, TaskRetryPolicy.DISABLED, diagnostics

    if not safe:
        diagnostics.append(
            CompilationDiagnostic(
                code="PMORCH310",
                severity="error",
                message=(
                    f"Step {node_name!r} is not retry-safe but profile requests "
                    f"{requested} retries; failing closed for external orchestration."
                ),
                subject_id=node_name,
                metadata={"write_intent": write_intent, "requested_retries": requested},
            )
        )
        return 0, TaskRetryPolicy.UNSAFE_REJECTED, diagnostics

    max_from_decl = decl.max_attempts if decl is not None else None
    retries = requested
    if max_from_decl is not None:
        retries = min(retries, max(0, int(max_from_decl) - 1))
    return retries, TaskRetryPolicy.SAFE, diagnostics


def reliability_metadata(plan: PipelinePlan, node_name: str) -> dict[str, Any]:
    """Collect portable repair/backfill/reconciliation fields for a node."""
    out: dict[str, Any] = {}
    for key in ("repair", "backfill", "reconciliation", "write_intents"):
        blob = plan.intents.get(key) or {}
        if isinstance(blob, Mapping) and node_name in blob:
            value = blob[node_name]
            out[key if key != "write_intents" else "write_intent"] = (
                value.to_dict() if hasattr(value, "to_dict") else value
            )
    return out


def apply_reliability_to_task(
    task: CompiledTask,
    *,
    plan: PipelinePlan,
    execution: ExecutionIntent,
) -> tuple[CompiledTask, list[CompilationDiagnostic]]:
    """Return an updated task with retry + reliability fields applied."""
    retries, policy, diagnostics = resolve_task_retry(
        node_name=task.node_name,
        node_kind=task.node_kind,
        plan=plan,
        execution=execution,
    )
    rel = reliability_metadata(plan, task.node_name)
    write_intent = rel.get("write_intent")
    if isinstance(write_intent, Mapping):
        write_intent_str = str(
            write_intent.get("intent") or write_intent.get("kind") or ""
        )
    else:
        write_intent_str = str(write_intent) if write_intent else task.write_intent

    updated = CompiledTask(
        task_id=task.task_id,
        node_name=task.node_name,
        node_kind=task.node_kind,
        dependencies=task.dependencies,
        retries=retries,
        retry_policy=policy,
        timeout_seconds=execution.timeout_seconds or task.timeout_seconds,
        write_intent=write_intent_str,
        repair=rel.get("repair")
        if isinstance(rel.get("repair"), dict)
        else task.repair,
        backfill=(
            rel.get("backfill")
            if isinstance(rel.get("backfill"), dict)
            else task.backfill
        ),
        reconciliation=(
            rel.get("reconciliation")
            if isinstance(rel.get("reconciliation"), dict)
            else task.reconciliation
        ),
        artifact_outputs=task.artifact_outputs,
        metadata={**dict(task.metadata), "reliability": rel},
    )
    return updated, diagnostics
