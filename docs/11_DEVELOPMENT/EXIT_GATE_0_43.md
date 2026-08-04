# Exit Gate 0.43 — First-Class Multi-Tenant Control-Plane Graduation (CP-GA)

> **Status: Released — ETLantic 0.43.0.** CP-GA graduation of the integrated
> 0.39–0.42 control-plane stack against the frozen support matrix. A production
> multi-tenant claim is published **only** for Supported isolation profiles
> below; Experimental profiles remain non-claims. Community support is
> **non-SLA**.

| Deliverable | Status |
|---|---|
| Planning: this exit gate / findings / What's New / migration | **Complete** |
| Frozen support envelope + compatibility policy | **Complete** ([cp_ga_support_matrix_0_43.json](cp_ga_support_matrix_0_43.json)) |
| Isolation matrix (043-I) | **Complete** |
| Compatibility / migrations (043-C) | **Complete** |
| Resilience / dual-store (043-R) | **Complete** |
| Backup / recovery (043-B) | **Complete** |
| Capacity / fairness (043-P) | **Complete** |
| Security / redaction (043-S) | **Complete** |
| Objectives / erasure (043-O) | **Complete** |
| Metadata / GitOps preview→promote (043-M) | **Complete** |
| Documentation / release record (043-D) | **Complete** |
| Lockstep version 0.43.0 | **Complete** |

## Supported claim (frozen)

| Profile | GA status | Notes |
|---|---|---|
| `isolated-deployment` | **Supported** | Separate deployment / database per tenant |
| `dedicated-schema` | **Supported** | Dedicated schema/engine per tenant |
| `shared-service` | **Experimental** | Requires real RLS / per-tenant credentials (not claimed) |

Support terms: measured capacity envelopes + overload fail-closed behavior;
**explicit non-SLA** community support.

## Quantified exit scorecard (13 gates)

From [IMPLEMENTATION_PLAN_0_43](IMPLEMENTATION_PLAN_0_43.md):

Evidence language: gates are **Met** against **in-process Memory campaigns**,
optional **SQLModel** when installed, and **FastAPI** opaque-404 tests — not
multi-process dual-API product drills or OpenLineage reconciliation.

| # | Measure | Required | Current |
|---|---|---:|---|
| 1 | Documented and fully tested isolation matrix | Pass | **Met** — [isolation_profile_matrix_0_43.json](isolation_profile_matrix_0_43.json) + [cp_ga_isolation_matrix_0_43.json](cp_ga_isolation_matrix_0_43.json) (sampled matrix ops + FastAPI) |
| 2 | Public schema compatibility + migration policy | Pass | **Met** — [cp_ga_compat_matrix_0_43.json](cp_ga_compat_matrix_0_43.json) |
| 3 | Install / upgrade / rollback / backup / restore | Pass | **Met** — audit export/restore + SQLModel persist campaigns (not clean-install smoke) |
| 4 | Multi-replica API + execution-host fault results | Pass | **Met** — in-process dual durable stores + lease fencing ([cp_ga_resilience_matrix_0_43.json](cp_ga_resilience_matrix_0_43.json)); true multi-process residual P1 |
| 5 | Cross-tenant tests for covered public operations | Pass | **Met** — isolation campaign coverage of matrix ops + FastAPI GA tests (not literally every route) |
| 6 | Capacity envelope, overload, support terms | Pass | **Met** — [cp_ga_capacity_envelope_0_43.json](cp_ga_capacity_envelope_0_43.json) |
| 7 | Stable diagnostics + verified redaction | Pass | **Met** — security campaign |
| 8 | Complete operator + recovery documentation | Pass | **Met** — [CP_GA_OPERATOR_RUNBOOK_0_43](CP_GA_OPERATOR_RUNBOOK_0_43.md) |
| 9 | No unresolved critical/high security finding | 0 | **Met** — [FINDINGS_0_43](FINDINGS_0_43.md) P0=0 |
| 10 | Release record: supported vs experimental | Pass | **Met** — support matrix |
| 11 | Reconciled design-time / runtime metadata identity | Pass | **Met** — preview plan_fingerprint matches SoD / promote gate (in-process) |
| 12 | Preview→production promote / rollback / cleanup | Pass | **Met** — GitOps campaign stale/cleanup/revoke denial |
| 13 | Objectives + erasure restart / authz / false-completion | Pass | **Met** — ops campaign including empty-provider fail-closed |

## Evidence map

| Gate item | Evidence |
|---|---|
| Qualification plan | [IMPLEMENTATION_PLAN_0_43](IMPLEMENTATION_PLAN_0_43.md) |
| Domain architecture | [MULTI_TENANT_CONTROL_PLANE_PLAN](MULTI_TENANT_CONTROL_PLANE_PLAN.md) |
| Traceability index | [cp_ga_traceability_0_43.json](cp_ga_traceability_0_43.json) |
| Findings | [FINDINGS_0_43](FINDINGS_0_43.md) |
| Migration | [MIGRATION_0_42_TO_0_43](MIGRATION_0_42_TO_0_43.md) |
| What's New | [WHATS_NEW_0_43](../01_GETTING_STARTED/WHATS_NEW_0_43.md) |
| Prior CP4 exit | [EXIT_GATE_0_42](EXIT_GATE_0_42.md) |

## Go / no-go

**Released** as `0.44.0` (tag `v0.43.0` / PyPI / RTD). ROADMAP current row
remains **Gate-ready for tag/publish** vocabulary until the next minor. All
thirteen gates are **Met** against the frozen Supported profiles under the
evidence language above.

## Explicit non-claims

- No unbounded tenant/user/pipeline scale claim
- No formal enterprise SLA
- No `shared-service` production isolation without a real second control
- No embedded IdP or embedded OPA evaluate path
- No multi-process dual-API / OpenLineage reconciliation as Met evidence
