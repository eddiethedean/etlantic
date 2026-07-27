# Getting Started

Welcome to ETLantic!

ETLantic catches incompatible data-pipeline wiring **before** you process
data. Define typed datasets, transformations, and pipelines in Python;
validate and plan them once; run locally or through optional engine plugins.

> **Project status:** ETLantic **0.23.0** is a **Beta** (PyPI) release suitable within the documented
> single-tenant reference deployment boundary. For the canonical onboarding
> path, start at [Current 0.23 Guide](CURRENT_VERSION.md). Experimental features
> and broader deployment models remain outside that claim. See
> [Capabilities](CAPABILITIES.md) for the shipped boundary and
> [Evaluator brief](EVALUATOR.md) for decision-makers. How to read status labels:
> [Documentation Status](../02_FOUNDATIONS/DOCUMENTATION_STATUS.md).

> **Planned for 0.24:** complete functional authoring, an authoring-complete
> `PipelineDefinition`, lossless JSON, GUI integration contracts, and a thin
> FastAPI/OpenAPI reference. These are future design, not 0.23 APIs. See the
> [0.24 plan](../11_DEVELOPMENT/PROGRAMMATIC_AUTHORING_0_24.md).

## Five-minute path

1. [Installation](INSTALLATION.md) — `pip install etlantic==0.23.0`
2. [Quickstart](QUICKSTART.md) — `etlantic init`, validate, plan, and run
3. [First Pipeline](FIRST_PIPELINE.md) — evolve the generated project
4. [Engine selection](ENGINE_SELECTION.md) — then an engine tutorial

!!! note "CLI run vs in-memory demos"
    The Quickstart binds assets to JSON files, so `etlantic run` works without
    seeding. In-memory demos (`PipelineRuntime.memory.seed`) only share data
    inside one Python process—use
    [`examples/memory_customers.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/memory_customers.py)
    from a checkout for that path. Prefer the same `--profile` for validate,
    plan, and run (`development` by default when omitted).

## What You'll Learn

- Install ETLantic from PyPI
- Define typed data contracts and transformations
- Wire a pipeline and validate it before execution
- Run locally with durable JSON assets via `etlantic init`
- Use the CLI for `inspect` / `validate` / `plan` / `run`
- Tell shipped APIs from future design

## Prerequisites

- Python 3.11+
- Basic type annotations
- Familiarity with ETL concepts helps; orchestration experience is optional

## Documentation Roadmap

1. [Installation](INSTALLATION.md)
2. [Quickstart](QUICKSTART.md)
3. [Your First Pipeline](FIRST_PIPELINE.md)
4. [Engine selection](ENGINE_SELECTION.md), then
   [Polars](../06_EXECUTION/POLARS_TUTORIAL.md),
   [Pandas](../06_EXECUTION/PANDAS_TUTORIAL.md),
   [SQL](../06_EXECUTION/SQL_TUTORIAL.md), or
   [PySpark](../06_EXECUTION/PYSPARK_TUTORIAL.md)
5. Diligence: [Capabilities](CAPABILITIES.md), [Evaluator Brief](EVALUATOR.md),
   [Compare](COMPARE.md)
6. [FAQ](FAQ.md) / [Troubleshooting](TROUBLESHOOTING.md) / [Cookbook](COOKBOOK.md) /
   [Best practices](BEST_PRACTICES.md)
7. [Project Structure](PROJECT_STRUCTURE.md) (after a second pipeline)
8. [Upgrade](UPGRADE.md) when moving between 0.x releases

## The ETLantic Mental Model

``` text
Typed Python classes
      │
      ▼
Validation (catch bad wiring)
      │
      ▼
PipelinePlan (secret-free, deterministic)
      │
      ▼
Run locally  |  Compile (Airflow)  |  Generate contracts
```

ETLantic 0.23.0 can execute registered Python implementations with its local
runtime and optional Polars/Pandas/SQL/PySpark plugins, compile plans to
Airflow DAGs via `etlantic-airflow`, execute plans through the Prefect local
MVP, and compile supported portable transformation families without native
engine implementations.

## Next Step

Continue with [Installation](INSTALLATION.md), then
[Quickstart](QUICKSTART.md).
