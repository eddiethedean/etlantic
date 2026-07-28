# Cookbook

> **Status: Available in ETLantic 0.28.0.** Short recipes for shipped workflows.
> Prefer these over Design Studies.

## Worked recipes

### Local JSON pipeline (copy-paste)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: py -3.11 -m venv .venv && .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install 'etlantic==0.28.0'
mkdir my-pipeline && cd my-pipeline
python -m etlantic init --with-toml
python -m etlantic validate pipeline.py:SamplePipeline --profile development
python -m etlantic run pipeline.py:SamplePipeline --profile development
```

Expect `succeeded` and Ada/Grace rows in `data/out.json`.

### Polars engine (after local success)

```bash
python -m pip install 'etlantic[polars]==0.28.0'
# set Profile.dataframe_engine="polars" (or use a profile JSON), then:
python -m etlantic validate pipeline.py:SamplePipeline --profile development
python -m etlantic run pipeline.py:SamplePipeline --profile development
```

Full walkthrough: [Polars tutorial](../06_EXECUTION/POLARS_TUTORIAL.md).

### Production allowlist (fail closed)

```bash
cp path/to/prod.example.json profiles/prod.json
# edit plugin_allowlist pins to ==0.28.0 and fill assets
python -m etlantic validate pipeline.py:SamplePipeline --profile profiles/prod.json
```

Empty allowlists fail with `PMPLUG401`. See
[Production profiles](../06_EXECUTION/PRODUCTION_PROFILES.md).

## First success

| Recipe | Link |
|---|---|
| Quickstart local pipeline | [Quickstart](QUICKSTART.md) (`python -m etlantic init`) |
| Evolve the generated project | [First Pipeline](FIRST_PIPELINE.md) |
| Day-two habits | [Best practices](BEST_PRACTICES.md) |
| In-memory SDK demo (checkout) | [`examples/memory_customers.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/memory_customers.py) |
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
