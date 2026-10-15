---
title: ETLantic 0.59 Current Version Guide
status: available
since: "0.59.0"
current_minor: "0.59"
---

# ETLantic 0.59 Current Version Guide

> **Status: ETLantic core 0.59.0 is the published Beta release. The separately versioned `etlantic-rsconnect` 0.60.0 preview is published; live Connect activation and production qualification remain deferred.**

The latest published and supported **core** package line is 0.59.x. The separately
published [`etlantic-rsconnect` 0.60.0 preview](https://pypi.org/project/etlantic-rsconnect/0.60.0/)
integrates with core `etlantic>=0.59.0,<0.61.0`; it does not change the core
version or support line. See the [0.60 preview exit record](../11_DEVELOPMENT/EXIT_GATE_0_60.md)
for its release status and qualification boundaries. The 0.59.0 release
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
