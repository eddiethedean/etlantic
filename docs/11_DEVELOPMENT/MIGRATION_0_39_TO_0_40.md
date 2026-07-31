# Migration 0.39 → 0.40

> **Status: Available for ETLantic 0.40.0.** Upgrade notes for adopters moving
> from the 0.39 CP1 control-plane incubation to the 0.40 CP2 registry /
> persistence line. **CP2 ≠ production multi-tenant** (**0.43**).

## Summary

| Area | Change |
|---|---|
| Package pin | `etlantic==0.40.0` (do not mix 0.39 and 0.40 minors) |
| Control plane | CP2: tenant/workspace directory, immutable revisions, isolation profiles |
| Identity | CP1 refs remain; CP2 adds durable **records** and revision/promotion types ([ADR-017](adr/ADR-017-REGISTRY-AND-ISOLATION.md)) |
| Public CP1 routes | Route identities stay stable while storage moves onto registry providers |
| Production multi-tenant | **Not** claimed in 0.40 — reserved for **0.43** |
| Histories | Fingerprints/metadata only; baselines do not mutate contracts |
| OpenLineage | Optional Experimental outbound export (`etlantic-openlineage`); cannot mutate registry authority |
| Ops | Metadata search/pagination, retention hooks, SQLite backup/restore transcript |

## Upgrade steps

1. Complete CP1 adoption on `0.39.0` first (identity, durable submit, SSE).

2. Pin core and official plugins / Medallantic together:

   ```bash
   python -m pip install --upgrade 'etlantic==0.40.0'
   # plus matching plugins / medallantic at ==0.40.0
   # optional: pip install 'etlantic[openlineage]==0.40.0'
   ```

3. Prefer `RegistryProvider` protocols for directory and revision access; do
   not treat in-process dicts as multi-worker registry storage.

4. Expect suspended tenants/workspaces to fail closed on registry operations.

5. Apply SQLModel registry migrations when using the optional persistence
   package (`etlantic_sqlmodel.migrations`).

6. Re-validate and re-plan existing pipelines after upgrade:

   ```bash
   etlantic validate TARGET --format json
   etlantic plan TARGET --format json
   ```

7. Do not announce or configure production shared-service multi-tenant
   isolation on CP2 alone — shared-service requires an independent second
   control (RLS or per-tenant credentials); WHERE-only filters are insufficient.

## Compatibility notes

- Additive relative to ADR-016 identity vocabulary.
- Revision wire shapes use `/1` with additive evolution preferred.
- FastAPI and SQLModel remain optional extras.
- Registry is not a data catalog and must not store source rows.
- Plugin floors move to `etlantic>=0.40.0,<0.41`.

## See also

- [What's New in 0.40](../01_GETTING_STARTED/WHATS_NEW_0_40.md)
- [Exit gate 0.40](EXIT_GATE_0_40.md)
- [Findings ledger 0.40](FINDINGS_0_40.md)
- [ADR-017: Registry and Isolation](adr/ADR-017-REGISTRY-AND-ISOLATION.md)
- [Implementation plan 0.40](IMPLEMENTATION_PLAN_0_40.md)
- [Isolation profile matrix](isolation_profile_matrix_0_40.json)
- [Migration 0.38 → 0.39](MIGRATION_0_38_TO_0_39.md)
