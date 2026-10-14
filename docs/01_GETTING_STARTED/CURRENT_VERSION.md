---
title: ETLantic 0.59 Current Version Guide
status: available
since: "0.59.0"
current_minor: "0.59"
---

# ETLantic 0.59 Current Version Guide

> **Status: ETLantic 0.59.0 is the published Beta release; external qualification campaigns for its new managed runtime and trigger capabilities are deferred.**

The latest published and supported package line is 0.59.x. The 0.59.0 release
consolidates managed configuration, dispatch, persistence, and
schedule ownership, and adds an external schedule-trigger contract. Its
[exit gate](../11_DEVELOPMENT/EXIT_GATE_0_59.md) tracks release qualification.
The 0.58 managed Prefect profile remains documented in its
[qualification decision](../11_DEVELOPMENT/evidence/phase_0_58/FINAL_QUALIFICATION_DECISION_2026-10-12.json);
that evidence does not qualify the new 0.59 changes.

See [What's new in 0.59](WHATS_NEW_0_59.md), [Migration 0.58 → 0.59](../11_DEVELOPMENT/MIGRATION_0_58_TO_0_59.md),
and [What's new in 0.57](WHATS_NEW_0_57.md) for the previous published release.

## After first success

1. Optional: [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md)
2. [Capabilities](CAPABILITIES.md) — current capability and support boundaries
3. [What's new in 0.59](WHATS_NEW_0_59.md) (current published release)
4. [What's new in 0.57](WHATS_NEW_0_57.md) (previous published release)
5. [Learning path](LEARNING_PATH.md)
6. [Upgrade](UPGRADE.md) for migration paths

Prefer `import etlantic as etl` for application code. See the [Quickstart](QUICKSTART.md)
for the CLI-first path and the [API reference](../10_REFERENCE/API_REFERENCE.md)
for public imports.
