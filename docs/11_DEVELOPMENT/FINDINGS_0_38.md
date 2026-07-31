# Findings Ledger 0.38 — Data Connectivity and Connector SDK

> **Status: Gate-ready for tag/publish rehearsal toward ETLantic 0.38.0.**
> Ledger for the 0.38 connectivity program. Record protocol, planning,
> landing-zone, publication, reference-provider, conformance, and
> release-integrity findings. Close a finding only when its regression test
> and durable evidence land. **P0 must be 0 before tag.** Package version is
> **0.38.0**.

## Severity policy

From [IMPLEMENTATION_PLAN_0_38](IMPLEMENTATION_PLAN_0_38.md):

| Severity | Meaning | Release treatment |
|---|---|---|
| **P0** | Secret/trust failure, silent semantic fallback, partial publication exposed, unsafe cursor advance, unusable artifact | Must close before 0.38 |
| **P1** | Material compatibility, correctness, cleanup, adoption, cost, or support risk | Close or defer with owner, mitigation, target phase, and non-blocking rationale |
| **P2** | Localized usability, performance, or maintainability defect | May defer with owner and target |
| **P3** | Cosmetic or opportunistic improvement | Backlog |

Changing severity without written rationale does not close a finding.

## Locked dispositions

Recorded in
[ADR-015: Connector Protocols](adr/ADR-015-CONNECTOR-PROTOCOLS.md). Do not
reopen without a written finding and migration plan.

| Decision | Outcome | Notes |
|---|---|---|
| Protocol families | `etlantic.source/1`, `etlantic.sink/1`, `etlantic.storage/1` | Entry points `etlantic.source_connectors`, `etlantic.sink_connectors`, `etlantic.storage_connectors` |
| Public package | `etlantic.connectors` | Runtime-checkable, async-first |
| Capability spellings | Frozen vocabulary in ADR-015 | Landing tokens + write/publication/transactions/reconciliation |
| Plan vs runtime evidence | Static plan records identity **scheme** only | Concrete files in `LandingReadManifest` / run report |
| Checkpoint schema | `etlantic.landing_checkpoint/1` | No rows, credentials, or absolute paths |
| Reference set | local-files built-in; `etlantic-s3`, `etlantic-iceberg`, `etlantic-snowflake`; PostgreSQL via `etlantic-sql` | Vendor SDKs stay out of core |
| StorageBinding | Compatibility adapter only | No silent connector capability claims |
| Continuous watch | Out of core | Compose in 0.39+ against same bindings |

## Maturity classifiers (038-M)

| Provider | Maturity | Classifier | Notes |
|---|---|---|---|
| `local-files` | Preview | Beta (core) | Snapshot + incremental fake/CI green |
| `s3` | Experimental | Alpha (`etlantic-s3`) | Fake multipart/conditional commit |
| `iceberg` | Experimental | Alpha (`etlantic-iceberg`) | Fake catalog; snapshot id publication |
| `snowflake` | Experimental | Alpha (`etlantic-snowflake`) | Fake autocommit=False + query_id |
| `postgresql` | Experimental | Beta package / Experimental connector path | Via `etlantic-sql` |

Matrix artifact:
[CONNECTOR_CAPABILITY_MATRIX_0_38.json](CONNECTOR_CAPABILITY_MATRIX_0_38.json).

## Wave 7 burn-in results

| ID | Result | Evidence |
|---|---|---|
| `038-A01` | Pass | Same logical pipeline under local-files / s3 / snowflake profiles — topology stable; resolutions differ (`tests/connectors/test_cross_provider_0_38.py`) |
| `038-A17` | Pass | Snapshot ↔ incremental mode switch without Extract rewrite |
| `038-A19` | Pass | Matrix caps match connector `info()` for local, s3, iceberg, snowflake, postgresql |
| `038-A20` / `038-X-01` | Soft-continue | In-repo third-party EP stub + public-import check; echo plugin PyPI proof deferred |
| Fake conformance | Pass | `scripts/check_connector_conformance.py --fake` |

## Open findings

Open **P0 count is 0**.

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| `038-X-01` | P1 | Ecosystem maintainers + echo plugin maintainer | Soft-continue (disposed for exit) | Independent third-party connector on distinct repo/CI not yet on PyPI | **Selection:** extend [`etlantic-plugin-echo`](https://github.com/eddiethedean/etlantic-plugin-echo) with `etlantic.source_connectors`. **Mitigation:** in-repo `tests/connectors/third_party_echo.py` loads via EP monkeypatch, public imports only, info conformance green; first-party `--fake` covers protocol proof. **Does not block** 0.38 tag. Target: echo repo EP before first Supported cloud promotion / 0.39. Non-blocking rationale: exit scorecard independent-connector cell satisfied by in-repo governance-separated stub + soft-continue disposition. |

## Closed in 0.38

| ID | Severity | Summary | Evidence |
|---|---|---|---|
| — | — | *(no P0 opened during Waves 1–8)* | Wave 7 burn-in + exit scorecard |

## Closure rules

1. Every P0 requires a regression test and linked durable evidence before
   severity can move or the finding can close.
2. Deferred P1 rows must name owner, target phase (usually 0.39+), mitigation,
   and why they do not block the 0.38 exit.
3. Do not reopen a locked disposition without an explicit finding ID and
   migration note.

## See also

- [Exit gate 0.38](EXIT_GATE_0_38.md)
- [Implementation plan 0.38](IMPLEMENTATION_PLAN_0_38.md)
- [Migration 0.37 → 0.38](MIGRATION_0_37_TO_0_38.md)
- [What's New in 0.38](../01_GETTING_STARTED/WHATS_NEW_0_38.md)
- [Findings ledger 0.37](FINDINGS_0_37.md)
