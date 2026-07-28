# Medallantic documentation

Medallantic is the engine-agnostic medallion pipeline facade built on ETLantic.
It owns bronze, silver, and gold vocabulary while ETLantic supplies portable
contracts, graph validation, deterministic planning, runtime coordination,
reports, and plugin integration.

## Current status

Medallantic 0.27 is a migration and planning adapter. It can:

- parse secret-free SparkForge pipeline IR
- map medallion steps onto an ordinary ETLantic graph
- validate dependencies and reject cycles
- map layer thresholds, write modes, retries, run intents, and selections
- enrich plans with write intents
- normalize legacy run results into `PipelineRunReport`
- verify declared Delta requirements against plugin capabilities

It does not yet execute SparkForge transformation callables or enforce legacy
rule expressions. Those paths currently produce `PMSF411` warnings and use
passthrough transformations for planning parity.

## Documentation map

- [Getting started](getting-started.md) — install, adapt, validate, and plan
- [Core concepts](concepts.md) — ownership and medallion-to-ETLantic mapping
- [SparkForge migration](sparkforge-migration.md) — IR conversion workflow
- [Runtime and reports](runtime-and-reports.md) — selections, retries, and results
- [Compatibility](compatibility.md) — supported mappings and current limits
- [Architecture](architecture.md) — package boundaries and extension rules
- [Development](development.md) — local tests and contribution constraints
- [Roadmap](../ROADMAP.md) — native builder and full-parity milestones

## Choose the right starting point

Use the current adapter when you need to inspect or migrate an existing
SparkForge definition without installing SparkForge or PySpark.

Use ETLantic directly when the pipeline does not need medallion vocabulary.

Do not design against planned APIs such as `MedallionPipeline` yet. Planned
examples become supported only after their milestone acceptance tests pass.

