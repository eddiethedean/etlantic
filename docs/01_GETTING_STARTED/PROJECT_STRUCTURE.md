# Project Structure

An ETLantic project separates **modeling** from **execution**. Your Python
classes define contracts and pipelines, while runtime configuration and
generated artifacts remain outside your source code.

## Recommended Layout

``` text
customer-pipeline/
│
├── pyproject.toml
├── README.md
│
├── src/
│   └── customer_pipeline/
│       ├── __init__.py
│       │
│       ├── contracts/
│       │   ├── customers.py
│       │   ├── orders.py
│       │   └── products.py
│       │
│       ├── transformations/
│       │   ├── normalize_customers.py
│       │   ├── calculate_metrics.py
│       │   └── enrich_orders.py
│       │
│       ├── implementations/
│       │   ├── local/
│       │   ├── polars/          # optional plugin
│       │   ├── pandas/          # optional plugin
│       │   ├── sql/             # optional plugin
│       │   ├── spark/           # optional (etlantic-pyspark)
│       │   # airflow compile lives in tooling / CI, not under implementations/
│       │
│       ├── pipelines/
│       │   ├── customer_pipeline.py
│       │   └── analytics_pipeline.py
│       │
│       ├── profiles/
│       │   ├── local.py
│       │   ├── development.py
│       │   └── production.py
│       │
│       └── resources/
│           ├── databases.py
│           └── storage.py
│
├── contracts/
│   ├── data/
│   ├── transformations/
│   └── pipelines/
│
├── tests/
│
└── docs/
```

## Source Code

### contracts/

Contains `Data` contract models (`Data` is the preferred public alias;
`DataContractModel` remains as a deprecated name).

``` python
class Customer(Data):
    ...
```

These classes define your business data and generate ODCS contracts.

### transformations/

Contains transformation contract definitions.

``` python
class NormalizeCustomers(Transformation):
    ...
```

These classes define interfaces, not implementations.

### implementations/

Contains runtime-specific implementations.

Example:

- Local Python (`"local"`)
- Polars / Pandas (optional plugins)
- SQL (`"sql"` via `etlantic-sql` and `Profile.sql_engine`)
- PySpark (`"pyspark"` via `etlantic-pyspark` and `Profile.spark_engine`)

A single transformation contract may have multiple implementations.

### pipelines/

Contains ETLantic pipeline definitions.

``` python
class CustomerPipeline(Pipeline):
    ...
```

These classes wire contracts and transformations together.

### profiles/

Profiles describe runtime bindings.

Examples:

-   local development
-   CI
-   production
-   cloud

The pipeline itself remains unchanged.

### resources/

Reusable runtime resources.

Examples include:

-   database connections
-   object storage
-   API clients
-   credentials
-   dependency providers

## Generated Contracts

The `contracts/` directory contains generated specifications.

``` text
contracts/
├── data/
├── transformations/
└── pipelines/
```

These artifacts should generally be committed to version control so they
can be reviewed, shared, and validated independently of Python source
code.

## Tests

Recommended layout:

``` text
tests/
├── contracts/
├── transformations/
├── pipelines/
├── implementations/
└── integration/
```

Separate contract validation from execution testing whenever possible.

## Documentation

Keep project-specific documentation in a local `docs/` directory.

ETLantic itself has its own documentation, while each project
documents business-specific pipelines, assumptions, and operational
guidance.

## Design Principles

A ETLantic project should follow these principles:

-   Data contracts are isolated from execution code.
-   Transformations define interfaces before implementations.
-   Execution engines remain interchangeable.
-   Pipelines model logical data flow.
-   Runtime configuration is separated into profiles.
-   Generated contracts are treated as first-class artifacts.

## Why This Structure?

This organization keeps business logic, contracts, runtime bindings, and
generated artifacts independent.

As projects grow, teams can evolve execution strategies without changing
pipeline definitions, or extend pipeline models without rewriting
existing implementations.

## Next Step

Continue with [FAQ](FAQ.md) for answers to common questions about
ETLantic's architecture and philosophy.
