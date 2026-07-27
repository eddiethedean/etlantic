"""Hard-fail scheduler abandons unrelated pending steps."""

from __future__ import annotations

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
    RunStatus,
    Transformation,
)


class Row(Data):
    id: int


class Boom(Transformation):
    rows: Input[Row]
    result: Output[Row]


class Ok(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Boom.implementation("local")
def boom_local(rows: list[Row]) -> list[Row]:
    raise RuntimeError("boom")


@Ok.implementation("local")
def ok_local(rows: list[Row]) -> list[Row]:
    return list(rows)


class BranchPipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    boom = Boom.step(rows=raw)
    ok = Ok.step(rows=raw)
    out_boom: Load[Row] = Load(input=boom.result, asset="out_boom")
    out_ok: Load[Row] = Load(input=ok.result, asset="out_ok")


def test_hard_fail_abandons_pending_siblings_and_report_not_succeeded() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1)])
    report = BranchPipeline.run(profile="development", runtime=runtime)
    by_name = {s.step_name: s for s in report.steps}
    assert by_name["boom"].status.value == "failed"
    assert by_name["ok"].status.value == "succeeded"
    assert by_name["out_boom"].status.value == "abandoned"
    assert by_name["out_ok"].status.value in {"abandoned", "succeeded"}
    assert by_name["out_ok"].status.value != "pending"
    assert report.status is not RunStatus.SUCCEEDED


def test_parallel_branch_diagnostics_complete() -> None:
    class CountDiag(Transformation):
        rows: Input[Row]
        result: Output[Row]

    @CountDiag.implementation("local")
    def count_local(rows: list[Row]) -> list[Row]:
        return list(rows)

    class WidePipeline(Pipeline):
        raw: Extract[Row] = Extract(asset="rows")
        a = CountDiag.step(rows=raw)
        b = CountDiag.step(rows=raw)
        c = CountDiag.step(rows=raw)
        d = CountDiag.step(rows=raw)
        out_a: Load[Row] = Load(input=a.result, asset="out_a")
        out_b: Load[Row] = Load(input=b.result, asset="out_b")
        out_c: Load[Row] = Load(input=c.result, asset="out_c")
        out_d: Load[Row] = Load(input=d.result, asset="out_d")

    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1)])
    report = WidePipeline.run(profile="development", runtime=runtime)
    assert report.status is RunStatus.SUCCEEDED
    assert len(report.steps) == 9
    assert all(s.status.value == "succeeded" for s in report.steps)
