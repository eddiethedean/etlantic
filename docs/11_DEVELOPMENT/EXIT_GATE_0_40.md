# Exit Gate 0.40 — Tenant Registry, Workspaces, and Persistence Isolation (CP2)

> **Status: Gate-ready for tag/publish rehearsal.** Package version **0.40.0**.
> **CP2 is not a production multi-tenant isolation claim** — that remains gated
> to **0.43**. Close only against exact candidate wheels when publishing.

| Deliverable | Status |
|---|---|
| Planning: ADR-017 / this exit gate / findings / What's New / migration | **Complete** |
| Tenant/workspace directory + lifecycle | **Complete** (040-T) |
| Immutable revision registry, aliases, promotions | **Complete** (040-R) |
| Persistence providers + migrations | **Complete** (040-P) |
| Histories / impact (metadata only) | **Complete** (040-H) |
| Workspace resources / safe roots | **Complete** (040-W) |
| OpenLineage outbound (non-authority) | **Complete** (040-L) |
| Isolation-profile matrix + ops evidence | **Complete** (040-O / exit) |
| Release notes: CP2 ≠ production multi-tenant | **Complete** |

## Quantified exit scorecard

From [IMPLEMENTATION_PLAN_0_40](IMPLEMENTATION_PLAN_0_40.md) exit gates:

| Measure | Required | Current |
|---|---:|---|
| Promotion preserves logical identity; prior revision immutable | Pass | **Met** |
| All registry ops enforce tenant/workspace scope | Pass | **Met** |
| Two-tenant/two-workspace matrix on supported isolation profiles | Pass | **Met** ([isolation_profile_matrix_0_40.json](isolation_profile_matrix_0_40.json)) |
| Shared-service second control (RLS or tenant credentials) | Pass | **Met** (WHERE-only insufficient stub + session second control) |
| Backup/restore / migration / rollback preserve scope | Pass | **Met** (SQLite dump/load round-trip) |
| Baselines distinct from contract revisions | Pass | **Met** |
| OpenLineage failures cannot mutate registry | Pass | **Met** (`etlantic-openlineage` failing transport) |
| Histories/impact metadata-only (no source rows) | Pass | **Met** |
| Unresolved P0 findings | 0 | **Met** |
| Production multi-tenant claim at CP2 | 0 | **Met** (explicit non-claim; **0.43**) |
| FastAPI / SQLModel remain optional dependencies of core | Pass | **Met** |

## Evidence map

| Gate item | Evidence |
|---|---|
| Registry / revision / isolation freeze | [ADR-017](adr/ADR-017-REGISTRY-AND-ISOLATION.md) |
| Implementation order | [IMPLEMENTATION_PLAN_0_40](IMPLEMENTATION_PLAN_0_40.md) |
| Domain architecture | [MULTI_TENANT_CONTROL_PLANE_PLAN](MULTI_TENANT_CONTROL_PLANE_PLAN.md) |
| Finding severity | [FINDINGS_0_40](FINDINGS_0_40.md) |
| Adopter migration | [MIGRATION_0_39_TO_0_40](MIGRATION_0_39_TO_0_40.md) |
| Adopter highlights | [WHATS_NEW_0_40](../01_GETTING_STARTED/WHATS_NEW_0_40.md) |
| Isolation matrix (fake) | [isolation_profile_matrix_0_40.json](isolation_profile_matrix_0_40.json) |
| Conformance / isolation scripts | `scripts/check_registry_conformance.py --fake`, `scripts/check_registry_isolation.py --fake` |
| Prior CP1 exit | [EXIT_GATE_0_39](EXIT_GATE_0_39.md) |

## Acceptance checklist

### Planning (Wave 0)

- [x] [IMPLEMENTATION_PLAN_0_40](IMPLEMENTATION_PLAN_0_40.md) published
- [x] [ADR-017](adr/ADR-017-REGISTRY-AND-ISOLATION.md) Accepted
- [x] This exit gate scaffold published
- [x] [FINDINGS_0_40](FINDINGS_0_40.md) ledger opened (P0 = 0)
- [x] [WHATS_NEW_0_40](../01_GETTING_STARTED/WHATS_NEW_0_40.md) completed at exit
- [x] [MIGRATION_0_39_TO_0_40](MIGRATION_0_39_TO_0_40.md) completed at exit
- [x] Indexes / roadmap mark 0.40 CP2 **Gate-ready / Released incubation**

### Registry and isolation (Waves 1–5)

- [x] Directory lifecycle + suspension fail-closed
- [x] Immutable revisions, aliases, promotions
- [x] SQLModel provider + migrations
- [x] Isolation-profile matrix green (fake evidence)
- [x] Metadata-only histories / impact
- [x] OpenLineage outbound non-authority proven
- [x] Ops: search/pagination, retention, backup/restore
- [x] Version bump to 0.40.0 (no git tag from this gate alone)

## Explicit non-claim

**CP2 ≠ production multi-tenant.** Operators must not announce shared-service
production isolation on 0.40 alone. Graduation remains **0.43**.
