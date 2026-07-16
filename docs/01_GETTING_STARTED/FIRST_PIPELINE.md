# Your First Pipeline

This tutorial walks through building a complete Pipelantic project
from start to finish. Rather than focusing on execution details, you'll
learn how to model a pipeline using typed Python classes.

> **Status:** Steps 1–8 match the shipped 0.4.0 surface (authoring, validation,
> contract generation, planning, and local execution). Dataframe engines and
> external orchestrators arrive in later milestones.

## Goal

We'll build a simple pipeline that:

1.  Reads raw customer records.
2.  Normalizes customer names.
3.  Writes curated customer records.
4.  Generates portable contracts.
5.  Validates the entire pipeline before execution.

## Step 1 --- Define the Data Contracts

``` python
from pipelantic import Data

class RawCustomer(Data):
    customer_id: int
    first_name: str
    last_name: str

class Customer(Data):
    customer_id: int
    full_name: str
```

These classes are the source of truth for your data. Pipelantic can
generate ODCS-compatible contracts directly from them.

## Step 2 --- Define the Transformation

``` python
from pipelantic import Transformation, Input, Output

class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]
```

Notice that the transformation defines **what** it accepts and **what**
it produces---not **how** it performs the work.

## Step 3 --- Provide an Implementation

``` python
@NormalizeCustomers.implementation("polars")
def normalize_customers(df):
    return (
        df.with_columns(
            (df["first_name"] + " " + df["last_name"])
            .alias("full_name")
        )
        .drop(["first_name", "last_name"])
    )
```

A Pandas, Spark, or remote implementation could be registered instead
without changing the transformation contract.

## Step 4 --- Build the Pipeline

``` python
from pipelantic import Pipeline, Sink, Source

class CustomerPipeline(Pipeline):
    raw: Source[RawCustomer] = Source(binding="customer_source")

    normalized = NormalizeCustomers.step(
        customers=raw,
    )

    curated: Sink[Customer] = Sink(
        input=normalized.result,
        binding="customer_sink",
    )
```

The pipeline models the logical flow of data between contracts and
transformations.

## Step 5 --- Validate

``` python
report = CustomerPipeline.validate()
report.raise_for_errors()
```

Validation checks:

-   Contract compatibility
-   Pipeline wiring
-   Required inputs and outputs
-   Parameter types
-   Plugin bindings (when configured)

## Step 6 --- Generate Contracts

``` python
CustomerPipeline.write_contracts("contracts/")
```

This produces:

``` text
contracts/
├── data/
│   ├── raw-customer.odcs.yaml
│   └── customer.odcs.yaml
├── transformations/
│   └── normalize-customers.dtcs.yaml
└── pipelines/
    └── customer-pipeline.dpcs.yaml
```

## Step 7 --- Plan

```python
plan = CustomerPipeline.plan(profile="local")
```

0.4.0 resolves registered implementations, source and sink bindings,
capabilities, resource references, and the physical execution graph without
reading data, resolving secrets, or executing the transformation during
planning.

## Step 8 --- Execute locally

``` python
from pipelantic import PipelineRuntime

runtime = PipelineRuntime()
runtime.memory.seed("customer_source", [...])
report = CustomerPipeline.run(profile="development", runtime=runtime)
print(report.to_text())
```

or

``` python
await CustomerPipeline.arun(profile="development", runtime=runtime)
```

Local execution consumes the same `PipelinePlan` as future orchestrators.
JSON/CSV and callable bindings are available in 0.4; Polars/Pandas/SQL
plugins ship later.

## What You Built

You created:

-   Typed data contracts
-   A typed transformation contract
-   A typed pipeline
-   Portable ODCS, DTCS, and DPCS contracts
-   A validated `PipelinePlan`
-   A local `PipelineRunReport`

## Key Takeaways

-   Python type annotations define the interface.
-   Contracts are generated automatically.
-   Pipelines describe intent, not execution.
-   Execution engines are interchangeable.
-   Validation and planning always happen before execution.

## Next Step

Continue with [Project Structure](PROJECT_STRUCTURE.md) to learn how to organize a
Pipelantic project for long-term maintainability.
