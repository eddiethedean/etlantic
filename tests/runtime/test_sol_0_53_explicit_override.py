# pyright: reportMissingParameterType=false, reportUnknownParameterType=false
"""Protected FINAL-004 compatibility contract for explicit request overrides."""

from __future__ import annotations

import anyio

from etlantic import Data, Extract, Input, Load, Output, Pipeline, Transformation
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.profile import Profile
from etlantic.runtime.execute import arun_pipeline
from etlantic.runtime.request import RunRequest


class OverrideRow(Data):
    id: int


class OverrideStep(Transformation):
    rows: Input[OverrideRow]
    result: Output[OverrideRow]


@OverrideStep.implementation("local")
def local_rows(rows):
    return [OverrideRow(id=1)]


@OverrideStep.implementation("null")
def alternate_rows(rows):
    return [OverrideRow(id=2)]


class ExplicitOverridePipeline(Pipeline):
    raw: Extract[OverrideRow] = Extract(asset="explicit-override-input")
    step = OverrideStep.step(rows=raw)
    out: Load[OverrideRow] = Load(input=step.result, asset="explicit-override-output")


def test_final_004_explicit_native_request_override_still_selects_implementation() -> (
    None
):
    async def run() -> None:
        runtime = PipelineRuntime()
        runtime.memory.seed("explicit-override-input", [OverrideRow(id=0)])
        report = await arun_pipeline(
            ExplicitOverridePipeline,
            profile=Profile(name="explicit-override", dataframe_engine="local"),
            runtime=runtime,
            request=RunRequest(implementation_overrides={"step": "null"}),
        )
        assert report.status.value == "succeeded"
        assert [row.id for row in runtime.memory.get("explicit-override-output")] == [2]

    anyio.run(run)
