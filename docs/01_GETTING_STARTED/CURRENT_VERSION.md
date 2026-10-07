---
title: ETLantic 0.56 Candidate Guide
status: candidate
since: "0.55.0"
current_minor: "0.56"
---

# ETLantic 0.56 Candidate Guide

> **Status: ETLantic 0.56.0 is a candidate; 0.55.0 remains the latest published Beta release.**

ETLantic 0.56 completes the managed application ETL path, including durable
run control, worker execution, results, lineage, and recovery actions. This
source tree is a qualification candidate, not a published installation target.
The 0.55.x package line remains supported for controlled single-tenant pilots
and Supported control-plane isolation profiles. Explicit class-authored
pipelines remain the supported default.

Partition repair and backfill in the candidate require configured PostgreSQL
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
