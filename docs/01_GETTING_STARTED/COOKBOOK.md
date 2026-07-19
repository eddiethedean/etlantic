# Cookbook

> **Status: Available in ETLantic 0.18.0.** Short recipes for shipped workflows.
> Prefer these over Design Studies.

## First success

| Recipe | Link |
|---|---|
| Five-minute local pipeline | [Quickstart](QUICKSTART.md) (paste); checkout: [`examples/quickstart.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/quickstart.py) |
| CLI inspect / validate / plan | [First Pipeline](FIRST_PIPELINE.md) |
| JSON and CSV storage | [File storage](../06_EXECUTION/FILE_STORAGE_TUTORIAL.md) |

## Engines

| Recipe | Link |
|---|---|
| Pick an engine | [Engine selection](ENGINE_SELECTION.md) |
| Polars / Pandas / SQL / PySpark | Tutorials under [Execution](../06_EXECUTION/README.md) |
| Polars↔Pandas Gate A interchange | [Interchange](../09_EXAMPLES/INTERCHANGE_POLARS_PANDAS.md) |
| Portable transform without native impl | [Portable transforms](../09_EXAMPLES/PORTABLE_TRANSFORMS.md) |

## CI and production

| Recipe | Link |
|---|---|
| SARIF validate in CI | [CI integration](../06_EXECUTION/CI_INTEGRATION.md) |
| Production profile + allowlist | [CI starter JSON](CAPABILITIES.md#ci-starter) / [prod.example.json](prod.example.json), [Production profiles](../06_EXECUTION/PRODUCTION_PROFILES.md) |
| Bounded production checklist | [Production readiness](../06_EXECUTION/PRODUCTION_READINESS.md) |
| Ops pilot | [Ops Pilot](../06_EXECUTION/OPS_PILOT.md) |

## Contracts and plans

| Recipe | Link |
|---|---|
| Generate ODCS / DTCS / DPCS | [Contract generation](../05_PIPELINES/CONTRACT_GENERATION.md) |
| Explain a plan | `etlantic plan explain TARGET --format json` — [Planning](../05_PIPELINES/PLANNING.md) |
| Diff pipelines or contracts | [CLI](../10_REFERENCE/CLI.md) `etlantic diff` |

## Secrets, reports, diagnostics

| Recipe | Link |
|---|---|
| Env / file secrets | [Secrets management](../06_EXECUTION/SECRETS_MANAGEMENT.md) |
| Run reports | [Run reports](../06_EXECUTION/RUN_REPORTS.md) |
| Common failures | [Troubleshooting](TROUBLESHOOTING.md) |
| Diagnostic codes | [Diagnostics](../10_REFERENCE/DIAGNOSTICS.md) |

## Orchestration

| Recipe | Link |
|---|---|
| Compile to Airflow DAGs | [Airflow tutorial](../06_EXECUTION/AIRFLOW_TUTORIAL.md) (compile-only package) |
| Prefect local execute | [Prefect](../09_EXAMPLES/PREFECT_RUN.md) |

## CLI run vs Python seed

Use CLI `validate` / `plan` always. For in-memory assets, seed and run in
Python:

```python
runtime = PipelineRuntime()
runtime.memory.seed("customer_source", rows)
CustomerPipeline.run(profile="development", runtime=runtime)
```

Use CLI `run` when extracts/loads bind to durable storage (JSON, CSV, SQL).
