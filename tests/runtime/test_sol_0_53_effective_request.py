"""Protected FINAL-004 contracts for effective adaptive request precedence.

The binding-only remediation must also preserve the approved parameter and
implementation override boundary before validation and placement.
"""

from __future__ import annotations

import anyio
import pytest

from etlantic import Extract, Input, Load, Output, Parameter, Pipeline, Transformation
from etlantic.exceptions import PipelineValidationError
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.plan import AdaptivePipelinePlan, plan_pipeline
from etlantic.profile import PlacementTarget
from etlantic.runtime.execute import arun_pipeline
from etlantic.runtime.request import RunRequest
from etlantic.transform import functions as F
from tests.plan.test_adaptive_planner_0_52 import Sample, adaptive_profile
from tests.runtime.test_adaptive_execution_0_53 import CrossRow


class RequestedFilter(Transformation):
    source: Input[CrossRow]
    minimum_id: Parameter[int]
    result: Output[CrossRow]


@RequestedFilter.portable
def requested_filter(source, minimum_id):
    return source.filter(F.col("id") >= minimum_id).select("id")


class ParameterRequestPipeline(Pipeline):
    raw: Extract[CrossRow] = Extract(asset="cross-rows")
    step = RequestedFilter.step(source=raw)
    out: Load[CrossRow] = Load(input=step.result, asset="cross-out")


def test_final_004_request_implementation_override_precedes_profile() -> None:
    profile = adaptive_profile(
        placement_targets={
            "first": PlacementTarget(engine="local", location="primary"),
            "second": PlacementTarget(engine="local", location="alternate"),
        },
        eligible_targets=("first", "second"),
        implementation_overrides={"raw": "first", "out": "first"},
    )
    plan = plan_pipeline(
        Sample,
        profile=profile,
        request=RunRequest(implementation_overrides={"raw": "second", "out": "second"}),
    )
    assert isinstance(plan, AdaptivePipelinePlan)
    assert {decision.node_name: decision.target_id for decision in plan.decisions} == {
        "raw": "second",
        "out": "second",
    }


def test_final_004_unknown_request_implementation_override_rejects() -> None:
    with pytest.raises(PipelineValidationError) as error:
        plan_pipeline(
            Sample,
            profile=adaptive_profile(),
            request=RunRequest(implementation_overrides={"out": "unqualified"}),
        )
    assert error.value.report is not None
    assert "PMADP121" in error.value.report.codes()


def test_final_004_required_parameter_override_precedes_validation() -> None:
    async def run() -> None:
        runtime = PipelineRuntime()
        runtime.memory.seed("cross-rows", [{"id": 1}, {"id": 2}, {"id": 3}])
        report = await arun_pipeline(
            ParameterRequestPipeline,
            profile=adaptive_profile(),
            runtime=runtime,
            request=RunRequest(parameter_overrides={"step": {"minimum_id": 2}}),
        )
        assert report.status.value == "succeeded"
        assert [row.id for row in runtime.memory.get("cross-out")] == [2, 3]

    anyio.run(run)
