"""Fail-closed, whole-plan admission for local adaptive execution."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from etlantic.exceptions import PipelineExecutionError
from etlantic.plan.adaptive_model import ADAPTIVE_PLAN_SCHEMA, AdaptivePipelinePlan
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
