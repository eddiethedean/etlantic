# Quickstart

Welcome to your first Pipelantic project.

In this guide you'll build a complete, typed pipeline in just a few
minutes. You'll define a data contract, create a transformation
contract, wire everything into a pipeline, validate it, and generate
portable contracts.

> **Goal:** Learn the Pipelantic mental model, not every feature.
>
> **Status:** Steps 1–7 match the shipped 0.4.0 surface (authoring, validation,
> contract generation, planning, and local execution). Dataframe/SQL/Spark
> plugins arrive in later milestones.

## Step 1 --- Define a Data Contract

``` python
from pipelantic import Data

class Customer(Data):
    id: int
    first_name: str
    last_name: str
```

This class is both a Pydantic model and the source of an ODCS-compatible
data contract.

## Step 2 --- Define a Transformation

``` python
from pipelantic import Transformation, Input, Output

class NormalizeCustomers(Transformation):
    customers: Input[Customer]
    result: Output[Customer]
```

The type annotations describe the transformation interface.
Pipelantic can derive a DTCS contract from this definition.

## Step 3 --- Build a Pipeline

``` python
from pipelantic import Pipeline, Sink, Source

class CustomerPipeline(Pipeline):
    raw: Source[Customer] = Source(binding="customer_source")

    normalized = NormalizeCustomers.step(
        customers=raw,
    )

    curated: Sink[Customer] = Sink(
        input=normalized.result,
        binding="customer_sink",
    )
```

Notice that the pipeline describes **logical data flow** rather than
execution.

## Step 4 --- Validate

``` python
report = CustomerPipeline.validate()

if report.has_errors:
    report.raise_for_errors()
```

Validation happens before execution so wiring and contract mismatches
are caught early.

## Step 5 --- Generate Contracts

``` python
CustomerPipeline.write_contracts("contracts/")
```

Pipelantic generates:

``` text
contracts/
├── data/
│   └── customer.odcs.yaml
├── transformations/
│   └── normalize-customers.dtcs.yaml
└── pipelines/
    └── customer-pipeline.dpcs.yaml
```

## Step 6 --- Plan

```python
plan = CustomerPipeline.plan(profile="local")
```

0.4.0 resolves a deterministic, secret-free `PipelinePlan` with
implementation, binding, capability, and execution-region decisions. Use
`CustomerPipeline.explain_plan(profile="local")` or the CLI
(`pipelantic plan …`) for a structured explanation.

## Step 7 --- Execute locally

``` python
from pipelantic import PipelineRuntime

runtime = PipelineRuntime()
# Seed in-memory source data for local runs, or register json/csv bindings.
runtime.memory.seed("customer_source", [...])

report = CustomerPipeline.run(
    profile="development",
    runtime=runtime,
)
print(report.status, report.to_text())
```

or

``` python
await CustomerPipeline.arun(
    profile="development",
    runtime=runtime,
)
```

Local execution uses the same `PipelinePlan` as future orchestrators. Source
and sink I/O in 0.4 uses Python callables, in-memory datasets, and stdlib
JSON/CSV bindings. Polars/Pandas/SQL plugins arrive in later milestones.

## What You've Learned

You have:

-   Defined a typed data contract.
-   Defined a typed transformation.
-   Built a pipeline.
-   Validated the pipeline.
-   Generated portable contracts.
-   Planned the pipeline with a profile.
-   Executed the pipeline locally and inspected a run report.

## Where to Go Next

Continue with [Your First Pipeline](FIRST_PIPELINE.md), where you'll build a realistic
end-to-end ETL pipeline and learn how data contracts, transformation
contracts, and pipeline contracts work together.
