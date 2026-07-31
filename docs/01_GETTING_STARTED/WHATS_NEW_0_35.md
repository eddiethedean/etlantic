# What's New in ETLantic 0.35

> **Status: Available in ETLantic 0.35.0.** Migration Completion and Joint Freeze
> (Medallantic **M7**): SparkForge inventory/generation, public authoring
> inspect/rewrite/provenance APIs, and an application-pipeline testing preview.

## Highlights

- **Migration tooling** — inventory a SparkForge project, emit a secret-free
  migration report, and generate native Medallantic definitions where safe
  (`python -m medallantic migrate inventory|generate`)
- **Authoring APIs** — `inspect_definition`, `rewrite_definition`, and
  `definition_provenance` for bounded, secret-free definition work
- **Testing preview** — `PipelineTestCase` / fixtures / snapshots under
  `etlantic.testing` (graduates at 0.37)
- **Joint freeze prep** — facade protocol/version `1` + generated-definition
  provenance; transitional adapters retained until a documented major

## Adopter actions

| Who | Action |
|---|---|
| Everyone on 0.35.x | Bump pins to `etlantic==0.35.0` and matching plugins / `medallantic==0.35.0` |
| SparkForge migrants | Run inventory before converting; prefer auto-safe IR generation |
| Test authors | Optional: try `etlantic.testing` pipeline cases (preview) |

## Not in 0.35

- Quantified joint upgrade burn-in (**0.36**)
- Stable application-pipeline testing foundation (**0.37**)
- Multi-tenant control plane (**0.39+**)
- Removal of transitional SparkForge adapters (major only)

## See also

- [Migration 0.34 → 0.35](../11_DEVELOPMENT/MIGRATION_0_34_TO_0_35.md)
- [Exit gate 0.35](../11_DEVELOPMENT/EXIT_GATE_0_35.md)
- [Medallantic SparkForge migration](../09_MEDALLANTIC/SPARKFORGE_MIGRATION.md)
