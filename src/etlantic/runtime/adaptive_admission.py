"""Fail-closed, whole-plan admission for local adaptive execution."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
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
    executor_pins: Mapping[str, Any] = field(default_factory=dict)
    storage_pins: Mapping[str, Any] = field(default_factory=dict)


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
        isinstance(retry.max_attempts, bool)
        or not isinstance(retry.max_attempts, int)
        or retry.max_attempts < 1
        or isinstance(retry.backoff_seconds, bool)
        or not isinstance(retry.backoff_seconds, (int, float))
        or not math.isfinite(float(retry.backoff_seconds))
        or retry.backoff_seconds < 0
    ):
        raise _reject("Adaptive retry policy is invalid", "PMADP522")
    for value in (
        request.timeout.run_seconds,
        request.timeout.step_seconds,
        request.cancellation.abandon_after_seconds,
    ):
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or value <= 0
        ):
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
    if runtime_record.get("schema") != "etlantic.adaptive_runtime/1":
        raise _reject("Adaptive runtime metadata schema is unsupported", "PMADP401")
    allowed_runtime = {
        "schema",
        "request",
        "support_row_id",
        "support_row",
        "policy",
        "binding",
        "bindings",
        "targets",
        "implementations",
        "compiler",
        "evidence_refs",
    }
    if set(runtime_record) - allowed_runtime:
        raise _reject("Adaptive runtime metadata contains unknown fields", "PMADP401")
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
    target_by_identity = {target.identity: target for target in plan.inventory.targets}
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
    dag = plan.physical_dag
    # Boundary markers are not executable operations. Require a closed
    # descriptor before any runtime/session effect is permitted.
    for unit in dag.units:
        if unit.kind.value in {"collection", "validation", "materialization", "reuse"}:
            requirement = unit.metadata.get("etlantic.requirement")
            if not isinstance(requirement, Mapping) or not requirement:
                raise _reject(
                    "Adaptive boundary is missing a qualified operation descriptor",
                    "PMADP500",
                )
    # Resolve the live trust boundary before a session is entered.  Stored
    # descriptors are data only; a live binding must still be present and
    # admissible for this invocation.
    if runtime is not None:
        registry = getattr(runtime, "registry", None)
        live_bindings = getattr(registry, "bindings", {}) or {}
        allowed_providers = {"memory", "local", "python", "null", "json", "csv"}
        manual_storage = getattr(runtime, "_manual_storage_bindings", {}) or {}
        if "memory" in manual_storage and getattr(runtime, "storage", {}).get(
            "memory"
        ) is not getattr(runtime, "memory", None):
            raise _reject("Adaptive storage binding identity drifted", "PMADP501")
        for node in plan.logical_graph.nodes:
            if node.name not in selected or node.kind.value not in {"source", "sink"}:
                continue
            binding = (
                request.binding_overrides.get(node.name) or node.binding or node.name
            )
            descriptor = live_bindings.get(binding)
            if descriptor is None:
                # Built-in in-memory bindings are implicit and require no
                # registry entry.  Any explicitly qualified binding must be
                # represented by a live descriptor.
                # The built-in memory connector is implicit; its binding may
                # legitimately have no registry descriptor until first write.
                if getattr(runtime, "memory", None) is None:
                    raise _reject("Adaptive binding is not live", "PMADP501")
                continue
            provider = str(getattr(descriptor, "provider", ""))
            if provider not in allowed_providers:
                raise _reject("Adaptive binding provider is not admitted", "PMADP501")
            if node.kind.value == "sink" and str(
                getattr(descriptor, "mode", "")
                or (getattr(descriptor, "metadata", {}) or {}).get("write_mode")
                or "overwrite"
            ) not in {"overwrite", "no_write"}:
                raise _reject("Adaptive sink write mode is not admitted", "PMADP522")
            # Built-in memory is an in-process singleton. Replacing its
            # binding after planning would silently redirect reads/writes and
            # defeats the stored trust decision, even when the replacement is
            # a subclass with the same nominal provider name.
            if (
                provider == "memory"
                and binding in {"memory", "local", "python"}
                and binding in manual_storage
                and getattr(runtime, "storage", {}).get(provider)
                is not getattr(runtime, "memory", None)
            ):
                raise _reject("Adaptive storage binding identity drifted", "PMADP501")

        # Physical executor analysis is a pure, metadata-only admission step.
        # It must run for every selected unit before the caller enters a
        # runtime session or permits any data effect.
        executors = getattr(runtime, "physical_executors", {}) or {}
        executor_pins: dict[str, Any] = {}
        for unit in dag.units:
            target = target_by_identity.get(unit.target_identity) or target_by_id.get(
                unit.target_identity
            )
            if target is None:
                raise _reject("Adaptive unit target is not admitted", "PMADP501")
            executor = executors.get(unit.target_identity) or executors.get(
                target.engine
            )
            executor_pins.setdefault(unit.target_identity, executor)
            executor_pins.setdefault(target.engine, executor)
            if executor is None:
                continue
            info = getattr(executor, "info", None)
            if info is None:
                raise _reject("Adaptive executor metadata is missing", "PMADP501")
            if (
                target.executor is not None
                and getattr(info, "identity", None) != target.executor
            ):
                raise _reject("Adaptive executor identity is not qualified", "PMADP501")
            if "etlantic.plan/2" not in tuple(getattr(info, "plan_versions", ())):
                raise _reject("Adaptive executor does not support plan/2", "PMADP501")
            if "etlantic.physical_unit/1" not in tuple(
                getattr(info, "unit_protocol_versions", ())
            ):
                raise _reject(
                    "Adaptive executor does not support physical-unit/1", "PMADP501"
                )
            if target.capability_fingerprint and getattr(
                info, "capability_fingerprint", ""
            ) not in {"", target.capability_fingerprint}:
                raise _reject(
                    "Adaptive executor capability fingerprint drifted", "PMADP501"
                )
            analyze = getattr(executor, "analyze", None)
            if not callable(analyze):
                raise _reject("Adaptive executor has no metadata analysis", "PMADP501")
            support = analyze(plan, unit)
            if not getattr(support, "supported", False):
                raise _reject(
                    f"Physical executor does not support unit {unit.identity}",
                    "PMADP500",
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
    storage_pins: dict[str, Any] = {}
    if runtime is not None:
        storage_pins.update(getattr(runtime, "storage", {}) or {})
        storage_pins.setdefault("memory", getattr(runtime, "memory", None))
    return AdaptiveAdmission(
        plan,
        row,
        tuple(dag.units),
        target_engines,
        request,
        executor_pins,
        storage_pins,
    )


__all__ = ["AdaptiveAdmission", "admit_adaptive_plan"]
