# ETLantic 0.28 User Guide

Use this page **after** Ada/Grace success on the docs home
[green path](../README.md). Do **not** start here for install.

ETLantic **0.28.0** is a **Beta** (PyPI) release for documented single-tenant
pilots. Linked reference and design pages may describe Experimental, partial,
or future work and retain their own status labels.

## After first success

1. Optional: [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md)
2. [Capabilities](CAPABILITIES.md) — what you can use today
3. [What's new in 0.28](WHATS_NEW_0_28.md)
4. [Learning path](LEARNING_PATH.md)
5. [Upgrade](UPGRADE.md) if migrating from an earlier minor

Prefer `import etlantic as etl` for application code.

## Choose your next task

| Goal | Guide |
|---|---|
| Author without classes / JSON round trip | [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md) |
| Visual builder / service integration | [Application integration](../08_VISUALIZATION/APPLICATION_INTEGRATION.md) |
| FastAPI reference adapter | `pip install etlantic-fastapi` / [Application integration](../08_VISUALIZATION/APPLICATION_INTEGRATION.md) |
| Read and write JSON or CSV | [File storage](../06_EXECUTION/FILE_STORAGE_TUTORIAL.md) |
| Execute with Polars | [Polars tutorial](../06_EXECUTION/POLARS_TUTORIAL.md) |
| Upgrade from 0.27 | [Migration 0.27 → 0.28](../11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md) |
| Upgrade hub (all minors) | [Upgrade](UPGRADE.md) |
| Day-0 CLI / SDK reminders | [Cheatsheet](../10_REFERENCE/CHEATSHEET.md) |

## Status labels

Pages and tables use **Available**, **Partial**, **Experimental**, **Gap**,
and **Future design**. **Available** means supported for documented
single-tenant **Beta** pilots in 0.28—not a 1.0 production compatibility
guarantee.
