# pyright: reportOptionalMemberAccess=false, reportUnknownMemberType=false
"""FINAL-004 implementation regressions for data-only portable authoring."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import anyio
import pytest

from etlantic.authoring import (
    definition_from_pipeline,
    pipeline_from_json,
    pipeline_to_json,
)
from etlantic.exceptions import PipelineValidationError
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.plan import (
    AdaptivePipelinePlan,
    plan_from_json,
    plan_pipeline,
    plan_pipeline_with_report,
    plan_to_json,
)
from etlantic.registry import PlanningContext
from etlantic.runtime.execute import arun_pipeline
from etlantic.runtime.request import RunRequest, RunSelection
from etlantic.runtime.scheduler import LocalScheduler
from tests.plan.test_adaptive_planner_0_52 import adaptive_profile
from tests.runtime.physical.test_qualification_0_53 import Chain, Project, setup
from tests.runtime.test_sol_0_53_effective_request import ParameterRequestPipeline


def _plan(model: Any, reporting: bool, **kwargs: Any) -> AdaptivePipelinePlan:
    if reporting:
        plan, report = plan_pipeline_with_report(model, **kwargs)
        assert not report.has_errors, report.codes()
    else:
        plan = plan_pipeline(model, **kwargs)
    assert isinstance(plan, AdaptivePipelinePlan)
    assert plan.metadata["etlantic.execution"] == "local-static-batch/1"
    return plan


@pytest.mark.parametrize("reporting", [False, True])
@pytest.mark.parametrize("serialized", [False, True])
def test_definition_portable_default_request_and_stored_execution(
    reporting: bool, serialized: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    definition = definition_from_pipeline(Chain)
    if serialized:
        definition = pipeline_from_json(pipeline_to_json(definition))

    def unavailable() -> None:
        raise AssertionError("Definition planning must not ask the live transformation")

    monkeypatch.setattr(Project, "portable_definition", unavailable)
    plan = _plan(definition, reporting, profile=adaptive_profile())

    async def run() -> None:
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 1}, {"id": None}])
        report = await LocalScheduler().execute(
            plan_from_json(plan_to_json(plan)), runtime=runtime, request=RunRequest()
        )
        assert report.status.value == "succeeded"
        assert [row.id for row in runtime.memory.get("out")] == [1, None]
        assert all(step.status.value == "succeeded" for step in report.steps)

    anyio.run(run)


@pytest.mark.parametrize("reporting", [False, True])
def test_definition_request_parameter_survives_both_serialization_boundaries(
    reporting: bool,
) -> None:
    request = RunRequest(parameter_overrides={"step": {"minimum_id": 2}})
    definition = pipeline_from_json(
        pipeline_to_json(definition_from_pipeline(ParameterRequestPipeline))
    )
    plan = _plan(definition, reporting, profile=adaptive_profile(), request=request)

    async def run() -> None:
        runtime = PipelineRuntime()
        runtime.memory.seed("cross-rows", [{"id": 1}, {"id": 2}, {"id": 3}])
        report = await LocalScheduler().execute(
            plan_from_json(plan_to_json(plan)), request=request, runtime=runtime
        )
        assert report.status.value == "succeeded"
        assert [row.id for row in runtime.memory.get("cross-out")] == [2, 3]

    anyio.run(run)


def test_serialized_definition_runs_through_public_sdk() -> None:
    definition = pipeline_from_json(pipeline_to_json(definition_from_pipeline(Chain)))

    async def run() -> None:
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 7}])
        report = await arun_pipeline(
            definition, profile=adaptive_profile(), runtime=runtime
        )
        assert report.status.value == "succeeded"
        assert [row.id for row in runtime.memory.get("out")] == [7]

    anyio.run(run)


@pytest.mark.parametrize(
    "families",
    [
        ("local",),
        pytest.param(("polars",), marks=pytest.mark.polars),
        pytest.param(("pandas",), marks=pytest.mark.pandas),
        pytest.param(
            ("polars", "pandas"), marks=[pytest.mark.polars, pytest.mark.pandas]
        ),
        pytest.param(
            ("pandas", "polars"), marks=[pytest.mark.polars, pytest.mark.pandas]
        ),
    ],
)
@pytest.mark.parametrize("reporting", [False, True])
def test_serialized_definition_matches_class_across_qualified_families(
    families: tuple[str, ...], reporting: bool
) -> None:
    if families == ("local",):
        runtime = PipelineRuntime()
        profile = adaptive_profile()
        context = PlanningContext.create(profile)
        class_plan = _plan(Chain, reporting, context=context)
    else:
        runtime, profile, class_plan = setup(Chain, families, RunRequest())
        context = PlanningContext.create(profile, registry=runtime.registry)
    definition = pipeline_from_json(pipeline_to_json(definition_from_pipeline(Chain)))
    plan = _plan(definition, reporting, context=context, request=RunRequest())
    assert [(d.node_name, d.target_id) for d in plan.decisions] == [
        (d.node_name, d.target_id) for d in class_plan.decisions
    ]
    assert (
        plan.metadata["etlantic.runtime"]["contracts"]
        == class_plan.metadata["etlantic.runtime"]["contracts"]
    )

    async def run() -> None:
        outputs = []
        statuses = []
        for candidate in (class_plan, plan):
            runtime.memory.seed("rows", [{"id": 1}, {"id": None}])
            report = await LocalScheduler().execute(
                plan_from_json(plan_to_json(candidate)),
                request=RunRequest(),
                runtime=runtime,
            )
            assert report.status.value == "succeeded"
            outputs.append([row.id for row in runtime.memory.get("out")])
            statuses.append(
                [(step.step_name, step.status, step.attempts) for step in report.steps]
            )
        assert outputs == [[1, None], [1, None]]
        assert statuses[0] == statuses[1]

    anyio.run(run)


@pytest.mark.parametrize("portable_plan", [None, {"planIdentity": "invalid"}])
def test_definition_missing_or_invalid_portable_ir_cannot_gain_eligibility(
    portable_plan: dict[str, Any] | None,
) -> None:
    definition = definition_from_pipeline(Chain)
    definition = replace(
        definition,
        transformations=tuple(
            replace(transform, portable_plan=portable_plan)
            for transform in definition.transformations
        ),
    )
    with pytest.raises(PipelineValidationError):
        plan_pipeline(definition, profile=adaptive_profile())
    plan, report = plan_pipeline_with_report(definition, profile=adaptive_profile())
    assert plan is None
    assert report.has_errors


@pytest.mark.parametrize("reporting", [False, True])
def test_selected_definition_does_not_resolve_unselected_contracts(
    reporting: bool, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Partial definition plans must load contracts only for selected nodes."""
    marker = tmp_path / "unselected_contract_loaded"
    module = tmp_path / "unselected_contract.py"
    module.write_text(
        "from pathlib import Path\n"
        "from tests.runtime.physical.test_qualification_0_53 import Row\n"
        f"Path({str(marker)!r}).write_text('loaded')\n"
        "raise RuntimeError('unselected contract module initialized')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    payload = definition_from_pipeline(Chain).to_dict()
    unused = dict(payload["nodes"][0])
    unused["name"] = "unused"
    unused["identity"] = "unused"
    unused["asset"] = "unused-rows"
    unused["contract_id"] = "unselected_contract:Row"
    unused["outputs"] = [
        dict(unused["outputs"][0], contract_id="unselected_contract:Row")
    ]
    payload["nodes"].append(unused)
    payload["contracts"].append(
        dict(
            payload["contracts"][0],
            identity="unused-row",
            authoring_id="unselected_contract:Row",
        )
    )
    definition = pipeline_from_json(
        pipeline_to_json(type(definition_from_pipeline(Chain)).from_dict(payload))
    )
    request = RunRequest(selection=RunSelection.until("out"))

    if reporting:
        plan, report = plan_pipeline_with_report(
            definition, profile=adaptive_profile(), request=request
        )
        assert not report.has_errors, report.codes()
    else:
        plan = plan_pipeline(definition, profile=adaptive_profile(), request=request)

    assert tuple(plan.logical_graph.node_names()) == ("raw", "first", "second", "out")
    assert not marker.exists()
