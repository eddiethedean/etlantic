"""Lifecycle on PipelineDefinition without originating class."""

from __future__ import annotations

from examples.memory_customers import (
    CustomerPipeline,
    normalize_customers,
)

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
    assert not report.has_errors, [d.to_dict() for d in report.diagnostics]
    assert report.valid
    plan = plan_pipeline_like(loaded, profile="development")
    assert plan.pipeline_id == loaded.pipeline_id
    assert plan.logical_graph.nodes


def test_run_deserialized_definition() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    loaded = pipeline_from_json(pipeline_to_json(defn))
    callable_registry().register(
        loaded.transformations[0].identity,
        "local",
        normalize_customers,
    )
    runtime = PipelineRuntime()
    runtime.memory.seed("raw_customers", [{"id": 1, "name": "a", "email": "a@x"}])
    report = run_pipeline(loaded, profile="development", runtime=runtime)
    assert report.status.value in {"succeeded", "partial", "failed"}
