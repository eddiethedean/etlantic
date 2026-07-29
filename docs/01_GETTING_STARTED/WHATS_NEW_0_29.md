# What's New in ETLantic 0.29

> **Status: Available in ETLantic 0.29.0.** Native Medallion Authoring
> (Medallantic **M1**): `MedallionPipeline` / builder surfaces lower to public
> `PipelineDefinition` with a shipped facade conformance kit.

## Highlights

- **Native medallion authoring** in `medallantic`: `MedallionPipeline`,
  `MedallionBuilder`, `Bronze`, `Silver`, and `Gold`
- Fluent and declarative/serialized definitions with partial pipelines,
  branches, prior-result references, cross-schema assets, tags, and
  deterministic names
- Stable facade diagnostics **`MDL1xx`** for construction and graph errors
- SparkForge IR isolated under **`medallantic.migrate.sparkforge`** (top-level
  `adapt_pipeline` / `ir` remain compatibility re-exports)
- Core **facade conformance kit**: `etlantic.testing.run_facade_conformance_suite`
  (JSON round-trip, graph equivalence, plan determinism, public-import check)
- `PipelineDefinition` extension bags validated on codec write; namespaced
  facade extensions survive validate → plan
- [Migration 0.28 → 0.29](../11_DEVELOPMENT/MIGRATION_0_28_TO_0_29.md) and
  [Exit gate 0.29](../11_DEVELOPMENT/EXIT_GATE_0_29.md)

## Not in 0.29

- Portable quality / rule DSL (**0.30 / M2**)
- Live callable execution and write lifecycle parity (**0.31 / M3**)
- Remaining demoted root aliases (still a 0.38 residual)
- New burn-in fixture slice (next burn-in band is **0.36+**)

## Upgrade

Pin core and plugins to the same minor:

```bash
python -m pip install --upgrade 'etlantic==0.29.0'
python -m pip install --upgrade 'medallantic==0.29.0'
```

See [Upgrade hub](UPGRADE.md) and [Facade packages](../11_DEVELOPMENT/FACADE_PACKAGES.md).
