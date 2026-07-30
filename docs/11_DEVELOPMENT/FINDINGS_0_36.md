# Findings Ledger 0.36 — Joint Compatibility Burn-In

> **Status: Active ledger.** Record compatibility, security, parity,
> migration, and release-integrity findings for the 0.36 burn-in. Close a
> finding only when its regression test and durable evidence land. **P0 must
> be 0 before tag.**

## Severity policy

From [IMPLEMENTATION_PLAN_0_36](IMPLEMENTATION_PLAN_0_36.md):

| Severity | Meaning | Release treatment |
|---|---|---|
| **P0** | Compatibility corruption, security boundary failure, silent semantic fallback, unexplained parity failure, unusable release artifact | Must close before 0.36 |
| **P1** | Material adoption, migration, performance, documentation, or support risk | Close or formally defer with owner, mitigation, target phase, and non-blocking rationale |
| **P2** | Localized usability or maintainability defect | May defer with owner and target |
| **P3** | Cosmetic or opportunistic improvement | Backlog |

Changing severity without written rationale does not close a finding.

## Locked decisions

These answers close the Wave 2 open-decision set for 0.36:

| Decision | Outcome | Notes |
|---|---|---|
| `etlantic.scheduler/1` | **Stable MVP** on the foundation path | Prefect-bounded direct-execution evidence; Airflow remains compile-only |
| `etlantic.quality/1` | **Remains provisional** | Wire schema outside the full stable-foundation claim; ContractModel remains semantic authority |
| `etlantic.testing` preview | **Minimum contract frozen** for burn-in | Foundation graduation remains **0.38** |
| 0.35 upgrade baseline | **Both `0.35.0` and newest `0.36.x`** | Preserve 0.35.0 known-defect fixtures even if a forward-fix patch ships |
| SQL portable intersection | **SQLite** evaluation set is portable | PostgreSQL-only behavior stays capability-gated |
| DataFusion | **No graduation** | Remains experimental Gate B; same applicable gates required before any future claim |

See also [Protocol evolution](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md)
(0.36 decision section) and
[Migration 0.35 → 0.36](MIGRATION_0_35_TO_0_36.md).

## Known tracked defect (0.35.0 baseline)

| ID | Severity | State | Summary | Evidence |
|---|---|---|---|---|
| `036-KD-REPORT-BARE-META` | P1 (compat) when unmigrated; treat load failure / silent loss as P0 | Tracked | 0.35.0 run reports may emit bare (non-namespaced) metadata keys that warn on load; 0.36 must migrate to namespaced keys without semantic loss | `tests/fixtures/releases/v0_35/known_defects/run_report_bare_metadata.json` and `tests/fixtures/releases/v0_35/known_defects/README.md` |

A patch release does not erase compatibility responsibility for already-published
0.35.0 artifacts. Keep the 0.35.0 fixture even when measuring against a newer
0.36.x forward-fix baseline.

## Open findings

No additional open P0–P3 findings are recorded in this ledger yet.

Maintainers: append rows below as burn-in work proceeds.

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| — | — | — | — | *(none yet)* | P0 count must remain **0** before tag |

## Closure rules

1. Every P0 requires a regression test and linked durable evidence before
   severity can move or the finding can close.
2. Deferred P1 rows must name owner, target phase (usually 0.37/0.38),
   mitigation, and why they do not block the 0.38 stable foundation.
3. Do not hide 0.35 published defects behind current-tree fixes — preserve
   fixtures under `tests/fixtures/releases/`.

## See also

- [Exit gate 0.36](EXIT_GATE_0_36.md)
- [Implementation plan 0.36](IMPLEMENTATION_PLAN_0_36.md)
- [Wire schema ranges](../10_REFERENCE/WIRE_SCHEMA_RANGES.md)
