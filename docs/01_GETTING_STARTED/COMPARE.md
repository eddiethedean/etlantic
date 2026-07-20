# Is ETLantic for me?

> **Status: Available in ETLantic 0.21.0.**

ETLantic is a typed **modeling, validation, and planning** layer for Python
data pipelines. It is not a dataframe engine, warehouse transformer, or
durable orchestrator.

## Quick decision

| If you need… | Start with | Use ETLantic when… |
|---|---|---|
| SQL analytics projects in a warehouse | **dbt** | You also need typed multi-engine Python pipelines |
| Durable DAG scheduling / ops | **Airflow / Dagster / Prefect** | You want typed contracts and secret-free plans that compile or execute into those tools |
| Row-level dataframe checks | **Pandera / Great Expectations** | You also need graph wiring and contract validation **before** run |
| Typed pipeline composition across engines | **ETLantic** | You want one logical model, fail-closed plans, and interchangeable backends |

## Compared to common tools

| Tool | Primary job | Relationship |
|---|---|---|
| **dbt** | SQL transformation project / warehouse analytics | Complementary |
| **Airflow** | Orchestration and scheduling | Complementary — `etlantic-airflow` **compiles** plans to DAG artifacts (does not install Airflow) |
| **Prefect** | Orchestration and scheduling | Complementary — `etlantic-prefect` is a local direct-execution scheduler MVP, not a DAG compiler |
| **Dagster** | Orchestration and software-defined assets | Complementary — Dagster compiler remains future |
| **Pandera / GE** | Dataframe / table validation libraries | Complementary — ETLantic validates wiring and contracts; row suites stay engine-side |
| **Polars / Pandas / Spark / SQL engines** | Execution | Complementary — install matching `etlantic-*` plugins |

## What ETLantic owns

- Typed `Data`, `Transformation`, and `Pipeline` authoring
- Multi-phase validation and deterministic, secret-free `PipelinePlan`
- ODCS / DTCS / DPCS interchange
- Local runtime, reports, schema observations, and plugin trust controls

## What ETLantic does not own

- Dataframe compute kernels
- Multi-worker / multi-tenant control planes
- Managed Spark clusters
- Release SBOM digests and attestations ship in 0.20; broader compliance
  programs and multi-tenant attestation remain adopter-owned

## Next

1. [Installation](INSTALLATION.md)
2. [Quickstart](QUICKSTART.md)
3. [Capabilities](CAPABILITIES.md)
4. [Evaluator brief](EVALUATOR.md) for enterprise decision packets
