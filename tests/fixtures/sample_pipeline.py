"""Sample pipeline fixture for CLI tests."""

from etlantic import Data, Extract, Input, Load, Output, Pipeline, Transformation


class Row(Data):
    id: int


class Identity(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Identity.implementation("local")
def identity_local(rows: list[Row]) -> list[Row]:
    return list(rows)


class SamplePipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    step = Identity.step(rows=raw)
    out: Load[Row] = Load(input=step.result, asset="out")
