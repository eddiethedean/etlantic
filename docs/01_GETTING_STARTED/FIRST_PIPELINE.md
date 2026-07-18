# Your First Pipeline

> **Status: Available in ETLantic 0.13.0.** This tutorial uses the local
> Python runtime and in-memory storage. It does not require a dataframe or SQL
> plugin.

This tutorial explains the pieces of the runnable quickstart and shows how to
inspect the artifacts ETLantic creates.

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
from etlantic import Pipeline, Sink, Source


class CustomerPipeline(Pipeline):
    raw: Source[RawCustomer] = Source(binding="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Sink[Customer] = Sink(
        input=normalized.result,
        binding="customer_sink",
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
- SparkForge adapter — `etlantic-sparkforge`

Dagster/Prefect compilers and managed cloud Spark providers remain future
work. See [Capabilities](CAPABILITIES.md).

Continue with [Project Structure](PROJECT_STRUCTURE.md) or run the complete
repository example in `examples/quickstart.py`.
