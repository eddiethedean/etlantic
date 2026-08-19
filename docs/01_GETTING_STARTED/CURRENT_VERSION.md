# ETLantic 0.48 User Guide

> **Status: Available in ETLantic 0.48.0 (published Beta).**

Use this page **after** Ada/Grace success on the docs home
[green path](../README.md). Do **not** start here for install.

ETLantic **0.48.0** is a gate-ready **Beta** release for documented
single-tenant pilots, **human-governed AI** context/proposals, the
**scheduler/runner service and remote federation**,
the planner and optimization SDK, developer intelligence (LSP / IDE / notebooks
from 0.44), **Supported** core streaming and dynamic control contracts, and
**production multi-tenant** for frozen Supported isolation profiles graduated
in **0.43** (`isolated-deployment`, `dedicated-schema`). Kafka, schema-registry,
Kubernetes, Spark Connect, and MCP extras remain Experimental. `shared-service`
remains Experimental. Support is community **non-SLA**. Linked reference and
design pages may describe Experimental, partial, or future work and retain
their own status labels.

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
| Adopt human-governed AI | [What's new in 0.48](WHATS_NEW_0_48.md) / [Migration 0.47 → 0.48](../11_DEVELOPMENT/MIGRATION_0_47_TO_0_48.md) / [ADR-024](../11_DEVELOPMENT/adr/ADR-024-HUMAN-GOVERNED-AI.md) |
| Adopt scheduler/runner and federation | [What's new in 0.47](WHATS_NEW_0_47.md) / [Migration 0.46 → 0.47](../11_DEVELOPMENT/MIGRATION_0_46_TO_0_47.md) / [ADR-023](../11_DEVELOPMENT/adr/ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md) |
| Adopt streaming and dynamic control | [What's new in 0.46](WHATS_NEW_0_46.md) / [Migration 0.45 → 0.46](../11_DEVELOPMENT/MIGRATION_0_45_TO_0_46.md) |
| Adopt optimization SDK | [What's new in 0.45](WHATS_NEW_0_45.md) / [Migration 0.44 → 0.45](../11_DEVELOPMENT/MIGRATION_0_44_TO_0_45.md) / [ADR-021](../11_DEVELOPMENT/adr/ADR-021-OPTIMIZER-PASS-PROTOCOL.md) / [Optimization Passes](../07_PLUGIN_SDK/OPTIMIZATION_PASSES.md) |
