# Migrating from 0.9 to 0.10

ETLantic 0.10 ships the **SparkForge Migration Preview**: an optional adapter
that maps medallion SparkForge constructs onto existing ETLantic models.
Orchestration, SQL, Spark, and CLI surfaces from 0.8–0.9 are unchanged.

## What changed

- Optional package `medallantic` (extra `etlantic[medallantic]`)
- SparkForge-independent IR (`SparkForgePipelineSpec`) → `adapt_pipeline`
- Debug / run-mode mapping → `RunSelection` / `RunIntent` / `DebugSession`
- Result normalization → `PipelineRunReport`
- Write / Delta capability compatibility helpers (fail closed)
- Representative IR fixtures + semantic parity suite
- Plugin packages bump to `0.10.0` and require `etlantic>=0.10.0,<1.0`

## Hard boundary

ETLantic core **does not** gain bronze, silver, gold, or medallion types.
Layer terminology stays in SparkForge and in adapter metadata only.

## Install

```bash
pip install --upgrade 'etlantic>=0.10.0'
pip install medallantic
# or: pip install 'etlantic[medallantic]'
```

## Progressive engine deprecation path

Use this sequence when pointing SparkForge at ETLantic:

1. **Plan-only** — adapt IR, `validate` / `plan` / `explain` without changing execution
2. **Dual reporting** — `adapt_run_result` alongside existing SparkForge reports
3. **ETLantic planning** — selections and intents via `debug_request_from_sparkforge`
4. **Plugin execution** — `Profile.spark_engine="pyspark"` / SQL plugins
5. **Facade** — keep medallion builder; retire duplicated SparkForge engines

Legacy engine extension names discovered in IR emit diagnostic `PMSF410`.

## Unchanged

- Local / Polars / Pandas / SQL / PySpark / Airflow plugins
- CLI surfaces from 0.9
- Plugin allowlists and SARIF diagnostics

## See also

- [SparkForge Feature Adoption](SPARKFORGE_ADOPTION.md)
- [Current Capabilities](../01_GETTING_STARTED/CAPABILITIES.md)
- Package README: `packages/medallantic/README.md`
