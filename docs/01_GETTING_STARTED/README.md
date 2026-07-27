# Getting Started

Welcome to ETLantic!

ETLantic catches incompatible data-pipeline wiring **before** you process
data. Define typed datasets, transformations, and pipelines in Python;
validate and plan them once; run locally or through optional engine plugins.

> **Project status:** ETLantic **0.25.0** is a **Beta** (PyPI) release suitable within the documented
> single-tenant reference deployment boundary. For the canonical onboarding
> path, start at [Current 0.25 Guide](CURRENT_VERSION.md). Experimental features
> and broader deployment models remain outside that claim. See
> [Capabilities](CAPABILITIES.md) for the shipped boundary and
> [Evaluator brief](EVALUATOR.md) for decision-makers. How to read status labels:
> [Documentation Status](../02_FOUNDATIONS/DOCUMENTATION_STATUS.md).

> **Shipped in 0.25:** compatibility burn-in for `etlantic.pipeline/1` and
> sibling codecs, Plugin SDK `/1` freeze decision (blockers published), and a
> published 1.0 removal inventory. See
> [What's New in 0.25](WHATS_NEW_0_25.md) and
> [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md).

## Five-minute path

1. [Installation](INSTALLATION.md) — `pip install etlantic==0.25.0`
2. [Quickstart](QUICKSTART.md) — `python -m etlantic init` → validate → run
3. [First Pipeline](FIRST_PIPELINE.md) — evolve the generated project
4. Optional: [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md)
5. [Engine selection](ENGINE_SELECTION.md) — then an engine tutorial

!!! note "CLI run vs in-memory demos"
    The Quickstart binds assets to JSON files, so `python -m etlantic run` works without
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
4. Optional: [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md)
5. [Engine selection](ENGINE_SELECTION.md), then
   [Polars](../06_EXECUTION/POLARS_TUTORIAL.md),
   [Pandas](../06_EXECUTION/PANDAS_TUTORIAL.md),
   [SQL](../06_EXECUTION/SQL_TUTORIAL.md), or
   [PySpark](../06_EXECUTION/PYSPARK_TUTORIAL.md)
6. Diligence: [Capabilities](CAPABILITIES.md), [Evaluator Brief](EVALUATOR.md),
   [Compare](COMPARE.md)
7. [FAQ](FAQ.md) / [Troubleshooting](TROUBLESHOOTING.md) / [Cookbook](COOKBOOK.md) /
   [Best practices](BEST_PRACTICES.md)
8. [Project Structure](PROJECT_STRUCTURE.md) (after a second pipeline)
9. [Upgrade](UPGRADE.md) when moving between 0.x releases

## The ETLantic Mental Model

``` text
Class / builders / JSON
      │
      ▼
PipelineDefinition (etlantic.pipeline/1)
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

ETLantic 0.25.0 can execute registered Python implementations with its local
runtime and optional Polars/Pandas/SQL/PySpark plugins, compile plans to
Airflow DAGs via `etlantic-airflow`, execute plans through the Prefect local
MVP, and compile supported portable transformation families without native
engine implementations.

## Next Step

Continue with [Installation](INSTALLATION.md), then
[Quickstart](QUICKSTART.md).
