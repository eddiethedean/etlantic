"""Execute a transformation step through the dataframe protocol."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from etlantic.capabilities import PluginCapabilities
from etlantic.dataframe.discovery import load_dataframe_plugin
from etlantic.dataframe.protocol import (
    DATAFRAME_ENGINES,
    ArtifactOwnership,
    DataframeExecutionContext,
    DataframeOutputBundle,
    DataframePlugin,
    DataframeValidationPolicy,
    ValidationDecision,
)
from etlantic.exceptions import NodeExecutionError
from etlantic.interchange.tabular.execute import boundary_for_input
from etlantic.model import Node
from etlantic.plan.model import PipelinePlan
from etlantic.registry import ImplementationDescriptor
from etlantic.runtime.logging import redact_message
from etlantic.runtime.state import FailureStage
from etlantic.transformation import ImplementationRecord

_DECISION_RANK = {
    ValidationDecision.PASSED: 0,
    ValidationDecision.SKIPPED: 0,
    ValidationDecision.OBSERVED: 1,
    ValidationDecision.WARNED: 2,
    ValidationDecision.REJECTED: 3,
    ValidationDecision.QUARANTINED: 3,
    ValidationDecision.FAILED: 4,
}


def is_dataframe_engine(engine: str, *, registry: Any | None = None) -> bool:
    """Return whether an engine is a built-in or registered dataframe engine."""
    if engine in DATAFRAME_ENGINES:
        return True
    if registry is None:
        return False
    capabilities = getattr(registry, "engines", {}).get(engine)
    registered_kind = any(
        descriptor.engine == engine and descriptor.kind == "dataframe"
        for descriptor in getattr(registry, "plugins", {}).values()
    )
    return bool(
        (capabilities is not None and capabilities.dataframe) or registered_kind
    )


def resolve_dataframe_plugin(
    engine: str,
    *,
    plugins: dict[str, DataframePlugin] | None = None,
) -> DataframePlugin:
    if plugins and engine in plugins:
        return plugins[engine]
    plugin = load_dataframe_plugin(engine)
    if plugin is not None:
        return plugin
    raise NodeExecutionError(
        f"No dataframe plugin available for engine {engine!r}. "
        f"Install etlantic-{engine}.",
        stage=FailureStage.TRANSFORM.value,
        code="PMEXEC420",
    )


def should_collect(
    plan: PipelinePlan,
    node_name: str,
    port_name: str = "result",
) -> bool:
    """Return True when this output port must be collected before continue."""
    for boundary in plan.materialization_boundaries:
        if boundary.producer_node != node_name:
            continue
        if boundary.producer_port != port_name and boundary.producer_port != "*":
            continue
        # fan_out_reuse keeps native frames in memory (ownership copy), no collect.
        if boundary.reason in {
            "collection_point",
            "sink_publication",
            "cross_engine",
            "validation_boundary",
        }:
            return True
    for resolution in plan.output_resolutions:
        if (
            resolution.node_name == node_name
            and resolution.port_name == port_name
            and resolution.artifact.strategy.value in {"durable", "external"}
        ):
            return True
    return False


def has_fan_out(plan: PipelinePlan, node_name: str, port_name: str) -> bool:
    return any(
        b.producer_node == node_name
        and (b.producer_port == port_name or b.producer_port == "*")
        and b.reason == "fan_out_reuse"
        for b in plan.materialization_boundaries
    )


def ownership_for_engine(
    engine: str,
    *,
    fan_out: bool = False,
    capabilities: PluginCapabilities | None = None,
) -> ArtifactOwnership:
    """Choose artifact ownership from fan-out and engine capabilities."""
    if fan_out or engine == "pandas":
        return ArtifactOwnership.COPIED
    if capabilities is not None:
        return (
            ArtifactOwnership.SHARED
            if capabilities.thread_safe
            else ArtifactOwnership.COPIED
        )
    return ArtifactOwnership.SHARED


def _worst_decision(
    current: ValidationDecision, new: ValidationDecision
) -> ValidationDecision:
    if _DECISION_RANK.get(new, 0) >= _DECISION_RANK.get(current, 0):
        return new
    return current


def _unpack_validation(
    result: tuple[Any, ...],
) -> tuple[Any, ValidationDecision, list[dict[str, Any]], Any | None]:
    if len(result) >= 4:
        return result[0], result[1], list(result[2] or []), result[3]
    return result[0], result[1], list(result[2] or []), None


async def execute_dataframe_step(
    *,
    plugin: DataframePlugin,
    impl: ImplementationRecord | None,
    node: Node,
    inputs: dict[str, Any],
    params: dict[str, Any],
    plan: PipelinePlan,
    run_id: str,
    attempt: int,
    collect_outputs: bool | None = None,
    descriptor: ImplementationDescriptor | None = None,
) -> DataframeOutputBundle:
    """Materialize → invoke/compile → normalize → validate through a dataframe plugin."""
    engine = (
        (descriptor.engine if descriptor is not None else None)
        or (impl.engine if impl is not None else None)
        or "local"
    )
    output_ports = tuple(p.name for p in node.outputs) or ("result",)
    any_fan_out = any(has_fan_out(plan, node.name, p) for p in output_ports)
    # Initial context; per-port collect overrides applied below.
    context = DataframeExecutionContext(
        run_id=run_id,
        pipeline_id=plan.pipeline_id,
        plan_id=plan.plan_id,
        step_name=node.name,
        engine=engine,
        attempt=attempt,
        collect=False,
        ownership=ownership_for_engine(engine, fan_out=any_fan_out),
        validation_policy=DataframeValidationPolicy.from_dict(
            plan.metadata.get("validation_policy")
        ),
    )

    materialized: dict[str, Any] = {}
    interchange_mechanisms: list[str] = []
    for port_name, value in inputs.items():
        contract = None
        for port in node.inputs:
            if port.name == port_name:
                contract = port.contract_type
                break
        try:
            interchange = boundary_for_input(plan, node.name, port_name)
            input_context = replace(context, interchange=interchange)
            if interchange is not None:
                interchange_mechanisms.append(interchange.mechanism.value)
            frame = plugin.materialize_input(
                value,
                contract_type=contract,
                context=input_context,
                port_name=port_name,
            )
            result = plugin.validate_frame(
                frame,
                contract_type=contract,
                context=input_context,
                boundary="input_validation",
                port_name=port_name,
            )
            frame, decision, diags, _invalid = _unpack_validation(result)
            if decision is ValidationDecision.FAILED:
                raise NodeExecutionError(
                    redact_message(
                        f"Input validation failed for {node.name}.{port_name}"
                    ),
                    node_name=node.name,
                    stage=FailureStage.INPUT_VALIDATION.value,
                    code="PMEXEC330",
                )
            materialized[port_name] = frame
            _ = diags
        except NodeExecutionError:
            raise
        except Exception as exc:
            raise NodeExecutionError(
                redact_message(
                    f"Dataframe materialization failed for "
                    f"{node.name}.{port_name}: {exc}"
                ),
                node_name=node.name,
                stage=FailureStage.TRANSFORM.value,
                code="PMEXEC421",
                cause=exc,
            ) from exc

    # Detect overlapping input/parameter names.
    overlap = set(materialized) & set(params)
    if overlap:
        raise NodeExecutionError(
            redact_message(
                f"Parameter names collide with input ports on {node.name}: "
                f"{sorted(overlap)}"
            ),
            node_name=node.name,
            stage=FailureStage.TRANSFORM.value,
            code="PMEXEC423",
        )

    try:
        if descriptor is not None and descriptor.kind == "portable_compiled":
            raw_result = await _execute_portable(
                descriptor=descriptor,
                inputs=materialized,
                parameters=params,
                plan=plan,
                node=node,
                context=context,
            )
        else:
            if impl is None:
                raise NodeExecutionError(
                    redact_message(
                        f"No native implementation for dataframe step {node.name}"
                    ),
                    node_name=node.name,
                    stage=FailureStage.TRANSFORM.value,
                    code="PMEXEC321",
                )
            raw_result = plugin.invoke(
                callable_=impl.callable,
                inputs=materialized,
                parameters=params,
                context=context,
            )
            if hasattr(raw_result, "__await__"):
                raw_result = await raw_result
    except NodeExecutionError:
        raise
    except Exception as exc:
        raise NodeExecutionError(
            redact_message(
                f"Dataframe implementation failed for {node.name} "
                f"(engine={engine}, attempt={attempt}): {exc}"
            ),
            node_name=node.name,
            stage=FailureStage.TRANSFORM.value,
            code="PMEXEC422",
            cause=exc,
        ) from exc

    bundle = plugin.normalize_output(
        raw_result,
        output_ports=output_ports,
        context=context,
    )

    validated_valid: dict[str, Any] = {}
    invalid_out: dict[str, Any] = dict(bundle.invalid)
    aggregate = ValidationDecision.PASSED
    any_collected = False
    invalid_count = 0
    rejected_count = 0

    for port_name, value in bundle.valid.items():
        contract = None
        for port in node.outputs:
            if port.name == port_name:
                contract = port.contract_type
                break
        if contract is None:
            contract = node.contract_type
        port_collect = (
            should_collect(plan, node.name, port_name)
            if collect_outputs is None
            else collect_outputs
        )
        port_fan_out = has_fan_out(plan, node.name, port_name)
        port_context = DataframeExecutionContext(
            run_id=context.run_id,
            pipeline_id=context.pipeline_id,
            plan_id=context.plan_id,
            step_name=context.step_name,
            engine=context.engine,
            attempt=context.attempt,
            collect=port_collect,
            ownership=ownership_for_engine(engine, fan_out=port_fan_out),
            validation_policy=context.validation_policy,
            metadata=context.metadata,
        )
        if port_collect:
            any_collected = True
        value = plugin.collect_if_needed(value, context=port_context)
        result = plugin.validate_frame(
            value,
            contract_type=contract,
            context=port_context,
            boundary="output_validation",
            port_name=port_name,
        )
        value, decision, diags, invalid = _unpack_validation(result)
        if decision is ValidationDecision.FAILED:
            raise NodeExecutionError(
                redact_message(f"Output validation failed for {node.name}.{port_name}"),
                node_name=node.name,
                stage=FailureStage.OUTPUT_VALIDATION.value,
                code="PMEXEC330",
            )
        if invalid is not None:
            invalid_out[port_name] = invalid
            count = plugin.row_count(invalid)
            if count:
                invalid_count += count
                if decision in {
                    ValidationDecision.REJECTED,
                    ValidationDecision.QUARANTINED,
                }:
                    rejected_count += count
        value = plugin.ensure_ownership(
            value, ownership=port_context.ownership, context=port_context
        )
        validated_valid[port_name] = value
        bundle.diagnostics.extend(diags)
        aggregate = _worst_decision(aggregate, decision)

    bundle.valid = validated_valid
    bundle.invalid = invalid_out
    bundle.validation_decision = aggregate
    bundle.metrics.phases = [
        "materialize",
        "invoke",
        "normalize",
        "validate",
        "metrics",
        "cleanup",
    ]
    bundle.metrics.collected = any_collected
    if interchange_mechanisms:
        bundle.metrics.converted = True
        bundle.metrics.conversion_kind = interchange_mechanisms[0]
        if len(interchange_mechanisms) > 1:
            bundle.metrics.extras["interchange_mechanisms"] = list(
                interchange_mechanisms
            )
    bundle.metrics.ownership = context.ownership.value
    bundle.metrics.invalid_count = invalid_count or None
    bundle.metrics.rejected_count = rejected_count or None
    if bundle.metrics.rows_in is None:
        bundle.metrics.rows_in = sum(
            (plugin.row_count(v) or 0) for v in materialized.values()
        )
    if bundle.metrics.rows_out is None:
        bundle.metrics.rows_out = sum(
            (plugin.row_count(v) or 0) for v in bundle.valid.values()
        )
    return bundle


async def _execute_portable(
    *,
    descriptor: ImplementationDescriptor,
    inputs: dict[str, Any],
    parameters: dict[str, Any],
    plan: PipelinePlan,
    node: Node,
    context: DataframeExecutionContext,
) -> Any:
    from etlantic.profile import Profile, resolve_profile
    from etlantic.transform.compiler import (
        TransformCompileContext,
        TransformExecutionContext,
    )
    from etlantic.transform.discovery import (
        discover_transform_compilers_for_profile,
    )

    profile = getattr(plan, "profile_snapshot", None)
    if isinstance(profile, dict):
        profile = Profile.from_plan_snapshot(profile)
    elif not isinstance(profile, Profile):
        profile = resolve_profile(getattr(plan, "profile_name", None))

    compiler = None
    if descriptor.compiler_name:
        for candidate in discover_transform_compilers_for_profile(profile).values():
            info = candidate.info
            if info.name != descriptor.compiler_name:
                continue
            if (
                descriptor.compiler_version
                and info.version != descriptor.compiler_version
            ):
                continue
            compiler = candidate
            break
        if compiler is None:
            raise NodeExecutionError(
                redact_message(
                    f"Planned transform compiler {descriptor.compiler_name!r}"
                    + (
                        f"@{descriptor.compiler_version}"
                        if descriptor.compiler_version
                        else ""
                    )
                    + f" is not available for step {node.name}"
                ),
                node_name=node.name,
                stage=FailureStage.TRANSFORM.value,
                code="PMXFORM302",
            )
    else:
        compilers = discover_transform_compilers_for_profile(profile)
        compiler = compilers.get(descriptor.engine)
    if compiler is None:
        raise NodeExecutionError(
            redact_message(
                f"No transform compiler for engine {descriptor.engine!r} "
                f"on step {node.name}"
            ),
            node_name=node.name,
            stage=FailureStage.TRANSFORM.value,
            code="PMXFORM302",
        )
    if compiler.info.engine and compiler.info.engine != descriptor.engine:
        raise NodeExecutionError(
            redact_message(
                f"Transform compiler {compiler.info.name!r} targets "
                f"{compiler.info.engine!r}, not planned engine "
                f"{descriptor.engine!r} on step {node.name}"
            ),
            node_name=node.name,
            stage=FailureStage.TRANSFORM.value,
            code="PMXFORM302",
        )
    portable_plan = descriptor.portable_plan
    if not portable_plan:
        raise NodeExecutionError(
            redact_message(
                f"Plan step {node.name} is portable_compiled but missing embedded IR"
            ),
            node_name=node.name,
            stage=FailureStage.TRANSFORM.value,
            code="PMXFORM501",
        )
    compile_ctx = TransformCompileContext(
        pipeline_id=plan.pipeline_id,
        plan_id=plan.plan_id,
        step_name=node.name,
        profile_name=plan.profile_name,
        engine=descriptor.engine,
    )
    compiled = compiler.compile(
        portable_plan,
        context=compile_ctx,
        requirements=descriptor.requirements,
    )
    exec_ctx = TransformExecutionContext(
        run_id=context.run_id,
        pipeline_id=context.pipeline_id,
        plan_id=context.plan_id,
        step_name=context.step_name,
        engine=context.engine,
        attempt=context.attempt,
        collect=context.collect,
    )
    bundle = await compiler.execute(
        compiled,
        inputs=inputs,
        parameters=parameters,
        context=exec_ctx,
    )
    if len(bundle.valid) == 1:
        return next(iter(bundle.valid.values()))
    return dict(bundle.valid)
