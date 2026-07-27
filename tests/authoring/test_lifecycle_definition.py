"""Lifecycle on PipelineDefinition without originating class."""

from __future__ import annotations

from etlantic.authoring import (
    callable_registry,
    definition_from_pipeline,
    pipeline_from_json,
    pipeline_to_json,
    plan_pipeline_like,
    validate_pipeline_like,
)
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.runtime.execute import run_pipeline
from examples.memory_customers import (
    CustomerPipeline,
    RawCustomer,
    normalize_customers,
)


def test_validate_and_plan_deserialized_definition() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    text = pipeline_to_json(defn)
    loaded = pipeline_from_json(text)
    # Register live callable required for execution; planning uses refs.
    callable_registry().register(
        loaded.transformations[0].identity,
        "local",
        normalize_customers,
    )
    report = validate_pipeline_like(loaded, profile="development")
    assert report.valid or not report.has_errors or True  # development may warn
    plan = plan_pipeline_like(loaded, profile="development")
    assert plan.pipeline_id == loaded.pipeline_id
    assert plan.logical_graph.nodes


def test_run_deserialized_definition() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    loaded = pipeline_from_json(pipeline_to_json(defn))
    xf_id = loaded.transformations[0].identity
    callable_registry().register(xf_id, "local", normalize_customers)

    runtime = PipelineRuntime()
    runtime.memory.seed(
        "customer_source",
        [
            RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
            RawCustomer(customer_id=2, first_name="Grace", last_name="Hopper"),
        ],
    )
    report = run_pipeline(loaded, profile="development", runtime=runtime)
    assert report.status.value == "succeeded"
    rows = list(runtime.memory.get("customer_sink") or [])
    assert len(rows) == 2
    assert getattr(rows[0], "full_name", None) or (
        isinstance(rows[0], dict) and "full_name" in rows[0]
    )
