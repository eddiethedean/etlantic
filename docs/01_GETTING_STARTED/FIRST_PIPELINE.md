# Your First Pipeline

> **Status: Available in ETLantic 0.52.0 (published Beta).** Extends the project from
> [Quickstart](QUICKSTART.md). Local Python + JSON assets only.

!!! tip "PyPI vs clone"
    This page is **PyPI-only**. No repository checkout required.

## Start from the init project

If you already finished [Quickstart](QUICKSTART.md), reuse that project
directory—do not reinstall. Otherwise install from PyPI, then scaffold:

```bash
# Only if you do not already have a Quickstart project:
python -m pip install 'etlantic==0.52.0'
mkdir my-pipeline && cd my-pipeline
python -m etlantic init --with-toml
```

(`init` needs an empty directory, or pass `--force`.)

Open `pipeline.py`: typed `Row`, portable `Identity`, and `SamplePipeline`
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
import etlantic as etl
from etlantic.transform import functions as F


class Row(etl.Data):
    id: int
    name: str


class NamedRow(etl.Data):
    """Output contract: same fields as Row, but a distinct type so validate
    and plan treat input vs published shape as separate contracts."""

    id: int
    name: str


class UpperName(etl.Transformation):
    rows: etl.Input[Row]
    result: etl.Output[NamedRow]


@UpperName.portable
def upper_name(rows):
    return rows.select("id", F.upper(F.col("name")).alias("name"))


class SamplePipeline(etl.Pipeline):
    raw: etl.Extract[Row] = etl.Extract(asset="rows")
    step = UpperName.step(rows=raw)
    out: etl.Load[NamedRow] = etl.Load(input=step.result, asset="out")
```

The lesson is **named contracts at each boundary**, not a schema change: `Row`
is what you extract; `NamedRow` is what you publish (here with upper-cased
`name`). The body uses ETLantic expressions rather than a local dataframe API;
the selected engine compiles it. Re-run validate → plan → run.
`data/out.json` should show `"ADA"` / `"GRACE"`.

## Next

- [Engine selection](ENGINE_SELECTION.md) — Local → Polars
- [SDK 10-minute tutorial](SDK_10_MINUTES.md) — after Ada/Grace (secondary)
- Contracts / fingerprints: [ODCS](../03_DATA_CONTRACTS/ODCS.md),
  [Plan and runtime API](../10_REFERENCE/API_PLAN_RUNTIME.md)
- Production profile starter:
  [Capabilities → CI starter](CAPABILITIES.md#ci-starter)
