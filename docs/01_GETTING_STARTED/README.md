# Getting Started

Welcome to ETLantic!

ETLantic catches incompatible data-pipeline wiring **before** you process
data. Define typed datasets, transformations, and pipelines in Python;
validate and plan them once; run locally or through optional engine plugins.

> **Project status:** Alpha **0.11.0**. See [Capabilities](CAPABILITIES.md)
> for the shipped boundary and [Evaluator brief](EVALUATOR.md) for
> decision-makers. How to read status labels:
> [Documentation Status](../02_FOUNDATIONS/DOCUMENTATION_STATUS.md).

## Five-minute path

1. [Current 0.10 guide](CURRENT_VERSION.md) — task-based map
2. [Installation](INSTALLATION.md) — `pip install etlantic`
3. [Quickstart](QUICKSTART.md) — copy, run, see Ada Lovelace
4. Break a type on purpose and re-run `validate()` — that failure is the product
5. [Capabilities](CAPABILITIES.md) — only after first success
6. [Evaluator brief](EVALUATOR.md) — if you are deciding whether to adopt

## What You'll Learn

- Install ETLantic from PyPI
- Define typed data contracts and transformations
- Wire a pipeline and validate it before execution
- Run locally with in-memory storage
- Use the CLI (`validate` / `plan` / `run`)
- Tell shipped APIs from future design

## Prerequisites

- Python 3.11+
- Basic type annotations
- Familiarity with ETL concepts helps; orchestration experience is optional

## Documentation Roadmap

1. [Installation](INSTALLATION.md)
2. [Quickstart](QUICKSTART.md)
3. [Your First Pipeline](FIRST_PIPELINE.md)
4. [Capabilities and Limitations](CAPABILITIES.md)
5. [Evaluator Brief](EVALUATOR.md)
6. [Troubleshooting](TROUBLESHOOTING.md)
7. [FAQ](FAQ.md)
8. [Project Structure](PROJECT_STRUCTURE.md) (after a second pipeline)

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

ETLantic 0.10 can execute registered Python implementations with its local
runtime and optional Polars/Pandas/SQL/PySpark plugins, and can compile plans
to Airflow DAGs via `etlantic-airflow`.

## Next Step

Continue with [Installation](INSTALLATION.md), then
[Quickstart](QUICKSTART.md).
