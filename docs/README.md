<div class="pipelantic-hero">
  <div class="pipelantic-hero__content">
    <h1>Pipelantic</h1>
    <p>Typed, contract-driven data pipeline modeling for Python.</p>
    <div class="pipelantic-hero__actions">
      <a class="md-button md-button--primary" href="01_GETTING_STARTED/QUICKSTART/">Quickstart</a>
      <a class="md-button" href="02_FOUNDATIONS/ARCHITECTURE/">Architecture</a>
    </div>
  </div>
</div>

# Pipelantic Documentation

Pipelantic is a proposed Python framework for defining typed,
contract-driven data pipelines and coordinating their execution through the
tools users already choose.

Its central idea is simple:

> Define data, transformations, and pipelines with typed Python classes.
> Validate and plan them once. Execute them through interchangeable backends.

Pipelantic is inspired by FastAPI's type-driven developer experience, but it
does not turn ETL into a web API metaphor. It applies the same principle—types
as executable interface declarations—to data engineering.

## Project Status

**0.1.0** ships the typed modeling kernel: authoring APIs, logical graphs,
validation diagnostics, inspection, and Mermaid. Planning, execution plugins,
and contract serialization are later milestones.

Many chapters still describe the intended 1.0 product. Examples beyond the
0.1 surface are design examples, not a promise that every illustrated API is
already available. See [Documentation Status](02_FOUNDATIONS/DOCUMENTATION_STATUS.md)
and the [Roadmap](11_DEVELOPMENT/ROADMAP.md).

## Thirty-Second Example

```python
from contractmodel import DataContractModel
from pipelantic import Input, Output, Pipeline, Sink, Source, Transformation


class RawCustomer(DataContractModel):
    customer_id: int
    first_name: str
    last_name: str


class Customer(DataContractModel):
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
- A resolved `PipelinePlan` for a selected profile
- Documentation and visualizations
- Backend-specific execution artifacts

The transformation implementation remains separate:

```python
@NormalizeCustomers.implementation("polars")
def normalize_customers(customers):
    ...
```

The same transformation may also have Pandas, SQL, PySpark, remote, or other
implementations.

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

### I want to understand the idea

1. [Manifesto](PIPELANTIC_MANIFESTO.md)
2. [Vision](02_FOUNDATIONS/VISION.md)
3. [Core Concepts](02_FOUNDATIONS/CORE_CONCEPTS.md)
4. [Architecture](02_FOUNDATIONS/ARCHITECTURE.md)
5. [Security Model](02_FOUNDATIONS/SECURITY.md)

### I want to author pipelines

1. [Getting Started](01_GETTING_STARTED/README.md)
2. [Data Contracts](03_DATA_CONTRACTS/README.md)
3. [Transformations](04_TRANSFORMATIONS/README.md)
4. [Pipelines](05_PIPELINES/README.md)

### I want to understand execution

1. [Execution Model](06_EXECUTION/EXECUTION_MODEL.md)
2. [Run Reports](06_EXECUTION/RUN_REPORTS.md)
3. [Lifecycle Extensions](06_EXECUTION/LIFECYCLE_EXTENSIONS.md)
4. [Logging](06_EXECUTION/LOGGING.md)
5. [Planning](05_PIPELINES/PLANNING.md)
6. [Profiles](05_PIPELINES/PROFILES.md)
7. [Plugins](06_EXECUTION/PLUGINS.md)
8. [Compilation](06_EXECUTION/COMPILATION.md)

### I want to build a plugin

1. [Plugin SDK](07_PLUGIN_SDK/README.md)
2. [SDK Overview](07_PLUGIN_SDK/OVERVIEW.md)
3. [Testing Plugins](07_PLUGIN_SDK/TESTING_PLUGINS.md)
4. [Distribution](07_PLUGIN_SDK/DISTRIBUTION.md)

### I want concrete examples

- [CSV to CSV](09_EXAMPLES/CSV_TO_CSV.md)
- [SQL to SQL](09_EXAMPLES/SQL_TO_SQL.md)
- [Polars Pipeline](09_EXAMPLES/POLARS_PIPELINE.md)
- [Airflow Pipeline](09_EXAMPLES/AIRFLOW_PIPELINE.md)
- [PySpark to Delta](09_EXAMPLES/PYSPARK_TO_DELTA.md)
- [End-to-End Pipeline](09_EXAMPLES/END_TO_END.md)

### I am integrating or migrating SparkForge

1. [SparkForge Feature Adoption](11_DEVELOPMENT/SPARKFORGE_ADOPTION.md)
2. [Roadmap](11_DEVELOPMENT/ROADMAP.md)
3. [Planning](05_PIPELINES/PLANNING.md)
4. [PySpark Execution](06_EXECUTION/PYSPARK_EXECUTION.md)
5. [SQL Execution](06_EXECUTION/SQL_EXECUTION.md)

## Documentation Map

| Section | Purpose |
|---|---|
| [Getting Started](01_GETTING_STARTED/README.md) | Learn the core workflow |
| [Foundations](02_FOUNDATIONS/README.md) | Understand product philosophy and architecture |
| [Data Contracts](03_DATA_CONTRACTS/README.md) | Define and operationalize typed datasets |
| [Transformations](04_TRANSFORMATIONS/README.md) | Define typed transformation interfaces |
| [Pipelines](05_PIPELINES/README.md) | Compose transformations into portable graphs |
| [Execution](06_EXECUTION/README.md) | Resolve and delegate runtime behavior |
| [Plugin SDK](07_PLUGIN_SDK/README.md) | Extend execution and infrastructure support |
| [Visualization](08_VISUALIZATION/README.md) | Generate lineage, diagrams, and documentation |
| [Examples](09_EXAMPLES/README.md) | Study complete workflows |
| [Reference](10_REFERENCE/README.md) | Review proposed CLI, configuration, and Python APIs |
| [Development](11_DEVELOPMENT/README.md) | Follow roadmap, decisions, testing, and contribution rules |
| [Specifications](specifications/DTCS_SPEC.md) | Read normative DTCS and DPCS documents |

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
