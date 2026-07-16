<div class="pipelantic-hero">
  <div class="pipelantic-hero__content">
    <h1>Pipelantic</h1>
    <p>Typed, contract-driven data pipeline modeling for Python.</p>
    <div class="pipelantic-hero__actions">
      <a class="md-button md-button--primary" href="01_GETTING_STARTED/QUICKSTART/">Quickstart</a>
      <a class="md-button" href="01_GETTING_STARTED/CAPABILITIES/">Capabilities</a>
    </div>
  </div>
</div>

# Pipelantic Documentation

Pipelantic is a Python framework for defining typed, contract-driven data
pipelines and coordinating their execution through the tools users already
choose.

Its central idea is simple:

> Define data, transformations, and pipelines with typed Python classes.
> Validate and plan them once. Execute them through interchangeable backends.

Pipelantic is inspired by FastAPI's type-driven developer experience, but it
does not turn ETL into a web API metaphor. It applies the same principle—types
as executable interface declarations—to data engineering.

## Project Status

**0.6.0** ships validation, profiles, an immutable secret-free
`PipelinePlan`, local Python execution, runtime secret resolution, run reports,
memory/callable/JSON/CSV storage, a versioned dataframe protocol with Polars
and Pandas plugins, and a versioned SQL protocol with the `pipelantic-sql`
PostgreSQL reference plugin.

Many chapters still describe the intended 1.0 product. Examples beyond the
shipped surface are design examples, not a promise that every illustrated API
is already available. Start with
[Current Capabilities and Limitations](01_GETTING_STARTED/CAPABILITIES.md).

## Thirty-Second Example

```python
from pipelantic import (
    Data,
    Input,
    Output,
    Pipeline,
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


class CustomerPipeline(Pipeline):
    raw: Source[RawCustomer] = Source(binding="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Sink[Customer] = Sink(
        input=normalized.result,
        binding="customer_sink",
    )
```

From these declarations, Pipelantic can derive:

- ODCS data contracts
- A DTCS transformation contract
- A DPCS pipeline contract
- Static wiring and compatibility diagnostics
- A logical lineage graph
- A deterministic, secret-free `PipelinePlan` (0.3.0)
- A local Python runtime and structured run report (0.4.0)
- Optional Polars and Pandas dataframe plugins (0.5.0)
- Optional SQL execution via `pipelantic-sql` (0.6.0)

Memory, callable, JSON, CSV, and no-write storage are included in core.
Spark and external orchestration plugins arrive later.

The transformation implementation remains separate:

```python
@NormalizeCustomers.implementation("local")
def normalize_customers(customers):
    ...

@NormalizeCustomers.implementation("polars")
def normalize_customers_polars(customers):
    ...

@NormalizeCustomers.implementation("sql")
def normalize_customers_sql(customers):
    ...
```

Install `pipelantic-polars` / `pipelantic-pandas` / `pipelantic-sql` for
engines; later milestones may add PySpark, remote, or other implementations.

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

Pipelantic owns modeling, validation, planning, and coordination.

Standards own contract meaning. ContractModel owns data-contract
operationalization. Plugins and external systems perform the work.

## The Three Contract Authorities

Pipelantic intentionally recognizes only three top-level contract families:

| Contract | Authority | Answers |
|---|---|---|
| Data contract | ODCS and ContractModel | What is valid data? |
| Transformation contract | DTCS | How is data expected to change? |
| Pipeline contract | DPCS | How are data and transformations composed? |

Profiles, plugins, resources, callbacks, artifacts, and execution plans are
implementation or runtime concepts—not additional contract standards.

## Choose Your Path

### I want to run something in five minutes

1. [Capabilities](01_GETTING_STARTED/CAPABILITIES.md)
2. [Installation](01_GETTING_STARTED/INSTALLATION.md)
3. [Quickstart](01_GETTING_STARTED/QUICKSTART.md)
4. Runnable code: `examples/quickstart.py`, `examples/file_storage.py`,
   `examples/dataframe_parity.py`, `examples/sql_to_sql.py`

### I want to understand the idea

1. [Manifesto](PIPELANTIC_MANIFESTO.md)
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

- [examples/quickstart.py](https://github.com/eddiethedean/pipelantic/blob/main/examples/quickstart.py) — local runtime
- [examples/file_storage.py](https://github.com/eddiethedean/pipelantic/blob/main/examples/file_storage.py) — JSON/CSV storage
- [examples/dataframe_parity.py](https://github.com/eddiethedean/pipelantic/blob/main/examples/dataframe_parity.py) — Polars/Pandas
- [examples/sql_to_sql.py](https://github.com/eddiethedean/pipelantic/blob/main/examples/sql_to_sql.py) — SQL (`pipelantic-sql`)

### I want design studies (not installable)

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
| [Future Design](06_EXECUTION/PLUGINS.md) | Spark, Airflow, and other unshipped plugins |
| [Visualization](08_VISUALIZATION/README.md) | Mermaid today; Graphviz/HTML are future |
| [Examples](09_EXAMPLES/README.md) | Runnable pointers + design studies |
| [Reference](10_REFERENCE/README.md) | CLI, API, compatibility |
| [Development](11_DEVELOPMENT/README.md) | Contributing, roadmap, release |
| [Specifications](specifications/DTCS_SPEC.md) | Normative DTCS and DPCS documents |

## Non-Goals

Pipelantic is not intended to become:

- A dataframe engine
- A distributed scheduler
- A storage system
- A secret manager
- A proprietary pipeline contract format
- A replacement for Pandas, Polars, SQL engines, Spark, Airflow, or Dagster

It is the typed control and interoperability layer that connects those systems
without allowing any one of them to define the pipeline's portable meaning.
