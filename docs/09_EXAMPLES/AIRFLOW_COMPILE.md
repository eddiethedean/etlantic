# Airflow Compile (runnable)

> **Status: Available in ETLantic 0.41.0.** Uses `etlantic-airflow` and
> `examples/airflow_compile.py`.

Compile an ETLantic `PipelinePlan` into an Airflow DAG artifact without
running Airflow itself.

## Setup

```bash
git clone --branch v0.41.0 https://github.com/eddiethedean/etlantic.git
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

## Expected output

The companion first proves that the same pipeline runs locally, then writes the
compile artifact. Run and plan identifiers vary:

```text
profile:  local
status:   succeeded
summary:  total=3 ok=3 failed=0 skipped=0 cancelled=0
Wrote examples/_generated_customer_airflow_dag.py dag_id=customerairflowpipeline tasks=['curated', 'normalized', 'raw']
{'target': 'airflow',
 'dag_id': 'customerairflowpipeline',
 'task_count': 3,
 'dependencies': {'raw': [], 'normalized': ['raw'], 'curated': ['normalized']},
 ...}
```

Successful compilation means the file was generated and can be reviewed; it
does not mean Airflow imported or scheduled it.

## What you get

- A compile artifact targeting `airflow`
- Secret-free plan metadata suitable for DAG generation
- A path to review before deploying into an Airflow environment

Airflow itself is not required on the compile machine. Install Airflow only
in the environment that will *run* the generated DAG.

## See also

- [Airflow execution guide](../06_EXECUTION/AIRFLOW.md)
- [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md)
