---
title: ETLantic 0.60 Candidate Version Guide
status: candidate
since: "0.60.0"
current_minor: "0.60"
---

# ETLantic 0.60 Candidate Version Guide

> **Status: Core 0.60.0 is an unpublished Beta candidate. The latest published and supported core line remains 0.59.x.**

The candidate adds public durable-dispatch contracts used by the optional
`etlantic-aws` 0.61 adapter. The AWS adapter is locally implemented, while live
AWS qualification and production support remain deferred. See [What's new in
0.60](WHATS_NEW_0_60.md), [Migration 0.59 → 0.60](../11_DEVELOPMENT/MIGRATION_0_59_TO_0_60.md),
and the [0.61 implementation plan](../11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_61.md).

The separately published [`etlantic-rsconnect` 0.60.0 preview](https://pypi.org/project/etlantic-rsconnect/0.60.0/)
was released while core remained at 0.59.0 and accepts `etlantic>=0.59.0,<0.61.0`.
Its publication does not qualify live Connect activation or production support;
see the [preview exit record](../11_DEVELOPMENT/EXIT_GATE_0_60.md).
The workspace carries a 0.60.1 adapter candidate with core compatibility
`etlantic>=0.60.0,<0.61.0`; existing deployed 0.60.0 bundles need the paused
resume upgrade described in the [Connect adapter migration guide](../11_DEVELOPMENT/MIGRATION_RSCONNECT_0_60_1.md).

For an install available from PyPI today, use the [0.59 release notes](WHATS_NEW_0_59.md),
[Migration 0.58 → 0.59](../11_DEVELOPMENT/MIGRATION_0_58_TO_0_59.md), and the
[Quickstart](QUICKSTART.md). Prefer `import etlantic as etl` for application code.
