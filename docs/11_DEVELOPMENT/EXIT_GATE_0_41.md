# Exit Gate 0.41 — Durable Submission, State, and Reproducibility (CP3)

> **Status: Gate-ready for tag/publish rehearsal.** Package version **0.41.0**.
> **CP3 is not a production multi-tenant isolation claim** — that remains gated
> to **0.43**. Close only against exact candidate wheels when publishing.

| Deliverable | Status |
|---|---|
| Planning: ADR-018 / this exit gate / findings / What's New / migration | **Complete** |
| Transactional submission / outbox / idempotency / admission | **Complete** (041-S) |
| Execution host leases, fencing, heartbeats, cancellation | **Complete** (041-H) |
| State providers, checkpoints, repair/replay | **Complete** (041-C / 041-R / 041-B) |
| External effects (unknown fail-closed) | **Complete** (041-E) |
| Preview workspaces / shadow / diffs | **Complete** (041-V) |
| SQLModel durable provider + migrations | **Complete** (041-P) |
| FastAPI `/v1/durable/*` surface | **Complete** |
| Chaos / crash-point / conformance evidence | **Complete** (041-O) |
| Release notes: CP3 ≠ production multi-tenant | **Complete** |

## Quantified exit scorecard

From [IMPLEMENTATION_PLAN_0_41](IMPLEMENTATION_PLAN_0_41.md) exit gates:

| Measure | Required | Current |
|---|---:|---|
| Accepted work survives API/broker/dispatcher/host loss | Pass | **Met** (outbox crash-point + restart idempotency) |
| Scoped idempotency (tenant/workspace/operation/principal) | Pass | **Met** |
| Checkpoint CAS + fencing prevent stale advancement | Pass | **Met** (memory + SQLModel dual-host) |
| Replay selects exact immutable inputs + differences | Pass | **Met** |
| Unknown external commit fails closed without auto-retry | Pass | **Met** |
| Preview cleanup scoped; staleness; no production authority | Pass | **Met** |
| State migration / corruption fail closed | Pass | **Met** (`diagnose_checkpoint`) |
| Multi-worker chaos (≥2 hosts) | Pass | **Met** ([durable_chaos_matrix_0_41.json](durable_chaos_matrix_0_41.json)) |
| Unresolved P0 findings | 0 | **Met** |
| Production multi-tenant claim at CP3 | 0 | **Met** (explicit non-claim; **0.43**) |
| FastAPI / SQLModel remain optional dependencies of core | Pass | **Met** |

## Evidence map

| Gate item | Evidence |
|---|---|
| Durable work freeze | [ADR-018](adr/ADR-018-DURABLE-SUBMISSION-AND-STATE.md) |
| Implementation order | [IMPLEMENTATION_PLAN_0_41](IMPLEMENTATION_PLAN_0_41.md) |
| Domain architecture | [MULTI_TENANT_CONTROL_PLANE_PLAN](MULTI_TENANT_CONTROL_PLANE_PLAN.md) |
| Finding severity | [FINDINGS_0_41](FINDINGS_0_41.md) |
| Adopter migration | [MIGRATION_0_40_TO_0_41](MIGRATION_0_40_TO_0_41.md) |
| Adopter highlights | [WHATS_NEW_0_41](../01_GETTING_STARTED/WHATS_NEW_0_41.md) |
| Chaos matrix (fake) | [durable_chaos_matrix_0_41.json](durable_chaos_matrix_0_41.json) |
| Conformance / chaos scripts | `scripts/check_durable_conformance.py`, `scripts/check_durable_chaos.py --fake` |
| Prior CP2 exit | [EXIT_GATE_0_40](EXIT_GATE_0_40.md) |

## Acceptance checklist

### Planning (Wave 0)

- [x] [IMPLEMENTATION_PLAN_0_41](IMPLEMENTATION_PLAN_0_41.md) published
- [x] [ADR-018](adr/ADR-018-DURABLE-SUBMISSION-AND-STATE.md) Accepted
- [x] This exit gate published
- [x] [FINDINGS_0_41](FINDINGS_0_41.md) ledger (P0 = 0)
- [x] [WHATS_NEW_0_41](../01_GETTING_STARTED/WHATS_NEW_0_41.md) completed at exit
- [x] [MIGRATION_0_40_TO_0_41](MIGRATION_0_40_TO_0_41.md) completed at exit
- [x] Indexes / roadmap mark 0.41 CP3 **Gate-ready / Released incubation**

### Durable coordination (Waves 1–5)

- [x] Protocol + MemoryDurableWorkStore complete
- [x] SQLModel provider + migrations
- [x] FastAPI durable routes + dual-write submit
- [x] Chaos / crash-point / conformance matrices green
- [x] Version bump to 0.41.0 (no git tag from this gate alone)

## Explicit non-claim

**CP3 ≠ production multi-tenant.** Operators must not announce shared-service
production isolation on 0.41 alone. Graduation remains **0.43**.
