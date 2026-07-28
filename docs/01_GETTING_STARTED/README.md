# Getting Started

Welcome to ETLantic!

ETLantic catches incompatible data-pipeline wiring **before** you process
data. Define typed datasets, transformations, and pipelines in Python;
validate and plan them once; run locally or through optional engine plugins.

> **Project status:** ETLantic **0.26.0** is a **Beta** (PyPI) release suitable within the documented
> single-tenant reference deployment boundary. **First run:** follow the
> [docs home green path](../README.md) (Installation → Quickstart → First Pipeline → Engine selection).
> This page is the Learn section index. Experimental features and broader
> deployment models remain outside that claim. See
> [Capabilities](CAPABILITIES.md) for the shipped boundary and
> [Documentation Status](../02_FOUNDATIONS/DOCUMENTATION_STATUS.md) for status labels.

## Pages in this section (order)

1. [Installation](INSTALLATION.md) — `pip install etlantic==0.26.0`
2. [Quickstart](QUICKSTART.md) — `python -m etlantic init` → validate → run
3. [First Pipeline](FIRST_PIPELINE.md) — evolve the generated project
4. [Engine selection](ENGINE_SELECTION.md) — then an engine tutorial

After first success: [Learning path](LEARNING_PATH.md) (How-to),
[FAQ](FAQ.md) / [Troubleshooting](TROUBLESHOOTING.md) / [Upgrade](UPGRADE.md)
(Support), [What's New in 0.25](WHATS_NEW_0_25.md).

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
- Run locally with durable JSON assets via `python -m etlantic init`
- Use the CLI for `inspect` / `validate` / `plan` / `run`
- Tell shipped APIs from future design

## Prerequisites

- Python 3.11+
- Basic type annotations
- Familiarity with ETL concepts helps; orchestration experience is optional

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

ETLantic 0.26.0 can execute registered Python implementations with its local
runtime and optional Polars/Pandas/SQL/PySpark plugins, compile plans to
Airflow DAGs via `etlantic-airflow`, execute plans through the Prefect local
MVP, and compile supported portable transformation families without native
engine implementations.

## Next Step

Continue with [Installation](INSTALLATION.md), then
[Quickstart](QUICKSTART.md).
