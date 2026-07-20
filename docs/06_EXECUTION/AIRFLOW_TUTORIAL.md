# Compile an Airflow DAG

> **Status: Available in ETLantic 0.21.0.** ETLantic compiles a plan; it does
> not install or operate an Airflow scheduler.

!!! warning "`etlantic-airflow` is compile-only"
    Installing `etlantic-airflow` (or `etlantic[airflow]`) provides the
    compile target for `etlantic compile --target airflow`. It does **not**
    install Apache Airflow. To import or run generated DAGs you need a
    separate Airflow installation in your deployment environment.


!!! note "Repository examples"
    Companion scripts under `examples/` are not installed with the PyPI
    wheel. Clone a matching checkout (prefer the `v0.21.0` tag) and use
    `uv sync` / the documented dependency group before running them.

## Install and compile

```bash
python -m pip install 'etlantic==0.21.0' 'etlantic-airflow==0.21.0'
git clone --branch v0.21.0 https://github.com/eddiethedean/etlantic.git
cd etlantic
python examples/airflow_compile.py
```

The example first proves local execution, then creates an Airflow profile with
a UTC cron schedule and retry policy. It writes
`examples/_generated_customer_airflow_dag.py`.

Complete source:
[`examples/airflow_compile.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/airflow_compile.py).

For CI compilation without running the example:

```bash
etlantic validate module.py:Pipeline --profile ./profiles/prod.json --format json
etlantic compile module.py:Pipeline --target airflow --profile ./profiles/prod.json -o dags/
```

Production profiles require an explicit plugin allowlist in a Profile JSON
file (the built-in `production` name is empty and fail-closed). See
[Production profiles](PRODUCTION_PROFILES.md). Inspect the generated
artifact and Airflow import errors before deployment. See
[Airflow compilation details](AIRFLOW.md).
