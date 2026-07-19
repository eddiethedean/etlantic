"""Airflow compiler tests (etlantic-airflow; Airflow runtime optional)."""

from __future__ import annotations

import json

import pytest

from etlantic import (
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
from etlantic.orchestration import OrchestrationCompilationError
from etlantic.registry import PlanningContext


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


class CustomerAirflowPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[Customer] = Load(input=normalized.result, asset="customer_sink")


@pytest.fixture
def airflow_plugin():
    pytest.importorskip("etlantic_airflow")
    from etlantic_airflow import create_plugin

    return create_plugin()


@pytest.fixture
def planned(airflow_plugin):
    runtime = PipelineRuntime()
    runtime.register_orchestrator_plugin("airflow", airflow_plugin)
    profile = Profile(
        name="airflow-test",
        orchestrator="airflow",
        schedule={
            "type": "cron",
            "expression": "0 2 * * *",
            "timezone": "UTC",
            "catchup": False,
        },
        execution={"retries": 1, "retry_delay_seconds": 60, "max_active_runs": 1},
    )
    plan = plan_pipeline(
        CustomerAirflowPipeline,
        context=PlanningContext.create(profile, registry=runtime.registry),
    )
    return plan, profile, airflow_plugin, runtime


@pytest.mark.airflow
def test_compile_airflow_dag_deterministic(planned, tmp_path):
    plan, profile, plugin, _runtime = planned
    a1 = compile_plan(plan, target="airflow", profile=profile, plugin=plugin)
    a2 = compile_plan(plan, target="airflow", profile=profile, plugin=plugin)
    assert a1.source == a2.source
    assert a1.dag_id == a2.dag_id
    assert a1.task_ids == {"raw", "normalized", "curated"}
    assert a1.dependencies["normalized"] == ("raw",)
    assert a1.dependencies["curated"] == ("normalized",)
    assert "password" not in a1.source.lower()
    assert "PythonOperator" in a1.source
    assert f'dag_id="{a1.dag_id}"' in a1.source or f"dag_id='{a1.dag_id}'" in a1.source
    path = a1.write(tmp_path / "customer_airflow_pipeline.py")
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "raw >> normalized" in text
    assert "normalized >> curated" in text


@pytest.mark.airflow
def test_plan_compile_method(planned):
    plan, profile, plugin, _ = planned
    artifact = plan.compile(target="airflow", profile=profile, plugin=plugin)
    assert artifact.target == "airflow"
    explained = artifact.explain()
    assert explained["task_count"] == 3


@pytest.mark.airflow
def test_event_schedule_fails_compilation(planned):
    plan, _profile, plugin, _ = planned
    bad = Profile(
        name="event",
        orchestrator="airflow",
        schedule={"type": "event"},
    )
    with pytest.raises(OrchestrationCompilationError) as exc:
        compile_plan(plan, target="airflow", profile=bad, plugin=plugin)
    assert any(d.code == "PMORCH320" for d in exc.value.diagnostics)


@pytest.mark.airflow
def test_unsafe_retries_fail_compilation(planned):
    plan, _profile, plugin, _ = planned
    data = plan.to_dict()
    data["intents"] = {
        **dict(data.get("intents") or {}),
        "retry_safety": {"curated": {"subject_id": "curated", "safe": False}},
    }
    from etlantic.plan.model import PipelinePlan

    unsafe = PipelinePlan.from_dict(data)
    profile = Profile(
        name="unsafe",
        orchestrator="airflow",
        execution={"retries": 3},
    )
    with pytest.raises(OrchestrationCompilationError) as exc:
        compile_plan(unsafe, target="airflow", profile=profile, plugin=plugin)
    assert any(d.code == "PMORCH310" for d in exc.value.diagnostics)


@pytest.mark.airflow
def test_local_run_and_compile_comparable(planned):
    """Local execution and Airflow compile share task/step identities.

    This does **not** prove Airflow workers execute ETLantic engines — see
    ``test_etlantic_step_is_reference_stub``.
    """
    plan, profile, plugin, runtime = planned
    runtime.memory.seed(
        "customer_source",
        [
            RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
            RawCustomer(customer_id=2, first_name="Grace", last_name="Hopper"),
        ],
    )
    local_profile = Profile(name="local-run", orchestrator="local")
    report = CustomerAirflowPipeline.run(profile=local_profile, runtime=runtime)
    assert report.status.value == "succeeded"
    artifact = compile_plan(plan, target="airflow", profile=profile, plugin=plugin)
    # Comparable identities: step names match compiled task ids
    step_names = [s.step_name for s in report.steps]
    assert set(step_names) == artifact.task_ids
    assert report.plan_id == plan.plan_id or report.plan_fingerprint


@pytest.mark.airflow
def test_etlantic_step_is_reference_stub():
    """Characterize the 0.8 reference operator: XCom refs only, no engine run."""
    pytest.importorskip("etlantic_airflow")
    from etlantic_airflow.operator import etlantic_step

    result = etlantic_step(
        plan_id="plan-1",
        pipeline_id="pipe-1",
        node_name="normalized",
        node_kind="step",
        artifact_outputs=[
            {
                "identity": "artifact:default/pipe-1/normalized.result",
                "logical_output": "normalized.result",
                "strategy": "durable",
            }
        ],
    )
    assert result["status"] == "succeeded"
    assert result["transport"] == "artifact_ref"
    assert result["node_name"] == "normalized"
    assert result["xcom"]
    payload = json.dumps(result)
    assert "Ada" not in payload
    assert "password" not in payload.lower()
    # Reference operator always succeeds without inspecting live data.
    empty = etlantic_step(
        plan_id="plan-1",
        pipeline_id="pipe-1",
        node_name="raw",
        node_kind="source",
    )
    assert empty["status"] == "succeeded"
    assert empty["xcom"][0]["transport"] == "artifact_ref"


@pytest.mark.airflow
def test_optional_airflow_import_of_generated_dag(planned, tmp_path):
    plan, profile, plugin, _ = planned
    artifact = compile_plan(plan, target="airflow", profile=profile, plugin=plugin)
    path = artifact.write(tmp_path / "importable_dag.py")
    airflow = pytest.importorskip("airflow")
    _ = airflow
    from etlantic_airflow import load_compiled_pipeline

    dag = load_compiled_pipeline(path)
    assert dag.dag_id == artifact.dag_id
    assert set(dag.task_ids) == artifact.task_ids
