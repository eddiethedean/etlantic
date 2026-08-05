# Findings Ledger 0.45 — Planner and Optimization SDK

> **Status: Released** — ETLantic **0.45.0** optimization SDK.
> Open **P0 count is 0**.

## Severity policy

From [IMPLEMENTATION_PLAN_0_45](IMPLEMENTATION_PLAN_0_45.md) and
[ADR-021](adr/ADR-021-OPTIMIZER-PASS-PROTOCOL.md):

| Severity | Meaning | Release treatment |
|---|---|---|
| **P0** | Pass executes data/secrets; silently crosses policy/security boundary; non-deterministic accept; unjustified rewrite on stale evidence | Must close before 0.45 |
| **P1** | Material explanation, selection, or conformance risk | Close or defer with owner |
| **P2** | Localized usability / maintainability | May defer with owner |
| **P3** | Cosmetic | Backlog |

## Locked dispositions

| Decision | Outcome | Notes |
|---|---|---|
| Protocol ownership | Core `etlantic.optimization` | ADR-021 |
| Default apply | Off (baseline plan) | Advisory until accept |
| Cost model | Pluggable providers | No universal currency |
| Evidence | Plan-time only | No live data access by passes |
| Production trust | `optimization_pass_allowlist` | Fail closed |

## Open findings

Open **P0 count is 0**.

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| — | — | — | — | No open P0 | — |

## Soft-continue from prior phases

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| `043-R-01` | P1 | Control-plane | Deferred | True multi-process dual-API drill | Out of 0.45 scope |
| `043-M-01` | P1 | Control-plane | Deferred | OpenLineage reconciliation product drill | Out of 0.45 scope |

## Closure rules

A finding closes only with a test, evidence artifact, or explicit deferral row.
