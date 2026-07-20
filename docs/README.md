<div class="etlantic-hero">
  <div class="etlantic-hero__content">
    <span class="etlantic-hero__eyebrow">Typed, contract-driven pipelines</span>
    <h1>Design once.<br><span class="etlantic-hero__nowrap">Validate everywhere.</span></h1>
    <p>Model data pipelines in Python, validate them as contracts, and run them where your engines already are.</p>
    <div class="etlantic-hero__actions">
      <a class="md-button md-button--primary" href="01_GETTING_STARTED/QUICKSTART/">Quickstart</a>
      <a class="md-button" href="01_GETTING_STARTED/INSTALLATION/">Installation</a>
    </div>
  </div>
</div>

ETLantic is a Python framework for defining typed, contract-driven data
pipelines and coordinating their execution through the tools users already
choose.

Its central idea is simple:

> Define data, transformations, and pipelines with typed Python classes.
> Validate and plan them once. Execute them through interchangeable backends.

ETLantic also treats validation as a continuous envelope around ETL. ETLantic
validates at every typed boundary—before extract, between steps, and at
load—without treating validation as an ordinary transform. See
[Validation Everywhere](02_FOUNDATIONS/VALIDATION_EVERYWHERE.md).

This is the practical meaning of the name: **ETL** is the data flow;
**ETLantic** is ETL surrounded by typed contracts, validation, planning, and
evidence from source to publication.

ETLantic is inspired by FastAPI's type-driven developer experience, but it
does not turn ETL into a web API metaphor. It applies the same principle—types
as executable interface declarations—to data engineering.

## Project status

**ETLantic 0.21.0** is **stable** for documented single-tenant reference
deployments. It models, validates, and plans typed Python data pipelines,
then runs them locally or through optional engine plugins.

- **Use today:** single-tenant reference deployments (see [Capabilities](01_GETTING_STARTED/CAPABILITIES.md)).
- **Not included:** multi-tenant control plane, managed Spark, unrestricted
  enterprise compliance attestations beyond shipped SBOM/attestations
  (adopter-owned for broader compliance programs).
- **Experimental:** Structured Streaming; `etlantic-datafusion` (Gate B stub).

[Install](01_GETTING_STARTED/INSTALLATION.md) ·
[Quickstart](01_GETTING_STARTED/QUICKSTART.md) ·
[Engine selection](01_GETTING_STARTED/ENGINE_SELECTION.md) ·
[Capabilities](01_GETTING_STARTED/CAPABILITIES.md)

!!! tip "Green path (start here only)"
    1. [Installation](01_GETTING_STARTED/INSTALLATION.md) — `pip install etlantic==0.21.0`
    2. [Quickstart](01_GETTING_STARTED/QUICKSTART.md) — five-minute success
    3. [First Pipeline](01_GETTING_STARTED/FIRST_PIPELINE.md) — contracts, validation, CLI
    4. [Engine selection](01_GETTING_STARTED/ENGINE_SELECTION.md) — then an engine tutorial

    Diligence (after first success): [Capabilities](01_GETTING_STARTED/CAPABILITIES.md),
    [What's new in 0.21](01_GETTING_STARTED/WHATS_NEW_0_21.md),
    [What's new in 0.20](01_GETTING_STARTED/WHATS_NEW_0_20.md),
    [Evaluator](01_GETTING_STARTED/EVALUATOR.md), [Compare](01_GETTING_STARTED/COMPARE.md).
    Pages marked **Future design** are not APIs. Design studies under Examples
    are aspirational—not installable APIs.

## Minimal working example

```python
from etlantic import (
    Data,
    Input,
    Output,
    Pipeline,
    PipelineRuntime,
    Load,
    Extract,
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
    raw: Extract[RawCustomer] = Extract(asset="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[Customer] = Load(
        input=normalized.result,
        asset="customer_sink",
    )


def main() -> None:
    CustomerPipeline.validate(profile="development").raise_for_errors()
    CustomerPipeline.plan(profile="development")
    runtime = PipelineRuntime()
    runtime.memory.seed(
        "customer_source",
        [RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace")],
    )
    CustomerPipeline.run(profile="development", runtime=runtime)
    print(runtime.memory.get("customer_sink"))


if __name__ == "__main__":
    main()
```

Copy into a file and run with Python after `pip install 'etlantic==0.21.0'`.
The PyPI wheel does **not** include `examples/`; from a checkout use
[`examples/quickstart.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/quickstart.py).
Prefer the full [Quickstart](01_GETTING_STARTED/QUICKSTART.md) (includes
`plan()`). From these declarations ETLantic can also generate
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

Runtime execution adds contract checks around extracts, transformation inputs
and outputs, engine/interchange boundaries, and loads. Those checks remain
visible in plan decisions and run evidence even when a backend safely fuses
their physical execution.

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
[Capabilities](01_GETTING_STARTED/CAPABILITIES.md). Paste the Quickstart file,
or from a checkout run
[`examples/quickstart.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/quickstart.py)
/ [`file_storage.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/file_storage.py).

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
3. [Secrets Management](06_EXECUTION/SECRETS_MANAGEMENT.md) (env + file; optional
   `etlantic-keyring`)
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

### I want to extend plugins (shipped protocols)

1. [Plugin SDK overview](07_PLUGIN_SDK/README.md) — shipped dataframe, SQL,
   Spark, orchestration, and transform-compiler protocols
2. [Testing Plugins](07_PLUGIN_SDK/TESTING_PLUGINS.md)
3. Future (not shipped): broader storage/resource/observability protocol catalogs —
   see [Storage today](06_EXECUTION/STORAGE_TODAY.md) vs Future-bannered pages

### I am integrating or migrating SparkForge

1. [SparkForge Feature Adoption](11_DEVELOPMENT/SPARKFORGE_ADOPTION.md)
2. [Roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md)

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
