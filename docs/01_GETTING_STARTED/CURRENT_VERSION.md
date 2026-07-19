# ETLantic 0.18 User Guide

This is the current manual for published ETLantic **0.18.0**. Core onboarding
paths below are available in 0.18; linked reference and design pages may also
describe Experimental, partial, or future work and retain their own status
labels. ETLantic 0.18.0 is **stable** only within the documented
single-tenant reference deployment boundary.

## Start here

1. [Install core](INSTALLATION.md) — Python 3.11+ and `pip install etlantic==0.18.0`
2. [Run the five-minute quickstart](QUICKSTART.md)
3. [Build your first pipeline](FIRST_PIPELINE.md)
4. [Choose an engine](ENGINE_SELECTION.md)

After first success: [Capabilities](CAPABILITIES.md),
[What's new in 0.18](WHATS_NEW_0_18.md), [Compare](COMPARE.md), or
[Upgrade](UPGRADE.md).

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
| Run Polars portable (no native impl) | [Portable transforms example](../09_EXAMPLES/PORTABLE_TRANSFORMS.md) / `examples/portable_polars_kernel.py` |
| Run Pandas portable (no native impl) | `examples/portable_pandas_kernel.py` |
| Run SQL portable (kernel + relational `/1`) | `etlantic-sql` + public conformance suite |
| Controlled pilot | [Pilot walkthrough](../06_EXECUTION/PILOT_WALKTHROUGH.md) |
| Upgrade from 0.17 | [Migration 0.17 → 0.18](../11_DEVELOPMENT/MIGRATION_0_17_TO_0_18.md) |
| Upgrade from 0.16 | [Migration 0.16 → 0.17](../11_DEVELOPMENT/MIGRATION_0_16_TO_0_17.md) |
| Upgrade from 0.15 | [Migration 0.15 → 0.16](../11_DEVELOPMENT/MIGRATION_0_15_TO_0_16.md) |
| Upgrade from 0.14 | [Migration 0.14 → 0.15](../11_DEVELOPMENT/MIGRATION_0_14_TO_0_15.md) |
| Upgrade from 0.13 | [Migration 0.13 → 0.14](../11_DEVELOPMENT/MIGRATION_0_13_TO_0_14.md) |
| Integrate validation into CI | [CI integration](../06_EXECUTION/CI_INTEGRATION.md) / [Production profiles](../06_EXECUTION/PRODUCTION_PROFILES.md) |
| Evaluate operational boundaries | [Production readiness](../06_EXECUTION/PRODUCTION_READINESS.md) |
| Build a shipped plugin protocol | [Dataframe](../07_PLUGIN_SDK/DATAFRAME_PLUGIN.md), [SQL](../07_PLUGIN_SDK/SQL_PLUGIN.md), [PySpark](../07_PLUGIN_SDK/PYSPARK_PLUGIN.md), [Orchestrator](../07_PLUGIN_SDK/ORCHESTRATOR_PLUGIN.md), [Transform compiler](../07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER.md), [Third-party tutorial](../07_PLUGIN_SDK/THIRD_PARTY_COMPILER_TUTORIAL.md) |

## Current authority

- [Capabilities](CAPABILITIES.md) is the source of truth for shipped behavior.
- [Python API](../10_REFERENCE/API_REFERENCE.md) documents public imports.
- [CLI reference](../10_REFERENCE/CLI.md) documents installed commands.
- [Known limitations](../10_REFERENCE/KNOWN_ISSUES.md) documents hard boundaries.
