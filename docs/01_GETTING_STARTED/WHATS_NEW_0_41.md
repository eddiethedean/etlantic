# What's New in ETLantic 0.41

> **Status: Available in ETLantic 0.41.0.** CP3 control-plane incubation:
> durable submission, outbox, leases/fencing, checkpoints, replay/repair,
> external-effect fail-closed outcomes, and preview workspaces.
> **Beta** — **CP3 is not production multi-tenant isolation** (that claim
> remains **0.43**).

## Highlights

- **DurableWorkStore** — provider-neutral accept/outbox, cancel, lease,
  heartbeat, release, attempts, checkpoint CAS, effects, replay, repair
  plans, and preview lifecycle
  ([ADR-018](../11_DEVELOPMENT/adr/ADR-018-DURABLE-SUBMISSION-AND-STATE.md))
- **MemoryDurableWorkStore** — in-memory conformance / local development
  reference with issuer-scoped idempotency and per-tenant admission limits
- **SQLModel reference provider** — transactional snapshot persistence and
  migration `002_durable_cp3`
- **FastAPI `/v1/durable/*`** — optional host routes; submit dual-writes when
  a durable store is injected (CP1 receipt paths unchanged)
- **Namespaced state** — `cursor:` / `watermark:` / `partition:` / `snapshot:`
  checkpoint identities, dry-run `explain_transition`, baseline acknowledgement
- **Unknown effects fail closed** — no automatic retry without reconciliation
  or idempotency evidence
- **Preview workspaces** — TTL, quotas, staleness, diffs, shadow runs without
  production authority
- **Chaos evidence** —
  [durable_chaos_matrix_0_41.json](../11_DEVELOPMENT/durable_chaos_matrix_0_41.json)
- **Explicit non-claim** — CP3 builds multi-worker recovery evidence, **not**
  production multi-tenant isolation (**0.43**)

## Adopter actions

| Who | Action |
|---|---|
| Everyone on 0.40.x | Upgrade to `etlantic==0.41.0` with matching plugins; see [migration](../11_DEVELOPMENT/MIGRATION_0_40_TO_0_41.md) |
| Control-plane hosts | Inject optional `DurableWorkStore`; drain outbox via adopter-owned brokers |
| Execution hosts | Acquire leases, heartbeat, fence terminal writes and checkpoint CAS |
| Multi-tenant operators | Do **not** claim production isolation until **0.43** |

## Not in 0.41

- Production multi-tenant isolation claim (**0.43**)
- Full policy engine, quotas, and GA audit (**0.42–0.43**)
- Embedded message broker or worker supervisor in core
- Exactly-once delivery marketing claims

## See also

- [Migration 0.40 → 0.41](../11_DEVELOPMENT/MIGRATION_0_40_TO_0_41.md)
- [Exit gate 0.41](../11_DEVELOPMENT/EXIT_GATE_0_41.md)
- [Findings ledger 0.41](../11_DEVELOPMENT/FINDINGS_0_41.md)
- [Implementation plan 0.41](../11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_41.md)
- [ADR-018: Durable Submission and State](../11_DEVELOPMENT/adr/ADR-018-DURABLE-SUBMISSION-AND-STATE.md)
- [Durable work](../06_EXECUTION/DURABLE_WORK.md)
