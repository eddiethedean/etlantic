# Migration 0.40 → 0.41

> **Status: Available for ETLantic 0.41.0.** Upgrade notes for adopters moving
> from the 0.40 CP2 registry line to the 0.41 CP3 durable-work incubation.
> **CP3 ≠ production multi-tenant** (**0.43**).

## Summary

| Area | Change |
|---|---|
| Package pin | `etlantic==0.41.0` (do not mix 0.40 and 0.41 minors) |
| Control plane | CP3: durable submission/outbox, leases/fencing, checkpoints, replay/repair, previews |
| CP1 submit | `/v1/definitions/{id}/runs` receipts unchanged; optional dual-write to `DurableWorkStore` |
| Host ops | New `/v1/durable/*` routes when `durable_work` is injected |
| Persistence | Optional SQLModel migration `002_durable_cp3` |
| Production multi-tenant | **Not** claimed in 0.41 — reserved for **0.43** |
| Brokers / workers | Remain adopter-owned; core is not a queue or supervisor |

## Upgrade steps

1. Complete CP2 adoption on `0.40.0` first (registry, isolation profiles).

2. Pin core and official plugins / Medallantic together:

   ```bash
   python -m pip install --upgrade 'etlantic==0.41.0'
   # plus matching plugins / medallantic at ==0.41.0
   ```

3. Apply SQLModel migrations when using the optional persistence package:

   ```python
   from etlantic_sqlmodel.migrations import apply_migrations
   apply_migrations(engine)  # includes 002_durable_cp3
   ```

4. Inject `DurableWorkStore` (memory or SQLModel) into `ETLanticAPI` for host
   coordination. Drain `pending_outbox` with your dispatcher, then
   `mark_published`.

5. Execution hosts must present the current fencing token on attempt finish and
   every checkpoint CAS (`attempt_id` + `fencing_token` are required). Cancel
   expires leases; heartbeat/CAS refuse `cancel_requested`. Treat `unknown`
   external effects as fail-closed.

6. Re-validate and re-plan existing pipelines after upgrade:

   ```bash
   etlantic validate TARGET --format json
   etlantic plan TARGET --format json
   ```

7. Do not announce production shared-service multi-tenant isolation on CP3
   alone — graduation remains **0.43**.

## Compatibility notes

- Additive relative to ADR-016 / ADR-017; durable wire shapes use `/1`.
- FastAPI and SQLModel remain optional extras.
- Plugin floors move to `etlantic>=0.41.0,<0.42`.
- Exactly-once marketing claims remain out of scope.

## See also

- [What's New in 0.41](../01_GETTING_STARTED/WHATS_NEW_0_41.md)
- [Exit gate 0.41](EXIT_GATE_0_41.md)
- [Findings ledger 0.41](FINDINGS_0_41.md)
- [ADR-018: Durable Submission and State](adr/ADR-018-DURABLE-SUBMISSION-AND-STATE.md)
- [Implementation plan 0.41](IMPLEMENTATION_PLAN_0_41.md)
- [Durable chaos matrix](durable_chaos_matrix_0_41.json)
- [Migration 0.39 → 0.40](MIGRATION_0_39_TO_0_40.md)
