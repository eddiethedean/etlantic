"""Fail-closed, whole-plan admission for local adaptive execution."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
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
    compiler_pins: Mapping[str, Any] = field(default_factory=dict)
    dataframe_pins: Mapping[str, Any] = field(default_factory=dict)
    contract_pins: Mapping[str, type[Any]] = field(default_factory=dict)


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


def admit_adaptive_plan(
    plan: Any,
    *,
    request: RunRequest,
    runtime: Any | None = None,
    workspace: Any | None = None,
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
    if runtime is not None:
        from importlib.metadata import version

        try:
            for package, expected in row.version_requirements.items():
                if (
                    package
                    in {
                        "etlantic",
                        "etlantic-polars",
                        "etlantic-pandas",
                        "polars",
                        "pandas",
                        "pyarrow",
                    }
                    and version(package) != expected
                ):
                    raise ValueError("Backend version is not qualified")
        except Exception as exc:
            raise _reject(
                "Adaptive backend qualification version drifted", "PMADP501"
            ) from exc
    selected = set(
        plan.selected_nodes or (node.name for node in plan.logical_graph.nodes)
    )
    if request.retry.max_attempts > 1:
        declarations = request.metadata.get("retry_safety") or {}
        for name in selected:
            declaration = declarations.get(name)
            if (
                not isinstance(declaration, Mapping)
                or declaration.get("safe") is not True
            ):
                raise _reject("Adaptive retry safety is unproven", "PMADP522")
            maximum = declaration.get("max_attempts")
            if maximum is not None and (
                isinstance(maximum, bool)
                or not isinstance(maximum, int)
                or maximum < request.retry.max_attempts
            ):
                raise _reject(
                    "Adaptive retry exceeds its safety declaration", "PMADP522"
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
        "contracts",
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
        if set(record) - {
            "node_name",
            "logical_nodes",
            "target_id",
            "target_identity",
            "kind",
            "implementation",
            "binding",
            "operation",
        }:
            raise _reject(
                "Adaptive implementation record contains unknown fields", "PMADP400"
            )
        node_name = record.get("node_name")
        if not isinstance(node_name, str):
            raise _reject("Adaptive implementation name is invalid", "PMADP400")
        logical_node = plan.logical_graph.node_map().get(node_name)
        if (
            logical_node is None
            or record.get("kind") != logical_node.kind.value
            or tuple(record.get("logical_nodes") or ()) != (logical_node.name,)
        ):
            raise _reject(
                "Adaptive implementation logical identity drifted", "PMADP401"
            )
        if logical_node.kind.value in {"source", "sink"} and record.get(
            "operation"
        ) != ("read" if logical_node.kind.value == "source" else "prepare"):
            raise _reject("Adaptive I/O operation is unsupported", "PMADP400")
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
            from etlantic.runtime.physical_operations import validate_operation

            try:
                operation = validate_operation(unit.kind.value, requirement)
                logical_name = unit.metadata.get(
                    "etlantic.logical_node"
                ) or unit.metadata.get("logical_node")
                logical_node = (
                    plan.logical_graph.node_map().get(logical_name)
                    if isinstance(logical_name, str)
                    else None
                )
                if operation.get("port") is not None and (
                    logical_node is None
                    or operation["port"] not in {p.name for p in logical_node.outputs}
                ):
                    raise ValueError("Boundary port is not contracted")
                if (
                    operation.get("checkpoint", "memory") != "memory"
                    and workspace is None
                ):
                    raise ValueError("Named checkpoint requires workspace")
            except ValueError as exc:
                raise _reject(
                    "Adaptive boundary is missing a qualified operation descriptor",
                    "PMADP500",
                ) from exc
    import hashlib

    from etlantic.planning.adaptive_budget import canonical_chunks
    from etlantic.runtime.physical_host import resolve_contract_type

    contract_pins = {}
    stored_contracts = runtime_record.get("contracts") or {}
    for node in plan.logical_graph.nodes:
        for surface in (node, *node.inputs, *node.outputs):
            contract_id = surface.contract_id
            if contract_id is None:
                continue
            model = surface.contract_type or resolve_contract_type(contract_id)
            if model is None or not hasattr(model, "model_json_schema"):
                raise _reject("Adaptive contract definition is unavailable", "PMADP501")
            digest = hashlib.sha256()
            for chunk in canonical_chunks(model.model_json_schema()):
                digest.update(chunk)
            if stored_contracts.get(contract_id) != digest.hexdigest():
                raise _reject("Adaptive contract definition drifted", "PMADP501")
            contract_pins[contract_id] = model
    # Resolve the live trust boundary before a session is entered.  Stored
    # descriptors are data only; a live binding must still be present and
    # admissible for this invocation.
    compiler_pins: dict[str, Any] = {}
    dataframe_pins: dict[str, Any] = {}
    if runtime is not None:
        registry = getattr(runtime, "registry", None)
        from importlib.metadata import version

        from etlantic.plugin_trust import filter_plugins_by_allowlist
        from etlantic.profile import Profile
        from etlantic.registry import PluginDescriptor

        captured_profile = Profile.from_plan_snapshot(
            mutable_copy(plan.profile_snapshot)
        )
        from etlantic.runtime.adaptive_support import qualification_bundle

        bundle, _bundle_digest = qualification_bundle()
        for target in plan.inventory.targets:
            qualification = bundle["rows"].get(f"chain/1:{target.engine}")
            if qualification is not None:
                for package, expected in qualification["versions"].items():
                    if version(package) != expected:
                        raise _reject(
                            "Adaptive inventory dependency version drifted", "PMADP501"
                        )
        distributions = {}
        for target in plan.inventory.targets:
            package = (
                "local" if target.engine == "local" else f"etlantic-{target.engine}"
            )
            distributions[package] = PluginDescriptor(
                name=package,
                kind="dataframe",
                engine=target.engine,
                version=version("etlantic") if package == "local" else version(package),
            )
        authorized, _trust_diagnostics = filter_plugins_by_allowlist(
            distributions, captured_profile
        )
        if set(authorized) != set(distributions):
            raise _reject("Adaptive dependency is not authorized", "PMADP501")
        from etlantic.storage.memory import MemoryStorage

        if type(getattr(runtime, "memory", None)) is not MemoryStorage:
            raise _reject("Adaptive memory provider is unqualified", "PMADP501")
        from etlantic.io_policy import SafeIoPolicy

        safe_io = (plan.profile_snapshot or {}).get("safe_io")
        try:
            safe_policy = (
                SafeIoPolicy.from_dict(mutable_copy(safe_io)) if safe_io else None
            )
        except (TypeError, ValueError) as exc:
            raise _reject("Adaptive safe-I/O policy is invalid", "PMADP522") from exc
        live_bindings = getattr(registry, "bindings", {}) or {}
        allowed_providers = {"memory", "local", "python", "null", "json", "csv"}
        if getattr(runtime, "storage", {}).get("memory") is not getattr(
            runtime, "memory", None
        ):
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
            stored_binding = (runtime_record.get("bindings") or {}).get(node.name)
            if (
                stored_binding is None
                or mutable_copy(stored_binding) != descriptor.to_dict()
            ):
                raise _reject("Adaptive binding descriptor drifted", "PMADP501")
            if (
                provider in {"json", "csv"}
                and node.kind.value == "sink"
                and not getattr(safe_policy, "enable_locking", True)
            ):
                raise _reject(
                    "Adaptive publication requires destination locking", "PMADP522"
                )
            storage = getattr(runtime, "storage", {}).get(
                "memory" if provider in {"local", "python"} else provider
            )
            if provider in {"json", "csv", "null"}:
                from etlantic.storage.csv_binding import CsvStorage
                from etlantic.storage.json_binding import JsonStorage
                from etlantic.storage.null import NullStorage

                if (
                    type(storage)
                    is not {
                        "json": JsonStorage,
                        "csv": CsvStorage,
                        "null": NullStorage,
                    }[provider]
                ):
                    raise _reject(
                        "Adaptive storage implementation is unqualified", "PMADP501"
                    )

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
                if target.executor is not None:
                    raise _reject(
                        "Adaptive selected executor is unavailable", "PMADP501"
                    )
                continue
            info = getattr(executor, "info", None)
            if info is None:
                raise _reject("Adaptive executor metadata is missing", "PMADP501")
            expected_identity = (
                target.executor or f"etlantic.physical.{target.engine}/1"
            )
            expected_package = (
                "etlantic" if target.engine == "local" else f"etlantic-{target.engine}"
            )
            if (
                info.identity != expected_identity
                or info.package != expected_package
                or info.version != row.version_requirements.get(expected_package)
            ):
                raise _reject(
                    "Adaptive executor identity/package/version is not qualified",
                    "PMADP501",
                )
            if not set(info.evidence_refs).intersection(row.evidence_refs):
                raise _reject("Adaptive executor has no qualified evidence", "PMADP501")
            if "etlantic.plan/2" not in tuple(getattr(info, "plan_versions", ())):
                raise _reject("Adaptive executor does not support plan/2", "PMADP501")
            if "etlantic.physical_unit/1" not in tuple(
                getattr(info, "unit_protocol_versions", ())
            ):
                raise _reject(
                    "Adaptive executor does not support physical-unit/1", "PMADP501"
                )
            if info.capability_fingerprint != target.capability_fingerprint:
                raise _reject(
                    "Adaptive executor capability fingerprint drifted", "PMADP501"
                )
            analyze = getattr(executor, "analyze", None)
            if not callable(analyze):
                raise _reject("Adaptive executor has no metadata analysis", "PMADP501")
            support = analyze(plan, unit)
            if (
                getattr(support, "executor_identity", None) != info.identity
                or getattr(support, "protocol_version", None)
                != "etlantic.physical_unit/1"
            ):
                raise _reject(
                    "Adaptive executor support identity/protocol drifted", "PMADP501"
                )
            if unit.kind.value not in tuple(info.unit_kinds):
                raise _reject("Adaptive executor unit kind is unsupported", "PMADP500")
            if not getattr(support, "supported", False):
                raise _reject(
                    f"Physical executor does not support unit {unit.identity}",
                    "PMADP500",
                )
        from etlantic.runtime.dataframe_exec import resolve_dataframe_plugin
        from etlantic.runtime.physical_host import stored_implementations
        from etlantic.transform.compiler import preflight_portable_support
        from etlantic.transform.discovery import (
            discover_transform_compilers_for_profile,
        )

        try:
            descriptors = stored_implementations(plan)
            compilers = dict(getattr(registry, "transform_compilers", {}) or {})
            if descriptors and any(
                desc.engine not in compilers for desc in descriptors.values()
            ):
                compiler_snapshot = captured_profile.to_plan_snapshot()
                selected_targets = {decision.target_id for decision in plan.decisions}
                compiler_snapshot["eligible_targets"] = [
                    target_id
                    for target_id in captured_profile.eligible_targets
                    if target_id in selected_targets
                ]
                compilers.update(
                    discover_transform_compilers_for_profile(
                        Profile.from_plan_snapshot(compiler_snapshot)
                    )
                )
            for name, descriptor in descriptors.items():
                compiler = compilers.get(descriptor.engine)
                if (
                    compiler is None
                    or compiler.info.name != descriptor.compiler_name
                    or compiler.info.version != descriptor.compiler_version
                    or compiler.info.compiler_protocol != descriptor.compiler_protocol
                ):
                    raise ValueError(
                        "Stored compiler identity/version/protocol is unavailable"
                    )
                preflight_portable_support(
                    descriptor, compiler, engine=descriptor.engine
                )
                compiler_pins[name] = compiler
            for decision in plan.decisions:
                engine = target_by_id[decision.target_id].engine
                if engine not in dataframe_pins:
                    dataframe_pins[engine] = resolve_dataframe_plugin(
                        engine,
                        plugins=dict(getattr(runtime, "dataframe_plugins", {}) or {}),
                        node_name=decision.node_name,
                    )
                    plugin = dataframe_pins[engine]
                    info = plugin.info
                    import hashlib

                    from etlantic.planning.adaptive_budget import canonical_chunks

                    digest = hashlib.sha256()
                    for chunk in canonical_chunks(info.capabilities.to_dict()):
                        digest.update(chunk)
                    target = target_by_id[decision.target_id]
                    if (
                        info.engine != engine
                        or info.protocol_version != "etlantic.dataframe/1"
                    ):
                        raise ValueError("Dataframe protocol drifted")
                    if engine == "local":
                        from etlantic.dataframe.local import LocalDataframePlugin
                        from etlantic.registry import builtin_stub_registry

                        if (
                            type(plugin) is not LocalDataframePlugin
                            or info != LocalDataframePlugin().info
                        ):
                            raise ValueError("Local dataframe implementation drifted")
                        base = builtin_stub_registry().engines["local"]
                        signatures = set()
                        for capabilities in (
                            base,
                            replace(base, extras=base.extras | {"batch"}),
                        ):
                            capability_digest = hashlib.sha256()
                            for chunk in canonical_chunks(capabilities.to_dict()):
                                capability_digest.update(chunk)
                            signatures.add(capability_digest.hexdigest())
                        if target.capability_fingerprint not in signatures:
                            raise ValueError("Local host capability drifted")
                    elif digest.hexdigest() != target.capability_fingerprint:
                        raise ValueError("Dataframe capability drifted")
                    if engine != "local" and (
                        info.name != f"etlantic-{engine}"
                        or info.version != version(f"etlantic-{engine}")
                    ):
                        raise ValueError("Dataframe package identity/version drifted")
        except Exception as exc:
            raise _reject(
                "Adaptive compiler/dataframe dependency drifted", "PMADP501"
            ) from exc
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
        compiler_pins,
        dataframe_pins,
        contract_pins,
    )


__all__ = ["AdaptiveAdmission", "admit_adaptive_plan"]
