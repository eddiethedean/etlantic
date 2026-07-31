# etlantic-airflow

Airflow reference orchestrator compiler for
[ETLantic](https://github.com/eddiethedean/etlantic) 0.39.

> **Note:** This plugin and ETLantic core use Beta classifiers for documented
> single-tenant pilots. Classifiers are not an enterprise SLA.

## Install

```bash
pip install etlantic-airflow
# To import generated DAGs into an Airflow process, install apache-airflow
# separately in the Airflow environment (not required for compile).
```

## Wiring

```python
from etlantic import Profile, plan_pipeline, compile_plan

profile = Profile(
    name="airflow-prod",
    orchestrator="airflow",
    schedule={"type": "cron", "expression": "0 2 * * *", "timezone": "UTC"},
    execution={"retries": 2, "timeout_seconds": 3600},
)
plan = plan_pipeline(MyPipeline, profile=profile)
artifact = compile_plan(plan, target="airflow", profile=profile)
artifact.write("dags/my_pipeline.py")
```

The `etlantic.orchestrator_plugins` entry point named `airflow` registers
`etlantic_airflow:create_plugin`. Set `orchestrator="airflow"` in the profile,
validate and plan first, then compile the valid plan with
`etlantic compile TARGET --target airflow -o dags/`.

## Capabilities

- Deterministic Airflow DAG module generation from a secret-free `PipelinePlan`
- Schedule, retry, timeout, and dependency mapping
- Retry-safety fail-closed for unsafe sinks
- Artifact-ref-only XCom payloads (no large inline data)
- Lifecycle correlation keys for normalized run reports

**Not included:** managed Airflow deployments, Dagster compile plugins, or
Prefect (shipped separately as an `ExecutionScheduler` local MVP, not as an
Airflow-style compiler).

## Links

[Documentation](https://etlantic.readthedocs.io/en/v0.39.0/06_EXECUTION/AIRFLOW/) ·
[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-airflow) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
