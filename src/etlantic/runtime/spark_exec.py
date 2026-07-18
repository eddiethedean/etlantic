"""Execute transformation steps through the Spark protocol."""

from __future__ import annotations

from typing import Any

from etlantic.exceptions import NodeExecutionError
from etlantic.model import Node
from etlantic.plan.model import PipelinePlan
from etlantic.registry import ImplementationDescriptor
from etlantic.runtime.logging import redact_message
from etlantic.runtime.state import FailureStage
from etlantic.spark.discovery import load_spark_plugin, load_spark_provider
from etlantic.spark.protocol import (
    SPARK_ENGINES,
    CompiledSparkPlan,
    DatasetRef,
    ExpressionStrategy,
    SparkAction,
    SparkActionKind,
    SparkCompilationContext,
    SparkDataFrameHandle,
    SparkExecutionContext,
    SparkExecutionResult,
    SparkPlanRegion,
    SparkPlugin,
    SparkUdfPolicy,
    SparkWrite,
    SparkWriteMode,
)
from etlantic.spark.provider import (
    ResourceContext,
    SparkProvider,
    SparkSessionHandle,
    SparkSessionRequest,
)
from etlantic.transformation import ImplementationRecord


def is_spark_engine(engine: str) -> bool:
    return engine in SPARK_ENGINES


def resolve_spark_plugin(
    engine: str = "pyspark",
    *,
    plugins: dict[str, SparkPlugin] | None = None,
) -> SparkPlugin:
    if plugins:
        if engine in plugins:
            return plugins[engine]
        if engine == "spark" and "pyspark" in plugins:
            return plugins["pyspark"]
        if engine == "pyspark" and "spark" in plugins:
            return plugins["spark"]
    plugin = load_spark_plugin(engine)
    if plugin is not None:
        return plugin
    raise NodeExecutionError(
        f"No Spark plugin available for engine {engine!r}. Install etlantic-pyspark.",
        node_name="spark",
        stage=FailureStage.TRANSFORM.value,
        code="PMEXEC440",
    )


def resolve_spark_provider(
    name: str = "local",
    *,
    providers: dict[str, SparkProvider] | None = None,
) -> SparkProvider:
    if providers and name in providers:
        return providers[name]
    provider = load_spark_provider(name)
    if provider is not None:
        return provider
    raise NodeExecutionError(
        f"No Spark provider available for {name!r}. Install etlantic-pyspark.",
        node_name="spark",
        stage=FailureStage.TRANSFORM.value,
        code="PMEXEC441",
    )


def _job_group(*, run_id: str, region_id: str | None, attempt: int) -> str:
    region = region_id or "default"
    return f"etlantic:{run_id}:{region}:{attempt}"


def _execution_context(
    *,
    plan: PipelinePlan,
    node: Node,
    run_id: str,
    attempt: int,
    region_id: str | None = None,
    session_handle: SparkSessionHandle | None = None,
    streaming: bool = False,
    allow_udfs: bool = True,
) -> SparkExecutionContext:
    return SparkExecutionContext(
        run_id=run_id,
        pipeline_id=plan.pipeline_id,
        plan_id=plan.plan_id,
        step_name=node.name,
        region_id=region_id,
        engine="pyspark",
        attempt=attempt,
        job_group=_job_group(run_id=run_id, region_id=region_id, attempt=attempt),
        streaming=streaming,
        session_handle_id=session_handle.identity if session_handle else None,
        allow_udfs=allow_udfs,
        metadata={"security_domain": plan.security_domain},
    )


def parse_udf_policy(value: str | SparkUdfPolicy | None) -> SparkUdfPolicy:
    if value is None:
        return SparkUdfPolicy.WARN
    if isinstance(value, SparkUdfPolicy):
        return value
    try:
        return SparkUdfPolicy(str(value))
    except ValueError:
        return SparkUdfPolicy.WARN


def assert_udf_policy(
    *,
    strategies: list[ExpressionStrategy] | tuple[ExpressionStrategy, ...],
    policy: SparkUdfPolicy,
    node_name: str,
) -> list[dict[str, Any]]:
    """Enforce UDF policy; return warning diagnostics or raise."""
    udf_kinds = {
        ExpressionStrategy.SCALAR_PYTHON_UDF,
        ExpressionStrategy.PANDAS_UDF,
        ExpressionStrategy.ITERATOR_PANDAS_UDF,
    }
    used = [s for s in strategies if s in udf_kinds]
    if not used:
        return []
    names = [s.value for s in used]
    if policy in {SparkUdfPolicy.NATIVE_REQUIRED, SparkUdfPolicy.DENY}:
        raise NodeExecutionError(
            f"UDF strategies {names} forbidden by spark_udf_policy={policy.value!r}.",
            node_name=node_name,
            stage=FailureStage.TRANSFORM.value,
            code="PMSPARK310",
        )
    if policy is SparkUdfPolicy.WARN:
        return [
            {
                "code": "PMSPARK311",
                "severity": "warning",
                "message": (
                    f"Spark step uses UDF strategies {names}; "
                    "native expressions preferred for portability."
                ),
            }
        ]
    return []


def assert_batch_not_in_streaming(
    *,
    streaming_region: bool,
    batch_only: bool,
    node_name: str,
) -> None:
    """Reject batch-only transformations from streaming regions."""
    if streaming_region and batch_only:
        raise NodeExecutionError(
            f"Batch-only transformation {node_name!r} cannot run in a streaming region.",
            node_name=node_name,
            stage=FailureStage.TRANSFORM.value,
            code="PMSPARK320",
        )


async def acquire_session(
    *,
    provider: SparkProvider,
    plan: PipelinePlan,
    run_id: str,
    enable_delta: bool = False,
    streaming: bool = False,
    resolve_secret: Any | None = None,
) -> SparkSessionHandle:
    request = SparkSessionRequest(
        app_name=f"etlantic-{plan.pipeline_name or plan.pipeline_id}",
        master=(plan.execution_settings or {}).get("spark_master"),
        execution_mode="streaming" if streaming else "batch",
        enable_delta=enable_delta,
        checkpoint_root=(plan.execution_settings or {}).get("spark_checkpoint_root"),
        required_capabilities=tuple(
            (plan.profile_snapshot or {}).get("required_spark_capabilities") or ()
        ),
        secret_refs=dict((plan.profile_snapshot or {}).get("secrets") or {}),
    )
    # Strip secret values — only refs belong in the request metadata path.
    # secret_refs from profile are SecretRef dicts; provider resolves at acquire.
    ctx = ResourceContext(
        run_id=run_id,
        pipeline_id=plan.pipeline_id,
        plan_id=plan.plan_id,
        security_domain=plan.security_domain,
        resolve_secret=resolve_secret,
    )
    # Ensure request.to_dict() never embeds passwords: secret_refs stay as keys.
    _ = request.to_dict()
    return provider.acquire(request, ctx)


async def release_session(
    *,
    provider: SparkProvider,
    handle: SparkSessionHandle,
    plan: PipelinePlan,
    run_id: str,
) -> None:
    ctx = ResourceContext(
        run_id=run_id,
        pipeline_id=plan.pipeline_id,
        plan_id=plan.plan_id,
        security_domain=plan.security_domain,
    )
    provider.release(handle, ctx)


async def execute_spark_source(
    *,
    plugin: SparkPlugin,
    node: Node,
    plan: PipelinePlan,
    location: str | None,
    binding: str | None,
) -> DatasetRef:
    """Resolve a Spark source to a DatasetRef without embedding credentials."""
    return plugin.dataset_from_binding(
        binding=binding or node.binding or node.name,
        location=location,
        metadata={"node": node.name, "plan_id": plan.plan_id},
    )


async def compile_spark_region(
    *,
    plugin: SparkPlugin,
    region: SparkPlanRegion,
    plan: PipelinePlan,
    run_id: str,
    udf_policy: SparkUdfPolicy = SparkUdfPolicy.WARN,
) -> CompiledSparkPlan:
    context = SparkCompilationContext(
        run_id=run_id,
        pipeline_id=plan.pipeline_id,
        plan_id=plan.plan_id,
        region_id=region.identity,
        security_domain=plan.security_domain,
        udf_policy=udf_policy,
        streaming=region.streaming,
        required_capabilities=tuple(
            (plan.profile_snapshot or {}).get("required_spark_capabilities") or ()
        ),
    )
    compiled = plugin.compile(region, context=context)
    assert_udf_policy(
        strategies=compiled.expression_strategies,
        policy=udf_policy,
        node_name=region.identity,
    )
    return compiled


async def execute_portable_spark_step(
    *,
    plugin: SparkPlugin,
    descriptor: ImplementationDescriptor,
    node: Node,
    inputs: dict[str, Any],
    params: dict[str, Any],
    plan: PipelinePlan,
    run_id: str,
    attempt: int,
    session_handle: SparkSessionHandle | None = None,
) -> Any:
    """Execute a portable_compiled step on Spark without region UDF fusion."""
    from etlantic.transform.compiler import (
        TransformCompileContext,
        TransformExecutionContext,
    )
    from etlantic.transform.discovery import (
        discover_transform_compilers,
        load_transform_compiler,
    )

    if session_handle is None or session_handle.session is None:
        raise NodeExecutionError(
            redact_message(
                f"portable Spark step {node.name!r} requires an acquired Spark session"
            ),
            node_name=node.name,
            stage=FailureStage.TRANSFORM.value,
            code="PMXFORM302",
        )

    compiler = None
    if descriptor.compiler_name:
        for candidate in discover_transform_compilers().values():
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
    else:
        compiler = load_transform_compiler(descriptor.engine)
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
    to_dataframe = getattr(plugin, "_to_dataframe", None)
    exec_ctx = TransformExecutionContext(
        run_id=run_id,
        pipeline_id=plan.pipeline_id,
        plan_id=plan.plan_id,
        step_name=node.name,
        engine=descriptor.engine,
        attempt=attempt,
        collect=False,
        metadata={
            "spark_session": session_handle.session,
            "to_dataframe": to_dataframe,
            "udf_policy": "deny",
        },
    )
    bundle = await compiler.execute(
        compiled,
        inputs=inputs,
        parameters=params,
        context=exec_ctx,
    )
    if len(bundle.valid) == 1:
        return next(iter(bundle.valid.values()))
    return dict(bundle.valid)


async def execute_spark_step(
    *,
    plugin: SparkPlugin,
    impl: ImplementationRecord,
    node: Node,
    inputs: dict[str, Any],
    params: dict[str, Any],
    plan: PipelinePlan,
    run_id: str,
    attempt: int,
    session_handle: SparkSessionHandle | None = None,
    region_id: str | None = None,
    streaming: bool = False,
    batch_only: bool = False,
    udf_policy: SparkUdfPolicy = SparkUdfPolicy.WARN,
) -> Any:
    """Invoke a Spark transformation; keep DataFrame handles lazy."""
    assert_batch_not_in_streaming(
        streaming_region=streaming,
        batch_only=batch_only,
        node_name=node.name,
    )
    allow_udfs = udf_policy not in {
        SparkUdfPolicy.NATIVE_REQUIRED,
        SparkUdfPolicy.DENY,
    }
    ctx = _execution_context(
        plan=plan,
        node=node,
        run_id=run_id,
        attempt=attempt,
        region_id=region_id,
        session_handle=session_handle,
        streaming=streaming,
        allow_udfs=allow_udfs,
    )
    # Attach live session for the plugin implementation if present
    if session_handle is not None:
        params = {**dict(params), "_spark_session": session_handle.session}
    result = plugin.execute_step(
        callable_=impl.callable,
        inputs=inputs,
        params=params,
        context=ctx,
    )
    if isinstance(result, (SparkDataFrameHandle, DatasetRef, SparkWrite)):
        return result
    # Allow native Spark DataFrame / plugin-private wrappers
    return result


async def execute_spark_sink(
    *,
    plugin: SparkPlugin,
    node: Node,
    source_value: Any,
    plan: PipelinePlan,
    run_id: str,
    attempt: int,
    target_location: str | None,
    write_mode: str = "append",
    merge_keys: tuple[str, ...] = (),
    partition_by: tuple[str, ...] = (),
    session_handle: SparkSessionHandle | None = None,
    enable_delta: bool = False,
) -> SparkExecutionResult:
    """Publish a Spark/Delta sink with fail-closed write modes."""
    try:
        mode = SparkWriteMode(write_mode)
    except ValueError as exc:
        raise NodeExecutionError(
            f"Unsupported Spark write mode {write_mode!r}.",
            node_name=node.name,
            stage=FailureStage.WRITE.value,
            code="PMSPARK330",
        ) from exc

    if mode in {SparkWriteMode.MERGE, SparkWriteMode.UPSERT} and not enable_delta:
        caps = plugin.capabilities()
        if not caps.supports("spark_delta") and not caps.supports("spark_merge"):
            raise NodeExecutionError(
                f"Write mode {mode.value!r} requires Delta capabilities; failing closed.",
                node_name=node.name,
                stage=FailureStage.WRITE.value,
                code="PMSPARK331",
            )

    target = plugin.dataset_from_binding(
        binding=node.binding or node.name,
        location=target_location,
        metadata={"node": node.name, "write_mode": mode.value},
    )
    if enable_delta and target.format is None:
        target = DatasetRef(
            name=target.name,
            format="delta",
            path=target.path or target_location,
            table=target.table,
            options=target.options,
        )

    write = SparkWrite(
        source=source_value,
        target=target,
        mode=mode,
        merge_keys=merge_keys,
        partition_by=partition_by,
    )
    ctx = _execution_context(
        plan=plan,
        node=node,
        run_id=run_id,
        attempt=attempt,
        session_handle=session_handle,
    )
    return plugin.execute_write(write, context=ctx)


def region_for_node(plan: PipelinePlan, node_name: str) -> SparkPlanRegion | None:
    for region in plan.regions:
        if node_name in region.node_names and is_spark_engine(region.engine):
            return SparkPlanRegion(
                identity=region.identity,
                node_names=region.node_names,
                security_domain=region.security_domain,
                streaming=bool((region.metadata or {}).get("streaming")),
                metadata=dict(region.metadata or {}),
            )
    return None


def default_region_compile(
    region: SparkPlanRegion,
    *,
    strategy: ExpressionStrategy = ExpressionStrategy.NATIVE_DF,
) -> CompiledSparkPlan:
    """Helper used by plugins for a minimal fused-region compile."""
    actions = tuple(
        SparkAction(
            kind=SparkActionKind.MATERIALIZE,
            node_name=name,
            reason="region_boundary",
        )
        for name in region.node_names[-1:]
    )
    return CompiledSparkPlan(
        region_id=region.identity,
        node_names=region.node_names,
        actions=actions,
        expression_strategies=(strategy,),
        streaming=region.streaming,
        logical_identities={n: n for n in region.node_names},
        metadata={"strategy": "lazy_fusion"},
    )
