# Exit Gate 0.42 — Tenant Policy, Quotas, Audit, and Supply-Chain (CP4)

> **Status: Released — ETLantic 0.42.0.** CP4 policy / quotas / audit line is
> published for documented pilots. **CP4 is not a production multi-tenant
> isolation claim** — that remains gated to **0.43**.

| Deliverable | Status |
|---|---|
| Planning: ADR-019 / this exit gate / findings / What's New / migration | **Complete** |
| Policy protocol + MemoryPolicyProvider + plan/submit hooks | **Complete** (042-P) |
| Approvals / SoD / promotion gates | **Complete** (042-A) |
| Quotas, fairness, suspension, containment | **Complete** (042-Q) |
| Data governance constraints | **Complete** (042-D) |
| Delivery objectives + escalation routing | **Complete** (042-L) |
| Governed erasure | **Complete** (042-R) |
| Supply-chain attestations + signed schema evidence | **Complete** (042-S) |
| AuditEvidenceStore integrity chain | **Complete** (042-U) |
| SQLModel CP4 providers + migrations | **Complete** |
| FastAPI `/v1` CP4 surfaces + durable completion | **Complete** |
| Chaos / outage / conformance evidence | **Complete** (042-O) |
| Soft-continues 041-P1-01 / 041-P1-02 closed | **Complete** |
| Release notes: CP4 ≠ production multi-tenant | **Complete** |

## Quantified exit scorecard

From [IMPLEMENTATION_PLAN_0_42](IMPLEMENTATION_PLAN_0_42.md) exit gates:

| Measure | Required | Current |
|---|---:|---|
| Policy/quota/identity outage fail-closed | Pass | **Met** ([cp4_outage_matrix_0_42.json](cp4_outage_matrix_0_42.json)) |
| Optimizer/compiler cannot cross policy/data boundary | Pass | **Met** (governance boundary tests) |
| Plan verifiable vs revision/plugins/policy bundle | Pass | **Met** (attestation suite) |
| Approvals durable, SoD, no secrets | Pass | **Met** (policy conformance) |
| Schema observation forgery/replay rejected | Pass | **Met** |
| Objectives restart-safe, deduped, authorized routing | Pass | **Met** (`check_objective_conformance.py`) |
| Erasure no false completion / no subject leakage | Pass | **Met** |
| Noisy-neighbor within budgets | Pass | **Met** (quota tests) |
| Audit integrity + backup/restore/migration | Pass | **Met** |
| Preview promotion revalidates approved revision | Pass | **Met** (`gate_pre_promote`) |
| Unresolved P0 findings | 0 | **Met** |
| Production multi-tenant claim at CP4 | 0 | **Met** (explicit non-claim; **0.43**) |
| FastAPI / SQLModel remain optional dependencies of core | Pass | **Met** |

## Evidence map

| Gate item | Evidence |
|---|---|
| CP4 freeze | [ADR-019](adr/ADR-019-POLICY-QUOTAS-AND-AUDIT.md) |
| Implementation order | [IMPLEMENTATION_PLAN_0_42](IMPLEMENTATION_PLAN_0_42.md) |
| Domain architecture | [MULTI_TENANT_CONTROL_PLANE_PLAN](MULTI_TENANT_CONTROL_PLANE_PLAN.md) |
| Finding severity | [FINDINGS_0_42](FINDINGS_0_42.md) |
| Adopter migration | [MIGRATION_0_41_TO_0_42](MIGRATION_0_41_TO_0_42.md) |
| Adopter highlights | [WHATS_NEW_0_42](../01_GETTING_STARTED/WHATS_NEW_0_42.md) |
| Outage / chaos matrix | [cp4_outage_matrix_0_42.json](cp4_outage_matrix_0_42.json) |
| Operator runbook | [CP4_OPERATOR_RUNBOOK](CP4_OPERATOR_RUNBOOK.md) |
| Prior CP3 exit | [EXIT_GATE_0_41](EXIT_GATE_0_41.md) |

## Acceptance checklist

### Planning (Wave 0)

- [x] [IMPLEMENTATION_PLAN_0_42](IMPLEMENTATION_PLAN_0_42.md) published
- [x] [ADR-019](adr/ADR-019-POLICY-QUOTAS-AND-AUDIT.md) Accepted
- [x] This exit gate published
- [x] [FINDINGS_0_42](FINDINGS_0_42.md) ledger (P0 = 0)
- [x] [WHATS_NEW_0_42](../01_GETTING_STARTED/WHATS_NEW_0_42.md) completed at exit
- [x] [MIGRATION_0_41_TO_0_42](MIGRATION_0_41_TO_0_42.md) completed at exit
- [x] Indexes / roadmap mark 0.42 CP4 **Released** (ROADMAP current row remains
  gate-ready-for-tag vocabulary until the next minor)

### CP4 coordination (Waves 1–7)

- [x] Protocol + memory providers complete
- [x] SQLModel providers + migrations
- [x] FastAPI CP4 routes
- [x] Chaos / outage / conformance matrices green
- [x] Version bump to 0.42.0 and publish path (`v0.42.0` tag / PyPI / RTD)

## Explicit non-claim

**CP4 ≠ production multi-tenant.** Operators must not announce shared-service
production isolation on 0.42 alone. Graduation remains **0.43**.
