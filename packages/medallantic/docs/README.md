# Medallantic documentation

Medallantic is the engine-agnostic medallion pipeline facade built on ETLantic.
It owns bronze, silver, and gold vocabulary while ETLantic supplies portable
contracts, graph validation, deterministic planning, runtime coordination,
reports, and plugin integration.

## Current status

Medallantic **0.30** (M2) builds on native authoring (**0.29 / M1**). It can:

- author bronze/silver/gold pipelines with `MedallionPipeline`,
  `MedallionBuilder`, `Bronze`, `Silver`, and `Gold`
- emit public `PipelineDefinition` / `etlantic.pipeline/1` documents
- parse secret-free SparkForge pipeline IR via
  `medallantic.migrate.sparkforge` (top-level `adapt_pipeline` remains)
- map medallion steps onto an ordinary ETLantic graph
- validate dependencies and reject cycles (`MDL1xx` / `PMSF*` diagnostics)
- map layer thresholds, write modes, retries, run intents, and selections
- enrich plans with write intents
- normalize legacy run results into `PipelineRunReport`
- verify declared Delta requirements against plugin capabilities
- pass `etlantic.testing.run_facade_conformance_suite`
- enforce portable `rules=` via `etlantic.quality/1` gates (Polars/Pandas/local
  live; SQL/PySpark fail closed at plan time when capabilities are missing)

It executes resolvable SparkForge-style transformation callables via
`medallantic.callables` (since **0.31**). Native PySpark Column rules ship in
**0.32** (`quality.pyspark_column` / `MDL130`); Moltres-only rules remain later.

## Quick start (native)

```python
from medallantic import MedallionBuilder
from etlantic.authoring import validate_pipeline_like, plan_pipeline_like

lowered = (
    MedallionBuilder("ecommerce", schema="demo")
    .bronze("orders", asset="bronze_orders")
    .silver("clean", source="orders", asset="silver_orders")
    .gold("kpis", source="clean", asset="gold_kpis", write_mode="merge")
    .lower()
)
defn = lowered.definition
report = validate_pipeline_like(defn, profile=lowered.profile)
plan = plan_pipeline_like(defn, profile=lowered.profile)
```

## Documentation map

- [Getting started](getting-started.md) — install, adapt, validate, and plan
- [Core concepts](concepts.md) — ownership and medallion-to-ETLantic mapping
- [SparkForge migration](sparkforge-migration.md) — IR conversion workflow
- [Runtime and reports](runtime-and-reports.md) — selections, retries, and results
- [Compatibility](compatibility.md) — supported mappings and current limits
- [Architecture](architecture.md) — package boundaries and extension rules
- [Development](development.md) — local tests and contribution constraints
- [Roadmap](../ROADMAP.md) — parity milestones (M2+)

## Choose the right starting point

Use **native authoring** for new medallion pipelines.

Use the **migrate** adapter when you need to inspect or migrate an existing
SparkForge definition without installing SparkForge or PySpark.

Use ETLantic directly when the pipeline does not need medallion vocabulary.
