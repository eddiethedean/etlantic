"""Private LocalScheduler conformance corpus (0.15 companion)."""

from __future__ import annotations

from etlantic import Extract, Input, Load, Output, Pipeline, Transformation
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.plan.planner import plan_pipeline
from etlantic.profile import Profile
from etlantic.registry import PlanningContext
from etlantic.runtime.request import RunRequest
from etlantic.runtime.scheduler import (
    SCHEDULER_PROTOCOL,
    LocalScheduler,
    SchedulingContext,
)
from etlantic.runtime.state import RunStatus
from tests.conftest import Customer, RawCustomer


class Normalize(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]


@Normalize.implementation("local")
def _normalize(customers: list[RawCustomer]) -> list[Customer]:
    return [
        Customer(
            customer_id=row.customer_id,
            full_name=f"{row.first_name} {row.last_name}",
        )
        for row in customers
    ]


class TinyPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="raw")
    normalized = Normalize.step(customers=raw)
    out: Load[Customer] = Load(input=normalized.result, asset="out")


def test_local_scheduler_analyze_accepts_plan() -> None:
    plan = plan_pipeline(
        TinyPipeline,
        context=PlanningContext.create(profile=Profile(name="sched")),
    )
    report = LocalScheduler().analyze(
        plan,
        request=RunRequest(),
        context=SchedulingContext(profile_name="sched"),
    )
    assert report.supported
    assert report.findings == ()


def test_local_scheduler_execute_preserves_run_semantics() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed(
        "raw",
        [RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace")],
    )
    report = TinyPipeline.run(profile="development", runtime=runtime)
    assert report.status is RunStatus.SUCCEEDED
    assert report.metadata.get("etlantic.scheduler") == "local"
    assert report.metadata.get("etlantic.scheduler_protocol") == SCHEDULER_PROTOCOL
    assert runtime.memory.get("out")


def test_local_scheduler_rejects_invalid_concurrency() -> None:
    plan = plan_pipeline(
        TinyPipeline,
        context=PlanningContext.create(profile=Profile(name="sched")),
    )
    request = RunRequest(metadata={"concurrency": 0})
    report = LocalScheduler().analyze(
        plan,
        request=request,
        context=SchedulingContext(),
    )
    assert report.supported is False
    assert any(f.code == "PMSCHED102" for f in report.findings)
