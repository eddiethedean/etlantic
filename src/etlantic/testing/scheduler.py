"""Public ExecutionScheduler conformance helpers (etlantic.scheduler/1)."""

from __future__ import annotations

from typing import Any

from etlantic.contracts import Data
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.pipeline import Extract, Load, Pipeline
from etlantic.plan.planner import plan_pipeline
from etlantic.ports import Input, Output
from etlantic.profile import Profile
from etlantic.registry import PlanningContext
from etlantic.runtime.logging import redact_message
from etlantic.runtime.request import RunRequest
from etlantic.runtime.scheduler import (
    SCHEDULER_PROTOCOL,
    ExecutionScheduler,
    LocalScheduler,
    SchedulingContext,
)
from etlantic.runtime.state import RunStatus
from etlantic.transformation import Transformation


class _RawCustomer(Data):
    customer_id: int
    first_name: str
    last_name: str


class _Customer(Data):
    customer_id: int
    full_name: str


class _Normalize(Transformation):
    customers: Input[_RawCustomer]
    result: Output[_Customer]


@_Normalize.implementation("local")
def _normalize(customers: list[_RawCustomer]) -> list[_Customer]:
    return [
        _Customer(
            customer_id=row.customer_id,
            full_name=f"{row.first_name} {row.last_name}",
        )
        for row in customers
    ]


class _TinyPipeline(Pipeline):
    raw: Extract[_RawCustomer] = Extract(asset="raw")
    normalized = _Normalize.step(customers=raw)
    out: Load[_Customer] = Load(input=normalized.result, asset="out")


def assert_scheduler_plugin_info(scheduler: ExecutionScheduler) -> None:
    """Assert a scheduler plugin advertises direct-execution protocol metadata."""
    info = scheduler.info
    assert info.scheduler_protocol == SCHEDULER_PROTOCOL
    assert info.direct_execution is True
    assert info.external_compilation is False
    assert info.name
    assert info.version


def run_scheduler_conformance_suite(
    scheduler: ExecutionScheduler,
) -> dict[str, Any]:
    """Minimal public suite shared by LocalScheduler and plugin schedulers."""
    import anyio

    assert_scheduler_plugin_info(scheduler)
    profile = Profile(name="scheduler-conformance")
    plan = plan_pipeline(
        _TinyPipeline,
        context=PlanningContext.create(profile=profile),
    )
    request = RunRequest()
    context = SchedulingContext(
        pipeline_id=plan.pipeline_id,
        plan_id=plan.plan_id,
        profile_name=profile.name,
    )
    support = scheduler.analyze(plan, request=request, context=context)
    assert support.supported, support.findings

    bad = scheduler.analyze(
        plan,
        request=RunRequest(metadata={"concurrency": 0}),
        context=context,
    )
    assert bad.supported is False
    assert any(f.code == "PMSCHED102" for f in bad.findings)

    async def _execute(sched: ExecutionScheduler, runtime: PipelineRuntime) -> Any:
        return await sched.execute(
            plan,
            request=request,
            runtime=runtime,
            pipeline_cls=_TinyPipeline,
            context=context,
        )

    runtime = PipelineRuntime()
    runtime.memory.seed(
        "raw",
        [_RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace")],
    )
    report = anyio.run(_execute, scheduler, runtime)
    assert report.status is RunStatus.SUCCEEDED
    assert report.metadata.get("etlantic.scheduler") == scheduler.info.name
    assert report.metadata.get("etlantic.scheduler_protocol") == SCHEDULER_PROTOCOL
    meta = str(report.metadata or {})
    assert meta == redact_message(meta)
    assert runtime.memory.get("out")

    local_runtime = PipelineRuntime()
    local_runtime.memory.seed(
        "raw",
        [_RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace")],
    )
    local_report = anyio.run(_execute, LocalScheduler(), local_runtime)
    assert local_report.status is report.status
    assert [row.model_dump() for row in local_runtime.memory.get("out")] == [
        row.model_dump() for row in runtime.memory.get("out")
    ]
    return {
        "scheduler": scheduler.info.name,
        "status": report.status.value,
        "outputs": [row.model_dump() for row in runtime.memory.get("out")],
    }
