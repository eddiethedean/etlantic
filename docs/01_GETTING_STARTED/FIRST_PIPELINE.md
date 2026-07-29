# Your First Pipeline

> **Status: Available in ETLantic 0.34.0.** Extends the project from
> [Quickstart](QUICKSTART.md). Local Python + JSON assets only.

!!! tip "PyPI vs clone"
    This page is **PyPI-only**. No repository checkout required.

## Start from the init project

```bash
python -m pip install 'etlantic==0.34.0'
mkdir my-pipeline && cd my-pipeline
python -m etlantic init --with-toml
```

(`init` needs an empty directory, or pass `--force`.)

Open `pipeline.py`: typed `Row`, local `Identity`, and `SamplePipeline`
(Extract → step → Load). Asset names bind in `profiles/development.json`.

## Validate, plan, and run

```bash
python -m etlantic inspect pipeline.py:SamplePipeline --format json
python -m etlantic validate pipeline.py:SamplePipeline --profile development --format json
python -m etlantic plan pipeline.py:SamplePipeline --profile development --format json
python -m etlantic run pipeline.py:SamplePipeline --profile development
```

Expected: `succeeded` and `data/out.json` mirroring Ada/Grace (identity).

If you have not yet seen validate-before-write fail, do the
[Quickstart required aha](QUICKSTART.md#required-aha), then restore
`Load[Row]` before continuing.

## Evolve the transform

Replace the passthrough with a reshape (upper-case names):

```python
from etlantic import Data, Extract, Input, Load, Output, Pipeline, Transformation


class Row(Data):
    id: int
    name: str


class NamedRow(Data):
    id: int
    name: str


class UpperName(Transformation):
    rows: Input[Row]
    result: Output[NamedRow]


@UpperName.implementation("local")
def upper_name(rows: list[Row]) -> list[NamedRow]:
    return [NamedRow(id=row.id, name=row.name.upper()) for row in rows]


class SamplePipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    step = UpperName.step(rows=raw)
    out: Load[NamedRow] = Load(input=step.result, asset="out")
```

Re-run validate → plan → run. `data/out.json` should show `"ADA"` / `"GRACE"`.

## Next

- [Engine selection](ENGINE_SELECTION.md) — Local → Polars
- [SDK 10-minute tutorial](SDK_10_MINUTES.md) — `import etlantic as etl`
- Contracts / fingerprints: [ODCS](../03_DATA_CONTRACTS/ODCS.md),
  [Plan and runtime API](../10_REFERENCE/API_PLAN_RUNTIME.md)
- Production profile starter:
  [Capabilities → CI starter](CAPABILITIES.md#ci-starter)
