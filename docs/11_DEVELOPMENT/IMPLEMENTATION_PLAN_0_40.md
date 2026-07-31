---
title: ETLantic 0.40 Implementation Plan
description: Implementation-grade plan for tenant registry, workspaces, and persistence.
plan_status: current
plan_last_reviewed: 0.37.0
---

# ETLantic 0.40 Implementation Plan

Phase 0.40 adds durable, scoped registry and workspace foundations behind the
0.39 API. It remains governed by the
[multi-tenant control-plane plan](MULTI_TENANT_CONTROL_PLANE_PLAN.md).

## Outcome

Contracts, pipelines, plans, plugins, and documentation have immutable,
workspace-scoped identities and revisions. Promotions, aliases, provenance,
schema/reliability histories, impact queries, safe landing-zone roots, and
optional OpenLineage export survive restarts and migrations without exposing
source rows or crossing tenant boundaries.

## Prerequisites And Non-Goals

- 0.39 identity and API compatibility gates are closed.
- Registry and workspace keys derive from the canonical identity model.
- This phase builds isolation mechanisms and evidence; the supported production
  isolation claim is not made until 0.43.
- The registry is not a data catalog that stores source records, and outbound
  catalog/OpenLineage integrations do not mutate ETLantic authority.

## Workstreams

| ID | Workstream | Deliverables | Completion evidence |
|---|---|---|---|
| 040-T | Tenant/workspace registry | Tenant, workspace, environment, and security-domain records; lifecycle states; suspension hooks | Lifecycle and cross-scope transition tests |
| 040-R | Revision registry | Stable logical identities; immutable revisions; aliases; promotion records; signatures and provenance | Deterministic revision/promotion tests and tamper detection |
| 040-P | Persistence providers | Provider protocol; optional SQLModel implementation; migrations; compound scope keys; transaction boundaries | Provider conformance plus upgrade/rollback/backup/restore suite |
| 040-H | History and impact | Immutable schema, plan, and reliability histories; field-level impact indexes; cache invalidation events | Impact fixtures and proof that histories contain fingerprints/metadata only |
| 040-W | Workspace resources | Authorized safe roots, artifact namespaces, checkpoint-store references, and preview namespace primitives | Traversal/symlink/namespace tests across a two-by-two scope matrix |
| 040-L | Lineage interop | Stable execution and design-time identity; optional `etlantic-openlineage` export | Reconciliation test joining plan identity, run events, and external lineage |
| 040-O | Operations | Search/pagination indexes, retention hooks, migration tooling, CLI/API administration | Load, restore, mixed-version migration, rollback, and redaction evidence |

## Delivery Sequence

1. Freeze registry identity, revision, promotion, and provider protocols.
2. Implement in-memory/reference conformance fixtures, then SQLModel persistence.
3. Move 0.39 resources onto scoped registry providers without changing public
   route identities.
4. Add histories, impact indexing, cache invalidation, and workspace resources.
5. Add outbound lineage integration and operational migration tooling.
6. Execute independent database and shared-service isolation profiles.

## Exit Gates

- Promotion preserves logical identity while recording immutable revision,
  signer, provenance, and environment transition without secrets.
- All registry, history, impact, search, cache, artifact, safe-root, and
  checkpoint operations enforce tenant and workspace scope.
- A two-tenant/two-workspace matrix passes against both supported database
  isolation profiles, with an independent second control for shared services.
- Backup/restore, forward migration, mixed-version operation, and rollback are
  demonstrated with no scope reassignment or history mutation.
- Schema and reliability baselines remain distinct from contract revisions and
  cannot mutate contracts implicitly.
- Design-time and runtime lineage identities reconcile; outbound catalog or
  OpenLineage failures cannot change ETLantic registry state.
- Searches and impact indexes return metadata only and do not retain source rows.

## Required Release Evidence

- Registry provider conformance report.
- Database isolation and shared-service control matrices.
- Migration, rollback, backup, and restore transcript.
- Metadata-retention and redaction inspection.
- Lineage identity reconciliation fixture and failure-path results.

