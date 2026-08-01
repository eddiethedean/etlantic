# What's New in ETLantic 0.40

> **Status: Available in ETLantic 0.40.0.** CP2 control-plane incubation:
> tenant/workspace registry, immutable revisions, persistence isolation
> profiles, metadata-only histories, and outbound OpenLineage preview.
> **Beta** — **CP2 is not production multi-tenant isolation** (that claim
> remains **0.43**).

## Highlights

- **Registry records** — durable `TenantRecord`, `WorkspaceRecord`,
  `EnvironmentRecord`, and `SecurityDomainRecord` alongside CP1 refs
  ([ADR-017](../11_DEVELOPMENT/adr/ADR-017-REGISTRY-AND-ISOLATION.md))
- **Lifecycle** — `active` / `suspended` / `archived` with fail-closed
  suspension
- **Immutable revisions** — `logical_id` + `revision_id`, aliases, promotion
  records, signature/provenance placeholders (metadata only)
- **RegistryProvider** — protocol façade for directories and revisions
  (memory + optional SQLModel)
- **Isolation profiles** — isolated-deployment, dedicated-schema, and
  shared-service with a required second control (RLS or tenant credentials);
  fake evidence in
  [isolation_profile_matrix_0_40.json](../11_DEVELOPMENT/isolation_profile_matrix_0_40.json)
- **Histories / impact** — fingerprints and metadata only; baselines do not
  mutate contracts
- **Ops** — revision metadata search/pagination, observation retention hooks,
  SQLite registry backup/restore round-trip
- **OpenLineage outbound** — optional Experimental `etlantic-openlineage`
  export that cannot mutate registry authority
- **Explicit non-claim** — CP2 builds mechanisms and evidence, **not**
  production multi-tenant isolation (**0.43**)

## Adopter actions

| Who | Action |
|---|---|
| Everyone on 0.39.x | Upgrade to `etlantic==0.40.0` with matching plugins; see [migration](../11_DEVELOPMENT/MIGRATION_0_39_TO_0_40.md) |
| Control-plane authors | Prefer `RegistryProvider` for directory/revision access; do not mutate revisions in place |
| Multi-tenant operators | Do **not** claim production isolation until **0.43** |
| Lineage adopters | Optional `pip install 'etlantic[openlineage]==0.40.0'`; treat export as non-authority |

## Not in 0.40

- Production multi-tenant isolation claim (**0.43**)
- Durable execution-host protocol, leases, fencing (**0.41**)
- Policy engine, quotas, and GA audit graduation (**0.42–0.43**)
- Storing source rows in registry or impact indexes

## See also

- [Migration 0.39 → 0.40](../11_DEVELOPMENT/MIGRATION_0_39_TO_0_40.md)
- [Exit gate 0.40](../11_DEVELOPMENT/EXIT_GATE_0_40.md)
- [Findings ledger 0.40](../11_DEVELOPMENT/FINDINGS_0_40.md)
- [Implementation plan 0.40](../11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_40.md)
- [ADR-017: Registry and Isolation](../11_DEVELOPMENT/adr/ADR-017-REGISTRY-AND-ISOLATION.md)
- [Multi-tenant control plane plan](../11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md)
