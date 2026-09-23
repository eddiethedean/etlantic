# pyright: reportUnknownVariableType=false, reportUnnecessaryComparison=false
"""Direct-execution scheduler boundary (etlantic.scheduler/1).

Built-in ``LocalScheduler`` is the zero-service default. Optional plugins such
as ``etlantic-prefect`` register under ``etlantic.scheduler_plugins``. External
compilers continue to use ``etlantic.orchestration/1`` (compile/submit/poll).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from etlantic.plan.adaptive_model import AdaptivePipelinePlan, PlanDocument
from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.request import RunRequest

SCHEDULER_PROTOCOL = "etlantic.scheduler/1"


class UnitStatus(StrEnum):
    """Normalized scheduler unit lifecycle states."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    ABANDONED = "abandoned"


@dataclass(frozen=True, slots=True)
class SchedulerInfo:
    """Built-in or plugin scheduler metadata."""

    name: str
    version: str
    scheduler_protocol: str = SCHEDULER_PROTOCOL
    direct_execution: bool = True
    external_compilation: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "scheduler_protocol": self.scheduler_protocol,
            "direct_execution": self.direct_execution,
            "external_compilation": self.external_compilation,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class SchedulerSupportFinding:
    code: str
    requirement: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "requirement": self.requirement,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class SchedulerSupportReport:
    supported: bool
    findings: tuple[SchedulerSupportFinding, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "supported": self.supported,
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass(frozen=True, slots=True)
class SchedulingContext:
    """Caller identity for analyze/execute (no data access in analyze)."""

    run_id: str | None = None
    pipeline_id: str | None = None
    plan_id: str | None = None
    profile_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ExecutionScheduler(Protocol):
    """Schedule resolved physical/logical units without re-planning."""

    @property
    def info(self) -> SchedulerInfo: ...

    def analyze(
        self,
        plan: PlanDocument,
        *,
        request: RunRequest,
        context: SchedulingContext,
    ) -> SchedulerSupportReport: ...

    async def execute(
        self,
        plan: PlanDocument,
        *,
        request: RunRequest,
        runtime: Any,
        pipeline_cls: type[Any] | None = None,
        workspace: Any = None,
        artifact_store: Any = None,
        context: SchedulingContext | None = None,
    ) -> PipelineRunReport: ...


class LocalScheduler:
    """Built-in zero-service direct-execution scheduler.

    Owns the scheduling entrypoint. ETLantic runtime host responsibilities
    (engine routing, validation, materialization, reports) remain in
    ``LocalOrchestrator`` for 0.15; the wave loop is invoked through that host
    without plugin/implementation reselection inside the scheduler.
    """

    def __init__(self) -> None:
        from etlantic import __version__

        self._info = SchedulerInfo(
            name="local",
            version=__version__,
            direct_execution=True,
            external_compilation=False,
            metadata={"host": "LocalOrchestrator"},
        )

    @property
    def info(self) -> SchedulerInfo:
        return self._info

    def analyze(
        self,
        plan: PlanDocument,
        *,
        request: RunRequest,
        context: SchedulingContext,
    ) -> SchedulerSupportReport:
        from etlantic.plan.adaptive_model import ADAPTIVE_PLAN_SCHEMA

        if (
            isinstance(plan, AdaptivePipelinePlan)
            or getattr(plan, "schema", None) == ADAPTIVE_PLAN_SCHEMA
        ):
            from etlantic.runtime.adaptive_support import is_executable_plan

            if not is_executable_plan(plan):
                return SchedulerSupportReport(
                    supported=False,
                    findings=(
                        SchedulerSupportFinding(
                            code="PMADP500",
                            requirement="etlantic.plan/2",
                            reason="Adaptive plan has no qualified local support row",
                        ),
                    ),
                )
            return SchedulerSupportReport(supported=True)
        findings: list[SchedulerSupportFinding] = []
        # Local scheduler schedules logical graph nodes (physical_units are
        # advisory metadata until fusion-driven unit scheduling lands).
        if plan.logical_graph is None or not plan.logical_graph.nodes:
            findings.append(
                SchedulerSupportFinding(
                    code="PMSCHED101",
                    requirement="logical_graph",
                    reason="Plan has no logical nodes to schedule",
                )
            )
        settings = plan.execution_settings or {}
        if settings.get("concurrency") is not None:
            concurrency = settings["concurrency"]
        elif request.metadata.get("concurrency") is not None:
            concurrency = request.metadata["concurrency"]
        else:
            concurrency = 4
        try:
            concurrency_i = int(concurrency)
        except (TypeError, ValueError):
            findings.append(
                SchedulerSupportFinding(
                    code="PMSCHED102",
                    requirement="concurrency",
                    reason="Concurrency must be an integer",
                )
            )
        else:
            if concurrency_i < 1:
                findings.append(
                    SchedulerSupportFinding(
                        code="PMSCHED102",
                        requirement="concurrency",
                        reason="Concurrency must be >= 1",
                    )
                )
        return SchedulerSupportReport(supported=not findings, findings=tuple(findings))

    async def execute(
        self,
        plan: PlanDocument,
        *,
        request: RunRequest,
        runtime: Any,
        pipeline_cls: type[Any] | None = None,
        workspace: Any = None,
        artifact_store: Any = None,
        context: SchedulingContext | None = None,
    ) -> PipelineRunReport:
        report = self.analyze(
            plan,
            request=request,
            context=context
            or SchedulingContext(
                pipeline_id=plan.pipeline_id,
                plan_id=plan.plan_id,
                profile_name=plan.profile_name,
            ),
        )
        if not report.supported:
            from etlantic.exceptions import PipelineExecutionError

            detail = "; ".join(f"{f.code}: {f.reason}" for f in report.findings)
            code = report.findings[0].code if report.findings else None
            raise PipelineExecutionError(
                f"LocalScheduler rejected plan: {detail}",
                code=code,
                stage="admission",
            )

        from etlantic.plan.adaptive_model import ADAPTIVE_PLAN_SCHEMA
        from etlantic.runtime.orchestrator import LocalOrchestrator

        if (
            isinstance(plan, AdaptivePipelinePlan)
            or getattr(plan, "schema", None) == ADAPTIVE_PLAN_SCHEMA
        ):
            from etlantic.runtime.adaptive_admission import admit_adaptive_plan
            from etlantic.runtime.physical_host import pipeline_plan_for_adaptive

            admission = admit_adaptive_plan(
                plan, request=request, runtime=runtime, workspace=workspace
            )
            host_plan = pipeline_plan_for_adaptive(
                plan,
                runtime=runtime,
                pipeline_cls=pipeline_cls,
                contract_pins=admission.contract_pins,
                binding_pins=admission.binding_pins,
            )
            host = LocalOrchestrator(
                runtime=runtime,
                plan=host_plan,
                request=request,
                pipeline_cls=pipeline_cls,
                workspace=workspace,
                artifacts=artifact_store,
                run_id=context.run_id if context is not None else None,
                physical_mode=True,
                adaptive_plan=plan,
                physical_executor_pins=admission.executor_pins,
                physical_storage_pins=admission.storage_pins,
                physical_compiler_pins=admission.compiler_pins,
                physical_dataframe_pins=dict(admission.dataframe_pins),
                physical_io_policy_pins=admission.io_policy_pins,
            )
            result = await host.execute()
            result.metadata.setdefault("etlantic.scheduler", self.info.name)
            result.metadata.setdefault(
                "etlantic.scheduler_protocol", SCHEDULER_PROTOCOL
            )
            return result

        host = LocalOrchestrator(
            runtime=runtime,
            plan=plan,
            request=request,
            pipeline_cls=pipeline_cls,
            workspace=workspace,
            artifacts=artifact_store,
            run_id=context.run_id if context is not None else None,
        )
        result = await host.execute()
        # Annotate scheduler identity without breaking report schema consumers.
        result.metadata.setdefault("etlantic.scheduler", self.info.name)
        result.metadata.setdefault("etlantic.scheduler_protocol", SCHEDULER_PROTOCOL)
        return result
