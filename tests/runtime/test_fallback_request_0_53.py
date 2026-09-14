"""Implementation-side regression for stored fallback target/engine collisions."""

from __future__ import annotations

import anyio

from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.plan import PipelinePlan, plan_from_json, plan_pipeline, plan_to_json
from etlantic.profile import PlacementTarget
from etlantic.runtime.orchestrator import LocalOrchestrator
from etlantic.runtime.request import RunRequest
from tests.plan.test_adaptive_planner_0_52 import adaptive_profile
from tests.runtime.test_sol_0_53_explicit_override import (
    ExplicitOverridePipeline,
    OverrideRow,
)


def test_stored_fallback_target_named_as_another_engine_keeps_planned_engine() -> None:
    # "null" is also a real implementation engine. Interpreting this target ID
    # as an engine silently runs the wrong body instead of producing an error.
    request = RunRequest(implementation_overrides={"step": "null"})
    generated = plan_pipeline(
        ExplicitOverridePipeline,
        profile=adaptive_profile(
            placement_targets={"null": PlacementTarget(engine="local")},
            eligible_targets=("null",),
            adaptive_fallback="explicit",
            portable_transform_policy="prefer",
        ),
        request=request,
    )
    stored = plan_from_json(plan_to_json(generated))
    assert isinstance(stored, PipelinePlan)
    assert stored.implementations["step"].engine == "local"
    assert stored.metadata["etlantic.adaptive_fallback"]["chosen_target"] == "null"

    async def run() -> None:
        runtime = PipelineRuntime()
        runtime.memory.seed("explicit-override-input", [OverrideRow(id=0)])
        host = LocalOrchestrator(
            runtime=runtime,
            plan=stored,
            request=request,
            pipeline_cls=ExplicitOverridePipeline,
        )
        report = await host.execute()
        assert report.status.value == "succeeded"
        assert [row.id for row in runtime.memory.get("explicit-override-output")] == [1]
        assert host.request is request
        assert request.implementation_overrides == {"step": "null"}

    anyio.run(run)
