"""Core orchestration protocol tests (no Airflow required)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from etlantic import (
    ORCHESTRATION_PROTOCOL_VERSION,
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
    Profile,
    Transformation,
    compile_plan,
    plan_pipeline,
)
from etlantic.orchestration import (
    ArtifactTransportPolicy,
    CompilationContext,
    ExecutionIntent,
    OrchestrationCompilationError,
    ScheduleIntent,
    TaskRetryPolicy,
    comparable_report_shape,
    correlate_poll_to_report,
    map_plan_to_tasks,
    resolve_task_retry,
    validate_artifact_for_transport,
    xcom_safe_payload,
)
from etlantic.orchestration.lifecycle import (
    CorrelationKeys,
    PollResult,
    SubmissionStatus,
)
from etlantic.plan.artifacts import ArtifactRef, ArtifactStrategy
from etlantic.registry import PlanningContext
from etlantic.reports.model import (
    PipelineRunReport,
    RunSummary,
    StepRunReport,
)
from etlantic.runtime.request import RunIntent
from etlantic.runtime.state import RunStatus, StepStatus


def test_orchestration_protocol_constant() -> None:
    assert ORCHESTRATION_PROTOCOL_VERSION == "etlantic.orchestration/1"


def test_artifact_transport_rejects_in_memory() -> None:
    ref = ArtifactRef(
        identity="artifact:x",
        logical_output="n.out",
        strategy=ArtifactStrategy.IN_MEMORY,
    )
    diags = validate_artifact_for_transport(ref)
    assert any(d.code == "PMORCH340" for d in diags)
    payload = xcom_safe_payload(ref)
    assert payload["transport"] == "artifact_ref"
    assert "password" not in str(payload).lower()


def test_artifact_size_policy() -> None:
    ref = ArtifactRef(
        identity="artifact:big",
        logical_output="n.out",
        strategy=ArtifactStrategy.LAZY,
    )
    policy = ArtifactTransportPolicy(require_durable_above=100)
    diags = validate_artifact_for_transport(ref, estimated_bytes=10_000, policy=policy)
    assert any(d.code == "PMORCH341" for d in diags)


class RawCustomer(Data):
    customer_id: int
    first_name: str
    last_name: str


class Customer(Data):
    customer_id: int
    full_name: str


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]


@NormalizeCustomers.implementation("local")
def normalize_local(customers):
    return [
        Customer(
            customer_id=c.customer_id,
            full_name=f"{c.first_name} {c.last_name}",
        )
        for c in customers
    ]


class CustomerOrchPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[Customer] = Load(input=normalized.result, asset="customer_sink")


def _plan():
    runtime = PipelineRuntime()
    profile = Profile(name="orch-plan", orchestrator="local")
    return plan_pipeline(
        CustomerOrchPipeline,
        context=PlanningContext.create(profile, registry=runtime.registry),
    )


def test_map_plan_to_tasks_preserves_dependencies() -> None:
    plan = _plan()
    ctx = CompilationContext(target="airflow")
    tasks, deps, diags = map_plan_to_tasks(plan, context=ctx)
    names = {t.task_id for t in tasks}
    assert "raw" in names and "normalized" in names and "curated" in names
    assert "raw" in deps["normalized"]
    assert "normalized" in deps["curated"]
    # Secret-like metadata must never slip through; transport errors are explicit.
    assert not any(d.code == "PMORCH342" for d in diags)
    assert not any(getattr(d, "severity", None) == "error" for d in diags)


def test_artifact_metadata_secret_like_fails_closed() -> None:
    ref = ArtifactRef(
        identity="artifact:x",
        logical_output="n.out",
        strategy=ArtifactStrategy.DURABLE,
        metadata={"password": "hunter2"},
    )
    diags = validate_artifact_for_transport(ref)
    assert any(d.code == "PMORCH342" for d in diags)


def test_retry_safety_rejects_unsafe_sink() -> None:
    plan = _plan()
    plan_intents = dict(plan.intents)
    plan_intents["retry_safety"] = {
        "curated": {"subject_id": "curated", "safe": False},
    }
    # PipelinePlan is frozen — rebuild via from_dict
    data = plan.to_dict()
    data["intents"] = plan_intents
    from etlantic.plan.model import PipelinePlan

    unsafe_plan = PipelinePlan.from_dict(data)
    retries, policy, diags = resolve_task_retry(
        node_name="curated",
        node_kind="sink",
        plan=unsafe_plan,
        execution=ExecutionIntent(retries=3),
    )
    assert retries == 0
    assert policy is TaskRetryPolicy.UNSAFE_REJECTED
    assert any(d.code == "PMORCH310" for d in diags)


def test_compile_missing_plugin_fails_closed() -> None:
    plan = _plan()
    with pytest.raises(OrchestrationCompilationError) as exc:
        compile_plan(plan, target="airflow", plugins={})
    assert exc.value.code == "PMORCH300"


def test_report_correlation_shape() -> None:
    now = datetime.now(UTC)
    report = PipelineRunReport(
        pipeline_id="pipe",
        plan_id="plan",
        run_id="run-1",
        intent=RunIntent.STANDARD,
        profile="local",
        status=RunStatus.SUCCEEDED,
        started_at=now,
        summary=RunSummary(total_steps=1, succeeded=1),
        steps=(
            StepRunReport(
                step_id="s1",
                step_name="normalized",
                status=StepStatus.SUCCEEDED,
            ),
        ),
        plan_fingerprint="fp",
    )
    poll = PollResult(
        correlation=CorrelationKeys(
            run_id="run-1",
            plan_id="plan",
            pipeline_id="pipe",
            dag_id="customerorchpipeline",
            backend_run_id="airflow-run-9",
        ),
        status=SubmissionStatus.SUCCEEDED,
        task_states={"normalized": "success"},
        message="ok",
    )
    correlated = correlate_poll_to_report(report, poll)
    assert correlated.backend_runs
    assert correlated.backend_runs[0].backend == "airflow"
    shape = comparable_report_shape(correlated)
    assert shape["step_names"] == ["normalized"]
    assert shape["status"] == "succeeded"


def test_schedule_intent_from_profile() -> None:
    profile = Profile(
        name="sched",
        orchestrator="airflow",
        schedule={
            "type": "cron",
            "expression": "0 2 * * *",
            "timezone": "UTC",
            "catchup": False,
        },
        execution={"retries": 2, "timeout_seconds": 3600},
    )
    assert ScheduleIntent.from_mapping(profile.schedule).expression == "0 2 * * *"
    assert ExecutionIntent.from_mapping(profile.execution).retries == 2
