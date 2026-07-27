# Airflow Compile (runnable)

> **Status: Available.** Uses `etlantic-airflow` and
> `examples/airflow_compile.py`.

Compile an ETLantic `PipelinePlan` into an Airflow DAG artifact without
running Airflow itself.

## Setup

```bash
git clone https://github.com/eddiethedean/etlantic.git
cd etlantic
uv sync --group airflow
```

## Run

```bash
uv run python examples/airflow_compile.py
```

Or via CLI after planning:

```bash
uv run etlantic compile examples/memory_customers.py:CustomerPipeline \
  --target airflow -o /tmp/etlantic-dags
```

## What you get

- A compile artifact targeting `airflow`
- Secret-free plan metadata suitable for DAG generation
- A path to review before deploying into an Airflow environment

Airflow itself is not required on the compile machine. Install Airflow only
in the environment that will *run* the generated DAG.

## See also

- [Airflow execution guide](../06_EXECUTION/AIRFLOW.md)
- Design study (aspirational):
  [Airflow Pipeline](https://github.com/eddiethedean/etlantic/blob/main/docs/09_EXAMPLES/AIRFLOW_PIPELINE.md)
  (GitHub only; not a current API guide)
- [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md)
