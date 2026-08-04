# What's New in ETLantic 0.42

> **Status: Available in ETLantic 0.42.0.** CP4 control-plane incubation:
> policy decisions, approvals/SoD, quotas, delivery objectives, governed
> erasure, supply-chain attestations, and integrity-protected audit.
> **Beta** — **CP4 is not production multi-tenant isolation** (that claim
> remains **0.43**).

## Highlights

- **PolicyProvider** — versioned `PolicyDecision` hooks (`pre_plan`,
  `post_plan`, `pre_submit`, `post_execution`, `pre_promote`, `pre_repair`,
  `privileged_op`) with deterministic `MemoryPolicyProvider` and optional OPA
  adapter ([ADR-019](../11_DEVELOPMENT/adr/ADR-019-POLICY-QUOTAS-AND-AUDIT.md))
- **Approvals / SoD** — durable approval requests; requester cannot self-approve;
  stale plan/policy fingerprints fail closed; promotion gates
- **QuotaProvider** — tenant/workspace concurrency, preview, events, repair,
  and storage budgets; suspension and emergency containment; fail-closed outage
- **Delivery objectives** — warning/hard deadlines, restart-safe evaluation,
  deduplicated breach/recovery, authorized notification routing
- **Governed erasure** — request → plan → report with legal holds; no subject
  values in evidence; no false completion while providers unsupported
- **Attestations** — signed plan/plugin/policy/SBOM verification; signed scoped
  schema observations
- **AuditEvidenceStore** — append-only hash chain distinct from `EventStore`
- **FastAPI CP4 routes** — `/v1/policy`, `/v1/approvals`, `/v1/quotas`,
  `/v1/erasure`, `/v1/audit`, `/v1/attestations` plus completed `/v1/durable`
  effects/repair/diagnose/shadow
- **SQLModel** — migration `003_cp4_governance`; normalized durable
  submission/outbox entity dual-write (closes `041-P1-01` / `041-P1-02`)
- **CLI** — `etlantic erasure plan|status`
- **Evidence** —
  [cp4_outage_matrix_0_42.json](../11_DEVELOPMENT/cp4_outage_matrix_0_42.json)
- **Explicit non-claim** — CP4 is multi-tenant **release candidate**, **not**
  production multi-tenant isolation (**0.43**)

## Adopter actions

| Who | Action |
|---|---|
| Everyone on 0.42.x | Upgrade to `etlantic==0.42.0` with matching plugins; see [migration](../11_DEVELOPMENT/MIGRATION_0_41_TO_0_42.md) |
| Control-plane hosts | Inject policy/approvals/quotas/audit/attestations as needed |
| Operators | Review [CP4 runbook](../11_DEVELOPMENT/CP4_OPERATOR_RUNBOOK.md) |
| Multi-tenant operators | Do **not** claim production isolation until **0.43** |

## Not in 0.42

- Production multi-tenant isolation claim (**0.43**)
- Frozen supported-isolation-profile matrix and capacity SLAs (**0.43**)
- Embedded OPA runtime dependency (adapter is optional)
- Exactly-once delivery marketing claims

## See also

- [Migration 0.41 → 0.42](../11_DEVELOPMENT/MIGRATION_0_41_TO_0_42.md)
- [Exit gate 0.42](../11_DEVELOPMENT/EXIT_GATE_0_42.md)
- [Findings ledger 0.42](../11_DEVELOPMENT/FINDINGS_0_42.md)
- [Implementation plan 0.42](../11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_42.md)
- [ADR-019: Policy, Quotas, and Audit](../11_DEVELOPMENT/adr/ADR-019-POLICY-QUOTAS-AND-AUDIT.md)
- [CP4 operator runbook](../11_DEVELOPMENT/CP4_OPERATOR_RUNBOOK.md)
