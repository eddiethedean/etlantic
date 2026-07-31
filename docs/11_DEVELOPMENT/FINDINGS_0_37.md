# Findings Ledger 0.37 — Stable Foundation

> **Status: Active ledger.** Record foundation, security, removal, testing
> graduation, acceptance-suite, and release-integrity findings for 0.37. Close a
> finding only when its regression test and durable evidence land. **P0 must
> be 0 before tag.**

## Severity policy

From [IMPLEMENTATION_PLAN_0_37](IMPLEMENTATION_PLAN_0_37.md):

| Severity | Meaning | Release treatment |
|---|---|---|
| **P0** | Foundation corruption, security boundary failure, silent semantic fallback, unexplained parity failure, unusable release artifact | Must close before 0.37 |
| **P1** | Material adoption, migration, performance, documentation, or support risk | Close or formally defer with owner, mitigation, target phase, and non-blocking rationale |
| **P2** | Localized usability or maintainability defect | May defer with owner and target |
| **P3** | Cosmetic or opportunistic improvement | Backlog |

Changing severity without written rationale does not close a finding.

## Locked dispositions

Carried forward from [FINDINGS_0_36](FINDINGS_0_36.md). Do not reopen without
a written finding and migration plan.

| Decision | Outcome | Notes |
|---|---|---|
| `etlantic.testing` | **Graduates** | Stable application-pipeline testing foundation in 0.37 |
| `etlantic.quality/1` | **Remains provisional** | Outside the full stable-foundation claim; ContractModel remains semantic authority |
| DataFusion / `etlantic-datafusion` | **Remains experimental** | No Gate B graduation; acceptance item 15 is non-blocking |
| Arrow interchange | **Gate A only** | Polars↔Pandas; acceptance item 14 does not claim Gate B |
| Demoted root aliases | **Removed** in 0.37.0 | Prefer owning-module or curated root imports |
| `DataContractModel` | **Removed** in 0.37.0 | Use `ContractModel` / `Data` |
| `etlantic.scheduler/1` | **Already stable MVP** | Prefect bounds unchanged from 0.36 |
| PyPI Beta classifier | **Retained** | Core and first-party packages stay Beta through foundation |

See also [Protocol evolution](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md) and
[Migration 0.36 → 0.37](MIGRATION_0_36_TO_0_37.md).

## Open findings

Open **P0 count is 0**. Deferred P1 residuals below do not block the in-tree
gate; they block announcement / consumer install until closed at tag time.

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| `037-REL-PYPI` | P1 | release maintainers | Open | PyPI does not yet serve `etlantic==0.37.0` (13/13 packages missing until tag workflow) | Non-blocking for in-tree gate; day-0 docs retain gate-ready PyPI pins per `check_docs`. Close on successful publish. |
| `037-REL-RTD` | P1 | release maintainers | Open | Immutable `/en/v0.37.0/` docs inactive/unbuilt (HTTP 404) | Non-blocking for in-tree gate; activate/build RTD version after tag. Same class of residual as 0.36 RTD activate. |
| `037-REL-ECHO-PIN` | P1 | release maintainers | Open | External `etlantic-plugin-echo` published pin still below `>=0.37,<0.38` | Workflow documents expected pin and installs `--no-deps`; bump in echo repo before announcing third-party conformance. |

## Closed in 0.37

| ID | Severity | Summary | Evidence |
|---|---|---|---|
| `037-DOC-WHATSNEW-HREF` | P1 | “What's new in 0.37” linked to `WHATS_NEW_0_36.md` | `CURRENT_VERSION.md`, `ALL_CURRENT_GUIDES.md`, `DOCUMENTATION_VERSIONING.md` |
| `037-DOC-DCM-LIVE` | P1 | Docs still described `DataContractModel` / demoted aliases as live | `API_REFERENCE.md`, `GLOSSARY.md`, `PROJECT_STRUCTURE.md`, `SURFACE_INVENTORY.md`, `surface-inventory.json`, `check_surface_inventory.py` |
| `037-DOC-VERSION-NAV` | P1 | Upgrade/nav/pin leftovers at 0.36 on current pages | CAPABILITIES, PILOT, DOCUMENTATION_STATUS, CURRENT_VERSION, UPGRADE, EARLIER_RELEASES, ENTERPRISE_EVALUATION, PORTABLE_COMPILER_MATRIX, FACADE_PACKAGES, RELEASE_PROCESS, WIRE_SCHEMA_RANGES, DEPRECATION_POLICY, ROADMAP_SUMMARY; datafusion stub string |
| `037-CI-MANIFEST-PATH` | P0 | Package job wrote candidate hashes to `v0_36/manifest.json` | `.github/workflows/checks.yml` → `v0_37/manifest.json` |
| `037-ODCS-DCM-MSG` | P2 | [ODCS](../03_DATA_CONTRACTS/ODCS.md) validator message named removed alias | `src/etlantic/interchange/odcs.py` |
| `037-SF-WEAK-ASSERT` | P1 | SF items 9/18/21 weak or no-op assertions; silent ImportError | `tests/stable_foundation/`; ResourceManager sync CM + zero-arg providers; `with_faults` arms injection env |
| `037-RES-SYNC-CM` | P0 | Sync resource context managers never entered/cleaned | `src/etlantic/lifecycle/resources.py` + SF-09 |

## Closure rules

1. Every P0 requires a regression test and linked durable evidence before
   severity can move or the finding can close.
2. Deferred P1 rows must name owner, target phase (usually 0.38+), mitigation,
   and why they do not block the stable foundation.
3. Do not reopen a locked disposition without an explicit finding ID and
   migration note.

## See also

- [Exit gate 0.37](EXIT_GATE_0_37.md)
- [Implementation plan 0.37](IMPLEMENTATION_PLAN_0_37.md)
- [Findings ledger 0.36](FINDINGS_0_36.md)
- [Removal candidates 0.37](REMOVAL_CANDIDATES_0_37.md)
