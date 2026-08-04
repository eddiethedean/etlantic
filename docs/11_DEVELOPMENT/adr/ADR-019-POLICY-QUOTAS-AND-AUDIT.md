# ADR-019: Policy Decisions, Quotas, Approvals, and Audit Evidence

Date: 2026-08-04  
Status: Accepted

## Context

ETLantic 0.39–0.41 froze identity (ADR-016), registry isolation (ADR-017), and
durable submission/state (ADR-018). Without a companion freeze for CP4,
implementations will invent incompatible policy envelopes, overload
`EventStore` as an audit log, leave `policy_fingerprint` as an opaque string
with no producer, treat admission limits as quotas, or claim production
multi-tenant isolation at 0.42.

This ADR locks the CP4 vocabulary for versioned policy decisions, approvals
and separation of duties, quota/fairness admission, integrity-protected audit
evidence, delivery-objective evaluation, governed erasure, supply-chain
verification, and the CP4 vs 0.43 graduation boundary.

Authoritative sequencing:
[IMPLEMENTATION_PLAN_0_42](../IMPLEMENTATION_PLAN_0_42.md),
[Multi-Tenant Control Plane Plan](../MULTI_TENANT_CONTROL_PLANE_PLAN.md),
[ADR-018: Durable Submission and State](ADR-018-DURABLE-SUBMISSION-AND-STATE.md),
and [ROADMAP § 0.42](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md).

## Decision

### Policy envelope

`PolicyDecision` is a versioned, redacted record with:

- `effect`: `allow` | `deny` | `require_approval`
- `policy_bundle_id`, `policy_fingerprint`
- `reasons[]`, `constraints{}`, `evidence_refs[]`

Hooks are explicit: `pre_plan`, `post_plan`, `pre_submit`, `post_execution`,
`pre_promote`, `pre_repair`, `privileged_op`. Decisions are inputs to
reproducibility (including durable `policy_fingerprint`), never ambient
process state. A missing policy provider on a protected profile fails closed.

OPA is an optional adapter behind the same `PolicyProvider` protocol. The
conformance reference is deterministic `MemoryPolicyProvider`.

### Approvals and separation of duties

Approval requests are durable, expirable, and revocable. The requester
principal must not be the sole approver (SoD). Stale approvals fail when the
plan hash or policy fingerprint drifts. Promotion requires a current
`allow` or satisfied approval against the exact approved revision.

### Quotas and fairness

Tenant+workspace budgets cover in-flight durable concurrency, preview
count/TTL, event emission rate, repair/backfill concurrency, and storage
bytes (metadata only). Over-limit denies admission. Provider outage fails
closed for protected mutations; read-only status may use a documented
degraded mode. Fairness uses weighted round-robin under shared pressure.
Suspension and emergency containment are durable scoped flags.

Per-tenant `admission_limit` from CP3 remains a lower-level guard; full
quota policy is authoritative when a `QuotaProvider` is injected.

### Audit evidence vs operational events

`AuditEvidenceStore` is distinct from `EventStore`. Audit records are
append-only and hash-chained (`prev_hash`, `record_hash`) with actor,
action, resource scope, and decision refs. Retention and export follow
tenant policy. Records never contain secret values or source rows.

### Delivery objectives and erasure

Versioned pipeline/step delivery objectives evaluate against durable
run/event history with restart-safe, deduplicated breach/recovery evidence
and authorized notification routing. Governed erasure uses subject-key /
field lineage without placing subject values in plans, reports, audit, or
diagnostics; completion is forbidden while required providers remain
unsupported, unknown, unauthorized, legally held, or unreconciled.

### Supply chain

Execution acquires authority only after verifying plan/revision identity,
approved plugins, policy bundle fingerprint, and optional SBOM/attestation
evidence. Signed schema observations are scoped; forgery, replay, and
cross-tenant/cross-environment evidence cannot satisfy a gate.

### CP4 is not production multi-tenant

0.42 is the multi-tenant **release candidate** gate. Production multi-tenant
isolation remains gated to **0.43**.

## Consequences

- Core hosts protocols and memory reference providers under
  `etlantic.control_plane`.
- FastAPI and SQLModel remain optional adapters with additive routes and
  migrations (`003_cp4_*`).
- Soft-continues `041-P1-01` and `041-P1-02` are closed in this phase.
- Docs and exit evidence must state **CP4 ≠ production multi-tenant (0.43)**.

## Alternatives

| Alternative | Why rejected |
|---|---|
| Reuse EventStore as audit | Lacks integrity chain; conflates ops with compliance |
| Ambient process policy | Breaks plan reproducibility and fingerprinting |
| Soft-fail on policy outage | Violates fail-closed protected-op requirement |
| Embed OPA as required dependency | Vendor lock-in; protocol stays vendor-neutral |
| Claim production multi-tenant at CP4 | Graduation remains **0.43** |

## Compatibility

- Additive relative to ADR-016, ADR-017, and ADR-018; wire schemas use `/1`.
- Existing CP1–CP3 operationIds and durable wire shapes stay stable.
- FastAPI and SQLModel stay optional outside core protocols.
