# Prefect Direct Execution

> **Status: Available in ETLantic 0.44.0.** This guide runs the shipped Prefect
> scheduler locally through `etlantic-prefect`.

Runnable companion:
[`examples/prefect_run.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/prefect_run.py).

## Install and run

From a repository checkout:

```bash
uv sync --group prefect
uv run python examples/prefect_run.py
```

For an application install, keep core and plugin on the same minor line:

```bash
pip install 'etlantic==0.44.0' 'etlantic-prefect==0.44.0'
```

The example creates a process-local `PipelineRuntime`, seeds an in-memory
source, registers the scheduler explicitly, and selects Prefect with:

```python
from etlantic_prefect import create_plugin

runtime.register_scheduler_plugin("prefect", create_plugin())
profile = Profile(name="prefect-demo", orchestrator="prefect")
report = CustomerPipeline.run(profile=profile, runtime=runtime)
```

## Expected output

Prefect emits its own timestamped orchestration logs. The stable application
output after those logs is:

```text
profile:  prefect-demo
status:   succeeded
summary:  total=3 ok=3 failed=0 skipped=0 cancelled=0
scheduler: prefect
{'customer_id': 1, 'full_name': 'Ada Lovelace'}
{'customer_id': 2, 'full_name': 'Grace Hopper'}
```

Run identifiers, timestamps, and durations vary. Prefect consumes the resolved
`PipelinePlan`; it does not reinterpret or re-plan the pipeline.

For deployment boundaries, see [Deployment](../06_EXECUTION/DEPLOYMENT.md) and
[Production Profiles](../06_EXECUTION/PRODUCTION_PROFILES.md).
