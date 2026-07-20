# Your First Pipeline

> **Status: Available in ETLantic 0.21.0.** This tutorial uses the local
> Python runtime and in-memory storage. It does not require a dataframe or SQL
> plugin.

This tutorial explains the pieces of the runnable quickstart and shows how to
inspect the artifacts ETLantic creates.

Install the published release with Python 3.11+:

```bash
python -m pip install 'etlantic==0.21.0'
```

## Define data contracts

```python
from etlantic import Data


class RawCustomer(Data):
    customer_id: int
    first_name: str
    last_name: str


class Customer(Data):
    customer_id: int
    full_name: str
```

These models validate records and provide the source for generated ODCS
artifacts.

## Define a transformation contract

```python
from etlantic import Input, Output, Transformation


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]
```

The class states what the transformation consumes and produces. It does not
execute anything by itself.

## Register local executable code

```python
@NormalizeCustomers.implementation("local")
def normalize_customers(customers: list[RawCustomer]) -> list[Customer]:
    return [
        Customer(
            customer_id=row.customer_id,
            full_name=f"{row.first_name} {row.last_name}",
        )
        for row in customers
    ]
```

The engine name must match an implementation the selected profile can use.
The built-in development profile selects local Python implementations.

## Connect the pipeline

```python
from etlantic import Extract, Load, Pipeline


class CustomerPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[Customer] = Load(
        input=normalized.result,
        asset="customer_sink",
    )
```

Bindings are logical names. At runtime, a storage provider resolves each name.

## Validate and inspect

```python
report = CustomerPipeline.validate(profile="development")
report.raise_for_errors()

graph = CustomerPipeline.inspect()
print(CustomerPipeline.to_mermaid())
```

Validation returns structured diagnostics. Inspection and Mermaid generation
do not execute transformation code.

### Try an intentional wiring error

In `CustomerPipeline`, change exactly this annotation:

```python
# before
curated: Load[Customer] = Load(

# intentionally broken
curated: Load[RawCustomer] = Load(
```

Then validate. ETLantic rejects the graph before it reads any data:

```bash
etlantic validate pipeline.py:CustomerPipeline --profile development
```

```text
PMPIPE210: The step "curated" expects RawCustomer on "input", but received Customer from "normalized.result".
```

Restore `Load[Customer]` before continuing.

### Inspect, validate, and plan from the CLI

With the complete quickstart saved as `pipeline.py`, run:

```bash
etlantic inspect pipeline.py:CustomerPipeline --format json
etlantic validate pipeline.py:CustomerPipeline --profile development --format json
etlantic plan pipeline.py:CustomerPipeline --profile development --format json
```

!!! warning "CLI process boundaries"
    These commands import definitions but do not inherit in-memory records
    seeded by a different Python process. Prefer the same `--profile` for
    validate, plan, and run (`development` here). If you omit `--profile`,
    `etlantic plan` defaults to `local` while `etlantic run` defaults to
    `development`.

## Generate portable contracts

```python
CustomerPipeline.write_contracts("contracts/")
```

This writes ODCS, DTCS, and DPCS artifacts derived from the same definitions.
Generated filenames are deterministic; inspect the returned `ContractBundle`
instead of depending on hand-written filename assumptions.

## Plan

```python
plan = CustomerPipeline.plan(profile="development")
print(plan.plan_id, plan.fingerprint)
print(CustomerPipeline.explain_plan(profile="development"))
```

Planning resolves implementations, bindings, capabilities, and execution
regions without reading data or resolving secret values.

## Run

```python
from etlantic import PipelineRuntime

runtime = PipelineRuntime()
runtime.memory.seed(
    "customer_source",
    [RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace")],
)

run_report = CustomerPipeline.run(
    profile="development",
    runtime=runtime,
)
print(run_report.status.value)

customers = runtime.memory.get("customer_sink")
print(customers[0].full_name)
```

Expected output:

```text
succeeded
Ada Lovelace
```

Use `await CustomerPipeline.arun(...)` when calling ETLantic from an existing
async application.

## Current boundary

This tutorial stays on the local Python runtime with memory, callable, JSON,
CSV, and no-write storage. Optional plugins are available today:

- Polars / Pandas — `etlantic-polars` / `etlantic-pandas`
- SQL — `etlantic-sql`
- PySpark batch — `etlantic-pyspark`
- Airflow compile — `etlantic-airflow`
- Prefect direct execution — `etlantic-prefect` (`ExecutionScheduler`, local MVP)
- SparkForge adapter — `etlantic-sparkforge`

Prefect direct execution shipped in 0.17; Prefect deployment/serve, Dagster
compilers, and managed cloud Spark providers remain outside the shipped
boundary. Keep core and optional plugin minors matched—for this guide, pin
both to `0.20.0`. See [Capabilities](CAPABILITIES.md).

Continue with [Engine selection](ENGINE_SELECTION.md), or continue diligence
with [Capabilities](CAPABILITIES.md). For a production profile starter, copy the
JSON from [Production profile starter](prod.example.json) (or the embedded block
in [Capabilities](CAPABILITIES.md#ci-starter)) into your own
`profiles/prod.json`—that file is **not** installed with the PyPI package.
From a git checkout, the companion script is
[`examples/quickstart.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/quickstart.py).
