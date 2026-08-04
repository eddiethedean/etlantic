# Findings Ledger 0.42 — Policy, Quotas, Audit, and Supply-Chain (CP4)

> **Status: Gate-ready** — ETLantic **0.42.0** CP4 exit. Open **P0 count is 0**.
> **CP4 ≠ production multi-tenant** (**0.43**).

## Severity policy

From [IMPLEMENTATION_PLAN_0_42](IMPLEMENTATION_PLAN_0_42.md):

| Severity | Meaning | Release treatment |
|---|---|---|
| **P0** | Cross-tenant policy/audit disclosure, secret/row leakage, false erasure completion, forged attestation acceptance, production multi-tenant false claim | Must close before 0.42 |
| **P1** | Material recovery, migration, chaos evidence, or adoption risk | Close or defer with owner, mitigation, target phase, and non-blocking rationale |
| **P2** | Localized usability, performance, or maintainability defect | May defer with owner and target |
| **P3** | Cosmetic or opportunistic improvement | Backlog |

Changing severity without written rationale does not close a finding.

## Locked dispositions

Recorded in
[ADR-019: Policy Decisions, Quotas, Approvals, and Audit Evidence](adr/ADR-019-POLICY-QUOTAS-AND-AUDIT.md).
Do not reopen without a written finding and migration plan.

| Decision | Outcome | Notes |
|---|---|---|
| Policy envelope | Versioned PolicyDecision + hooks | Explicit inputs; fail-closed |
| Approvals / SoD | Durable, expirable; requester ≠ sole approver | Stale plan/fingerprint reject |
| Quotas | Tenant+workspace budgets + fairness | Outage → fail closed (mutations) |
| Audit vs events | Separate AuditEvidenceStore hash chain | No secrets / source rows |
| Objectives / erasure | Durable eval + lineage closure | No subject values in evidence |
| Supply chain | Verify before authority | Signed scoped schema evidence |
| CP4 vs GA | CP4 ≠ production multi-tenant | Graduation remains **0.43** |

## Closed from 0.41 soft-continues

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| `041-P1-01` | P1 | Control-plane | **Closed** | Normalize durable SQL entity tables | Dual-write `DurableSubmissionEntityRow` / `DurableOutboxEntityRow` in `003_cp4_governance` |
| `041-P1-02` | P1 | Control-plane + FastAPI | **Closed** | Full DurableWorkStore HTTP surface | `/v1/durable/effects`, repair, diagnose, shadow routes |

## Open findings

Open **P0 count is 0**.

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| — | — | — | — | No open P0 | — |

## Soft-continue from prior phases

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| `038-X-01` | P1 | Ecosystem + echo maintainer | Soft-continue | Independent echo connector on PyPI | Non-blocking for CP4 |

## Closure rules

1. Every P0 requires a regression test and linked CP4 evidence before
   severity can move or the finding can close.
2. Deferred P1 rows must name owner, target phase, mitigation, and
   non-blocking rationale.
3. Do not reopen ADR-019 locked dispositions without a written finding and
   migration plan.
