"""Local orchestrator: execute a PipelinePlan in-process."""

from __future__ import annotations

import inspect
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, get_args, get_origin

import anyio

from etlantic.exceptions import (
    NodeExecutionError,
    PipelineCancelledError,
    PipelineExecutionError,
    PipelineTimeoutError,
)
from etlantic.lifecycle.callbacks import FailureAction, StepFailureContext
from etlantic.lifecycle.outbound import Emit
from etlantic.lifecycle.resources import Inject
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.model import LogicalGraph, Node, NodeKind
from etlantic.plan.artifacts import ArtifactRef, ArtifactStrategy, artifact_identity
from etlantic.plan.model import PipelinePlan
from etlantic.registry import BindingDescriptor, ImplementationDescriptor
from etlantic.reliability import (
    FreshnessExpectation,
    PartitionCompletenessExpectation,
    RetrySafetyDeclaration,
)
from etlantic.reliability_runtime import (
    assert_retry_safe,
    check_freshness,
    check_partition_completeness,
    resolve_freshness_observed_at,
    write_mode_for_request,
)
from etlantic.reports.model import (
    ArtifactResult,
    PipelineRunReport,
    RunDiagnostic,
    RunSummary,
    SchemaObservationResult,
    StepRunReport,
    ValidationResult,
)
from etlantic.runtime.artifacts import ArtifactStore
from etlantic.runtime.context import AttemptContext, RunContext, StepContext
from etlantic.runtime.dataframe_exec import (
    execute_dataframe_step,
    is_dataframe_engine,
    resolve_dataframe_plugin,
)
from etlantic.runtime.events import LifecycleEvent, SecurityEvent
from etlantic.runtime.invoke import maybe_await
from etlantic.runtime.logging import RunLogger, redact_message
from etlantic.runtime.request import MaterializationPolicy, RunRequest
from etlantic.runtime.spark_exec import (
    acquire_session,
    execute_portable_spark_step,
    execute_spark_sink,
    execute_spark_source,
    execute_spark_step,
    is_spark_engine,
    parse_udf_policy,
    region_for_node,
    release_session,
    resolve_spark_plugin,
    resolve_spark_provider,
)
from etlantic.runtime.sql_exec import (
    execute_sql_sink,
    execute_sql_source,
    execute_sql_step,
    is_sql_engine,
    materialize_sql_temp,
    resolve_sql_plugin,
    safe_staging_name,
)
from etlantic.runtime.state import FailureStage, RunStatus, StepStatus
from etlantic.schema_drift import (
    SchemaObservation,
    normalize_schema_from_fields,
    normalize_schema_from_model,
)
from etlantic.schema_policy import (
    DriftAction,
    InMemorySchemaHistory,
    SchemaDriftPolicy,
    evaluate_drift,
)
from etlantic.secrets.provider import SecretResolutionContext
from etlantic.secrets.ref import SecretRef
from etlantic.spark.provider import SparkSessionHandle
from etlantic.sql.protocol import RelationRef, SqlExecutionContext, SqlQuery
from etlantic.storage.protocol import as_records
from etlantic.transformation import ImplementationRecord, Transformation


def _all_subclasses(cls: type[Any]) -> list[type[Any]]:
    found: list[type[Any]] = []
    for sub in cls.__subclasses__():
        found.append(sub)
        found.extend(_all_subclasses(sub))
    return found


def _logical_type_of(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, (list, tuple)):
        return "array"
    return type(value).__name__


def _observe_records_schema(
    subject_id: str,
    data: Any,
    *,
    layer: str,
    plugin: Any | None = None,
) -> SchemaObservation | None:
    from etlantic.runtime.artifacts import _looks_like_frame

    if _looks_like_frame(data) and plugin is not None:
        inspected = plugin.inspect_schema(data, identity=f"observed:{subject_id}")
        if isinstance(inspected, dict) and inspected.get("fields") is not None:
            from etlantic.dataframe.helpers import normalized_from_field_dicts

            schema = normalized_from_field_dicts(
                list(inspected["fields"]),
                identity=inspected.get("identity", f"observed:{subject_id}"),
            )
            return SchemaObservation(
                subject_id=subject_id,
                schema=schema,
                inspector=layer,
                metadata={"layer": layer, "source": "dataframe_inspect"},
            )

    records = as_records(data, None)
    if not records:
        return SchemaObservation(
            subject_id=subject_id,
            schema=normalize_schema_from_fields([], identity=f"observed:{subject_id}"),
            inspector=layer,
            metadata={"layer": layer},
        )
    sample = records[0]
    if hasattr(sample, "model_dump"):
        mapping = sample.model_dump()
    elif isinstance(sample, dict):
        mapping = sample
    else:
        mapping = {"value": sample}
    fields = [
        {"name": key, "logical_type": _logical_type_of(val), "required": True}
        for key, val in mapping.items()
    ]
    return SchemaObservation(
        subject_id=subject_id,
        schema=normalize_schema_from_fields(fields, identity=f"observed:{subject_id}"),
        inspector=layer,
        metadata={"layer": layer},
    )


@dataclass
class _NodeState:
    node: Node
    status: StepStatus = StepStatus.PENDING
    attempts: int = 0
    started_at: datetime | None = None
    ended_at: datetime | None = None
    error: str | None = None
    stage: str | None = None
    records_in: int | None = None
    records_out: int | None = None
    implementation: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LocalOrchestrator:
    """Async-first local DAG executor for PipelinePlan."""

    runtime: PipelineRuntime
    plan: PipelinePlan
    request: RunRequest
    pipeline_cls: type[Any] | None = None
    workspace: Path | None = None
    artifacts: ArtifactStore | None = None
    drift_policy: SchemaDriftPolicy = field(default_factory=SchemaDriftPolicy)
    schema_history: InMemorySchemaHistory = field(default_factory=InMemorySchemaHistory)
    transform_lookup: dict[str, type[Transformation]] = field(default_factory=dict)
    outbound_events: list[dict[str, Any]] = field(default_factory=list)
    _spark_session: SparkSessionHandle | None = field(default=None, repr=False)
    _spark_compiled: dict[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if self.pipeline_cls is not None:
            self._index_transformations(self.pipeline_cls)
        if self.artifacts is None:
            self.artifacts = ArtifactStore(workspace=self.workspace)
        elif self.workspace is not None and self.artifacts.workspace is None:
            self.artifacts.workspace = self.workspace

    def _index_transformations(self, pipeline_cls: type[Any]) -> None:
        members = getattr(pipeline_cls, "__pipeline_members__", {})
        for value in members.values():
            xf = getattr(value, "transformation", None)
            if xf is not None:
                self.transform_lookup[xf.identity()] = xf

    def _strategy_for(self, node_name: str, port_name: str) -> ArtifactStrategy:
        if self.request.materialization is MaterializationPolicy.NONE:
            return ArtifactStrategy.IN_MEMORY
        if self.request.materialization is MaterializationPolicy.DURABLE:
            return ArtifactStrategy.DURABLE
        for resolution in self.plan.output_resolutions:
            if resolution.node_name == node_name and resolution.port_name == port_name:
                return resolution.artifact.strategy
        return ArtifactStrategy.IN_MEMORY

    async def execute(self) -> PipelineRunReport:
        from etlantic.lifecycle.lifespan import run_lifespan

        run_id = f"run-{uuid.uuid4().hex[:12]}"
        started = datetime.now(UTC)
        logger = RunLogger(run_id=run_id, pipeline_id=self.plan.pipeline_id)
        artifacts = self.artifacts or ArtifactStore(workspace=self.workspace)
        graph = self.plan.logical_graph
        nodes = {n.name: _NodeState(node=n) for n in graph.nodes}
        producers = self._producers(graph)
        consumers = self._consumers(graph)
        selected = set(self.plan.selected_nodes or [n.name for n in graph.nodes])
        validations: list[ValidationResult] = []
        diagnostics: list[RunDiagnostic] = []
        schema_obs: list[SchemaObservationResult] = []
        cancelled = False
        status = RunStatus.RUNNING
        run_context = RunContext(
            run_id=run_id,
            pipeline_id=self.plan.pipeline_id,
            plan_id=self.plan.plan_id,
            profile=self.plan.profile_name,
            intent=self.request.intent.value,
        )

        self.runtime.events.emit(
            LifecycleEvent(
                kind="run_started",
                run_id=run_id,
                pipeline_id=self.plan.pipeline_id,
                status=status.value,
            )
        )

        async def run_body() -> None:
            nonlocal status
            concurrency = (
                self.plan.execution_settings.get("concurrency")
                or self.request.metadata.get("concurrency")
                or 4
            )
            limiter = anyio.CapacityLimiter(int(concurrency))
            pending = set(selected)
            completed: set[str] = set()
            failed: set[str] = set()

            while True:
                ready = [
                    name
                    for name in list(pending)
                    if producers[name].issubset(completed)
                ]
                if not ready:
                    if pending:
                        for name in list(pending):
                            nodes[name].status = StepStatus.ABANDONED
                            nodes[name].error = "Upstream dependencies unmet"
                            pending.discard(name)
                    break

                async def _one(n: str) -> None:
                    async with limiter:
                        await self._execute_node(
                            name=n,
                            state=nodes[n],
                            run_id=run_id,
                            artifacts=artifacts,
                            graph=graph,
                            validations=validations,
                            diagnostics=diagnostics,
                            schema_obs=schema_obs,
                            logger=logger,
                            run_context=run_context,
                        )
                        if nodes[n].status is StepStatus.SUCCEEDED:
                            completed.add(n)
                        else:
                            hard_fail = nodes[n].status is not StepStatus.SKIPPED
                            if hard_fail:
                                failed.add(n)
                            stack = list(consumers.get(n, ()))
                            seen: set[str] = set()
                            while stack:
                                child = stack.pop()
                                if child in seen:
                                    continue
                                seen.add(child)
                                if child in pending:
                                    pending.discard(child)
                                    nodes[child].status = StepStatus.ABANDONED
                                    if hard_fail:
                                        failed.add(child)
                                stack.extend(consumers.get(child, ()))
                            if not hard_fail:
                                # Soft-skip: stop the wave without marking the run failed.
                                pending.clear()

                async with anyio.create_task_group() as wave:
                    for name in ready:
                        pending.discard(name)
                        wave.start_soon(_one, name)
                if failed:
                    break

        cancel_exc = anyio.get_cancelled_exc_class()
        try:
            async with run_lifespan(self.runtime, run_id):
                timeout = self.request.timeout.run_seconds
                if timeout is not None:
                    with anyio.fail_after(timeout):
                        await self.runtime.run_middleware.run(run_context, run_body)
                else:
                    await self.runtime.run_middleware.run(run_context, run_body)
        except TimeoutError as exc:
            status = RunStatus.TIMED_OUT
            diagnostics.append(
                RunDiagnostic(
                    code="PMEXEC408",
                    severity="error",
                    message=redact_message(
                        f"Run timed out after {self.request.timeout.run_seconds}s"
                    ),
                )
            )
            report = self._build_report(
                run_id=run_id,
                started=started,
                nodes=nodes,
                validations=validations,
                diagnostics=diagnostics,
                schema_obs=schema_obs,
                artifacts=artifacts,
                status=status,
            )
            self.runtime.reports.put(report)
            raise PipelineTimeoutError(
                redact_message(str(exc)),
                run_id=run_id,
                report=report,
                code="PMEXEC408",
            ) from exc
        except cancel_exc as exc:
            cancelled = True
            status = RunStatus.CANCELLED
            report = self._build_report(
                run_id=run_id,
                started=started,
                nodes=nodes,
                validations=validations,
                diagnostics=diagnostics,
                schema_obs=schema_obs,
                artifacts=artifacts,
                status=status,
            )
            self.runtime.reports.put(report)
            raise PipelineCancelledError(
                "Run cancelled", run_id=run_id, report=report, code="PMEXEC409"
            ) from exc
        except PipelineExecutionError:
            status = RunStatus.FAILED
            raise
        except Exception as exc:
            status = RunStatus.FAILED
            diagnostics.append(
                RunDiagnostic(
                    code="PMEXEC500",
                    severity="error",
                    message=redact_message(str(exc)),
                )
            )
            report = self._build_report(
                run_id=run_id,
                started=started,
                nodes=nodes,
                validations=validations,
                diagnostics=diagnostics,
                schema_obs=schema_obs,
                artifacts=artifacts,
                status=status,
            )
            self.runtime.reports.put(report)
            raise PipelineExecutionError(
                redact_message(str(exc)),
                run_id=run_id,
                report=report,
                code="PMEXEC500",
            ) from exc
        finally:
            # Drop run-scoped SQL staging tables when present.
            import contextlib

            for plugin in getattr(self.runtime, "sql_plugins", {}).values():
                cleanup = getattr(plugin, "cleanup_staging", None)
                if callable(cleanup):
                    with contextlib.suppress(Exception):
                        cleanup()
            if self._spark_session is not None:
                with contextlib.suppress(Exception):
                    providers = getattr(self.runtime, "spark_providers", None) or {}
                    provider = resolve_spark_provider("local", providers=providers)
                    await release_session(
                        provider=provider,
                        handle=self._spark_session,
                        plan=self.plan,
                        run_id=run_id,
                    )
                self._spark_session = None
            await self.runtime.resources.cleanup_scope("run", run_id)

        step_reports = tuple(self._step_report(s) for s in nodes.values())
        failed_count = sum(
            1
            for s in nodes.values()
            if s.status
            in {StepStatus.FAILED, StepStatus.TIMED_OUT, StepStatus.ABANDONED}
        )
        succeeded = sum(1 for s in nodes.values() if s.status is StepStatus.SUCCEEDED)
        skipped = sum(1 for s in nodes.values() if s.status is StepStatus.SKIPPED)
        if cancelled:
            status = RunStatus.CANCELLED
        elif failed_count:
            status = RunStatus.FAILED if succeeded == 0 else RunStatus.PARTIAL
        else:
            status = RunStatus.SUCCEEDED

        ended = datetime.now(UTC)
        report = PipelineRunReport(
            pipeline_id=self.plan.pipeline_id,
            plan_id=self.plan.plan_id,
            run_id=run_id,
            intent=self.request.intent,
            profile=self.plan.profile_name,
            status=status,
            started_at=started,
            ended_at=ended,
            duration=ended - started,
            summary=RunSummary(
                total_steps=len(nodes),
                succeeded=succeeded,
                failed=failed_count,
                skipped=skipped,
                cancelled=sum(
                    1 for s in nodes.values() if s.status is StepStatus.CANCELLED
                ),
            ),
            steps=step_reports,
            artifacts=tuple(
                ArtifactResult(
                    identity=ref.identity,
                    logical_output=ref.logical_output,
                    strategy=ref.strategy.value,
                )
                for ref in artifacts.list_refs()
            ),
            validations=tuple(validations),
            diagnostics=tuple(diagnostics),
            schema_observations=tuple(schema_obs),
            plan_fingerprint=self.plan.fingerprint,
            lineage=tuple(
                {
                    "from": f"{e.producer_node}.{e.producer_port}",
                    "to": f"{e.consumer_node}.{e.consumer_port}",
                }
                for e in graph.edges
                if e.producer_node in selected and e.consumer_node in selected
            ),
            backend_runs=(),
            metadata={
                "orchestrator": "local",
                "outbound_events": list(self.outbound_events),
            },
        )
        self.runtime.reports.put(report)
        event_kind = "run_completed" if status is RunStatus.SUCCEEDED else "run_failed"
        self.runtime.events.emit(
            LifecycleEvent(
                kind=event_kind,
                run_id=run_id,
                pipeline_id=self.plan.pipeline_id,
                status=status.value,
            )
        )
        await self.runtime.callbacks.emit(event_kind, report)
        return report

    def _build_report(
        self,
        *,
        run_id: str,
        started: datetime,
        nodes: dict[str, _NodeState],
        validations: list[ValidationResult],
        diagnostics: list[RunDiagnostic],
        schema_obs: list[SchemaObservationResult],
        artifacts: ArtifactStore,
        status: RunStatus,
    ) -> PipelineRunReport:
        ended = datetime.now(UTC)
        selected = set(self.plan.selected_nodes or [n.name for n in nodes])
        return PipelineRunReport(
            pipeline_id=self.plan.pipeline_id,
            plan_id=self.plan.plan_id,
            run_id=run_id,
            intent=self.request.intent,
            profile=self.plan.profile_name,
            status=status,
            started_at=started,
            ended_at=ended,
            duration=ended - started,
            summary=RunSummary(total_steps=len(nodes)),
            steps=tuple(self._step_report(s) for s in nodes.values()),
            artifacts=tuple(
                ArtifactResult(
                    identity=ref.identity,
                    logical_output=ref.logical_output,
                    strategy=ref.strategy.value,
                )
                for ref in artifacts.list_refs()
            ),
            validations=tuple(validations),
            diagnostics=tuple(diagnostics),
            schema_observations=tuple(schema_obs),
            plan_fingerprint=self.plan.fingerprint,
            lineage=tuple(
                {
                    "from": f"{e.producer_node}.{e.producer_port}",
                    "to": f"{e.consumer_node}.{e.consumer_port}",
                }
                for e in self.plan.logical_graph.edges
                if e.producer_node in selected and e.consumer_node in selected
            ),
            metadata={
                "orchestrator": "local",
                "outbound_events": list(self.outbound_events),
            },
        )

    def _step_report(self, state: _NodeState) -> StepRunReport:
        duration = None
        if state.started_at and state.ended_at:
            duration = (state.ended_at - state.started_at).total_seconds()
        return StepRunReport(
            step_id=state.node.identity,
            step_name=state.node.name,
            status=state.status,
            attempts=state.attempts,
            started_at=state.started_at,
            ended_at=state.ended_at,
            duration_seconds=duration,
            failure_stage=state.stage,
            error_message=redact_message(state.error) if state.error else None,
            records_in=state.records_in,
            records_out=state.records_out,
            implementation=state.implementation,
            metadata=dict(state.metadata),
        )

    def _producers(self, graph: LogicalGraph) -> dict[str, set[str]]:
        producers: dict[str, set[str]] = {n.name: set() for n in graph.nodes}
        for edge in graph.edges:
            producers.setdefault(edge.consumer_node, set()).add(edge.producer_node)
        return producers

    def _consumers(self, graph: LogicalGraph) -> dict[str, set[str]]:
        consumers: dict[str, set[str]] = {n.name: set() for n in graph.nodes}
        for edge in graph.edges:
            consumers.setdefault(edge.producer_node, set()).add(edge.consumer_node)
        return consumers

    async def _execute_node(
        self,
        *,
        name: str,
        state: _NodeState,
        run_id: str,
        artifacts: ArtifactStore,
        graph: LogicalGraph,
        validations: list[ValidationResult],
        diagnostics: list[RunDiagnostic],
        schema_obs: list[SchemaObservationResult],
        logger: RunLogger,
        run_context: RunContext,
    ) -> None:
        max_attempts = max(1, self.request.retry.max_attempts)
        last_error: BaseException | None = None
        retry_decl = self._retry_safety_for(name)

        for attempt in range(1, max_attempts + 1):
            state.attempts = attempt
            state.status = StepStatus.RUNNING if attempt == 1 else StepStatus.RETRYING
            state.started_at = state.started_at or datetime.now(UTC)
            current_attempt = attempt
            step_context = StepContext(
                run=run_context,
                step_name=name,
                node_kind=state.node.kind.value,
                attempt=current_attempt,
            )
            bound_step_context = step_context
            self.runtime.events.emit(
                LifecycleEvent(
                    kind="step_started",
                    run_id=run_id,
                    pipeline_id=self.plan.pipeline_id,
                    step_name=name,
                    attempt=current_attempt,
                    status=state.status.value,
                )
            )
            try:

                async def terminal(
                    attempt_no: int = current_attempt,
                    ctx: StepContext = bound_step_context,
                ) -> None:
                    await self._run_node_once(
                        state=state,
                        run_id=run_id,
                        artifacts=artifacts,
                        graph=graph,
                        validations=validations,
                        diagnostics=diagnostics,
                        schema_obs=schema_obs,
                        attempt=attempt_no,
                        step_context=ctx,
                    )

                step_timeout = self.request.timeout.step_seconds
                try:
                    if step_timeout is not None:
                        with anyio.fail_after(step_timeout):
                            await self.runtime.step_middleware.run(
                                step_context, terminal
                            )
                    else:
                        await self.runtime.step_middleware.run(step_context, terminal)
                finally:
                    await self.runtime.resources.cleanup_scope(
                        "attempt", f"{name}:{current_attempt}"
                    )
                state.status = StepStatus.SUCCEEDED
                state.ended_at = datetime.now(UTC)
                self.runtime.events.emit(
                    LifecycleEvent(
                        kind="step_completed",
                        run_id=run_id,
                        pipeline_id=self.plan.pipeline_id,
                        step_name=name,
                        attempt=attempt,
                        status=state.status.value,
                    )
                )
                return
            except TimeoutError as exc:
                state.status = StepStatus.TIMED_OUT
                state.stage = FailureStage.ORCHESTRATOR.value
                state.error = redact_message(str(exc))
                state.ended_at = datetime.now(UTC)
                last_error = exc
                break
            except Exception as exc:
                last_error = exc
                state.stage = (
                    getattr(exc, "stage", None) or FailureStage.TRANSFORM.value
                )
                state.error = redact_message(str(exc))
                results = await self.runtime.callbacks.emit(
                    "step_failed",
                    StepFailureContext(
                        run_id=run_id,
                        pipeline_id=self.plan.pipeline_id,
                        step_name=name,
                        attempt=attempt,
                        error=exc,
                        stage=state.stage,
                    ),
                )
                action = FailureAction.FAIL
                for result in results:
                    if isinstance(result, FailureAction):
                        action = result

                can_retry = attempt < max_attempts and (
                    action is FailureAction.RETRY
                    or (action is FailureAction.FAIL and self._should_retry(exc))
                )
                if can_retry and (
                    action is FailureAction.RETRY or self._should_retry(exc)
                ):
                    try:
                        assert_retry_safe(
                            retry_decl,
                            attempt=attempt + 1,
                            step_name=name,
                            run_id=run_id,
                        )
                    except PipelineExecutionError as retry_exc:
                        state.status = StepStatus.FAILED
                        state.ended_at = datetime.now(UTC)
                        state.error = redact_message(str(retry_exc))
                        diagnostics.append(
                            RunDiagnostic(
                                code=retry_exc.code or "PMEXEC300",
                                severity="error",
                                message=redact_message(str(retry_exc)),
                                node_name=name,
                            )
                        )
                        return
                    backoff = self.request.retry.backoff_seconds * attempt
                    if backoff > 0:
                        await anyio.sleep(backoff)
                    continue
                if action is FailureAction.SKIP or action is FailureAction.CONTINUE:
                    state.status = StepStatus.SKIPPED
                    state.ended_at = datetime.now(UTC)
                    diagnostics.append(
                        RunDiagnostic(
                            code="PMEXEC301",
                            severity="warning",
                            message=redact_message(
                                f"Step {name} continued/skipped after failure: {exc}"
                            ),
                            node_name=name,
                        )
                    )
                    return
                state.status = StepStatus.FAILED
                state.ended_at = datetime.now(UTC)
                diagnostics.append(
                    RunDiagnostic(
                        code=getattr(exc, "code", None) or "PMEXEC300",
                        severity="error",
                        message=redact_message(str(exc)),
                        node_name=name,
                    )
                )
                self.runtime.events.emit(
                    LifecycleEvent(
                        kind="step_failed",
                        run_id=run_id,
                        pipeline_id=self.plan.pipeline_id,
                        step_name=name,
                        attempt=attempt,
                        status=state.status.value,
                        message=redact_message(str(exc)),
                    )
                )
                logger.log(
                    "error",
                    f"Step {name} failed",
                    step_name=name,
                    attempt=attempt,
                    error=redact_message(str(exc)),
                )
                return

        if last_error is not None and state.status is not StepStatus.SUCCEEDED:
            state.status = (
                StepStatus.TIMED_OUT
                if isinstance(last_error, TimeoutError)
                else StepStatus.FAILED
            )
            state.ended_at = datetime.now(UTC)

    def _should_retry(self, exc: BaseException) -> bool:
        from etlantic.exceptions import NodeExecutionError

        # Unknown SQL commit outcomes must never be retried blindly.
        if isinstance(exc, NodeExecutionError) and exc.code == "PMEXEC434":
            return False
        retry_on = self.request.retry.retry_on
        if not retry_on:
            return self.request.retry.max_attempts > 1
        return type(exc).__name__ in retry_on

    def _retry_safety_for(self, step_name: str) -> RetrySafetyDeclaration | None:
        raw = (self.request.metadata.get("retry_safety") or {}).get(step_name)
        if isinstance(raw, RetrySafetyDeclaration):
            return raw
        if isinstance(raw, dict):
            return RetrySafetyDeclaration(
                subject_id=str(raw.get("subject_id") or step_name),
                safe=bool(raw.get("safe", True)),
                max_attempts=raw.get("max_attempts"),
            )
        return None

    async def _run_node_once(
        self,
        *,
        state: _NodeState,
        run_id: str,
        artifacts: ArtifactStore,
        graph: LogicalGraph,
        validations: list[ValidationResult],
        diagnostics: list[RunDiagnostic],
        schema_obs: list[SchemaObservationResult],
        attempt: int,
        step_context: StepContext,
    ) -> None:
        node = state.node
        if node.kind is NodeKind.SOURCE:
            if is_spark_engine(self._engine_for(node.name)):
                plugin = resolve_spark_plugin(
                    "pyspark",
                    plugins=getattr(self.runtime, "spark_plugins", None),
                )
                await self._ensure_spark_session(run_id=run_id)
                binding_name = node.binding or node.name
                binding_name = self.request.binding_overrides.get(
                    node.name, binding_name
                )
                descriptor = self._binding_descriptor(node, binding_name)
                location = descriptor.location if descriptor is not None else None
                # Memory/python sources: read records then let the plugin wrap.
                provider = descriptor.provider if descriptor is not None else "memory"
                if provider in {"memory", "local", "python", "json", "csv", "callable"}:
                    data = await self._read_source(node, run_id=run_id)
                    self._store_outputs(node, data, artifacts)
                    state.records_out = _count(data)
                    state.metadata["spark"] = {
                        "source_kind": "records",
                        "provider": provider,
                    }
                    return
                data = await execute_spark_source(
                    plugin=plugin,
                    node=node,
                    plan=self.plan,
                    location=location,
                    binding=binding_name,
                )
                validations.append(
                    ValidationResult(
                        node_name=node.name,
                        boundary="source",
                        status="skipped",
                        message="Spark source resolved as DatasetRef (lazy)",
                    )
                )
                self._store_outputs(node, data, artifacts)
                state.records_out = 0
                state.metadata["spark"] = {"source_kind": "dataset_ref"}
                return
            if is_sql_engine(self._engine_for(node.name)):
                plugin = resolve_sql_plugin(
                    "sql",
                    plugins=getattr(self.runtime, "sql_plugins", None),
                )
                binding_name = node.binding or node.name
                binding_name = self.request.binding_overrides.get(
                    node.name, binding_name
                )
                descriptor = self._binding_descriptor(node, binding_name)
                location = descriptor.location if descriptor is not None else None
                data = await execute_sql_source(
                    plugin=plugin,
                    node=node,
                    plan=self.plan,
                    run_id=run_id,
                    attempt=attempt,
                    location=location,
                    binding=binding_name,
                )
                validations.append(
                    ValidationResult(
                        node_name=node.name,
                        boundary="source",
                        status="skipped",
                        message="SQL source resolved as RelationRef (no row fetch)",
                    )
                )
                self._store_outputs(node, data, artifacts)
                state.records_out = 0
                return
            data = await self._read_source(node, run_id=run_id)
            await self._observe_schema(node, data, schema_obs=schema_obs)
            await self._check_source_reliability(node, data, run_id=run_id)
            data = await self._validate_boundary(
                node, data, boundary="source", validations=validations
            )
            self._store_outputs(node, data, artifacts)
            state.records_out = _count(data)
            return

        if node.kind is NodeKind.SINK:
            inputs = self._gather_inputs(node, graph, artifacts)
            payload = next(iter(inputs.values()), [])
            if is_spark_engine(self._engine_for(node.name)):
                plugin = resolve_spark_plugin(
                    "pyspark",
                    plugins=getattr(self.runtime, "spark_plugins", None),
                )
                await self._ensure_spark_session(run_id=run_id)
                binding_name = node.binding or node.name
                binding_name = self.request.binding_overrides.get(
                    node.name, binding_name
                )
                descriptor = self._binding_descriptor(node, binding_name)
                location = descriptor.location if descriptor is not None else None
                provider = descriptor.provider if descriptor is not None else "memory"
                write_mode = "append"
                merge_keys: tuple[str, ...] = ()
                partition_by: tuple[str, ...] = ()
                if descriptor is not None and descriptor.metadata:
                    write_mode = str(
                        descriptor.metadata.get("write_mode")
                        or descriptor.metadata.get("write_intent")
                        or write_mode
                    )
                    merge_keys = tuple(
                        str(x) for x in (descriptor.metadata.get("merge_keys") or ())
                    )
                    partition_by = tuple(
                        str(x) for x in (descriptor.metadata.get("partition_by") or ())
                    )
                if write_mode_for_request(self.request).value == "no_write":
                    state.records_in = 0
                    state.records_out = 0
                    return
                # Local memory/json/csv sinks: collect Spark frames to records.
                if provider in {"memory", "local", "python", "json", "csv", "callable"}:
                    if not isinstance(payload, list):
                        payload = plugin.to_records(
                            payload, contract_type=node.contract_type
                        )
                    await self._write_sink(node, payload, run_id=run_id)
                    state.records_in = _count(payload)
                    state.records_out = state.records_in
                    state.metadata["spark"] = {
                        "sink_kind": "records",
                        "provider": provider,
                    }
                    return
                enable_delta = provider in {"delta", "pyspark"} or write_mode in {
                    "merge",
                    "upsert",
                    "overwrite_partition",
                }
                result = await execute_spark_sink(
                    plugin=plugin,
                    node=node,
                    source_value=payload,
                    plan=self.plan,
                    run_id=run_id,
                    attempt=attempt,
                    target_location=location,
                    write_mode=write_mode,
                    merge_keys=merge_keys,
                    partition_by=partition_by,
                    session_handle=self._spark_session,
                    enable_delta=enable_delta,
                )
                for diag in result.diagnostics:
                    diagnostics.append(
                        RunDiagnostic(
                            code=str(diag.get("code") or "PMSPARK000"),
                            severity=str(diag.get("severity") or "warning"),
                            message=redact_message(str(diag.get("message") or "")),
                            node_name=node.name,
                        )
                    )
                state.records_in = (
                    result.metrics.rows_affected or result.metrics.rows_in
                )
                state.records_out = (
                    result.metrics.rows_affected or result.metrics.rows_out
                )
                state.metadata["spark"] = result.metrics.to_dict()
                if result.schema_observation:
                    state.metadata["spark_schema"] = result.schema_observation
                return
            if is_sql_engine(self._engine_for(node.name)) and not isinstance(
                payload, list
            ):
                plugin = resolve_sql_plugin(
                    "sql",
                    plugins=getattr(self.runtime, "sql_plugins", None),
                )
                binding_name = node.binding or node.name
                binding_name = self.request.binding_overrides.get(
                    node.name, binding_name
                )
                descriptor = self._binding_descriptor(node, binding_name)
                location = descriptor.location if descriptor is not None else None
                write_intent = "insert_select"
                if descriptor is not None and descriptor.metadata:
                    write_intent = str(
                        descriptor.metadata.get("write_intent") or write_intent
                    )
                allow_trusted = bool(
                    (self.plan.profile_snapshot or {}).get("allow_trusted_sql")
                )
                if write_mode_for_request(self.request).value == "no_write":
                    state.records_in = 0
                    state.records_out = 0
                    return
                result = await execute_sql_sink(
                    plugin=plugin,
                    node=node,
                    source_value=payload,
                    plan=self.plan,
                    run_id=run_id,
                    attempt=attempt,
                    target_location=location,
                    write_intent=write_intent,
                    allow_trusted_sql=allow_trusted,
                )
                for diag in result.diagnostics:
                    diagnostics.append(
                        RunDiagnostic(
                            code=str(diag.get("code") or "PMSQL000"),
                            severity=str(diag.get("severity") or "warning"),
                            message=redact_message(str(diag.get("message") or "")),
                            node_name=node.name,
                        )
                    )
                if result.outcome.value == "unknown":
                    raise NodeExecutionError(
                        "SQL sink commit outcome unknown; refusing unsafe retry.",
                        node_name=node.name,
                        stage=FailureStage.WRITE.value,
                        code="PMEXEC434",
                    )
                if result.outcome.value != "committed":
                    raise NodeExecutionError(
                        f"SQL sink write failed with outcome {result.outcome.value!r}.",
                        node_name=node.name,
                        stage=FailureStage.WRITE.value,
                        code="PMEXEC436",
                    )
                state.records_in = result.metrics.rows_affected or 0
                state.records_out = result.metrics.rows_affected or 0
                self.runtime.events.emit(
                    LifecycleEvent(
                        kind="publication",
                        run_id=run_id,
                        pipeline_id=self.plan.pipeline_id,
                        step_name=node.name,
                        attempt=attempt,
                        status="succeeded",
                    )
                )
                return
            # SQL-region sink with Python list payload: load directly into target.
            if is_sql_engine(self._engine_for(node.name)) and isinstance(payload, list):
                binding_name = node.binding or node.name
                binding_name = self.request.binding_overrides.get(
                    node.name, binding_name
                )
                descriptor = self._binding_descriptor(node, binding_name)
                provider = descriptor.provider if descriptor is not None else "memory"
                if provider != "sql":
                    raise NodeExecutionError(
                        f"SQL-engine sink {node.name!r} has non-sql binding "
                        f"provider {provider!r} with list payload; failing closed.",
                        node_name=node.name,
                        stage=FailureStage.WRITE.value,
                        code="PMEXEC437",
                    )
                plugin = resolve_sql_plugin(
                    "sql",
                    plugins=getattr(self.runtime, "sql_plugins", None),
                )
                location = descriptor.location if descriptor is not None else None
                allow_trusted = bool(
                    (self.plan.profile_snapshot or {}).get("allow_trusted_sql")
                )
                target = plugin.relation_from_binding(
                    binding=binding_name,
                    location=location,
                )
                ctx = SqlExecutionContext(
                    run_id=run_id,
                    pipeline_id=self.plan.pipeline_id,
                    plan_id=self.plan.plan_id,
                    step_name=node.name,
                    allow_trusted_sql=allow_trusted,
                )
                if write_mode_for_request(self.request).value == "no_write":
                    state.records_in = _count(payload)
                    state.records_out = 0
                    return
                # Load rows straight into the sink relation (avoids TEXT staging
                # → typed target INSERT SELECT mismatches on PostgreSQL).
                loaded = plugin.load_records(payload, target=target, context=ctx)
                if loaded.outcome.value == "unknown":
                    raise NodeExecutionError(
                        "SQL sink commit outcome unknown; refusing unsafe retry.",
                        node_name=node.name,
                        stage=FailureStage.WRITE.value,
                        code="PMEXEC434",
                    )
                if loaded.outcome.value != "committed":
                    raise NodeExecutionError(
                        f"SQL load_records failed with outcome "
                        f"{loaded.outcome.value!r}.",
                        node_name=node.name,
                        stage=FailureStage.WRITE.value,
                        code="PMEXEC436",
                    )
                state.records_in = _count(payload)
                state.records_out = loaded.metrics.rows_affected or _count(payload)
                self.runtime.events.emit(
                    LifecycleEvent(
                        kind="publication",
                        run_id=run_id,
                        pipeline_id=self.plan.pipeline_id,
                        step_name=node.name,
                        attempt=attempt,
                        status="succeeded",
                    )
                )
                return
            # SQL IR into a non-sql storage sink must not silently ignore the IR.
            if isinstance(payload, (RelationRef, SqlQuery)):
                raise NodeExecutionError(
                    f"Sink {node.name!r} received a SQL handle but is not in a "
                    "SQL execution region; failing closed.",
                    node_name=node.name,
                    stage=FailureStage.WRITE.value,
                    code="PMEXEC437",
                )
            payload = self._coerce_to_records(payload, contract_type=node.contract_type)
            payload = await self._validate_boundary(
                node, payload, boundary="pre_publication", validations=validations
            )
            await self._observe_schema(node, payload, schema_obs=schema_obs)
            if write_mode_for_request(self.request).value == "no_write":
                state.records_in = _count(payload)
                state.records_out = 0
                return
            await self._write_sink(node, payload, run_id=run_id)
            state.records_in = _count(payload)
            state.records_out = _count(payload)
            self.runtime.events.emit(
                LifecycleEvent(
                    kind="publication",
                    run_id=run_id,
                    pipeline_id=self.plan.pipeline_id,
                    step_name=node.name,
                    attempt=attempt,
                    status="succeeded",
                )
            )
            return

        if node.kind is NodeKind.STEP:
            inputs = self._gather_inputs(node, graph, artifacts)
            state.records_in = sum(_count(v) for v in inputs.values())
            params = self._parameters_for(node)
            descriptor = self.plan.implementations.get(node.name)
            if descriptor is not None and descriptor.kind == "portable_compiled":
                impl = None
                engine = descriptor.engine
                state.implementation = descriptor.identity
                if not is_dataframe_engine(engine) and not is_spark_engine(engine):
                    raise NodeExecutionError(
                        redact_message(
                            f"portable_compiled step {node.name!r} requires a "
                            f"dataframe or spark engine, got {engine!r}"
                        ),
                        node_name=node.name,
                        stage=FailureStage.TRANSFORM.value,
                        code="PMXFORM302",
                    )
            else:
                impl = self._resolve_implementation(node)
                engine = impl.engine
                state.implementation = impl.identity

            if (
                descriptor is not None
                and descriptor.kind == "portable_compiled"
                and is_spark_engine(engine)
            ):
                plugin = resolve_spark_plugin(
                    engine,
                    plugins=getattr(self.runtime, "spark_plugins", None),
                )
                await self._ensure_spark_session(run_id=run_id)
                for _port_name in inputs:
                    validations.append(
                        ValidationResult(
                            node_name=node.name,
                            boundary="input_validation",
                            status="skipped",
                            message="delegated to portable spark compiler",
                        )
                    )
                result = await execute_portable_spark_step(
                    plugin=plugin,
                    descriptor=descriptor,
                    node=node,
                    inputs=inputs,
                    params=params,
                    plan=self.plan,
                    run_id=run_id,
                    attempt=attempt,
                    session_handle=self._spark_session,
                )
                output_ports = [p.name for p in node.outputs] or ["result"]
                port_name = output_ports[0]
                strategy = self._strategy_for(node.name, port_name)
                logical = f"{node.name}.{port_name}"
                ref = ArtifactRef(
                    identity=artifact_identity(
                        pipeline_id=self.plan.pipeline_id,
                        node_name=node.name,
                        port_name=port_name,
                        security_domain=self.plan.security_domain,
                    ),
                    logical_output=logical,
                    strategy=strategy,
                    security_domain=self.plan.security_domain,
                )
                consumers_spark = True
                for edge in graph.edges_from(node.name):
                    if not is_spark_engine(self._engine_for(edge.consumer_node)):
                        consumers_spark = False
                        break
                stored = result
                if not consumers_spark and not isinstance(result, list):
                    stored = plugin.to_records(result, contract_type=node.contract_type)
                artifacts.put(ref, stored, durable=False)
                state.records_out = _count(stored) if isinstance(stored, list) else 0
                state.metadata["spark"] = {
                    "portable_compiled": True,
                    "udf_policy": "deny",
                    "consumers_spark": consumers_spark,
                }
                return

            if is_dataframe_engine(engine):
                plugin = resolve_dataframe_plugin(
                    engine,
                    plugins=getattr(self.runtime, "dataframe_plugins", None),
                )
                # Skip record-oriented input validation; plugin validates.
                for _port_name in inputs:
                    validations.append(
                        ValidationResult(
                            node_name=node.name,
                            boundary="input_validation",
                            status="skipped",
                            message=f"delegated to {engine} plugin",
                        )
                    )
                bundle = await execute_dataframe_step(
                    plugin=plugin,
                    impl=impl,
                    descriptor=descriptor,
                    node=node,
                    inputs=inputs,
                    params=params,
                    plan=self.plan,
                    run_id=run_id,
                    attempt=attempt,
                )
                for diag in bundle.diagnostics:
                    diagnostics.append(
                        RunDiagnostic(
                            code=str(diag.get("code") or "PMDF000"),
                            severity=str(diag.get("severity") or "warning"),
                            message=redact_message(str(diag.get("message") or "")),
                            node_name=node.name,
                        )
                    )
                outputs = dict(bundle.valid)
                for port_name, value in bundle.invalid.items():
                    logical = f"{node.name}.{port_name}#invalid"
                    ref = ArtifactRef(
                        identity=artifact_identity(
                            pipeline_id=self.plan.pipeline_id,
                            node_name=node.name,
                            port_name=f"{port_name}#invalid",
                            security_domain=self.plan.security_domain,
                        ),
                        logical_output=logical,
                        strategy=ArtifactStrategy.IN_MEMORY,
                        security_domain=self.plan.security_domain,
                    )
                    artifacts.put(ref, value, durable=False)
                validations.append(
                    ValidationResult(
                        node_name=node.name,
                        boundary="output_validation",
                        status=bundle.validation_decision.value,
                        records_checked=bundle.metrics.rows_out,
                        records_invalid=bundle.metrics.invalid_count or 0,
                    )
                )
                await self._observe_schema(node, outputs, schema_obs=schema_obs)
                for port_name, value in outputs.items():
                    strategy = self._strategy_for(node.name, port_name)

                    logical = f"{node.name}.{port_name}"
                    ref = ArtifactRef(
                        identity=artifact_identity(
                            pipeline_id=self.plan.pipeline_id,
                            node_name=node.name,
                            port_name=port_name,
                            security_domain=self.plan.security_domain,
                        ),
                        logical_output=logical,
                        strategy=strategy,
                        security_domain=self.plan.security_domain,
                    )
                    durable = artifacts.should_durable(strategy)
                    if durable:
                        # Collect to records only for durable / storage strategies.
                        value = plugin.to_records(value, contract_type=None)
                    artifacts.put(
                        ref,
                        value,
                        durable=durable,
                        ownership=bundle.metrics.ownership,
                    )
                state.records_in = bundle.metrics.rows_in or state.records_in
                state.records_out = bundle.metrics.rows_out or 0
                state.metadata["dataframe"] = bundle.metrics.to_dict()
                return

            if is_sql_engine(impl.engine):
                plugin = resolve_sql_plugin(
                    impl.engine,
                    plugins=getattr(self.runtime, "sql_plugins", None),
                )
                allow_trusted = bool(
                    (self.plan.profile_snapshot or {}).get("allow_trusted_sql")
                )
                # Hybrid: fetch SQL handles into records when feeding local engines
                # is handled in _gather_inputs; here inputs should already be
                # RelationRef / SqlQuery for SQL-to-SQL.
                for _port_name in inputs:
                    validations.append(
                        ValidationResult(
                            node_name=node.name,
                            boundary="input_validation",
                            status="skipped",
                            message="delegated to sql plugin",
                        )
                    )
                result = await execute_sql_step(
                    plugin=plugin,
                    impl=impl,
                    node=node,
                    inputs=inputs,
                    params=params,
                    plan=self.plan,
                    run_id=run_id,
                    attempt=attempt,
                    allow_trusted_sql=allow_trusted,
                )

                # If consumers are also SQL, keep IR (or temp relation). If any
                # consumer is non-SQL, materialize later at gather time.
                output_ports = [p.name for p in node.outputs] or ["result"]
                port_name = output_ports[0]
                stored: Any = result
                consumers_sql = True
                for edge in graph.edges_from(node.name):
                    if not is_sql_engine(self._engine_for(edge.consumer_node)):
                        consumers_sql = False
                        break
                if consumers_sql and isinstance(result, SqlQuery):
                    temp_name = safe_staging_name(
                        run_id=run_id, node_name=node.name, port_name=port_name
                    )
                    stored = await materialize_sql_temp(
                        plugin=plugin,
                        query=result,
                        temp_name=temp_name,
                        plan=self.plan,
                        node=node,
                        run_id=run_id,
                        attempt=attempt,
                        allow_trusted_sql=allow_trusted,
                    )
                strategy = self._strategy_for(node.name, port_name)
                logical = f"{node.name}.{port_name}"
                ref = ArtifactRef(
                    identity=artifact_identity(
                        pipeline_id=self.plan.pipeline_id,
                        node_name=node.name,
                        port_name=port_name,
                        security_domain=self.plan.security_domain,
                    ),
                    logical_output=logical,
                    strategy=strategy,
                    security_domain=self.plan.security_domain,
                )
                artifacts.put(ref, stored, durable=False)
                state.records_out = 0
                state.metadata["sql"] = {
                    "rows_fetched": plugin.rows_fetched_total(),
                    "result_kind": type(stored).__name__,
                    "consumers_sql": consumers_sql,
                }
                return

            if is_spark_engine(impl.engine):
                plugin = resolve_spark_plugin(
                    impl.engine,
                    plugins=getattr(self.runtime, "spark_plugins", None),
                )
                await self._ensure_spark_session(run_id=run_id)
                udf_policy = parse_udf_policy(
                    (self.plan.profile_snapshot or {}).get("spark_udf_policy")
                )
                spark_region = region_for_node(self.plan, node.name)
                streaming = bool(spark_region and spark_region.streaming) or bool(
                    (self.plan.profile_snapshot or {}).get("spark_streaming")
                )
                batch_only = False
                desc = self.plan.implementations.get(node.name)
                if desc is not None:
                    batch_only = bool((desc.metadata or {}).get("batch_only"))
                if not batch_only:
                    batch_only = bool(getattr(impl.callable, "batch_only", False))
                # Prefer compiled region metadata once per region
                if spark_region and spark_region.identity not in self._spark_compiled:
                    from etlantic.runtime.spark_exec import compile_spark_region

                    compiled = await compile_spark_region(
                        plugin=plugin,
                        region=spark_region,
                        plan=self.plan,
                        run_id=run_id,
                        udf_policy=udf_policy,
                    )
                    self._spark_compiled[spark_region.identity] = compiled
                for _port_name in inputs:
                    validations.append(
                        ValidationResult(
                            node_name=node.name,
                            boundary="input_validation",
                            status="skipped",
                            message="delegated to spark plugin",
                        )
                    )
                result = await execute_spark_step(
                    plugin=plugin,
                    impl=impl,
                    node=node,
                    inputs=inputs,
                    params=params,
                    plan=self.plan,
                    run_id=run_id,
                    attempt=attempt,
                    session_handle=self._spark_session,
                    region_id=spark_region.identity if spark_region else None,
                    streaming=streaming,
                    batch_only=batch_only,
                    udf_policy=udf_policy,
                )
                output_ports = [p.name for p in node.outputs] or ["result"]
                port_name = output_ports[0]
                strategy = self._strategy_for(node.name, port_name)
                logical = f"{node.name}.{port_name}"
                ref = ArtifactRef(
                    identity=artifact_identity(
                        pipeline_id=self.plan.pipeline_id,
                        node_name=node.name,
                        port_name=port_name,
                        security_domain=self.plan.security_domain,
                    ),
                    logical_output=logical,
                    strategy=strategy,
                    security_domain=self.plan.security_domain,
                )
                # Keep lazy handles for spark consumers; collect for others later.
                consumers_spark = True
                for edge in graph.edges_from(node.name):
                    if not is_spark_engine(self._engine_for(edge.consumer_node)):
                        consumers_spark = False
                        break
                stored = result
                if not consumers_spark and not isinstance(result, list):
                    stored = plugin.to_records(result, contract_type=node.contract_type)
                artifacts.put(ref, stored, durable=False)
                compiled_meta = self._spark_compiled.get(
                    spark_region.identity if spark_region else "", None
                )
                state.records_out = _count(stored) if isinstance(stored, list) else 0
                state.metadata["spark"] = {
                    "result_kind": type(result).__name__,
                    "consumers_spark": consumers_spark,
                    "region": spark_region.identity if spark_region else None,
                    "compiled": compiled_meta.to_dict() if compiled_meta else None,
                    "streaming": streaming,
                }
                return

            for port_name, value in inputs.items():
                inputs[port_name] = await self._validate_boundary(
                    node,
                    value,
                    boundary="input_validation",
                    validations=validations,
                    port_name=port_name,
                )
            state.records_in = sum(_count(v) for v in inputs.values())
            result = await self._invoke_transform(
                impl,
                inputs,
                params,
                node=node,
                step_context=step_context,
                attempt=attempt,
            )
            result, emits = self._split_emits(result)
            for emit in emits:
                self.outbound_events.append(
                    {
                        "event": emit.event,
                        "payload": emit.payload
                        if not hasattr(emit.payload, "model_dump")
                        else emit.payload.model_dump(mode="json"),
                        "step": node.name,
                    }
                )
                self.runtime.events.emit(
                    LifecycleEvent(
                        kind="outbound_event",
                        run_id=run_id,
                        pipeline_id=self.plan.pipeline_id,
                        step_name=node.name,
                        message=emit.event,
                    )
                )
            if isinstance(result, dict) and any(p.name in result for p in node.outputs):
                outputs = result
            else:
                default_port = node.outputs[0].name if node.outputs else "result"
                outputs = {default_port: result}
            for port_name, value in outputs.items():
                outputs[port_name] = await self._validate_boundary(
                    node,
                    value,
                    boundary="output_validation",
                    validations=validations,
                    port_name=port_name,
                )
            await self._observe_schema(node, outputs, schema_obs=schema_obs)
            for port_name, value in outputs.items():
                strategy = self._strategy_for(node.name, port_name)
                logical = f"{node.name}.{port_name}"
                ref = ArtifactRef(
                    identity=artifact_identity(
                        pipeline_id=self.plan.pipeline_id,
                        node_name=node.name,
                        port_name=port_name,
                        security_domain=self.plan.security_domain,
                    ),
                    logical_output=logical,
                    strategy=strategy,
                    security_domain=self.plan.security_domain,
                )
                durable = (
                    self.request.materialization is MaterializationPolicy.DURABLE
                    or artifacts.should_durable(strategy)
                )
                artifacts.put(ref, value, durable=durable)
            state.records_out = sum(_count(v) for v in outputs.values())
            return

        raise NodeExecutionError(
            f"Unsupported node kind {node.kind}",
            node_name=node.name,
            stage=FailureStage.ORCHESTRATOR.value,
            run_id=run_id,
            code="PMEXEC310",
        )

    def _split_emits(self, result: Any) -> tuple[Any, list[Emit[Any]]]:
        if isinstance(result, Emit):
            return None, [result]
        if (
            isinstance(result, tuple)
            and len(result) == 2
            and isinstance(result[1], Emit)
        ):
            return result[0], [result[1]]
        if (
            isinstance(result, tuple)
            and result
            and all(isinstance(item, Emit) for item in result[1:])
        ):
            return result[0], list(result[1:])
        return result, []

    def _gather_inputs(
        self, node: Node, graph: LogicalGraph, artifacts: ArtifactStore
    ) -> dict[str, Any]:
        inputs: dict[str, Any] = {}
        consumer_engine = self._engine_for(node.name)
        for edge in graph.edges:
            if edge.consumer_node != node.name:
                continue
            key = f"{edge.producer_node}.{edge.producer_port}"
            value = artifacts.get_raw(key)
            # Hybrid boundary: SQL handle → Python/dataframe records.
            if not is_sql_engine(consumer_engine) and isinstance(
                value, (RelationRef, SqlQuery)
            ):
                plugin = resolve_sql_plugin(
                    "sql",
                    plugins=getattr(self.runtime, "sql_plugins", None),
                )
                allow_trusted = bool(
                    (self.plan.profile_snapshot or {}).get("allow_trusted_sql")
                )
                ctx = SqlExecutionContext(
                    run_id="hybrid",
                    pipeline_id=self.plan.pipeline_id,
                    plan_id=self.plan.plan_id,
                    step_name=node.name,
                    allow_trusted_sql=allow_trusted,
                )
                fetched = plugin.fetch_records(
                    value, params={}, context=ctx, contract_type=node.contract_type
                )
                value = fetched.records or []
            inputs[edge.consumer_port] = value
        return inputs

    def _engine_for(self, node_name: str) -> str:
        for region in self.plan.regions:
            if node_name in region.node_names:
                return region.engine
        impl = self.plan.implementations.get(node_name)
        if impl is not None:
            return impl.engine
        return str(
            (self.plan.execution_settings or {}).get("spark_engine")
            or (self.plan.execution_settings or {}).get("sql_engine")
            or (self.plan.execution_settings or {}).get("dataframe_engine")
            or "local"
        )

    async def _ensure_spark_session(self, *, run_id: str) -> SparkSessionHandle:
        if self._spark_session is not None:
            return self._spark_session
        provider_name = str(
            (self.plan.profile_snapshot or {}).get("resources", {}).get("spark")
            or "local"
        )
        providers = getattr(self.runtime, "spark_providers", None) or {}
        try:
            provider = resolve_spark_provider(provider_name, providers=providers)
        except NodeExecutionError:
            provider = resolve_spark_provider("local", providers=providers)
        enable_delta = "spark_delta" in (
            (self.plan.profile_snapshot or {}).get("required_spark_capabilities") or ()
        ) or bool(
            (self.plan.profile_snapshot or {}).get("metadata", {}).get("enable_delta")
        )
        streaming = bool((self.plan.profile_snapshot or {}).get("spark_streaming"))
        self._spark_session = await acquire_session(
            provider=provider,
            plan=self.plan,
            run_id=run_id,
            enable_delta=enable_delta,
            streaming=streaming,
        )
        # Attach session to plugins that support it
        for plugin in (getattr(self.runtime, "spark_plugins", None) or {}).values():
            if hasattr(plugin, "bind_session"):
                plugin.bind_session(self._spark_session)
        return self._spark_session

    def _coerce_to_records(self, data: Any, *, contract_type: type[Any] | None) -> Any:
        """Convert native frames to records for storage/publication boundaries."""
        from etlantic.runtime.artifacts import _looks_like_frame

        if not _looks_like_frame(data):
            return data
        module = type(data).__module__ or ""
        engine = "polars" if module.startswith("polars") else "pandas"
        try:
            plugin = resolve_dataframe_plugin(
                engine,
                plugins=getattr(self.runtime, "dataframe_plugins", None),
            )
            return plugin.to_records(data, contract_type=contract_type)
        except Exception:
            # Fallback: best-effort via Arrow / to_dicts duck typing
            if hasattr(data, "to_dicts") and callable(data.to_dicts):
                rows = (
                    data.collect().to_dicts()
                    if hasattr(data, "collect")
                    else data.to_dicts()
                )
                return as_records(rows, contract_type)
            if hasattr(data, "to_dict") and callable(data.to_dict):
                orient = data.to_dict(orient="records")
                return as_records(orient, contract_type)
            return data

    def _store_outputs(self, node: Node, data: Any, artifacts: ArtifactStore) -> None:
        port = node.outputs[0].name if node.outputs else "result"
        strategy = self._strategy_for(node.name, port)
        logical = f"{node.name}.{port}"
        ref = ArtifactRef(
            identity=artifact_identity(
                pipeline_id=self.plan.pipeline_id,
                node_name=node.name,
                port_name=port,
                security_domain=self.plan.security_domain,
            ),
            logical_output=logical,
            strategy=strategy,
            security_domain=self.plan.security_domain,
        )
        durable = (
            self.request.materialization is MaterializationPolicy.DURABLE
            or artifacts.should_durable(strategy)
        )
        artifacts.put(ref, data, durable=durable)

    def _parameters_for(self, node: Node) -> dict[str, Any]:
        params = {
            p.name: p.value
            for p in node.parameters
            if p.has_value and p.value is not ...
        }
        overrides = self.request.parameter_overrides.get(node.name, {})
        params.update(overrides)
        return params

    def _resolve_implementation(self, node: Node) -> ImplementationRecord:
        if not node.transformation_id:
            raise NodeExecutionError(
                f"Step {node.name} has no transformation_id",
                node_name=node.name,
                stage=FailureStage.TRANSFORM.value,
                code="PMEXEC320",
            )
        descriptor: ImplementationDescriptor | None = self.plan.implementations.get(
            node.name
        )
        engine = (
            self.request.implementation_overrides.get(node.name)
            or (descriptor.engine if descriptor else None)
            or "local"
        )
        xf = self.transform_lookup.get(node.transformation_id)
        if xf is None:
            for candidate in _all_subclasses(Transformation):
                if candidate.identity() == node.transformation_id:
                    xf = candidate
                    self.transform_lookup[node.transformation_id] = xf
                    break
        if xf is None:
            raise NodeExecutionError(
                f"No transformation class for {node.transformation_id}",
                node_name=node.name,
                stage=FailureStage.TRANSFORM.value,
                code="PMEXEC320",
            )
        record = xf.implementations().get(engine)
        if record is None:
            available = ", ".join(sorted(xf.implementations())) or "(none)"
            raise NodeExecutionError(
                f"No implementation for engine {engine!r} on "
                f"{node.transformation_id}; available: {available}",
                node_name=node.name,
                stage=FailureStage.TRANSFORM.value,
                code="PMEXEC321",
            )
        return record

    async def _invoke_transform(
        self,
        impl: ImplementationRecord,
        inputs: dict[str, Any],
        params: dict[str, Any],
        *,
        node: Node,
        step_context: StepContext,
        attempt: int,
    ) -> Any:
        kwargs = {**inputs, **params}
        attempt_ctx = AttemptContext(step=step_context, attempt=attempt)
        # Inject annotated resources.
        for name, param in impl.signature.parameters.items():
            inject_name = self._inject_name(param.annotation)
            if inject_name is None and name in self.runtime.resources.providers:
                inject_name = name
            if inject_name is None:
                continue
            kwargs[name] = await self.runtime.resources.get(
                inject_name,
                scope="attempt",
                scope_key=f"{step_context.step_name}:{attempt}",
                context={"step": step_context, "attempt": attempt_ctx},
            )
        try:
            sig = impl.signature
            if any(
                p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            ):
                accepted = kwargs
            else:
                accepted = {k: v for k, v in kwargs.items() if k in sig.parameters}
        except Exception:
            accepted = kwargs
        return await maybe_await(impl.callable, **accepted)

    def _inject_name(self, annotation: Any) -> str | None:
        if annotation is inspect.Parameter.empty:
            return None
        origin = get_origin(annotation)
        if origin is Annotated:
            for arg in get_args(annotation)[1:]:
                if isinstance(arg, Inject):
                    return arg.name
        return None

    def _binding_descriptor(
        self, node: Node, binding_name: str
    ) -> BindingDescriptor | None:
        override = self.request.binding_overrides.get(node.name)
        if override:
            if override in self.runtime.registry.bindings:
                return self.runtime.registry.bindings[override]
            for desc in self.plan.bindings.values():
                if desc.binding == override:
                    return desc
        return self.plan.bindings.get(node.name) or self.plan.bindings.get(binding_name)

    async def _read_source(self, node: Node, *, run_id: str) -> Any:
        binding_name = node.binding or node.name
        binding_name = self.request.binding_overrides.get(node.name, binding_name)
        descriptor = self._binding_descriptor(node, binding_name)
        provider_name = descriptor.provider if descriptor is not None else "memory"
        if provider_name in {"local", "python"}:
            provider_name = "memory"
        storage = self.runtime.storage.get(provider_name)
        if storage is None:
            storage = self.runtime.memory
            provider_name = "memory"
        location = descriptor.location if descriptor is not None else None
        context: dict[str, Any] = {"run_id": run_id, "node": node.name}
        if descriptor is not None and descriptor.secret_ref is not None:
            context["secret"] = await self._resolve_secret(
                descriptor.secret_ref, run_id=run_id, step=node.name
            )
        return await storage.read(
            binding=binding_name,
            location=location,
            contract_type=node.contract_type,
            context=context,
        )

    async def _write_sink(self, node: Node, data: Any, *, run_id: str) -> None:
        binding_name = node.binding or node.name
        binding_name = self.request.binding_overrides.get(node.name, binding_name)
        descriptor = self._binding_descriptor(node, binding_name)
        provider_name = descriptor.provider if descriptor is not None else "memory"
        if provider_name in {"local", "python"}:
            provider_name = "memory"
        if self.request.no_write:
            provider_name = "null"
        storage = self.runtime.storage.get(provider_name) or self.runtime.memory
        location = descriptor.location if descriptor is not None else None
        context: dict[str, Any] = {"run_id": run_id, "node": node.name}
        if descriptor is not None and descriptor.secret_ref is not None:
            context["secret"] = await self._resolve_secret(
                descriptor.secret_ref, run_id=run_id, step=node.name
            )
        await storage.write(
            binding=binding_name,
            location=location,
            data=data,
            contract_type=node.contract_type,
            context=context,
        )

    async def _resolve_secret(self, ref: SecretRef, *, run_id: str, step: str) -> Any:
        cached = self.runtime.secret_cache.get(ref)
        if cached is not None:
            return cached
        provider = self.runtime.secret_providers.get(ref.provider)
        if provider is None:
            raise PipelineExecutionError(
                f"No secret provider registered for {ref.provider!r}",
                run_id=run_id,
                code="PMEXEC400",
            )
        context = SecretResolutionContext(
            run_id=run_id,
            pipeline_id=self.plan.pipeline_id,
            step_name=step,
            purpose=ref.purpose,
        )
        try:
            value = await provider.resolve(ref, context)
        except Exception as exc:
            self.runtime.events.emit(
                SecurityEvent(
                    kind="secret_resolution",
                    run_id=run_id,
                    provider=ref.provider,
                    secret_identity=ref.identity(),
                    outcome="failure",
                    step_name=step,
                    message=redact_message(str(exc)),
                )
            )
            raise
        self.runtime.secret_cache.put(ref, value)
        self.runtime.events.emit(
            SecurityEvent(
                kind="secret_resolution",
                run_id=run_id,
                provider=ref.provider,
                secret_identity=ref.identity(),
                outcome="success",
                step_name=step,
            )
        )
        return value

    async def _check_source_reliability(
        self, node: Node, data: Any, *, run_id: str
    ) -> None:
        expectations = self.request.metadata.get("freshness") or {}
        raw = expectations.get(node.name) or expectations.get(node.binding or "")
        if isinstance(raw, FreshnessExpectation):
            observed_at = resolve_freshness_observed_at(
                raw,
                node_name=node.name,
                binding=node.binding,
                metadata=dict(self.request.metadata),
            )
            result = check_freshness(raw, observed_at=observed_at)
            if not result.ok:
                raise NodeExecutionError(
                    result.message or "Freshness check failed",
                    node_name=node.name,
                    stage=FailureStage.FRESHNESS.value,
                    run_id=run_id,
                    code="PMEXEC350",
                )
        partitions = self.request.metadata.get("partitions") or {}
        pref = partitions.get(node.name) or partitions.get(node.binding or "")
        if isinstance(pref, PartitionCompletenessExpectation):
            observed: set[str] = set()
            for row in as_records(data, None):
                mapping = row.model_dump() if hasattr(row, "model_dump") else row
                if isinstance(mapping, dict):
                    key = "|".join(str(mapping.get(k, "")) for k in pref.partition_keys)
                    observed.add(key)
            ok, message = check_partition_completeness(
                pref, observed_partitions=observed
            )
            if not ok:
                raise NodeExecutionError(
                    message or "Partition completeness failed",
                    node_name=node.name,
                    stage=FailureStage.FRESHNESS.value,
                    run_id=run_id,
                    code="PMEXEC351",
                )

    async def _validate_boundary(
        self,
        node: Node,
        data: Any,
        *,
        boundary: str,
        validations: list[ValidationResult],
        port_name: str | None = None,
    ) -> Any:
        contract = node.contract_type
        if contract is None and port_name:
            for port in list(node.inputs) + list(node.outputs):
                if port.name == port_name:
                    contract = port.contract_type
                    break
        if contract is None:
            validations.append(
                ValidationResult(
                    node_name=node.name,
                    boundary=boundary,
                    status="skipped",
                )
            )
            return data
        try:
            records = as_records(data, contract)
            validations.append(
                ValidationResult(
                    node_name=node.name,
                    boundary=boundary,
                    status="passed",
                    records_checked=len(records),
                    records_invalid=0,
                )
            )
            return records
        except Exception as exc:
            validations.append(
                ValidationResult(
                    node_name=node.name,
                    boundary=boundary,
                    status="failed",
                    message=redact_message(str(exc)),
                )
            )
            raise NodeExecutionError(
                redact_message(
                    f"Validation failed at {boundary} for {node.name}: {exc}"
                ),
                node_name=node.name,
                stage=boundary,
                code="PMEXEC330",
                cause=exc,
            ) from exc

    async def _observe_schema(
        self,
        node: Node,
        data: Any,
        *,
        schema_obs: list[SchemaObservationResult],
    ) -> None:
        model = node.contract_type
        if model is None and not data:
            return
        declared = normalize_schema_from_model(model) if model is not None else None
        payload = data
        if isinstance(data, dict):
            # Multi-output: observe first port payload.
            payload = next(iter(data.values()), [])
        plugin = None
        impl = self.plan.implementations.get(node.name)
        engine = (
            impl.engine
            if impl is not None
            else (self.plan.profile_snapshot or {}).get("dataframe_engine")
        )
        if engine and is_dataframe_engine(str(engine)):
            try:
                plugin = resolve_dataframe_plugin(
                    str(engine),
                    plugins=getattr(self.runtime, "dataframe_plugins", None),
                )
            except NodeExecutionError:
                plugin = None
        current = _observe_records_schema(
            node.name, payload, layer="current", plugin=plugin
        )
        previous = self.schema_history.latest(node.name)
        if current is not None:
            self.schema_history.record(current)
        decision = evaluate_drift(
            subject_id=node.name,
            declared=declared,
            previous=previous,
            current=current,
            policy=self.drift_policy,
            profile_name=self.plan.profile_name,
        )
        if declared is not None:
            schema_obs.append(
                SchemaObservationResult(
                    subject_id=node.name,
                    layer="declared",
                    fingerprint=declared.fingerprint(),
                )
            )
        if previous is not None:
            schema_obs.append(
                SchemaObservationResult(
                    subject_id=node.name,
                    layer="previous",
                    fingerprint=previous.schema.fingerprint(),
                )
            )
        if current is not None:
            schema_obs.append(
                SchemaObservationResult(
                    subject_id=node.name,
                    layer="current",
                    fingerprint=current.schema.fingerprint(),
                    drift_decision=decision.action.value,
                )
            )
        if decision.action is DriftAction.BLOCK:
            raise NodeExecutionError(
                f"Schema drift blocked for {node.name}",
                node_name=node.name,
                stage=FailureStage.SCHEMA_DRIFT.value,
                code="PMEXEC340",
            )


def _count(data: Any) -> int:
    if data is None:
        return 0
    if isinstance(data, (list, tuple)):
        return len(data)
    if hasattr(data, "__len__") and not isinstance(data, (str, bytes, dict)):
        try:
            return len(data)
        except Exception:
            pass
    # LazyFrame: unknown without collect
    if type(data).__name__ == "LazyFrame":
        return 0
    return 1
