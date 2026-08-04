# Findings Ledger 0.43 — CP-GA Multi-Tenant Graduation

> **Status: Closed for gate-ready 0.43.0** — CP-GA qualification complete.
> Open **P0 count is 0**. Campaign findings are recorded here.

## Severity policy

From [IMPLEMENTATION_PLAN_0_43](IMPLEMENTATION_PLAN_0_43.md):

| Severity | Meaning | Release treatment |
|---|---|---|
| **P0** | Cross-tenant disclosure, lost accepted work, crossed scope under failover, false production multi-tenant claim for Experimental profile | Must close before 0.43 |
| **P1** | Material recovery, migration, capacity, or GitOps risk | Close or defer with owner, mitigation, target, non-blocking rationale |
| **P2** | Localized usability / maintainability | May defer with owner and target |
| **P3** | Cosmetic | Backlog |

## Locked dispositions

| Decision | Outcome | Notes |
|---|---|---|
| Supported isolation profiles | `isolated-deployment`, `dedicated-schema` | Frozen in support matrix |
| `shared-service` | Experimental | Needs real RLS / per-tenant credentials |
| Support terms | Non-SLA + measured envelopes | No invented enterprise SLA |
| SQLModel reference | Snapshot dual-path canonical | Entity rows are denormalized mirrors |
| Auth | Principal injection / OIDC claim map | No embedded IdP |
| OPA | Stub / fallback only | No embedded evaluate |

## Open findings

Open **P0 count is 0**.

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| — | — | — | — | No open P0 | — |

## Deferred P1 (non-blocking for gate-ready)

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| `043-R-01` | P1 | Control-plane | Deferred | True multi-process dual-API / dual-host product drill | Mitigated by in-process dual-store campaigns; target post-0.43 harden wave |
| `043-M-01` | P1 | Control-plane | Deferred | OpenLineage design/runtime reconciliation product drill | Mitigated by preview fingerprint identity in GitOps campaign; not claimed Met |

## Soft-continue from prior phases

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| `038-X-01` | P1 | Ecosystem + echo maintainer | Soft-continue | Independent echo connector on PyPI | Non-blocking for CP-GA |

## Closure rules

1. Every P0 requires a regression campaign entry in the traceability index.
2. Deferred P1 rows must name owner, target phase, mitigation, and rationale.
3. Changing severity without written rationale does not close a finding.
