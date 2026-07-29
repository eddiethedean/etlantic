# Exit Gate 0.32 — PySpark and Delta Differential Parity (M4)

> **Status: Shipped in ETLantic 0.32.0.** Medallantic M4 PySpark/SparkForge
> differential parity lands in **0.32.0**.

| Deliverable | Status |
|---|---|
| `storage.delta.*` vocabulary + `PMPLAN440`/`441` | Done |
| Spark protocol: cancel, cache/checkpoint, logical-step identity | Done |
| Catalog mutation policy + JDBC/asset binding refs | Done |
| `etlantic-pyspark` Delta ops + truthful caps | Done |
| Live `PipelineBuilder` bridge (`from_pipeline_builder`) | Done |
| PySpark df→df callables + Column rules (`MDL130`) | Done |
| Runtime map overrides + invalidation | Done |
| SparkForge differential suite + classifications | Done |
| Docs: What's New / Migration 0.31→0.32 / this exit gate | Done |
| Core + plugins + medallantic bumped to 0.32.0 | Done |

## Engine bar

- **Sparkless (default CI):** differential corpus, capability fail-closed,
  callable/Column plan gates green.
- **Real PySpark / Delta:** advertised `storage.delta.*` semantics when
  `delta-spark` is installed; otherwise fail closed with stable diagnostics
  (set `ETLANTIC_DELTA_LIVE=1` for optional live suites).
- **Core remains free of Spark/Delta dependencies.**

## Acceptance checklist

- [x] Every in-tree SparkForge fixture classified equivalent /
  plugin_dependent / intentionally_rejected
- [x] Live bridge extracts secret-free IR (no passwords/tokens in metadata)
- [x] Native Column rules fail closed off Spark (`MDL130`)
- [x] Maintenance ops are not planned as generic `write.*` modes
- [x] `run_sparkforge_differential_suite` green
- [x] What's New / Migration / this exit gate pass docs gates

## Residual / follow-ons (0.34+)

- Trend / quality analytics providers (**M6 / 0.34**)
- Automated migration inventory (**M7 / 0.35**)

## See also

- [ROADMAP § 0.32](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md#032--pyspark-and-delta-differential-parity)
- [What's New 0.32](../01_GETTING_STARTED/WHATS_NEW_0_32.md)
- [Migration 0.31 → 0.32](MIGRATION_0_31_TO_0_32.md)
- [Exit gate 0.31](EXIT_GATE_0_31.md)
- [Medallantic roadmap](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/ROADMAP.md)
