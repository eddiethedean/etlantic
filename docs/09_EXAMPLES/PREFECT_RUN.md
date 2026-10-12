# Prefect Direct Execution

> **Status: Available in ETLantic 0.57.2 Beta.** This guide runs the shipped Prefect
> scheduler locally through `etlantic-prefect`.

!!! warning "Clone required"
    `examples/prefect_run.py` is **not** on the PyPI wheel. Use a git checkout
    plus `uv sync --group prefect`.

## Install and run

From a repository checkout:

```bash
uv sync --group prefect
uv run python examples/prefect_run.py
```

For an application install, keep core and plugin on the same minor line:

```bash
pip install 'etlantic==0.57.2' 'etlantic-prefect==0.57.2'
```

The example creates a process-local `PipelineRuntime`, seeds an in-memory
source, registers the scheduler explicitly, and selects Prefect with:

```python
from etlantic_prefect import create_plugin

runtime.register_scheduler_plugin("prefect", create_plugin())
profile = Profile(
    name="prefect-demo",
    orchestrator="prefect",
    portable_transform_policy="require",
)
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
The example's transformation is portable, so its body remains eligible for
future adaptive planning before the resolved plan reaches Prefect.

## Managed execution

Phase 0.58 adds an experimental managed path using a versioned Prefect Process
deployment, a durable ETLantic dispatcher, and PostgreSQL-backed control-plane
stores. The clean-wheel campaign covers separate Process workers, both
CSV-to-PostgreSQL and PostgreSQL-to-PostgreSQL replace-mode transfers, submitter
exit, uncertain-create recovery, post-dispatch deployment-drift rejection with
bounded pre-attempt recovery, and a graceful Prefect API restart. It does not
qualify the path for production: broader crash/effect recovery, host parity, and
the full supported-version matrix remain open. Deployment setup, trusted worker
configuration, supervision, and qualification status are documented in the
[`etlantic-prefect` package guide](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-prefect/README.md)
and [phase 0.58 plan](../11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_58.md).
For a separately hosted FastAPI control plane, see the
[Posit Connect deployment recipe](PREFECT_MANAGED_CONNECT.md).

For deployment boundaries, see [Deployment](../06_EXECUTION/DEPLOYMENT.md) and
[Production Profiles](../06_EXECUTION/PRODUCTION_PROFILES.md).
