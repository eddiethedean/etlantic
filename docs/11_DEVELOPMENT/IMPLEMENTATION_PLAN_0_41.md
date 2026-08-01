---
title: ETLantic 0.41 Implementation Plan
description: Implementation-grade plan for durable submission, state, replay, and preview workspaces.
plan_status: current
plan_last_reviewed: 0.41.0-dev
---

# ETLantic 0.41 Implementation Plan

Phase 0.41 makes accepted work, execution ownership, checkpoints, and replay
durable across API and worker failure. It consumes the 0.39 API and 0.40 registry
without weakening their scope boundaries.

Freeze: [ADR-018](adr/ADR-018-DURABLE-SUBMISSION-AND-STATE.md). Exit tracking:
[EXIT_GATE_0_41](EXIT_GATE_0_41.md), [FINDINGS_0_41](FINDINGS_0_41.md).

## Outcome

A transactionally accepted submission is delivered to a leased, fenced
execution host; attempts, events, checkpoints, artifacts, and external effects
have enough provenance to resume, replay, repair, or fail safely. Preview
workspaces are durable, bounded, expiring forks rather than ad hoc flags.

## Prerequisites And Non-Goals

- 0.40 registry migrations, scope keys, and recovery gates are closed.
- Submission, attempt, checkpoint, and artifact identities reuse registry scope.
- Exactly-once marketing claims are out of scope. ETLantic records normalized
  effect state and reports unknown commit outcomes rather than guessing.
- Broker and persistence vendors remain provider choices, not core requirements.
- **CP3 ≠ production multi-tenant** (**0.43**).

## Workstreams

| ID | Workstream | Deliverables | Completion evidence | Status |
|---|---|---|---|---|
| 041-S | Transactional submission | Admission record, scoped idempotency, transactional outbox, broker dispatcher | Crash-point matrix between API commit, outbox publication, and broker delivery | Wave 1–2 |
| 041-H | Execution host | Lease, fencing token, heartbeat, release, cancellation, attempt history, stale-owner rejection | Multi-host lease expiry and stale publish tests | Wave 1–3 |
| 041-C | State providers | Namespaced cursor/watermark/checkpoint/partition/snapshot CAS, explain_transition, corruption diagnostics | Provider conformance, corruption, conflict, and migration suite | Wave 1–2 |
| 041-R | Reproducibility | Immutable plan/revision/plugin/policy linkage; secret-free attempt context; exact artifact selection | Replay fixture proving the same declared inputs and differences are explainable | Wave 1 |
| 041-E | External effects | Normalized pending/committed/failed/unknown effect record; reconciliation evidence | Unknown-commit tests that fail closed without duplicating effects | Wave 1 (memory done) |
| 041-B | Repair/backfill | Resume, replay, repair, partition backfill, dry-run state preview, baseline linkage | Partial-failure recovery and bounded backfill fixtures | Wave 1 |
| 041-V | Preview workspaces | Fork provenance, TTL, cleanup, quotas, diffs, shadow-run non-authority | Expiry/cleanup, stale fork, quota, and no-production-authority tests | Wave 1–3 |
| 041-O | Operations | Queue/lease metrics hooks, chaos evidence, state migration runbooks | Failure injection, capacity results, and operator drill | Wave 4–5 |
| 041-P | SQLModel provider | Optional transactional DurableWorkStore + migrations | SQL crash-point and dual-host lease tests | Wave 2 |

## Delivery Sequence

1. Freeze submission/outbox/attempt/lease/event state machines and invariants (ADR-018).
2. Complete memory provider protocol gaps (release, admission, repair, preview depth).
3. Implement SQLModel transactional acceptance and dispatcher crash recovery.
4. Wire FastAPI optional DurableWorkStore and `/v1/durable/*` host routes.
5. Run chaos tests across API, broker, host, database, checkpoint, and sink edges.
6. Close exit gate, What's New, migration, and 0.41.0 bump.

## Exit Gates

- Accepted work survives API loss, broker redelivery, dispatcher restart, and
  execution-host loss without being silently dropped or run by a stale owner.
- Scoped idempotency suppresses duplicate submissions and deliveries without
  conflating tenants, workspaces, revisions, or requested operations.
- Checkpoint compare-and-swap and atomic acknowledgement prevent a failed or
  stale attempt from advancing durable state.
- Replay selects exact immutable inputs and explains every permitted difference.
- An unknown external commit is surfaced as unknown and requires explicit repair;
  it is never automatically treated as safe to repeat.
- Preview forks expire and clean up only their own scoped resources, respect
  quotas, record staleness, and grant no implicit production authority.
- State migrations and corrupted-state recovery preserve auditability and fail
  closed when compatibility cannot be established.

## Required Release Evidence

- Submission/outbox crash-point and duplicate-delivery matrix.
- Lease/fencing chaos report with at least two execution hosts.
- State-provider conformance and corruption-recovery results.
- Replay/repair/backfill provenance records.
- Preview TTL, cleanup, staleness, and authority matrix.
