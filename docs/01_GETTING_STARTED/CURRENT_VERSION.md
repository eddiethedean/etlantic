# ETLantic 0.44 User Guide

> **Status: Available in ETLantic 0.44.0 (published Beta).**

Use this page **after** Ada/Grace success on the docs home
[green path](../README.md). Do **not** start here for install.

ETLantic **0.44.0** is a published **Beta** (PyPI) release for documented
single-tenant pilots, developer intelligence (LSP / IDE / notebooks), and
**production multi-tenant** for frozen Supported isolation profiles graduated
in **0.43** (`isolated-deployment`, `dedicated-schema`). `shared-service`
remains Experimental. Support is community **non-SLA**. Linked reference and
design pages may describe Experimental, partial, or future work and retain
their own status labels.

## After first success

1. Optional: [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md)
2. [Capabilities](CAPABILITIES.md) — what you can use today
3. [What's new in 0.44](WHATS_NEW_0_44.md)
4. [Learning path](LEARNING_PATH.md)
5. [Upgrade](UPGRADE.md) if migrating from an earlier minor

Prefer `import etlantic as etl` for application code. Portable quality rules live
under `etl.quality` (`etlantic.quality/1`). Control-plane identity, registry,
durable work, and CP4 governance live under `etl.control_plane` /
`etlantic.control_plane`. IDE surfaces live under `etlantic.ide` with optional
`etlantic[lsp]` / `etlantic[notebook]`.

## Choose your next task

| Goal | Guide |
|---|---|
| Adopt developer intelligence (LSP / IDE) | [What's new in 0.44](WHATS_NEW_0_44.md) / [Migration 0.43 → 0.44](../11_DEVELOPMENT/MIGRATION_0_43_TO_0_44.md) / [ADR-020](../11_DEVELOPMENT/adr/ADR-020-DEVELOPER-INTELLIGENCE.md) |
| Adopt CP-GA multi-tenant | [What's new in 0.43](WHATS_NEW_0_43.md) / [Migration 0.42 → 0.43](../11_DEVELOPMENT/MIGRATION_0_42_TO_0_43.md) / [CP-GA runbook](../11_DEVELOPMENT/CP_GA_OPERATOR_RUNBOOK_0_43.md) |
| Adopt CP4 policy / quotas / audit | [What's new in 0.42](WHATS_NEW_0_42.md) / [Migration 0.41 → 0.42](../11_DEVELOPMENT/MIGRATION_0_41_TO_0_42.md) / [CP4 runbook](../11_DEVELOPMENT/CP4_OPERATOR_RUNBOOK.md) |
| Adopt CP3 durable work | [What's new in 0.41](WHATS_NEW_0_41.md) / [Migration 0.40 → 0.41](../11_DEVELOPMENT/MIGRATION_0_40_TO_0_41.md) / [Durable work](../06_EXECUTION/DURABLE_WORK.md) |
| Adopt CP2 registry / revisions | [What's new in 0.40](WHATS_NEW_0_40.md) / [Migration 0.39 → 0.40](../11_DEVELOPMENT/MIGRATION_0_39_TO_0_40.md) |
| Embed control-plane HTTP API | [What's new in 0.43](WHATS_NEW_0_43.md) / `pip install etlantic-fastapi` |
| Inventory / migrate SparkForge projects | [What's new in 0.39](WHATS_NEW_0_39.md) / [SparkForge migration](../09_MEDALLANTIC/SPARKFORGE_MIGRATION.md) |
| Optional OpenLineage outbound | `pip install 'etlantic[openlineage]==0.44.0'` (Experimental) |

## Related

- [Installation](INSTALLATION.md)
- [Capabilities](CAPABILITIES.md)
- [Upgrade](UPGRADE.md)
- [Exit gate 0.44](../11_DEVELOPMENT/EXIT_GATE_0_44.md)
