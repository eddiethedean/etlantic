# Your First Pipeline

> **Status: Available in ETLantic 0.28.0.** This tutorial extends the project
> created by [Quickstart](QUICKSTART.md) (`python -m etlantic init`). It uses the local
> Python runtime and JSON asset bindings—no dataframe or SQL plugin required.

## Start from the init project

If you have not already (`init` needs an **empty directory**, or pass
`--force`):

```bash
python -m pip install 'etlantic==0.28.0'
mkdir my-pipeline && cd my-pipeline
python -m etlantic init --with-toml
```

Open `pipeline.py`. The scaffold defines a typed `Row` contract, an `Identity`
transformation, and `SamplePipeline` wired as Extract → step → Load.

## Walk the generated pieces

### Data contract

```python
class Row(Data):
    id: int
    name: str
```

Records must match this shape when read from `json://data/sample.json` and when
written to `json://data/out.json`.

### Transformation contract and local implementation

```python
class Identity(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Identity.implementation("local")
def identity_local(rows: list[Row]) -> list[Row]:
    return list(rows)
```

The class states what the transformation consumes and produces. The
`@implementation("local")` function is the executable body for the development
profile.

### Pipeline wiring

```python
class SamplePipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    step = Identity.step(rows=raw)
    out: Load[Row] = Load(input=step.result, asset="out")
```

Asset names (`rows`, `out`) are logical. `profiles/development.json` binds them
to JSON paths.

## Validate, plan, and run (CLI)

Targets use `path.py:ClassName` (here `pipeline.py:SamplePipeline`). See
[CLI — Pipeline targets](../10_REFERENCE/CLI.md).

```bash
python -m etlantic inspect pipeline.py:SamplePipeline --format json
python -m etlantic validate pipeline.py:SamplePipeline --profile development --format json
python -m etlantic plan pipeline.py:SamplePipeline --profile development --format json
python -m etlantic run pipeline.py:SamplePipeline --profile development
```

Prefer the same `--profile` for validate, plan, and run. If you omit
`--profile`, the CLI defaults to `development` (or your project's
`default_profile`).

Expected run status: `succeeded`. `data/out.json` should mirror the sample
rows (identity transform).

## Try an intentional wiring error

Add a second contract and change **only** the Load annotation so the graph
wiring is inconsistent (keep `input=` and `asset=` complete so the file still
parses):

```python
class Other(Data):
    id: int
    name: str


class SamplePipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    step = Identity.step(rows=raw)
    # Broken: Load expects Other but upstream step.result is still Row
    out: Load[Other] = Load(input=step.result, asset="out")
```

Then validate. ETLantic rejects the graph before it reads any data:

```bash
python -m etlantic validate pipeline.py:SamplePipeline --profile development
```

```text
PMPIPE210: The step "out" expects Other on "input", but received Row from "step.result".
```

Restore `out: Load[Row] = Load(input=step.result, asset="out")` (and remove
`Other` if unused) before continuing.

## Evolve the transform

Replace `Identity` with a real reshape so the tutorial teaches more than a
passthrough. Example: upper-case names.

```python
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

## Generate portable contracts

```python
from pipeline import SamplePipeline

SamplePipeline.write_contracts("contracts/")
```

This writes ODCS, DTCS, and DPCS artifacts derived from the same definitions.

## Plan from Python

```python
from pipeline import SamplePipeline

plan = SamplePipeline.plan(profile="development")
print(plan.plan_id, plan.fingerprint)
print(SamplePipeline.explain_plan(profile="development"))
```

Planning resolves implementations, bindings, capabilities, and execution
regions without reading data or resolving secret values.

## Current boundary

This tutorial stays on the local Python runtime with memory, callable, JSON,
CSV, and no-write storage. Optional plugins are available today:

- Polars / Pandas — `etlantic-polars` / `etlantic-pandas`
- SQL — `etlantic-sql`
- PySpark batch — `etlantic-pyspark`
- Airflow compile — `etlantic-airflow`
- Prefect direct execution — `etlantic-prefect`
- Medallantic migration adapter — `medallantic`

Keep core and optional plugin minors matched—for this guide, pin both to
`0.28.0`. See [Capabilities](CAPABILITIES.md).

Continue with [Engine selection](ENGINE_SELECTION.md). For a production profile
starter, copy the JSON from
[Production profile starter](prod.example.json) (or the embedded block in
[Capabilities](CAPABILITIES.md#ci-starter)) into your own `profiles/prod.json`.
