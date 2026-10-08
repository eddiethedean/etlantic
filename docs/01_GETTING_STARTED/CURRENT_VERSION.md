---
title: ETLantic 0.56 Release Guide
status: available
since: "0.55.0"
current_minor: "0.56"
---

# ETLantic 0.56 Release Guide

> **Status: ETLantic 0.56.2 is the current published Beta release.**

ETLantic 0.56 completes the managed application ETL path, including durable
run control, worker execution, results, lineage, and recovery actions. This
0.56.2 is published on PyPI and GitHub Releases. The 0.56.x package line is
supported for controlled single-tenant pilots
and Supported control-plane isolation profiles. Explicit class-authored
pipelines remain the supported default.

Partition repair and backfill require configured PostgreSQL
partition columns and explicitly allowed capabilities. Unsupported providers
fail closed. See [What's new in 0.56](WHATS_NEW_0_56.md) and [Migration
0.55 → 0.56](../11_DEVELOPMENT/MIGRATION_0_55_TO_0_56.md).

## After first success

1. Optional: [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md)
2. [Capabilities](CAPABILITIES.md) — current capability and support boundaries
3. [What's new in 0.56](WHATS_NEW_0_56.md)
4. [Learning path](LEARNING_PATH.md)
5. [Upgrade](UPGRADE.md) for migration paths

Prefer `import etlantic as etl` for application code. See the [Quickstart](QUICKSTART.md)
for the CLI-first path and the [API reference](../10_REFERENCE/API_REFERENCE.md)
for public imports.
