# Medallantic

Medallantic is ETLantic's engine-agnostic medallion facade. It owns
bronze/silver/gold vocabulary and conventions while ETLantic supplies portable
contracts, graph validation, deterministic planning, execution coordination,
reports, and plugin integration.

```text
Medallantic
  bronze • silver • gold • layer defaults • SparkForge migration
                              ↓
ETLantic
  contracts • graph • validation • plan • lifecycle • evidence • trust
                              ↓
Plugins and providers
  local • Polars • Pandas • SQL • PySpark • storage • orchestration
```

!!! important
    Medallion semantics remain in `medallantic`. ETLantic core does not acquire
    bronze, silver, gold, or medallion-specific runtime branches.

## What ships in 0.39

- native class and fluent-builder authoring
- deterministic lowering to public `PipelineDefinition`
- portable `rules=` quality gates
- importable `transform_ref` execution
- bronze preserve, silver refresh, and gold publish lifecycle defaults
- write-intent, run-intent, selection, retry, and report mapping
- secret-free SparkForge IR migration **and** live `from_pipeline_builder`
- fine-grained `storage.delta.*` capability map + classified differential suite
- PySpark Column / callable rule path (`MDL130` fail-closed off Spark)
- SQLAlchemy / `SqlPipelineBuilder` live bridge + dialect tiers (M5)
- Non-portable Moltres / SQLAlchemy rules (`quality.moltres_expr`)
- **M6 elevation:** `explain_medallion_plan`, layer lifecycle views, and
  alignment with core observability / run-history pilot surfaces
- stable `MDL*` diagnostics and facade conformance

Native PySpark Column and Moltres-only semantics remain subject to their
documented compatibility and differential gates.

## Choose a path

| Goal | Guide |
|---|---|
| Install and build a first pipeline | [Getting started](GETTING_STARTED.md) |
| Choose class or builder authoring | [Native authoring](AUTHORING.md) |
| Add portable layer rules | [Quality rules](QUALITY.md) |
| Plan and run a lowered pipeline | [Execution and reports](EXECUTION.md) |
| Move an existing SparkForge definition | [SparkForge migration](SPARKFORGE_MIGRATION.md) |
| Check engines, versions, and write modes | [Compatibility](COMPATIBILITY.md) |
| Diagnose a failure | [Troubleshooting](TROUBLESHOOTING.md) |
| Understand ownership boundaries | [Architecture](ARCHITECTURE.md) |
| Browse public symbols | [API reference](API_REFERENCE.md) |

Use Medallantic for an opinionated medallion architecture. Use ETLantic
directly when a pipeline does not need that vocabulary.
