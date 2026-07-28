# Exit Gate 0.31 — Execution, State, and Materialization (M3)

> **Status: Shipped in ETLantic 0.31.0.** Medallantic M3 execution and
> materialization parity land in **0.31.0**.

| Deliverable | Status |
|---|---|
| Callable `transform_ref` via ETLantic implementations | Done |
| STANDARD / INITIALIZE / INCREMENTAL / REFRESH / VALIDATE run intents | Done |
| `IncrementalStrategy` + `StateStore` (memory / file); commit-after-materialization | Done |
| Write intents including `skip_if_exists` + partition-replace capability checks | Done |
| Medallantic bronze preserve / silver refresh / gold publish defaults | Done |
| Accept-rate enforcement (`enforce_accept_rates` / `MDL120`) | Done |
| Lifecycle conformance suite (`run_lifecycle_conformance_suite`) | Done |
| Docs: What's New / Migration 0.30→0.31 / this exit gate | Done |
| Core + plugins + medallantic bumped to 0.31.0 | Done |

## Engine bar

- **Live:** local / Polars / Pandas for portable write modes advertised via
  `write.*` extras (append, overwrite, skip_if_exists, partition_replace where
  claimed).
- **SQL / PySpark:** advertise capabilities; unsupported write/state fail
  **before mutation** (`PMPLAN430` / `PMPLAN431`). Live merge/partition-replace
  remain plugin-gated.
- Quality `observed` port and live SQL/PySpark portable quality compilers stay
  deferred (0.30 residual / later minors).

## Acceptance checklist

- [x] `transform_ref` executes; `MDL111` only for unresolved/incompatible refs
- [x] VALIDATE forces `NO_WRITE` and does not commit watermarks
- [x] Failed / no-write runs do not advance `StateStore`
- [x] Unsupported write modes fail closed before mutation
- [x] Layer lifecycle defaults live in Medallantic only (no bronze/silver/gold
  in core wire schemas)
- [x] Lifecycle conformance suite green
- [x] What's New / Migration / this exit gate pass docs gates

## Residual / follow-ons (0.32+)

- Native PySpark Column rules and SparkForge differential parity (**M4 / 0.32**)
- Moltres / SQL builder differential parity (**M5 / 0.33**)
- Trend / quality analytics providers (**M6 / 0.34**)
- Quality `observed` port

## See also

- [ROADMAP § 0.31](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md#031--execution-state-and-materialization-semantics)
- [What's New 0.31](../01_GETTING_STARTED/WHATS_NEW_0_31.md)
- [Migration 0.30 → 0.31](MIGRATION_0_30_TO_0_31.md)
- [Exit gate 0.30](EXIT_GATE_0_30.md)
- [Medallantic roadmap](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/ROADMAP.md)
