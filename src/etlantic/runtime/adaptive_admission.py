"""Fail-closed, whole-plan admission for local adaptive execution."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from etlantic.exceptions import PipelineExecutionError
from etlantic.plan.adaptive_model import ADAPTIVE_PLAN_SCHEMA, AdaptivePipelinePlan
from etlantic.plan.freeze import mutable_copy
from etlantic.plan.serialize import verify_plan_fingerprint
from etlantic.runtime.adaptive_support import (
    SupportRow,
    is_executable_plan,
    support_row_for,
)
from etlantic.runtime.request import RunRequest


@dataclass(frozen=True, slots=True)
class AdaptiveAdmission:
    plan: AdaptivePipelinePlan
    support_row: SupportRow
    units: tuple[Any, ...]
    target_engines: Mapping[str, str]
    request: RunRequest


def _reject(message: str, code: str) -> PipelineExecutionError:
    return PipelineExecutionError(message, code=code, stage="admission")


def _validate_request(request: RunRequest) -> None:
    intent = getattr(request.intent, "value", request.intent)
    if intent not in {"standard", "validate"}:
        raise _reject(
            "Adaptive execution supports only standard and validate intents",
            "PMADP522",
        )
    invalidation = getattr(request.invalidation, "value", request.invalidation)
    if invalidation != "none":
        raise _reject(
            "Adaptive execution does not support invalidation policies",
            "PMADP522",
        )
    concurrency = request.metadata.get("concurrency", 4)
    if (
        isinstance(concurrency, bool)
        or not isinstance(concurrency, int)
        or concurrency < 1
    ):
        raise _reject(
            "Adaptive concurrency must be a non-boolean integer >= 1", "PMADP522"
        )
    retry = request.retry
    if (
        retry.max_attempts < 1
        or not math.isfinite(float(retry.backoff_seconds))
        or retry.backoff_seconds < 0
    ):
        raise _reject("Adaptive retry policy is invalid", "PMADP522")
    for value in (
        request.timeout.run_seconds,
        request.timeout.step_seconds,
        request.cancellation.abandon_after_seconds,
    ):
        if value is not None and (not math.isfinite(float(value)) or value <= 0):
            raise _reject("Adaptive timeout policy is invalid", "PMADP522")
    if not request.cancellation.cooperative:
        raise _reject(
            "Adaptive execution requires cooperative cancellation", "PMADP522"
        )
    if request.cancellation.abandon_after_seconds is not None:
        raise _reject(
            "Adaptive execution does not support abandonment deadlines", "PMADP522"
        )


def admit_adaptive_plan(
    plan: Any,
    *,
    request: RunRequest,
    runtime: Any | None = None,
) -> AdaptiveAdmission:
    """Validate the complete stored DAG before execution effects.

    ``runtime`` is only consulted for already-authorized, data-only capability
    metadata. The function never enters a runtime session or reads a binding.
    """
    if getattr(plan, "schema", None) != ADAPTIVE_PLAN_SCHEMA:
        raise _reject("Adaptive admission requires etlantic.plan/2", "PMADP500")
    if not isinstance(plan, AdaptivePipelinePlan):
        raise _reject("Adaptive plan type is unsupported", "PMADP500")
    try:
        verify_plan_fingerprint(plan)
    except Exception as exc:
        raise _reject(
            f"Adaptive plan fingerprint is invalid: {exc}", "PMADP401"
        ) from exc
    _validate_request(request)
    if not is_executable_plan(plan):
        raise _reject(
            "Adaptive plan has no qualified local executable support row", "PMADP500"
        )
    row = support_row_for(plan)
    assert row is not None
    selected = set(
        plan.selected_nodes or (node.name for node in plan.logical_graph.nodes)
    )
    metadata = dict(plan.metadata)
    stored_row = metadata.get("etlantic.support_row")
    if not isinstance(stored_row, Mapping):
        raise _reject(
            "Executable adaptive plan is missing its support-row record", "PMADP401"
        )
    if (
        stored_row.get("schema") != row.to_dict()["schema"]
        or stored_row.get("row_id") != row.row_id
        or tuple(stored_row.get("evidence_refs") or ()) != row.evidence_refs
    ):
        raise _reject("Adaptive support-row record does not match the plan", "PMADP401")
    runtime_record = metadata.get("etlantic.runtime")
    if not isinstance(runtime_record, Mapping):
        raise _reject(
            "Executable adaptive plan is missing runtime metadata", "PMADP401"
        )
    stored_request = runtime_record.get("request")
    if mutable_copy(stored_request or {}) != mutable_copy(request.to_dict()):
        raise _reject(
            "Runtime request differs from the fingerprinted adaptive request",
            "PMADP122",
        )
    if runtime_record.get("support_row_id") not in {None, row.row_id}:
        raise _reject("Adaptive runtime support-row identity drifted", "PMADP401")
    implementations = metadata.get("etlantic.implementations")
    if not isinstance(implementations, (list, tuple)):
        raise _reject(
            "Executable adaptive plan is missing implementation records", "PMADP401"
        )
    implementation_nodes = {
        str(record.get("node_name"))
        for record in implementations
        if isinstance(record, Mapping)
    }
    if implementation_nodes != selected:
        raise _reject(
            "Adaptive implementation records do not cover the selection", "PMADP403"
        )
    target_by_id = {target.target_id: target for target in plan.inventory.targets}
    for record in implementations:
        if not isinstance(record, Mapping):
            raise _reject("Adaptive implementation record is not an object", "PMADP400")
        target = target_by_id.get(str(record.get("target_id")))
        if target is None or record.get("target_identity") != target.identity:
            raise _reject("Adaptive implementation target identity drifted", "PMADP401")
        if record.get("kind") == "step" and not isinstance(
            record.get("implementation"), Mapping
        ):
            raise _reject(
                "Adaptive step is missing its implementation descriptor", "PMADP401"
            )
    # Compare resolved names, rather than accepting a request that could cause
    # a fresh slice or a different logical closure at runtime.
    requested = tuple(request.selection.resolve(plan.logical_graph))
    planned = tuple(
        plan.selected_nodes or (node.name for node in plan.logical_graph.nodes)
    )
    if requested != planned:
        raise _reject(
            "Runtime selection differs from fingerprinted adaptive plan", "PMADP122"
        )
    dag = plan.physical_dag
    if set(dag.logical_to_physical) != selected or set(dag.topological_order) != {
        unit.identity for unit in dag.units
    }:
        raise _reject("Adaptive physical DAG coverage is incomplete", "PMADP403")
    if any(
        unit.protocol_versions.get("physical_unit") != "etlantic.physical_unit/1"
        for unit in dag.units
    ):
        raise _reject(
            "Adaptive physical-unit protocol version is unsupported", "PMADP400"
        )
    if any(
        unit.target_identity
        not in {target.identity for target in plan.inventory.targets}
        for unit in dag.units
    ):
        raise _reject("Adaptive unit references an unknown target", "PMADP403")
    target_engines = {
        target.identity: target.engine for target in plan.inventory.targets
    }
    if runtime is not None:
        # A runtime may expose a trust report, but no backend is loaded here.
        from etlantic.plugin_trust import is_non_blocking_trust_diagnostic

        diagnostics = getattr(runtime, "_plugin_diagnostics", ())
        errors = [
            diagnostic
            for diagnostic in diagnostics
            if str(getattr(getattr(diagnostic, "severity", None), "value", "")).lower()
            == "error"
            and not is_non_blocking_trust_diagnostic(diagnostic)
        ]
        if errors:
            raise _reject("Adaptive runtime trust admission failed", "PMADP501")
    return AdaptiveAdmission(plan, row, tuple(dag.units), target_engines, request)


__all__ = ["AdaptiveAdmission", "admit_adaptive_plan"]
