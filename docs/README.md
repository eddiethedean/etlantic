<div class="etlantic-hero">
  <div class="etlantic-hero__content">
    <span class="etlantic-hero__eyebrow">Typed, contract-driven pipelines</span>
    <h1>Design once.<br><span class="etlantic-hero__nowrap">Validate everywhere.</span></h1>
    <p>Model data pipelines in Python, validate them as contracts, and run them where your engines already are.</p>
    <div class="etlantic-hero__actions">
      <a class="md-button md-button--primary" href="01_GETTING_STARTED/QUICKSTART/">Quickstart</a>
      <a class="md-button" href="01_GETTING_STARTED/CAPABILITIES/">Capabilities</a>
    </div>
  </div>
</div>

ETLantic is a Python framework for defining typed, contract-driven data
pipelines and coordinating their execution through the tools users already
choose.

Its central idea is simple:

> Define data, transformations, and pipelines with typed Python classes.
> Validate and plan them once. Execute them through interchangeable backends.

ETLantic is inspired by FastAPI's type-driven developer experience, but it
does not turn ETL into a web API metaphor. It applies the same principle—types
as executable interface declarations—to data engineering.

## Project Status

**0.14.0** ships validation, profiles, an immutable secret-free
`PipelinePlan`, local Python execution, runtime secret resolution, run reports,
memory/callable/JSON/CSV storage, a versioned dataframe protocol with Polars
and Pandas plugins, a versioned SQL protocol with the `etlantic-sql`
PostgreSQL reference plugin, a versioned Spark protocol with the
`etlantic-pyspark` reference plugin (local provider + portable compiler), and a
versioned orchestration protocol with the `etlantic-airflow` reference
compiler. Portable Polars and PySpark compilers claim kernel +
`portable-relational/1`. Structured Streaming APIs are experimental.

!!! tip "Green path (start here only)"
    1. [Current 0.14 guide](01_GETTING_STARTED/CURRENT_VERSION.md) — task-based map
    2. [Installation](01_GETTING_STARTED/INSTALLATION.md) — `pip install etlantic`
    3. [Quickstart](01_GETTING_STARTED/QUICKSTART.md) — five-minute success
    4. [Capabilities](01_GETTING_STARTED/CAPABILITIES.md) — shipped vs not
    5. [Evaluator brief](01_GETTING_STARTED/EVALUATOR.md) — for decision-makers

    Pages marked **Future design** are not APIs. [Capabilities](01_GETTING_STARTED/CAPABILITIES.md)
    is the single source of truth. Prefer the Green path above; persona paths
    below are optional after first success.

Read **Available** pages and the Green path first. Chapters under
[Design Proposals](11_DEVELOPMENT/DESIGN_PROPOSALS.md) and Examples marked
**Future design** are not current APIs. Design studies are not a promise that
every illustrated surface is installable.

Portable PySpark-inspired authoring ships in 0.11 via `@Transformation.portable`
and `etlantic.transform`, emitting `dtcs.transform-plan/2`. **0.12** added
planning integration and Polars **kernel** portable execution. **0.13–0.14**
add Polars, PySpark, and Pandas `portable-relational/1` compilers plus the
public conformance SDK. Safe SQL portable lowering remains 0.15+. Start with
[Portable Transformations](04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md).

## Minimal working example

```python
from etlantic import (
    Data,
    Input,
    Output,
    Pipeline,
    PipelineRuntime,
    Sink,
    Source,
    Transformation,
)


class RawCustomer(Data):
    customer_id: int
    first_name: str
    last_name: str


class Customer(Data):
    customer_id: int
    full_name: str


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]


@NormalizeCustomers.implementation("local")
def normalize_customers(customers: list[RawCustomer]) -> list[Customer]:
    return [
        Customer(
            customer_id=row.customer_id,
            full_name=f"{row.first_name} {row.last_name}",
        )
        for row in customers
    ]


class CustomerPipeline(Pipeline):
    raw: Source[RawCustomer] = Source(binding="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Sink[Customer] = Sink(
        input=normalized.result,
        binding="customer_sink",
    )


CustomerPipeline.validate(profile="development").raise_for_errors()
runtime = PipelineRuntime()
runtime.memory.seed(
    "customer_source",
    [RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace")],
)
CustomerPipeline.run(profile="development", runtime=runtime)
print(runtime.memory.get("customer_sink"))
```

Copy into a file and run with Python after `pip install etlantic`, or use
`examples/quickstart.py`. From these declarations ETLantic can also generate
ODCS / DTCS / DPCS contracts, Mermaid lineage, and a secret-free
`PipelinePlan`. Optional plugins add Polars, Pandas, SQL, PySpark, and Airflow
compilation.

The transformation implementation remains separate—register `"polars"`,
`"sql"`, and other engines the same way after installing the matching plugin.

## The Architecture in One View

```text
Typed Python authoring or portable contracts
                    │
                    ▼
          Typed logical pipeline model
                    │
                    ▼
     Introspection and semantic validation
                    │
                    ▼
        Profile and capability resolution
                    │
                    ▼
        Immutable PipelinePlan (resolved IR)
                    │
          ┌─────────┼──────────┐
          ▼         ▼          ▼
      Execute    Compile    Generate
          │         │          │
          ▼         ▼          ▼
      Plugins   Airflow/SQL  Docs/graphs
```

ETLantic owns modeling, validation, planning, and coordination.

Standards own contract meaning. ContractModel owns data-contract
operationalization. Plugins and external systems perform the work.

## The Three Contract Authorities

ETLantic intentionally recognizes only three top-level contract families:

| Contract | Authority | Answers |
|---|---|---|
| Data contract | ODCS and ContractModel | What is valid data? |
| Transformation contract | DTCS | How is data expected to change? |
| Pipeline contract | DPCS | How are data and transformations composed? |

Profiles, plugins, resources, callbacks, artifacts, and execution plans are
implementation or runtime concepts—not additional contract standards.

## Choose Your Path

Follow the **Green path** above for first success. Optional persona forks:

### I want to run something in five minutes

Same as the Green path: [Installation](01_GETTING_STARTED/INSTALLATION.md) →
[Quickstart](01_GETTING_STARTED/QUICKSTART.md) → then
[Capabilities](01_GETTING_STARTED/CAPABILITIES.md). Runnable code:
`examples/quickstart.py`, `examples/file_storage.py`.

### I want to understand the idea

1. [Manifesto](ETLANTIC_MANIFESTO.md)
2. [Evaluator brief](01_GETTING_STARTED/EVALUATOR.md)
3. [Core Concepts](02_FOUNDATIONS/CORE_CONCEPTS.md)
4. [Architecture](02_FOUNDATIONS/ARCHITECTURE.md)
5. [Documentation Status](02_FOUNDATIONS/DOCUMENTATION_STATUS.md)

### I want to author pipelines

1. [Getting Started](01_GETTING_STARTED/README.md)
2. [Data Contracts](03_DATA_CONTRACTS/README.md)
3. [Transformations](04_TRANSFORMATIONS/README.md)
4. [Pipelines](05_PIPELINES/README.md)

### I want to understand execution (shipped)

1. [Execution Model](06_EXECUTION/EXECUTION_MODEL.md)
2. [Local Python](06_EXECUTION/LOCAL_PYTHON.md)
3. [Secrets Management](06_EXECUTION/SECRETS_MANAGEMENT.md) (env + file only)
4. [Polars](06_EXECUTION/POLARS.md) / [Pandas](06_EXECUTION/PANDAS.md)
5. [SQL](06_EXECUTION/SQL.md)
6. [Run Reports](06_EXECUTION/RUN_REPORTS.md)

### I want runnable examples

- [examples/quickstart.py](https://github.com/eddiethedean/etlantic/blob/main/examples/quickstart.py) — local runtime
- [examples/file_storage.py](https://github.com/eddiethedean/etlantic/blob/main/examples/file_storage.py) — JSON/CSV storage
- [examples/dataframe_parity.py](https://github.com/eddiethedean/etlantic/blob/main/examples/dataframe_parity.py) — Polars/Pandas
- [examples/sql_to_sql.py](https://github.com/eddiethedean/etlantic/blob/main/examples/sql_to_sql.py) — SQL (`etlantic-sql`)
- [examples/sql_boundary_hybrid.py](https://github.com/eddiethedean/etlantic/blob/main/examples/sql_boundary_hybrid.py) — SQL → Python boundary
- [examples/sql_transactional_write.py](https://github.com/eddiethedean/etlantic/blob/main/examples/sql_transactional_write.py) — insert-select publication
- [examples/sql_failure_recovery.py](https://github.com/eddiethedean/etlantic/blob/main/examples/sql_failure_recovery.py) — unsupported merge fails closed

### I want design studies (aspirational)

These pages describe intended 1.0 workflows. They are **not** current API guides:

- [CSV to CSV](09_EXAMPLES/CSV_TO_CSV.md) (design narrative; prefer `examples/file_storage.py`)
- [SQL to SQL](09_EXAMPLES/SQL_TO_SQL.md) (design narrative; prefer `examples/sql_to_sql.py`)
- [Airflow Pipeline](09_EXAMPLES/AIRFLOW_PIPELINE.md)
- [PySpark to Delta](09_EXAMPLES/PYSPARK_TO_DELTA.md)

### I want to build a dataframe or SQL plugin

1. [Dataframe Plugin protocol](07_PLUGIN_SDK/DATAFRAME_PLUGIN.md)
2. [SQL Plugin protocol](07_PLUGIN_SDK/SQL_PLUGIN.md)
3. [Dataframe Plugins overview](06_EXECUTION/DATAFRAME_PLUGINS.md)
4. [SQL overview](06_EXECUTION/SQL.md)
5. [Compatibility](10_REFERENCE/COMPATIBILITY.md)

### I want other plugins (future)

1. [Plugin SDK overview](07_PLUGIN_SDK/README.md) (future design)
2. [Testing Plugins](07_PLUGIN_SDK/TESTING_PLUGINS.md)

### I am integrating or migrating SparkForge

1. [SparkForge Feature Adoption](11_DEVELOPMENT/SPARKFORGE_ADOPTION.md)
2. [Roadmap](11_DEVELOPMENT/ROADMAP.md)

## Documentation Map

| Section | Purpose |
|---|---|
| [Getting Started](01_GETTING_STARTED/README.md) | Learn the core workflow |
| [Foundations](02_FOUNDATIONS/README.md) | Understand product philosophy and architecture |
| [Data Contracts](03_DATA_CONTRACTS/README.md) | Define and operationalize typed datasets |
| [Transformations](04_TRANSFORMATIONS/README.md) | Define typed transformation interfaces |
| [Pipelines](05_PIPELINES/README.md) | Compose transformations into portable graphs |
| [Execution](06_EXECUTION/README.md) | Local runtime, secrets, dataframe and SQL engines |
| [Orchestration](06_EXECUTION/AIRFLOW.md) | Airflow compiler (`etlantic-airflow`); other orchestrators future |
| [Visualization](08_VISUALIZATION/README.md) | Mermaid, Graphviz DOT, HTML lineage |
| [Examples](09_EXAMPLES/README.md) | Runnable pointers + design studies |
| [Reference](10_REFERENCE/README.md) | CLI, API, compatibility |
| [Development](11_DEVELOPMENT/README.md) | Contributing, roadmap, release |
| [Specifications](specifications/DTCS_SPEC.md) | Normative DTCS and DPCS documents |

## Non-Goals

ETLantic is not intended to become:

- A dataframe engine
- A distributed scheduler
- A storage system
- A secret manager
- A proprietary pipeline contract format
- A replacement for Pandas, Polars, SQL engines, Spark, Airflow, or Dagster

It is the typed control and interoperability layer that connects those systems
without allowing any one of them to define the pipeline's portable meaning.
