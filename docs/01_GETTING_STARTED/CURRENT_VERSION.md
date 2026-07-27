# ETLantic 0.23 User Guide

This is the current manual for published ETLantic **0.23.0**. Core onboarding
paths below are available in 0.23; linked reference and design pages may also
describe Experimental, partial, or future work and retain their own status
labels. ETLantic 0.23.0 is a **Beta** (PyPI) release suitable only within the documented
single-tenant reference deployment boundary.

!!! info "Next phase: 0.24"
    Programmatic builders, lossless pipeline-definition JSON, visual-builder
    integration, and a thin FastAPI/OpenAPI reference are planned for 0.24;
    they are not available in 0.23. See the
    [0.24 Programmatic Authoring Plan](../11_DEVELOPMENT/PROGRAMMATIC_AUTHORING_0_24.md).

## Start here

1. [Install core](INSTALLATION.md) — Python 3.11+ and `pip install etlantic==0.23.0`
2. [Run the five-minute quickstart](QUICKSTART.md)
3. [Build your first pipeline](FIRST_PIPELINE.md)
4. [Choose an engine](ENGINE_SELECTION.md)

After first success: [Capabilities](CAPABILITIES.md),
[What's new in 0.23](WHATS_NEW_0_23.md), [Compare](COMPARE.md), or
[Upgrade](UPGRADE.md). Prefer `import etlantic as etl` for application code.

## Choose your next task

| Goal | Guide |
|---|---|
| Read and write JSON or CSV | [File storage](../06_EXECUTION/FILE_STORAGE_TUTORIAL.md) |
| Execute with Polars | [Polars tutorial](../06_EXECUTION/POLARS_TUTORIAL.md) |
| Execute with Pandas | [Pandas tutorial](../06_EXECUTION/PANDAS_TUTORIAL.md) |
| Polars↔Pandas Gate A interchange | [Interchange example](../09_EXAMPLES/INTERCHANGE_POLARS_PANDAS.md) |
| Keep work inside SQL | [SQL tutorial](../06_EXECUTION/SQL_TUTORIAL.md) |
| Run a local Spark batch | [PySpark tutorial](../06_EXECUTION/PYSPARK_TUTORIAL.md) |
| Compile a DAG | [Airflow tutorial](../06_EXECUTION/AIRFLOW_TUTORIAL.md) |
| Author portable transforms | [Portable transformations](../04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md) |
| Build a third-party plugin | [Building a Plugin](../07_PLUGIN_SDK/BUILDING_A_PLUGIN.md) |
| Follow functional/JSON/GUI authoring work | [0.24 Programmatic Authoring Plan](../11_DEVELOPMENT/PROGRAMMATIC_AUTHORING_0_24.md) |
| Check plugin compatibility | `etlantic plugin compatibility` / [CLI](../10_REFERENCE/CLI.md) |
| Resilience / performance budgets | [Exit gate 0.23](../11_DEVELOPMENT/EXIT_GATE_0_23.md) / [Benchmarks](../11_DEVELOPMENT/BENCHMARKS.md) |
| Controlled pilot | [Pilot walkthrough](../06_EXECUTION/PILOT_WALKTHROUGH.md) |
| Trust / safe I/O / outbound policy | [Security](../02_FOUNDATIONS/SECURITY.md) / [Exit gate 0.20](../11_DEVELOPMENT/EXIT_GATE_0_20.md) |
| Upgrade from 0.22 | [Migration 0.22 → 0.23](../11_DEVELOPMENT/MIGRATION_0_22_TO_0_23.md) |
| Upgrade from 0.21 | [Migration 0.21 → 0.22](../11_DEVELOPMENT/MIGRATION_0_21_TO_0_22.md) |

## Status labels

Pages and tables use **Available**, **Partial**, **Experimental**, **Gap**,
and **Future design**. Only **Available** surfaces are supported production
API in 0.23.
