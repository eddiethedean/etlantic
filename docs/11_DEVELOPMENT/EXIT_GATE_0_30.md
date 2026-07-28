# Exit Gate 0.30 — Portable Quality and Rule Semantics (M2)

> **Status: Shipped in ETLantic 0.30.0.** Medallantic M2 portable quality and
> rule semantics land in **0.30.0**.

| Deliverable | Status |
|---|---|
| Provisional `etlantic.quality/1` AST + JSON Schema (portable core) | Done |
| ContractModel-backed mapping; no parallel schema/rule system | Done |
| Quality-gate plans: accepted/rejected ports, cost, fallback evidence (`observed` deferred) | Done |
| Plan-time fail-closed for unsupported required rules (`PMPLAN420`/`421`) | Done |
| Engine-independent quality conformance fixtures | Done |
| Live Polars + Pandas (+ local) for portable core | Done |
| SQL / PySpark capability ads + plan-time fail-closed (live subset classified) | Done |
| Medallantic shorthand DSL → quality AST; layer defaults; accept-rate helper | Done |
| Replace `MDL110` unenforced passthrough with real gate lowering | Done |
| Docs: What's New / Migration 0.29→0.30 / this exit gate | Done |
| Core + plugins + medallantic bumped to 0.30.0 | Done |

## Protocol and engine decisions

- **Protocol home:** provisional `etlantic.quality/1` in ETLantic; ContractModel
  is semantic authority. Do not block on ContractModel bounded-validation
  protocol first.
- **Engine bar:** live Polars/Pandas (+ local ContractModel path) for the
  portable core. SQL/PySpark advertise no portable `quality.*` extras by
  default and fail closed when required rules are present. Native PySpark
  Column / Moltres-only rules remain **0.32 / 0.33**.

## Acceptance checklist

- [x] Shared fixtures produce contract-equivalent decisions, accepted/rejected
  artifacts, counts, reasons, and diagnostics on every engine that advertises
  a given portable rule
- [x] Unsupported required rules fail at plan/analysis with stable diagnostics
  (never silently pass)
- [x] Polars and Pandas (plus local) are green for the portable core rule set
- [x] SQL and PySpark coverage is classified (live vs advertise+fail-closed)
  and CI-gated
- [x] Medallantic shorthand lowers to `etlantic.quality/1`; layer thresholds
  remain Medallantic policy
- [x] No bronze/silver/gold identifiers in core wire schemas
- [x] No second schema/rule system outside ContractModel authority
- [x] What's New / Migration 0.29→0.30 / this exit gate pass docs gates

## Residual / follow-ons (0.31+)

- Execution, state, and materialization parity (**M3 / 0.31**), including
  validation-only runs and transform_ref execution
- Native PySpark Column rules and SparkForge differential parity (**M4 / 0.32**)
- Moltres / SQL builder differential parity (**M5 / 0.33**)
- Trend / quality analytics providers (**M6 / 0.34**)
- ContractModel may later absorb or align `etlantic.quality/1`

## See also

- [ROADMAP § 0.30](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md#030--portable-quality-and-rule-semantics)
- [What's New 0.30](../01_GETTING_STARTED/WHATS_NEW_0_30.md)
- [Migration 0.29 → 0.30](MIGRATION_0_29_TO_0_30.md)
- [Exit gate 0.29](EXIT_GATE_0_29.md)
- [Roadmap summary](ROADMAP_SUMMARY.md)
- [Medallantic roadmap](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/ROADMAP.md)
- [Validation](../03_DATA_CONTRACTS/VALIDATION.md)
