# Why ETLantic?

## The State of Data Engineering

Modern data engineering has an abundance of excellent execution tools.
Dataframes, schedulers, databases, cloud services, and orchestration
platforms continue to improve every year.

What remains fragmented is **how pipelines are modeled**.

Developers often describe the same pipeline multiple times:

-   Python classes for business logic
-   YAML files for configuration
-   DAG definitions for orchestration
-   Data contracts for governance
-   Documentation for people
-   Diagrams for architecture reviews

Every duplicate representation introduces opportunities for drift.

## The Missing Layer

Most tools focus on **execution**.

ETLantic focuses on **modeling**.

It provides a single, typed description of a pipeline that can be
validated, documented, visualized, and executed through different
runtimes.

Rather than replacing existing tools, ETLantic sits above them.

``` text
Business Intent
       │
       ▼
ETLantic
       │
       ├── Validation
       ├── Documentation
       ├── Contract Generation
       ├── Visualization
       ├── Planning
       ▼
Execution Plugins
(Polars, Pandas, SQL, PySpark, Airflow, …)
```

## Why Python Types?

Python's type annotation ecosystem has matured dramatically.

Projects such as FastAPI and Pydantic demonstrated that type annotations
can power:

-   validation
-   documentation
-   editor tooling
-   code generation
-   developer productivity

ETLantic applies those same ideas to ETL.

A transformation should be understandable from its type signature alone.

## Why Contracts?

Contracts establish clear expectations between producers and consumers.

ETLantic embraces three complementary standards:

-   **[ODCS](../03_DATA_CONTRACTS/ODCS.md)** for data contracts
-   **[DTCS](../04_TRANSFORMATIONS/DTCS.md)** for transformation contracts
-   **[DPCS](../05_PIPELINES/DPCS.md)** for pipeline contracts

Developers should author Python classes---not hand-maintain contract
files. ETLantic generates portable contracts whenever possible.

## Why Separate Modeling from Execution?

Execution technologies evolve quickly.

Organizations may migrate from one dataframe library or orchestrator to
another over time.

Pipeline definitions should not need to change simply because the
runtime changes.

ETLantic allows the same logical pipeline to target multiple
execution environments through bindings and profiles.

## Why Another Framework?

ETLantic is intentionally **not**:

-   a dataframe library
-   a scheduler
-   a workflow engine
-   an orchestration platform

Instead, it provides the missing modeling layer that allows these
systems to work together through a common, typed representation.

## Who Benefits?

ETLantic is designed for:

-   data engineers
-   analytics engineers
-   platform teams
-   organizations adopting contract-driven development
-   framework authors building new execution plugins

## The Long-Term Goal

Our goal is an ecosystem where a developer can define a pipeline once,
validate it once, and execute it anywhere.

Python types become the source of truth.

Contracts become portable artifacts.

Execution becomes an implementation detail.

That separation allows teams to focus on solving business problems
rather than maintaining multiple disconnected representations of the
same pipeline.
