# ETLantic 0.41 User Guide

> **Status: Available in ETLantic 0.41.0.**

Use this page **after** Ada/Grace success on the docs home
[green path](../README.md). Do **not** start here for install.

ETLantic **0.41.0** is a **Beta** (PyPI) release for documented single-tenant
pilots plus CP3 durable-work incubation. **CP3 is not production
multi-tenant isolation** (**0.43**). Linked reference and design pages may
describe Experimental, partial, or future work and retain their own status
labels.

## After first success

1. Optional: [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md)
2. [Capabilities](CAPABILITIES.md) — what you can use today
3. [What's new in 0.41](WHATS_NEW_0_41.md)
4. [Learning path](LEARNING_PATH.md)
5. [Upgrade](UPGRADE.md) if migrating from an earlier minor

Prefer `import etlantic as etl` for application code. Portable quality rules live
under `etl.quality` (`etlantic.quality/1`). Control-plane identity, registry,
and durable work live under `etl.control_plane` / `etlantic.control_plane`.

## Choose your next task

| Goal | Guide |
|---|---|
| Adopt CP3 durable work | [What's new in 0.41](WHATS_NEW_0_41.md) / [Migration 0.40 → 0.41](../11_DEVELOPMENT/MIGRATION_0_40_TO_0_41.md) / [Durable work](../06_EXECUTION/DURABLE_WORK.md) |
| Adopt CP2 registry / revisions | [What's new in 0.40](WHATS_NEW_0_40.md) / [Migration 0.39 → 0.40](../11_DEVELOPMENT/MIGRATION_0_39_TO_0_40.md) |
| Embed control-plane HTTP API | [What's new in 0.41](WHATS_NEW_0_41.md) / `pip install etlantic-fastapi` |
| Inventory / migrate SparkForge projects | [What's new in 0.39](WHATS_NEW_0_39.md) / [SparkForge migration](../09_MEDALLANTIC/SPARKFORGE_MIGRATION.md) |
| Optional OpenLineage outbound | `pip install 'etlantic[openlineage]==0.41.0'` (Experimental) |

## Related

- [Installation](INSTALLATION.md)
- [Capabilities](CAPABILITIES.md)
- [Exit gate 0.41](../11_DEVELOPMENT/EXIT_GATE_0_41.md)
- [Earlier releases](EARLIER_RELEASES.md)
