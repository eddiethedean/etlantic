# ETLantic 0.25 User Guide

This is the current manual for ETLantic **0.25.1** — use it **after** first
success on the docs home [green path](../README.md). Core onboarding paths below
are available in 0.25; linked reference and design pages may also describe
Experimental, partial, or future work and retain their own status labels.
**Supported for documented single-tenant pilots (Beta).** This is not a 1.0
compatibility guarantee.

## After first success

1. [Install core](INSTALLATION.md) — Python 3.11+ and `pip install etlantic==0.25.1`
2. [Quickstart](QUICKSTART.md) — first validate → run (then the required aha)
3. [Build your first pipeline](FIRST_PIPELINE.md)
4. [Choose an engine](ENGINE_SELECTION.md)
5. Optional: [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md)

Next: [Capabilities](CAPABILITIES.md),
[What's new in 0.25](WHATS_NEW_0_25.md), [Compare](COMPARE.md), or
[Upgrade](UPGRADE.md). Prefer `import etlantic as etl` for application code.

## Choose your next task

| Goal | Guide |
|---|---|
| Author without classes / JSON round trip | [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md) |
| Visual builder / service integration | [Application integration](../08_VISUALIZATION/APPLICATION_INTEGRATION.md) |
| FastAPI reference adapter | `pip install etlantic-fastapi` / [Application integration](../08_VISUALIZATION/APPLICATION_INTEGRATION.md) |
| Read and write JSON or CSV | [File storage](../06_EXECUTION/FILE_STORAGE_TUTORIAL.md) |
| Execute with Polars | [Polars tutorial](../06_EXECUTION/POLARS_TUTORIAL.md) |
| Upgrade from 0.24 | [Migration 0.24 → 0.25](../11_DEVELOPMENT/MIGRATION_0_24_TO_0_25.md) |
| Day-0 CLI / SDK reminders | [Cheatsheet](../10_REFERENCE/CHEATSHEET.md) |

## Status labels

Pages and tables use **Available**, **Partial**, **Experimental**, **Gap**,
and **Future design**. **Available** means supported for documented
single-tenant **Beta** pilots in 0.25—not a 1.0 production compatibility
guarantee.
