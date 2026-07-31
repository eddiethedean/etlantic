# ADR-017: Registry Records, Revisions, and Isolation Profiles

Date: 2026-07-31  
Status: Accepted

## Context

ETLantic 0.39 (CP1) froze opaque identity **refs** and an immutable
`ControlPlaneContext`. Without a companion freeze for durable registry
**records**, revision identity, promotion, and persistence isolation profiles,
0.40 (CP2) implementations will invent incompatible tenant directories, mutate
revisions in place, store source rows in histories, or treat a single
`WHERE tenant_id` filter as production isolation.

This ADR locks the CP2 vocabulary for directory records, lifecycle states,
immutable revisions, aliases, promotion, the `RegistryProvider` façade,
supported isolation profiles, metadata-only history/impact invariants, outbound
OpenLineage non-authority, and the CP2 vs 0.43 graduation boundary.

Authoritative sequencing:
[IMPLEMENTATION_PLAN_0_40](../IMPLEMENTATION_PLAN_0_40.md),
[Multi-Tenant Control Plane Plan](../MULTI_TENANT_CONTROL_PLANE_PLAN.md),
[ADR-016: Control-Plane Identity](ADR-016-CONTROL-PLANE-IDENTITY.md), and
[ROADMAP § 0.40](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md).

## Decision

### Records vs CP1 refs

CP1 types (`TenantRef`, `WorkspaceRef`, `EnvironmentRef`, `SecurityDomain`)
remain opaque routing and authorization carriers. CP2 adds durable directory
**records** that may carry lifecycle, display labels, and secret-free metadata
without becoming credentials or authority overrides:

| Record | Meaning |
|---|---|
| `TenantRecord` | Durable tenant directory entry keyed by `tenant_id` |
| `WorkspaceRecord` | Tenant-owned workspace directory entry |
| `EnvironmentRecord` | Deployment / promotion slice bound to tenant (and workspace when scoped) |
| `SecurityDomainRecord` | Data-handling boundary directory entry |

Path or header claims still never override server-derived
`ControlPlaneContext` (ADR-016). Records are looked up only after authz.

### Lifecycle states

Every directory record uses exactly these lifecycle states:

| State | Meaning |
|---|---|
| `active` | Normal read/write under authz |
| `suspended` | Fail closed on subsequent registry mutations and scoped gets that would disclose or change state |
| `archived` | Retained for audit/history; not writable; reads may be policy-gated |

Suspension hooks must fail closed: a suspended tenant or workspace rejects
registry `put` / `get` (and equivalent) operations rather than silently
succeeding or returning cross-scope existence hints.

### Revision identity

Registry content is addressed by:

- `logical_id` — stable identity preserved across revisions and promotions
- `revision_id` — immutable, append-only revision key

Revisions are never updated in place. Content carries a
`content_fingerprint` (hash of the stored metadata document) for tamper
detection. Signature and provenance fields are **placeholders** (metadata
only): no embedded credentials, signing material, or source rows.

**Aliases** map a scoped alias name to a `revision_id` (and its `logical_id`)
without mutating the target revision.

**Promotion records** record an environment (or channel) transition from one
revision to another while preserving `logical_id`. `promote()` appends a
`PromotionRecord` and may publish a new immutable revision; it must not mutate
the prior revision.

Candidate wire schema ids:

- `etlantic.control_plane.tenant_record/1`
- `etlantic.control_plane.workspace_record/1`
- `etlantic.control_plane.environment_record/1`
- `etlantic.control_plane.security_domain_record/1`
- `etlantic.control_plane.registry_revision/1`
- `etlantic.control_plane.alias/1`
- `etlantic.control_plane.promotion/1`

### RegistryProvider protocol façade

Public protocol seams (FastAPI- and SQLModel-free) compose:

- `TenantDirectory` — tenant record lifecycle
- `WorkspaceDirectory` — workspace record lifecycle (scoped)
- `RevisionRegistry` — revisions, aliases, promotions
- `RegistryProvider` — façade exposing the directories (and later histories)

Every mutating or read method on tenant-owned resources takes
`ControlPlaneContext` where scoped. Cross-tenant tenant-directory
administration may use security-domain principals under separate policy and
audit — never an accidental extension of ordinary tenant routes.

Unscoped `get(id)` APIs remain non-conforming for tenant-owned resources.

### Isolation profiles

Supported persistence isolation profiles for CP2 evidence (not a GA claim):

| Profile | Primary control | Second control (required for shared service) |
|---|---|---|
| `isolated-deployment` | Separate deployment / database per tenant | N/A (deployment boundary) |
| `dedicated-schema` | Dedicated database or schema per tenant | Schema / catalog boundary |
| `shared-service` | Compound scope keys + application filters | Independent second control: row-level security (RLS) **or** per-tenant credentials |

A shared-service profile that relies only on application `WHERE tenant_id`
clauses is non-conforming for CP2 isolation evidence.

### Histories and impact

Schema, plan, reliability, and impact indexes store **fingerprints and
metadata only**. They never retain source rows or resolved secrets.

Accepting an operational **baseline** must not mutate or alias the
authoritative contract revision. Baselines are observations, not contract
authority.

### OpenLineage outbound non-authority

Optional outbound OpenLineage / catalog export is one-way from ETLantic
identities. Export failures, retries, or remote acknowledgements **must not**
mutate registry records, revisions, aliases, promotions, or baselines.

### CP2 is not production multi-tenant

0.40 (CP2) incubates registry mechanisms, isolation profiles, and evidence.
It does **not** claim production multi-tenant isolation. That claim remains
gated to **0.43** after CP1–CP4 pass as an integrated system.

Release notes and exit evidence must state this boundary explicitly.

## Consequences

- Wave 1 protocols and in-memory fakes must use the frozen record and revision
  type names; suspension fails closed; revisions are append-only.
- SQLModel / Alembic work (later waves) must implement compound scope keys and
  the isolation-profile matrix, including a verified second control for
  shared-service.
- Histories, impact, and search must prove metadata-only retention.
- Docs must not describe CP2 as production multi-tenant or claim OpenLineage
  can write registry authority.

## Alternatives

| Alternative | Why rejected |
|---|---|
| Reuse CP1 refs as durable directory rows | Refs lack lifecycle and durable metadata; conflates routing with storage |
| In-place revision updates | Breaks provenance, promotion, and tamper detection |
| Shared DB with only `WHERE tenant_id` | Insufficient second control for shared-service evidence |
| History stores that retain sample rows | Violates fail-closed metadata policy |
| OpenLineage webhook mutates promotions | External systems must not become registry authority |
| Claim production multi-tenant at CP2 | Graduation remains **0.43** |

## Compatibility

- Additive relative to ADR-016 identity vocabulary; refs remain the request
  scope carriers.
- Wire schemas use `/1` with additive evolution preferred.
- Core package version for this ADR freeze wave remains **0.39.0** until the
  0.40 exit bump.
- FastAPI and SQLModel stay optional adapters outside core protocols.
