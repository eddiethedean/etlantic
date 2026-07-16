"""Execute a transformation step through the dataframe protocol."""

from __future__ import annotations

from typing import Any

from pipelantic.dataframe.discovery import load_dataframe_plugin
from pipelantic.dataframe.protocol import (
    DATAFRAME_ENGINES,
    ArtifactOwnership,
    DataframeExecutionContext,
    DataframeOutputBundle,
    DataframePlugin,
    DataframeValidationPolicy,
    ValidationDecision,
)
from pipelantic.exceptions import NodeExecutionError
from pipelantic.model import Node
from pipelantic.plan.model import PipelinePlan
from pipelantic.runtime.logging import redact_message
from pipelantic.runtime.state import FailureStage
from pipelantic.transformation import ImplementationRecord


def is_dataframe_engine(engine: str) -> bool:
    return engine in DATAFRAME_ENGINES


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
        f"Install pipelantic-{engine}.",
        stage=FailureStage.TRANSFORM.value,
        code="PMEXEC420",
    )


def should_collect(
    plan: PipelinePlan,
    node_name: str,
    port_name: str = "result",
) -> bool:
    for boundary in plan.materialization_boundaries:
        if boundary.producer_node != node_name:
            continue
        if boundary.producer_port != port_name and boundary.producer_port != "*":
            continue
        if boundary.reason in {
            "collection_point",
            "sink_publication",
            "cross_engine",
            "validation_boundary",
            "fan_out_reuse",
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


def ownership_for_engine(engine: str, *, fan_out: bool = False) -> ArtifactOwnership:
    if engine == "pandas" or fan_out:
        return ArtifactOwnership.COPIED
    return ArtifactOwnership.SHARED


async def execute_dataframe_step(
    *,
    plugin: DataframePlugin,
    impl: ImplementationRecord,
    node: Node,
    inputs: dict[str, Any],
    params: dict[str, Any],
    plan: PipelinePlan,
    run_id: str,
    attempt: int,
    collect_outputs: bool | None = None,
) -> DataframeOutputBundle:
    """Materialize → invoke → normalize → validate through a dataframe plugin."""
    engine = impl.engine
    collect = (
        should_collect(plan, node.name) if collect_outputs is None else collect_outputs
    )
    context = DataframeExecutionContext(
        run_id=run_id,
        pipeline_id=plan.pipeline_id,
        plan_id=plan.plan_id,
        step_name=node.name,
        engine=engine,
        attempt=attempt,
        collect=collect,
        ownership=ownership_for_engine(engine),
        validation_policy=DataframeValidationPolicy.from_dict(
            plan.metadata.get("validation_policy")
        ),
    )

    materialized: dict[str, Any] = {}
    for port_name, value in inputs.items():
        contract = None
        for port in node.inputs:
            if port.name == port_name:
                contract = port.contract_type
                break
        try:
            frame = plugin.materialize_input(
                value,
                contract_type=contract,
                context=context,
                port_name=port_name,
            )
            frame, decision, diags = plugin.validate_frame(
                frame,
                contract_type=contract,
                context=context,
                boundary="input_validation",
                port_name=port_name,
            )
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
                    f"Dataframe materialization failed for {node.name}.{port_name}: {exc}"
                ),
                node_name=node.name,
                stage=FailureStage.TRANSFORM.value,
                code="PMEXEC421",
                cause=exc,
            ) from exc

    try:
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

    output_ports = tuple(p.name for p in node.outputs) or ("result",)
    bundle = plugin.normalize_output(
        raw_result,
        output_ports=output_ports,
        context=context,
    )

    validated_valid: dict[str, Any] = {}
    for port_name, value in bundle.valid.items():
        contract = None
        for port in node.outputs:
            if port.name == port_name:
                contract = port.contract_type
                break
        if contract is None:
            contract = node.contract_type
        value = plugin.collect_if_needed(value, context=context)
        value, decision, diags = plugin.validate_frame(
            value,
            contract_type=contract,
            context=context,
            boundary="output_validation",
            port_name=port_name,
        )
        if decision is ValidationDecision.FAILED:
            raise NodeExecutionError(
                redact_message(f"Output validation failed for {node.name}.{port_name}"),
                node_name=node.name,
                stage=FailureStage.OUTPUT_VALIDATION.value,
                code="PMEXEC330",
            )
        value = plugin.ensure_ownership(
            value, ownership=context.ownership, context=context
        )
        validated_valid[port_name] = value
        bundle.diagnostics.extend(diags)

    bundle.valid = validated_valid
    bundle.metrics.phases = [
        "materialize",
        "invoke",
        "normalize",
        "validate",
        "metrics",
        "cleanup",
    ]
    bundle.metrics.collected = collect
    bundle.metrics.ownership = context.ownership.value
    if bundle.metrics.rows_in is None:
        bundle.metrics.rows_in = sum(
            (plugin.row_count(v) or 0) for v in materialized.values()
        )
    if bundle.metrics.rows_out is None:
        bundle.metrics.rows_out = sum(
            (plugin.row_count(v) or 0) for v in bundle.valid.values()
        )
    return bundle
