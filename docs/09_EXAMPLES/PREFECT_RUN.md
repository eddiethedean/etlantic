# Prefect Direct Execution

> **Status: Available in ETLantic 0.21.0.** This guide runs the shipped Prefect
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
pip install 'etlantic==0.21.0' 'etlantic-prefect==0.21.0'
```

The example creates a process-local `PipelineRuntime`, seeds an in-memory
source, and selects Prefect with:

```python
profile = Profile(name="prefect-demo", orchestrator="prefect")
report = CustomerPipeline.run(profile=profile, runtime=runtime)
```

Expected output includes a succeeded run report, Prefect scheduler metadata,
and the two normalized customer records. Prefect consumes the resolved
`PipelinePlan`; it does not reinterpret or re-plan the pipeline.

For deployment boundaries, see [Deployment](../06_EXECUTION/DEPLOYMENT.md) and
[Production Profiles](../06_EXECUTION/PRODUCTION_PROFILES.md).
