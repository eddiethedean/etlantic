# ETLantic 0.48 User Guide

> **Status: Available in ETLantic 0.48.0 (shipped Beta).**

Use this page **after** Ada/Grace success on the docs home
[green path](../README.md). Do **not** start here for install.

ETLantic **0.48.0** is a **Beta** release for documented
single-tenant pilots. You can embed an HTTP control plane with **Supported**
isolation profiles (`isolated-deployment`, `dedicated-schema`). There is no
hosted multi-tenant SaaS. The line includes **human-governed AI**
context/proposals, the **scheduler/runner service and remote federation**,
the planner and optimization SDK, developer intelligence (LSP / IDE / notebooks
from 0.44), and **Supported** core streaming and dynamic-control contracts.
Kafka, schema-registry, Kubernetes, Spark Connect, and MCP extras remain
Experimental. `shared-service` remains Experimental. Support is community
**non-SLA**.

## After first success

1. Optional: [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md)
2. [Capabilities](CAPABILITIES.md) — what you can use today
3. [What's new in 0.48](WHATS_NEW_0_48.md)
4. [Learning path](LEARNING_PATH.md)
5. [Upgrade](UPGRADE.md) if migrating from an earlier minor

Prefer `import etlantic as etl` for application code. Agent helpers live
under `etl.agents`. Streaming contracts live
under `etl.streaming`. Resource providers live under `etl.resources`.
Optimization lives under `etl.optimization` (`etlantic.optimization/1`).
Portable quality rules live under `etl.quality`. Control-plane surfaces live
under `etl.control_plane`. IDE surfaces live under `etlantic.ide` with optional
`etlantic[lsp]` / `etlantic[notebook]`.

## Choose your next task

| Goal | Guide |
|---|---|
| Adopt human-governed AI | [Human-governed AI tutorial](HUMAN_GOVERNED_AI.md) / [What's new in 0.48](WHATS_NEW_0_48.md) |
| Adopt scheduler/runner and federation | [Scheduler tutorial](SCHEDULER_TUTORIAL.md) / [What's new in 0.47](WHATS_NEW_0_47.md) |
| Adopt streaming and dynamic control | [What's new in 0.46](WHATS_NEW_0_46.md) / [Migration 0.45 → 0.46](../11_DEVELOPMENT/MIGRATION_0_45_TO_0_46.md) |
| Adopt optimization SDK | [What's new in 0.45](WHATS_NEW_0_45.md) / [Migration 0.44 → 0.45](../11_DEVELOPMENT/MIGRATION_0_44_TO_0_45.md) / [ADR-021](../11_DEVELOPMENT/adr/ADR-021-OPTIMIZER-PASS-PROTOCOL.md) / [Optimization Passes](../07_PLUGIN_SDK/OPTIMIZATION_PASSES.md) |
