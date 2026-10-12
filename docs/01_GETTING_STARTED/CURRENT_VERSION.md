---
title: ETLantic 0.58 Release Candidate Guide
status: available
since: "0.58.0"
current_minor: "0.58"
---

# ETLantic 0.58 Release Candidate Guide

> **Status: ETLantic 0.58.0 Beta release candidate; publication is pending.**

The latest published and supported package line is 0.57.x. This 0.58.0
candidate adds an opt-in managed Prefect path for the bounded support profile
in the [qualification decision](../11_DEVELOPMENT/evidence/phase_0_58/FINAL_QUALIFICATION_DECISION_2026-10-12.json).
Its [exit gate](../11_DEVELOPMENT/EXIT_GATE_0_58.md) records the release
checks. Explicit class-authored pipelines and direct Prefect execution remain
available.

See [What's new in 0.58](WHATS_NEW_0_58.md), [Migration 0.57 → 0.58](../11_DEVELOPMENT/MIGRATION_0_57_TO_0_58.md),
and [What's new in 0.57](WHATS_NEW_0_57.md) for the latest published release.

## After first success

1. Optional: [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md)
2. [Capabilities](CAPABILITIES.md) — current capability and support boundaries
3. [What's new in 0.58](WHATS_NEW_0_58.md) (release candidate)
4. [What's new in 0.57](WHATS_NEW_0_57.md) (latest published release)
5. [Learning path](LEARNING_PATH.md)
6. [Upgrade](UPGRADE.md) for migration paths

Prefer `import etlantic as etl` for application code. See the [Quickstart](QUICKSTART.md)
for the CLI-first path and the [API reference](../10_REFERENCE/API_REFERENCE.md)
for public imports.
