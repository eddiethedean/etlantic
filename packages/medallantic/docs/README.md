# Medallantic documentation

Medallantic is the engine-agnostic medallion pipeline facade built on ETLantic.
It owns bronze, silver, and gold vocabulary while ETLantic supplies portable
contracts, graph validation, deterministic planning, runtime coordination,
reports, and plugin integration.

## Current status

Medallantic **0.34** includes the shipped M1–M6 milestones. It can:

- author bronze/silver/gold pipelines with `MedallionPipeline`,
  `MedallionBuilder`, `Bronze`, `Silver`, and `Gold`
- emit public `PipelineDefinition` / `etlantic.pipeline/1` documents
- parse secret-free SparkForge pipeline IR via
  `medallantic.migrate.sparkforge` (top-level `adapt_pipeline` remains)
- adapt live SparkForge `PipelineBuilder` and SQL `SqlPipelineBuilder`
  definitions through the explicit migration namespaces
- map medallion steps onto an ordinary ETLantic graph
- validate dependencies and reject cycles (`MDL1xx` / `PMSF*` diagnostics)
- map layer thresholds, write modes, retries, run intents, and selections
- enrich plans with write intents
- normalize legacy run results into `PipelineRunReport`
- verify declared Delta requirements against plugin capabilities
- pass `etlantic.testing.run_facade_conformance_suite`
- enforce portable `rules=` via `etlantic.quality/1` gates, with unsupported
  engine/capability combinations failing closed at plan time

It executes resolvable SparkForge-style transformation callables via
`medallantic.callables`. Native PySpark Column rules use
`quality.pyspark_column` / `MDL130`; Moltres-only rules use
`quality.moltres_expr` / `MDL132`. Both paths are capability-gated.

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
SparkForge or SQL pipeline-builder definition. Secret-free IR conversion does
not require the legacy package; live bridges do.

Use ETLantic directly when the pipeline does not need medallion vocabulary.
