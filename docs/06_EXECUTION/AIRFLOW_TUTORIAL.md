# Compile an Airflow DAG

> **Status: Available in ETLantic 0.13.0.** ETLantic compiles a plan; it does
> not install or operate an Airflow scheduler.

## Install and compile

```bash
python -m pip install 'etlantic==0.13.0' 'etlantic-airflow==0.13.0'
git clone https://github.com/eddiethedean/etlantic.git
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
etlantic validate module.py:Pipeline --profile production --format json
etlantic compile module.py:Pipeline --target airflow --profile production -o dags/
```

Production profiles require an explicit plugin allowlist. Inspect the generated
artifact and Airflow import errors before deployment. See
[Airflow compilation details](AIRFLOW.md).
