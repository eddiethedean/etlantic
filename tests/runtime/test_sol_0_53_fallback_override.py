"""Protected FINAL-004 target/engine distinction for opted-in fallback plans."""

from __future__ import annotations

import anyio

from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.plan import PipelinePlan, plan_pipeline
from etlantic.profile import PlacementTarget
from etlantic.runtime.request import RunRequest
from etlantic.runtime.scheduler import LocalScheduler
from tests.plan.test_adaptive_planner_0_52 import adaptive_profile
from tests.runtime.test_sol_0_53_explicit_override import (
    ExplicitOverridePipeline,
    OverrideRow,
)


def test_final_004_fallback_preserves_resolved_request_target() -> None:
    profile = adaptive_profile(
        placement_targets={"qualified": PlacementTarget(engine="local")},
        eligible_targets=("qualified",),
        adaptive_fallback="explicit",
        portable_transform_policy="prefer",
    )
    request = RunRequest(implementation_overrides={"step": "qualified"})
    plan = plan_pipeline(ExplicitOverridePipeline, profile=profile, request=request)
    assert isinstance(plan, PipelinePlan)
    assert plan.schema == "etlantic.plan/1"
    assert plan.metadata["etlantic.adaptive_fallback"]["chosen_target"] == "qualified"
    assert plan.implementations["step"].engine == "local"

    async def run() -> None:
        runtime = PipelineRuntime()
        runtime.memory.seed("explicit-override-input", [OverrideRow(id=0)])
        report = await LocalScheduler().execute(
            plan,
            request=request,
            runtime=runtime,
            pipeline_cls=ExplicitOverridePipeline,
        )
        assert report.status.value == "succeeded"
        assert [row.id for row in runtime.memory.get("explicit-override-output")] == [1]

    anyio.run(run)
