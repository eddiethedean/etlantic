---
title: ETLantic 0.55 User Guide
status: candidate
since: "0.55.0"
current_minor: "0.55"
---

# ETLantic 0.55 User Guide

> **Status: 0.55.0 Beta release candidate; publication pending.** ETLantic
> 0.54.0 remains the latest published package until the 0.55.0 tag is
> released.

ETLantic 0.55 continues the documented Beta envelope for controlled
single-tenant pilots and Supported control-plane isolation profiles. It adds
Experimental, evidence-qualified data-first authoring and inferred models.
Explicit class-authored pipelines remain the supported default.

The inferred-model feature covers bounded records, CSV, JSON, Pandas, and
Polars paths plus the scoped metadata and SQLite target adapters listed in the
[0.55 qualification gate](../11_DEVELOPMENT/EXIT_GATE_0_55.md). It does not
make unsupported providers or write modes available. See [What's new in
0.55](WHATS_NEW_0_55.md) and [Migration 0.54 → 0.55](../11_DEVELOPMENT/MIGRATION_0_54_TO_0_55.md).

## After first success

1. Optional: [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md)
2. [Capabilities](CAPABILITIES.md) — current capability and support boundaries
3. [What's new in 0.55](WHATS_NEW_0_55.md)
4. [Learning path](LEARNING_PATH.md)
5. [Upgrade](UPGRADE.md) for migration paths

Prefer `import etlantic as etl` for application code. See the [Quickstart](QUICKSTART.md)
for the CLI-first path and the [API reference](../10_REFERENCE/API_REFERENCE.md)
for public imports.
