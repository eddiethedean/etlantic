# etlantic-prefect

Optional Prefect **ExecutionScheduler** for ETLantic (`etlantic.scheduler/1`).
The local MVP is shipped in ETLantic 0.20.

This is **not** an Airflow-style `compile_plan` / DAG compiler. It coordinates
already-resolved `PipelinePlan` logical nodes via Prefect 3 tasks while ETLantic
owns validation, retries, materialization, and `PipelineRunReport`.

## Install

```bash
pip install etlantic-prefect
```

## Usage

```python
from etlantic import Profile, PipelineRuntime

profile = Profile(name="dev", orchestrator="prefect")
report = MyPipeline.run(profile=profile, runtime=runtime)
```

Local direct invocation only for the shipped 0.20 MVP — no Prefect Cloud/server or
deployment/serve required. Keep `LocalScheduler` (`orchestrator="local"`) as the
default development path.

## Decision table

| Path | Protocol | Package |
|---|---|---|
| Local in-process | `ExecutionScheduler` | built-in |
| Prefect direct execution | `ExecutionScheduler` | `etlantic-prefect` |
| Airflow DAG artifacts | `OrchestratorPlugin` / `compile_plan` | `etlantic-airflow` |

## Links

[Prefect example](https://etlantic.readthedocs.io/en/v0.37.0/09_EXAMPLES/PREFECT_RUN/) ·
[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-prefect) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
