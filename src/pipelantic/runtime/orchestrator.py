"""Local orchestrator: execute a PipelinePlan in-process."""

from __future__ import annotations

import inspect
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import anyio

from pipelantic.exceptions import (
    NodeExecutionError,
    PipelineCancelledError,
    PipelineExecutionError,
    PipelineTimeoutError,
)
from pipelantic.lifecycle.callbacks import FailureAction, StepFailureContext
from pipelantic.lifecycle.runtime import PipelineRuntime
from pipelantic.model import LogicalGraph, Node, NodeKind
from pipelantic.plan.artifacts import ArtifactRef, ArtifactStrategy, artifact_identity
from pipelantic.plan.model import PipelinePlan
from pipelantic.registry import ImplementationDescriptor
from pipelantic.reliability_runtime import write_mode_for_request
from pipelantic.reports.model import (
    ArtifactResult,
    PipelineRunReport,
    RunDiagnostic,
    RunSummary,
    SchemaObservationResult,
    StepRunReport,
    ValidationResult,
)
from pipelantic.runtime.artifacts import ArtifactStore
from pipelantic.runtime.events import LifecycleEvent, SecurityEvent
from pipelantic.runtime.invoke import maybe_await
from pipelantic.runtime.logging import RunLogger
from pipelantic.runtime.request import RunRequest
from pipelantic.runtime.state import FailureStage, RunStatus, StepStatus
from pipelantic.schema_drift import normalize_schema_from_model
from pipelantic.schema_policy import (
    DriftAction,
    InMemorySchemaHistory,
    SchemaDriftPolicy,
    evaluate_drift,
    observe_model_schema,
)
from pipelantic.secrets.provider import SecretResolutionContext
from pipelantic.secrets.ref import SecretRef
from pipelantic.storage.protocol import as_records
from pipelantic.transformation import ImplementationRecord, Transformation


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


@dataclass
class LocalOrchestrator:
    """Async-first local DAG executor for PipelinePlan."""

    runtime: PipelineRuntime
    plan: PipelinePlan
    request: RunRequest
    pipeline_cls: type[Any] | None = None
    workspace: Path | None = None
    drift_policy: SchemaDriftPolicy = field(default_factory=SchemaDriftPolicy)
    schema_history: InMemorySchemaHistory = field(default_factory=InMemorySchemaHistory)
    transform_lookup: dict[str, type[Transformation]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.pipeline_cls is not None:
            self._index_transformations(self.pipeline_cls)

    def _index_transformations(self, pipeline_cls: type[Any]) -> None:
        members = getattr(pipeline_cls, "__pipeline_members__", {})
        for value in members.values():
            xf = getattr(value, "transformation", None)
            if xf is not None:
                self.transform_lookup[xf.identity()] = xf

    async def execute(self) -> PipelineRunReport:
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        started = datetime.now(UTC)
        logger = RunLogger(run_id=run_id, pipeline_id=self.plan.pipeline_id)
        artifacts = ArtifactStore(workspace=self.workspace)
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
                        )
                        if nodes[n].status is StepStatus.SUCCEEDED:
                            completed.add(n)
                        else:
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
                                    failed.add(child)
                                stack.extend(consumers.get(child, ()))

                async with anyio.create_task_group() as wave:
                    for name in ready:
                        pending.discard(name)
                        wave.start_soon(_one, name)
                if failed:
                    break

        try:
            timeout = self.request.timeout.run_seconds
            if timeout is not None:
                with anyio.fail_after(timeout):
                    await self.runtime.run_middleware.run(
                        {"run_id": run_id, "plan": self.plan},
                        run_body,
                    )
            else:
                await self.runtime.run_middleware.run(
                    {"run_id": run_id, "plan": self.plan},
                    run_body,
                )
        except TimeoutError as exc:
            status = RunStatus.TIMED_OUT
            diagnostics.append(
                RunDiagnostic(
                    code="PMEXEC408",
                    severity="error",
                    message=f"Run timed out after {self.request.timeout.run_seconds}s",
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
                str(exc), run_id=run_id, report=report, code="PMEXEC408"
            ) from exc
        except Exception as exc:
            if (
                type(exc).__name__ in {"CancelledError"}
                or "cancel" in type(exc).__name__.lower()
            ):
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
            if isinstance(exc, PipelineExecutionError):
                status = RunStatus.FAILED
                raise
            status = RunStatus.FAILED
            diagnostics.append(
                RunDiagnostic(
                    code="PMEXEC500",
                    severity="error",
                    message=str(exc),
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
                str(exc), run_id=run_id, report=report, code="PMEXEC500"
            ) from exc
        finally:
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
            backend_runs=(),
            metadata={"orchestrator": "local"},
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
            metadata={"orchestrator": "local"},
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
            error_message=state.error,
            records_in=state.records_in,
            records_out=state.records_out,
            implementation=state.implementation,
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
    ) -> None:
        max_attempts = max(1, self.request.retry.max_attempts)
        last_error: BaseException | None = None

        for attempt in range(1, max_attempts + 1):
            state.attempts = attempt
            state.status = StepStatus.RUNNING if attempt == 1 else StepStatus.RETRYING
            state.started_at = state.started_at or datetime.now(UTC)
            current_attempt = attempt
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

                async def terminal(attempt_no: int = current_attempt) -> None:
                    await self._run_node_once(
                        state=state,
                        run_id=run_id,
                        artifacts=artifacts,
                        graph=graph,
                        validations=validations,
                        schema_obs=schema_obs,
                        attempt=attempt_no,
                    )

                step_timeout = self.request.timeout.step_seconds
                if step_timeout is not None:
                    with anyio.fail_after(step_timeout):
                        await self.runtime.step_middleware.run(
                            {"step": name, "attempt": attempt},
                            terminal,
                        )
                else:
                    await self.runtime.step_middleware.run(
                        {"step": name, "attempt": attempt},
                        terminal,
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
                state.error = str(exc)
                state.ended_at = datetime.now(UTC)
                last_error = exc
                break
            except Exception as exc:
                last_error = exc
                state.stage = (
                    getattr(exc, "stage", None) or FailureStage.TRANSFORM.value
                )
                state.error = str(exc)
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
                if action is FailureAction.RETRY and attempt < max_attempts:
                    continue
                if action is FailureAction.SKIP:
                    state.status = StepStatus.SKIPPED
                    state.ended_at = datetime.now(UTC)
                    return
                state.status = StepStatus.FAILED
                state.ended_at = datetime.now(UTC)
                diagnostics.append(
                    RunDiagnostic(
                        code="PMEXEC300",
                        severity="error",
                        message=str(exc),
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
                        message=str(exc),
                    )
                )
                logger.log(
                    "error",
                    f"Step {name} failed",
                    step_name=name,
                    attempt=attempt,
                    error=str(exc),
                )
                return

        if last_error is not None and state.status is not StepStatus.SUCCEEDED:
            state.status = (
                StepStatus.TIMED_OUT
                if isinstance(last_error, TimeoutError)
                else StepStatus.FAILED
            )
            state.ended_at = datetime.now(UTC)

    async def _run_node_once(
        self,
        *,
        state: _NodeState,
        run_id: str,
        artifacts: ArtifactStore,
        graph: LogicalGraph,
        validations: list[ValidationResult],
        schema_obs: list[SchemaObservationResult],
        attempt: int,
    ) -> None:
        node = state.node
        if node.kind is NodeKind.SOURCE:
            data = await self._read_source(node, run_id=run_id)
            data = await self._validate_boundary(
                node, data, boundary="source", validations=validations
            )
            await self._observe_schema(node, data, schema_obs=schema_obs)
            self._store_outputs(node, data, artifacts)
            state.records_out = _count(data)
            return

        if node.kind is NodeKind.SINK:
            inputs = self._gather_inputs(node, graph, artifacts)
            payload = next(iter(inputs.values()), [])
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
            return

        if node.kind is NodeKind.STEP:
            inputs = self._gather_inputs(node, graph, artifacts)
            for port_name, value in inputs.items():
                inputs[port_name] = await self._validate_boundary(
                    node,
                    value,
                    boundary="input_validation",
                    validations=validations,
                    port_name=port_name,
                )
            state.records_in = sum(_count(v) for v in inputs.values())
            params = self._parameters_for(node)
            impl = self._resolve_implementation(node)
            state.implementation = impl.identity if impl else None
            result = await self._invoke_transform(impl, inputs, params, node=node)
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
                logical = f"{node.name}.{port_name}"
                ref = ArtifactRef(
                    identity=artifact_identity(
                        pipeline_id=self.plan.pipeline_id,
                        node_name=node.name,
                        port_name=port_name,
                        security_domain=self.plan.security_domain,
                    ),
                    logical_output=logical,
                    strategy=ArtifactStrategy.IN_MEMORY,
                    security_domain=self.plan.security_domain,
                )
                durable = (
                    self.request.materialization.value == "durable"
                    or artifacts.should_durable(ArtifactStrategy.DURABLE)
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

    def _gather_inputs(
        self, node: Node, graph: LogicalGraph, artifacts: ArtifactStore
    ) -> dict[str, Any]:
        inputs: dict[str, Any] = {}
        for edge in graph.edges:
            if edge.consumer_node != node.name:
                continue
            key = f"{edge.producer_node}.{edge.producer_port}"
            inputs[edge.consumer_port] = artifacts.get(key)
        return inputs

    def _store_outputs(self, node: Node, data: Any, artifacts: ArtifactStore) -> None:
        port = node.outputs[0].name if node.outputs else "result"
        logical = f"{node.name}.{port}"
        ref = ArtifactRef(
            identity=artifact_identity(
                pipeline_id=self.plan.pipeline_id,
                node_name=node.name,
                port_name=port,
                security_domain=self.plan.security_domain,
            ),
            logical_output=logical,
            strategy=ArtifactStrategy.IN_MEMORY,
            security_domain=self.plan.security_domain,
        )
        artifacts.put(ref, data)

    def _parameters_for(self, node: Node) -> dict[str, Any]:
        params = {
            p.name: p.value
            for p in node.parameters
            if p.has_value and p.value is not ...
        }
        overrides = self.request.parameter_overrides.get(node.name, {})
        params.update(overrides)
        return params

    def _resolve_implementation(self, node: Node) -> ImplementationRecord | None:
        if not node.transformation_id:
            return None
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
            # Search registered transformation classes by identity.
            for candidate in Transformation.__subclasses__():
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
        if record is None and engine != "local":
            record = xf.implementations().get("local")
        if record is None and xf.implementations():
            record = next(iter(xf.implementations().values()))
        if record is None:
            # Identity passthrough default for testing when no impl registered.
            async def _identity(**kwargs: Any) -> Any:
                if "result" in kwargs:
                    return kwargs["result"]
                if len(kwargs) == 1:
                    return next(iter(kwargs.values()))
                return kwargs

            return ImplementationRecord(
                engine="local",
                identity=f"{node.transformation_id}::local-identity",
                callable=_identity,
                is_async=True,
                signature=inspect.signature(_identity),
            )
        return record

    async def _invoke_transform(
        self,
        impl: ImplementationRecord | None,
        inputs: dict[str, Any],
        params: dict[str, Any],
        *,
        node: Node,
    ) -> Any:
        if impl is None:
            raise NodeExecutionError(
                f"No implementation for step {node.name}",
                node_name=node.name,
                stage=FailureStage.TRANSFORM.value,
                code="PMEXEC321",
            )
        kwargs = {**inputs, **params}
        # Filter to signature parameters when possible.
        try:
            sig = impl.signature
            accepted = {
                k: v
                for k, v in kwargs.items()
                if k in sig.parameters
                or any(
                    p.kind in (inspect.Parameter.VAR_KEYWORD,)
                    for p in sig.parameters.values()
                )
            }
            if any(
                p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            ):
                accepted = kwargs
            else:
                accepted = {k: v for k, v in kwargs.items() if k in sig.parameters}
        except Exception:
            accepted = kwargs
        return await maybe_await(impl.callable, **accepted)

    async def _read_source(self, node: Node, *, run_id: str) -> Any:
        binding_name = node.binding or node.name
        binding_name = self.request.binding_overrides.get(node.name, binding_name)
        descriptor = self.plan.bindings.get(node.name) or self.plan.bindings.get(
            binding_name
        )
        provider_name = descriptor.provider if descriptor is not None else "memory"
        if provider_name in {"local", "python"}:
            provider_name = "memory"
        if self.request.no_write and provider_name not in self.runtime.storage:
            provider_name = "null"
        storage = self.runtime.storage.get(provider_name)
        if storage is None:
            storage = self.runtime.memory
            provider_name = "memory"
        location = descriptor.location if descriptor is not None else None
        if descriptor is not None and descriptor.secret_ref is not None:
            await self._resolve_secret(
                descriptor.secret_ref, run_id=run_id, step=node.name
            )
        return await storage.read(
            binding=binding_name,
            location=location,
            contract_type=node.contract_type,
            context={"run_id": run_id, "node": node.name},
        )

    async def _write_sink(self, node: Node, data: Any, *, run_id: str) -> None:
        binding_name = node.binding or node.name
        binding_name = self.request.binding_overrides.get(node.name, binding_name)
        descriptor = self.plan.bindings.get(node.name) or self.plan.bindings.get(
            binding_name
        )
        provider_name = descriptor.provider if descriptor is not None else "memory"
        if provider_name in {"local", "python"}:
            provider_name = "memory"
        if self.request.no_write:
            provider_name = "null"
        storage = self.runtime.storage.get(provider_name) or self.runtime.memory
        location = descriptor.location if descriptor is not None else None
        if descriptor is not None and descriptor.secret_ref is not None:
            await self._resolve_secret(
                descriptor.secret_ref, run_id=run_id, step=node.name
            )
        await storage.write(
            binding=binding_name,
            location=location,
            data=data,
            contract_type=node.contract_type,
            context={"run_id": run_id, "node": node.name},
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
                    message=str(exc),
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
                    message=str(exc),
                )
            )
            raise NodeExecutionError(
                f"Validation failed at {boundary} for {node.name}: {exc}",
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
        if model is None:
            return
        declared = normalize_schema_from_model(model)
        current = observe_model_schema(node.name, model, layer="current")
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
    return 1
