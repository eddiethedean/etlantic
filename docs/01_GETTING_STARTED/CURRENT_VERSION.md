---
title: ETLantic 0.57 Release Candidate Guide
status: candidate
since: "0.57.0"
current_minor: "0.57"
---

# ETLantic 0.57 Release Candidate Guide

> **Status: ETLantic 0.57.0 is in candidate qualification. ETLantic 0.56.2 remains the current published Beta release.**

ETLantic 0.57 adds the transport-independent managed backend, schedule service,
provider schema inspection, and role status/drain contracts. Publication is
pending the [0.57 exit gate](../11_DEVELOPMENT/EXIT_GATE_0_57.md). ETLantic
0.56.2 remains published on PyPI and GitHub Releases. The 0.56.x package line
is supported for controlled single-tenant pilots
and Supported control-plane isolation profiles. Explicit class-authored
pipelines remain the supported default.

Partition repair and backfill require configured PostgreSQL
partition columns and explicitly allowed capabilities. Unsupported providers
fail closed. See [What's new in 0.57](WHATS_NEW_0_57.md) and [Migration
0.56 → 0.57](../11_DEVELOPMENT/MIGRATION_0_56_TO_0_57.md).

## After first success

1. Optional: [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md)
2. [Capabilities](CAPABILITIES.md) — current capability and support boundaries
3. [What's new in 0.57](WHATS_NEW_0_57.md)
4. [Learning path](LEARNING_PATH.md)
5. [Upgrade](UPGRADE.md) for migration paths

Prefer `import etlantic as etl` for application code. See the [Quickstart](QUICKSTART.md)
for the CLI-first path and the [API reference](../10_REFERENCE/API_REFERENCE.md)
for public imports.
