# What's New in ETLantic 0.32

> **Status: Available in ETLantic 0.32.0.** PySpark and Delta Differential Parity
> (Medallantic **M4**): storage capability vocabulary, live SparkForge bridge,
> Column rules, and classified differential fixtures.

## Highlights

- **`storage.delta.*` extras** for merge / optimize / vacuum / history /
  time travel / schema evolution (not generic writes); plan fail-closed
  `PMPLAN440` / `PMPLAN441`
- Spark protocol hardening: cancel, cache/checkpoint points, logical-step
  identity, catalog mutation policy, JDBC/asset binding refs
- **`etlantic-pyspark`**: truthful Delta storage ops, region execute, cancel;
  Sparkless default + optional live Delta (`ETLANTIC_DELTA_LIVE`)
- Medallantic **live `PipelineBuilder` bridge**
  (`medallantic.migrate.sparkforge.from_pipeline_builder`)
- Real PySpark **df→df callables**; non-portable **Column rules**
  (`quality.pyspark_column`, `MDL130`)
- Runtime map: implementation overrides + invalidation modes
- Differential suite: `etlantic.testing.run_sparkforge_differential_suite`
  (equivalent / plugin_dependent / intentionally_rejected)
- [Migration 0.31 → 0.32](../11_DEVELOPMENT/MIGRATION_0_31_TO_0_32.md) and
  [Exit gate 0.32](../11_DEVELOPMENT/EXIT_GATE_0_32.md)

## Not in 0.32

- SQL / `SqlPipelineBuilder` differential (**0.33 / M5**)
- Trend / quality analytics providers (**0.34**)
- Automated SparkForge project inventory (**0.35**)
- Moltres-only rules

## Upgrade

Pin core and plugins to the same minor:

```bash
python -m pip install --upgrade 'etlantic==0.32.0'
python -m pip install --upgrade 'medallantic==0.32.0'
```

Plugin authors: pin `etlantic>=0.32.0,<0.33`.
