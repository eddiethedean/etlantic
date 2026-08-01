# ADR-018: Durable Submission, Outbox, Leases, and Preview State

Date: 2026-07-31  
Status: Accepted

## Context

ETLantic 0.39 (CP1) froze durable accept and scoped idempotency. 0.40 (CP2)
froze registry scope keys and isolation profiles. Without a companion freeze
for CP3 durable work coordination, implementations will embed brokers in core,
treat BackgroundTasks as workers, conflate CP1 `SubmissionStore` with CP3
`DurableWorkStore`, invent incompatible lease/fencing semantics, or claim
production multi-tenant isolation at 0.41.

This ADR locks the CP3 vocabulary for transactional submission/outbox, leases
and fencing, attempt context, namespaced checkpoints, external-effect
outcomes, repair/replay plans, preview workspaces, and the CP3 vs 0.43
graduation boundary.

Authoritative sequencing:
[IMPLEMENTATION_PLAN_0_41](../IMPLEMENTATION_PLAN_0_41.md),
[Multi-Tenant Control Plane Plan](../MULTI_TENANT_CONTROL_PLANE_PLAN.md),
[ADR-016: Control-Plane Identity](ADR-016-CONTROL-PLANE-IDENTITY.md),
[ADR-017: Registry and Isolation](ADR-017-REGISTRY-AND-ISOLATION.md), and
[ROADMAP § 0.41](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md).

## Decision

### Accept is not execute

`DurableWorkStore.accept` commits an immutable submission record and an outbox
record in one provider transaction. Returning success means the request
survived API loss; it does not mean execution started.

Core does **not** embed a message broker or worker supervisor. The reference
dispatcher drains `pending_outbox`, publishes to an adopter-owned broker (or
in-process sink for tests), then calls `mark_published`. Vendor brokers remain
provider choices.

### CP1 SubmissionStore vs CP3 DurableWorkStore

CP1 `SubmissionStore` remains the HTTP accept surface for
`/v1/definitions/{id}/runs` receipts. CP3 `DurableWorkStore` is the
execution-coordination store (outbox, leases, attempts, checkpoints, effects,
replay, previews).

Optional FastAPI injection may dual-write durable accept when a
`DurableWorkStore` is present. Host operations use `/v1/durable/*` routes.
Unscoped `get(id)` APIs remain non-conforming.

### Idempotency and admission

Idempotency keys are scoped by tenant, workspace, operation, and the
authenticated issuer-qualified principal (`issuer`, `kind`, `subject`). A key
may be replayed only with the same immutable submission inputs.

Per-tenant in-flight admission limits may reject new accepts when too many
non-terminal submissions are open. Full quota/fairness policy remains **0.42**.

### Leases and fencing

Execution hosts acquire a TTL lease before starting an attempt. Every host
write carries a monotonically increasing fencing token. Heartbeats renew TTL.
`release_lease` voluntarily ends ownership. Stale or expired fencing fails
closed on terminal attempt writes and checkpoint CAS.

A submission has at most one running attempt. Cancellation requests block new
leases; acknowledging cancel terminals the submission as `cancelled`.

### Namespaced state identities

Cursors, watermarks, partitions, and snapshots are namespaced checkpoint
identities (`cursor:`, `watermark:`, `partition:`, `snapshot:`) on the same
CAS surface—not five separate persistence systems. Checkpoint records may
link `schema_baseline_id`. Dry-run `explain_transition` returns fingerprint-
only explanations without mutating state.

### External effects

Normalized effect statuses are `none`, `pending`, `committed`,
`not_committed`, `failed`, and `unknown`. An `unknown` outcome never becomes
an automatic safe retry without reconciliation or idempotency evidence.
Records carry opaque IDs and redacted metadata only—never resolved secrets or
source rows.

### Replay, resume, repair, backfill

`replay` selects exact immutable fingerprints from the source submission and
explains permitted differences. `plan_resume`, `plan_repair`, and
`plan_backfill` return fingerprint-only plans (partition-aware invalidation,
reusable artifacts, minimum-safe closure). They do not execute work.

### Preview workspaces

Preview workspaces require distinct base and candidate revision IDs, a future
expiry, and a positive quota. Cleanup is scoped and idempotent and must not
delete shared or production resources. Evidence becomes stale when code, plan,
policy, or environment fingerprints change.

Shadow runs require explicit authorization. Shadow effects can never be
promoted as authoritative production outputs. Promotion separation-of-duties
hardening remains **0.42**.

### CP3 is not production multi-tenant

0.41 incubates durable coordination, multi-worker recovery evidence, and
preview workspaces. It does **not** claim production multi-tenant isolation.
That claim remains gated to **0.43**.

## Consequences

- Wave 1 protocols and `MemoryDurableWorkStore` must implement the frozen
  state machine, release lease, admission, namespaced state helpers, repair
  plans, and preview staleness/shadow invariants.
- SQLModel adapters must implement transactional accept+outbox and fencing
  CAS with compound tenant/workspace keys.
- FastAPI may inject `DurableWorkStore` optionally; CP1 operationIds stay
  stable.
- Docs and exit evidence must state **CP3 ≠ production multi-tenant (0.43)**.

## Alternatives

| Alternative | Why rejected |
|---|---|
| Embed broker/worker supervisor in core | Violates “not a queue” boundary; vendor lock-in |
| Replace CP1 SubmissionStore with DurableWorkStore on submit | Breaks AcceptReceipt `/1` clients |
| Separate tables/protocols per cursor/watermark/partition | Unnecessary persistence sprawl |
| Auto-retry unknown external effects | Unsafe duplication; fails closed required |
| Implicit production authority for shadow/preview | Violates untrusted-fork policy |
| Claim production multi-tenant at CP3 | Graduation remains **0.43** |

## Compatibility

- Additive relative to ADR-016 and ADR-017; wire schemas use `/1`.
- FastAPI and SQLModel stay optional adapters outside core protocols.
- Exactly-once marketing claims remain out of scope.
