# ETLantic 0.14 User Guide

This is the current, installable ETLantic manual. Every page linked from this
guide documents behavior available in ETLantic 0.14 unless it is explicitly
marked **Experimental**.

## Start here

1. [Install core](INSTALLATION.md) — Python 3.11+ and `pip install etlantic`
2. [Run the five-minute quickstart](QUICKSTART.md)
3. [Build your first pipeline](FIRST_PIPELINE.md)
4. [Check current capabilities](CAPABILITIES.md)

## Choose your next task

| Goal | Guide |
|---|---|
| Read and write JSON or CSV | [File storage](../06_EXECUTION/FILE_STORAGE_TUTORIAL.md) |
| Execute with Polars | [Polars tutorial](../06_EXECUTION/POLARS_TUTORIAL.md) |
| Execute with Pandas | [Pandas tutorial](../06_EXECUTION/PANDAS_TUTORIAL.md) |
| Keep work inside SQL | [SQL tutorial](../06_EXECUTION/SQL_TUTORIAL.md) |
| Run a local Spark batch | [PySpark tutorial](../06_EXECUTION/PYSPARK_TUTORIAL.md) |
| Compile a DAG | [Airflow tutorial](../06_EXECUTION/AIRFLOW_TUTORIAL.md) |
| Author portable transforms | [Portable transformations](../04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md) |
| Run Polars/PySpark portable relational (no native impl) | [Portable example](../09_EXAMPLES/PORTABLE_TRANSFORMATION.md) / `examples/portable_polars_kernel.py` |
| Upgrade from 0.11 | [Migration 0.11 → 0.12](../11_DEVELOPMENT/MIGRATION_0_11_TO_0_12.md) |
| Integrate validation into CI | [CI integration](../06_EXECUTION/CI_INTEGRATION.md) |
| Evaluate operational boundaries | [Production readiness](../06_EXECUTION/PRODUCTION_READINESS.md) |
| Build a shipped plugin protocol | [Dataframe](../07_PLUGIN_SDK/DATAFRAME_PLUGIN.md), [SQL](../07_PLUGIN_SDK/SQL_PLUGIN.md), [PySpark](../07_PLUGIN_SDK/PYSPARK_PLUGIN.md), [Orchestrator](../07_PLUGIN_SDK/ORCHESTRATOR_PLUGIN.md), [Transform compiler](../07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER.md) |

## Current authority

- [Capabilities](CAPABILITIES.md) is the source of truth for shipped behavior.
- [Python API](../10_REFERENCE/API_REFERENCE.md) documents public imports.
- [CLI reference](../10_REFERENCE/CLI.md) documents installed commands.
- [Known limitations](../10_REFERENCE/KNOWN_ISSUES.md) documents hard boundaries.
- Pages under **Design Proposals** / marked **Future design** are not 0.14 APIs
  even when linked from older navigation.

Material under **Design Proposals** is not part of the 0.14 user guide and must
not be copied into current applications.
