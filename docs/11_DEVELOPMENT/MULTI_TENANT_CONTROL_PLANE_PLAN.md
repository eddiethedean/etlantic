# Multi-Tenant Control Plane Plan

> **Status: planned first-class feature program; not available in ETLantic
> 0.36.0.** Incubation is sequenced across 0.39–0.42. A production,
> multi-tenant compatibility claim is gated for 0.43 only after every isolation,
> durability, policy, and operations gate on this page passes.
>
> **Current boundary:** Process-local registries, runtimes, caches, report
> stores, and reference adapters in 0.36 are not multi-tenant merely because
> they carry identity fields.
>
> **Authority:** The
> [main roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md)
> owns release order; this plan owns control-plane scope and graduation. Use
> [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md) for shipped behavior
> and the [Planning Hub](PLAN_INDEX.md) for portfolio status.
>
> **Review trigger:** Update when any CP1–CP-GA gate changes state, scope, or
> evidence requirements.

## Decision

ETLantic will treat a multi-tenant control plane as a first-class planned
product surface, not as an indefinitely adopter-owned residual.

“First-class” means the program must ship:

- versioned public domain models and provider protocols;
- typed SDK, CLI, and HTTP operations with semantic parity;
- a separately installable control-plane package;
- reference persistence and deployment profiles;
- tenant-isolation, authorization, durability, and recovery conformance suites;
- stable diagnostics, migrations, compatibility policy, and operator runbooks;
- security, performance, failure-injection, backup, and restore evidence.

This commitment does **not** change the current product boundary. ETLantic
0.36 is still limited to the documented single-tenant reference deployment.
No current process-local registry, runtime, cache, report store, or FastAPI
reference adapter becomes multi-tenant merely because it carries a tenant
field.

## Program Placement

| Phase | Planned outcome | Claim allowed at exit |
|---|---|---|
| 0.37 prerequisite | Stable library foundation and frozen core contracts | Single-tenant stable foundation |
| 0.39 / CP1 | Typed control API, identity context, authorization envelope | Control API incubation |
| 0.40 / CP2 | Tenant/workspace registry, persistence isolation, metadata identity, and outbound OpenLineage | Tenant-aware registry and metadata-export preview |
| 0.41 / CP3 | Durable submission, state, leases, recovery, and GitOps preview workspaces | Multi-worker and preview-workspace preview |
| 0.42 / CP4 | Policy, quotas, audit, supply-chain, and preview-promotion gates | Multi-tenant release candidate |
| 0.43 / CP-GA | Operational graduation of the complete program, including preview-to-production evidence | First supported multi-tenant control plane |

The 0.39–0.42 releases are implementation and burn-in phases. They do not
independently authorize an unrestricted production claim. The 0.43 gate is a
graduation decision over the integrated program, not a promise that an HTTP
router alone is a control plane.

## Product Boundary

The planned control plane coordinates ETLantic definitions, plans, submissions,
events, reports, policies, and execution hosts. It does not move pipeline
execution into the API process.

```text
Identity provider / trusted gateway
                │
                ▼
        Control API boundary
  authentication · authorization · quotas
                │
     ┌──────────┼───────────┐
     ▼          ▼           ▼
 Registry   Submission   Audit/event
 and policy    store       stores
     │          │           │
     └──────────┼───────────┘
                ▼
      Durable broker / submitter
                │
                ▼
      Isolated execution hosts
  validate signed envelope · acquire secrets
                │
                ▼
       External data systems
```

ETLantic core remains independently usable without FastAPI, SQLModel, an
identity provider, a broker, or a server. Planned concrete integrations live
in optional packages and depend on public core protocols.

## Non-Goals

The control-plane program will not:

- claim that context variables, Python objects, threads, or coroutines create a
  security boundary;
- execute mutually untrusted tenants in one Python interpreter;
- become a proprietary scheduler, data engine, secret manager, identity
  provider, cluster provisioner, or warehouse;
- accept arbitrary import paths, plugins, filesystem paths, secret-provider
  names, or network destinations from request bodies;
- store source rows, resolved secret values, live backend objects, or
  unbounded artifact previews in control-plane records;
- use FastAPI `BackgroundTasks` as a durable execution mechanism;
- make SQLModel sessions or HTTP request objects pipeline runtime resources;
- promise an SLA before measured service objectives, capacity envelopes,
  escalation ownership, and operational support exist.

## Canonical Identity and Scope Model

Every control-plane resource is scoped explicitly. No production operation may
fall back to a process-global “current tenant” or an implicit default
workspace.

| Concept | Meaning | Required properties |
|---|---|---|
| Principal | Authenticated human or workload | Issuer-qualified, immutable subject identity |
| Tenant | Top-level authorization and billing boundary | Opaque immutable ID; never inferred from display name |
| Workspace | Tenant-owned authoring and operations namespace | Unique within tenant; explicit lifecycle state |
| Environment | Deployment/promotion slice such as development or production | Bound to policy and approved execution targets |
| Security domain | Data-handling and reuse boundary | Preserved in plans, artifacts, caches, and execution envelopes |
| Request context | Principal plus tenant/workspace/environment and correlation data | Server-derived, immutable, and request-scoped |

Planned typed references should preserve these identities without embedding
credentials or display names. Candidate models include `TenantRef`,
`WorkspaceRef`, `EnvironmentRef`, `PrincipalRef`, and an immutable
`ControlPlaneContext`; exact names remain provisional until CP1 freezes them.

### Scope rules

1. Authentication establishes the principal.
2. A trusted server-side mapping establishes the tenant memberships.
3. The requested workspace must resolve inside an authorized tenant.
4. The environment and security domain must be permitted for the requested
   action.
5. Resource lookup uses the complete scope, not a globally unique object ID
   followed by a later authorization check.
6. A worker receives a signed or integrity-protected execution envelope and
   revalidates scope before acquiring credentials or touching artifacts.
7. Cross-tenant administration uses separate routes, credentials, policy, and
   audit events; it is never an accidental extension of tenant routes.

Tenant IDs supplied in paths, headers, messages, or request bodies are routing
claims only. They never override the authenticated membership and policy
decision.

## Supported Isolation Profiles

The program may support multiple deployment profiles, but each profile must
have its own conformance claim and documented residual risk.

| Profile | Boundary | Minimum controls |
|---|---|---|
| Isolated deployment | Dedicated control plane and execution infrastructure per tenant | Separate credentials, stores, queues, keys, and workers |
| Dedicated database | Shared API tier; database or cluster per tenant | Server-side routing, separate credentials, no caller-selected URLs |
| Dedicated schema | Shared database; schema per tenant | Fixed schema mapping, restricted roles, migration isolation |
| Shared service | Shared tables and infrastructure | Composite tenant keys, database row policy where available, mandatory repository scope, defense-in-depth tests |

The 0.43 graduation decision must state exactly which profiles are supported.
Passing one profile does not imply the others are safe.

Shared-service support requires both application-layer scope enforcement and a
second independent control such as database row-level security, tenant-specific
credentials, or a verified policy proxy. A single forgotten `WHERE tenant_id`
must not be sufficient to expose another tenant.

Execution of mutually untrusted Python remains process- or container-isolated
in every profile.

## Authorization Model

Authorization is deny by default and action-oriented. A broad “workspace
member” check is insufficient.

Initial action families:

| Resource | Representative actions |
|---|---|
| Tenant/workspace | read, configure, suspend, delete, administer membership |
| Pipeline definition | list, read, create, edit, validate, promote, archive |
| Profile/environment | read, plan-with, submit-with, administer bindings |
| Plan | create, read, compare, approve, sign, submit |
| Run | submit, read, cancel, retry, replay, repair, approve |
| Artifact | list metadata, read bounded preview, download, delete |
| Schema history | observe, read, propose, acknowledge, promote baseline |
| Plugin/provider | inspect, approve, bind, revoke |
| Policy/audit | read decision, administer policy, export evidence |

Decisions include the principal, tenant, workspace, environment, action,
resource revision, requested overrides, run intent, security domain, policy
revision, and decision reason.

List, search, event-stream, and bulk operations filter before pagination and
serialization. They must not reveal unauthorized counts, identifiers, cursor
positions, timing distinctions, or error details. The API adopts and documents
a consistent non-enumeration policy for `403` versus `404`.

Policy failure is an authorization failure. Production cannot silently fall
back from an unavailable external policy engine to a permissive local rule.

## Public Protocol Boundaries

Core-facing application code should depend on small, tenant-aware protocols,
not FastAPI routers or SQLModel repositories.

Candidate protocol families:

- tenant and workspace directory;
- revisioned pipeline/contract registry;
- authorization and policy decision provider;
- durable submission and idempotency store;
- run, report, event, and artifact metadata stores;
- execution-host directory and submitter;
- quota and rate decision provider;
- append-only audit evidence sink;
- state/checkpoint provider;
- signing and envelope verification provider.

Every protocol method that reads or mutates a tenant-owned resource must accept
an immutable authorization scope. APIs such as `get(resource_id)` are
non-conforming when the resource can be tenant-owned; the scope must be part of
the lookup key.

Provider protocols define behavior and normalized evidence. Concrete queues,
databases, policy engines, identity providers, and schedulers remain
replaceable integrations.

## HTTP and SDK Contract

The FastAPI package is the reference HTTP adapter, not the semantic owner.

Planned rules:

- version the HTTP surface independently and expose explicit schema versions;
- derive tenant membership from authenticated identity;
- scope ordinary routes by workspace, with separate administrative routes;
- require `Idempotency-Key` on submission and other safely repeatable
  mutations;
- require `If-Match` or an equivalent revision token for mutable resources;
- return `202 Accepted` only after durable acceptance;
- use bounded pagination with opaque, tenant-scoped cursors;
- use consistent typed problem details and stable diagnostic identities;
- keep artifact contents off generic metadata routes;
- make client disconnects independent from durable run state;
- authorize SSE/WebSocket connection, resume cursor, and every emitted event;
- revalidate long-lived stream authority on policy or membership changes.

The SDK, CLI, and HTTP adapter operate on the same typed request and response
models. Transport-specific convenience must not change validation, planning,
authorization, or idempotency semantics.

## Durable Submission and Execution

Submission is a control-plane transaction, not a background function call.

The acceptance boundary must atomically establish:

- tenant/workspace/environment scope;
- normalized request fingerprint;
- caller-scoped idempotency record;
- selected immutable pipeline and profile revisions;
- secret-free plan identity or plan-construction request;
- authorization and policy decision references;
- initial submission state;
- an outbox or equivalent durable dispatch record.

If durable state cannot commit, the API does not return `202`. If state commits
but broker publication fails, a transactional outbox or equivalent recovery
loop completes dispatch without creating a second submission.

Execution hosts use leases and fencing tokens. A stale worker cannot publish a
terminal status, checkpoint, or artifact after ownership transfers. Attempt
history is append-only and distinguishes retry, replay, resume, repair,
backfill, and reconciliation.

Control-plane submission state is distinct from `PipelineRunReport` step
status. The mapping between accepted, queued, leased, running, terminal, and
reconciliation-required states must be explicit and versioned.

## Persistence Requirements

Reference repositories must:

- use tenant/workspace compound keys and database constraints;
- enforce scope in the query itself, before object materialization;
- support optimistic concurrency or compare-and-swap where races matter;
- use transactions for state transitions and outbox publication;
- prevent mass assignment of scope, policy, ownership, and protected state;
- separate request, persistence, domain, and response models;
- use bounded queries, pagination, retention, and deletion workflows;
- preserve immutable revisions and append-only evidence where required;
- make administrative bypass explicit, separately authorized, and audited;
- fail startup when migration state is unknown or incompatible.

Production never calls `create_all()` or performs destructive migrations
automatically. Expand/contract migrations, rollback compatibility, mixed-version
workers, and tenant-by-tenant migration failure must be rehearsed.

Control-plane and pipeline-data credentials are always separate.

## Secrets, Plugins, Artifacts, and Caches

### Secrets

- Persist `SecretRef` and provider metadata only.
- Bind allowed secret scopes to tenant, workspace, environment, execution host,
  and plan identity.
- Resolve values only inside an authorized execution boundary.
- Never accept a raw secret value through generic plan, run, or profile APIs.
- Audit references and access decisions without recording resolved values.

### Plugins and providers

- Production plugin authorization remains fail closed.
- Tenant requests cannot install packages or choose arbitrary entry points.
- A control-plane deployment has an operator-approved plugin catalog.
- Tenant/workspace policy may further restrict that catalog but cannot broaden
  it.
- Execution envelopes carry approved package identities, versions,
  capabilities, and provenance.

### Artifacts and caches

- Every identity and storage key includes tenant, workspace, environment,
  security domain, run/attempt, and logical output as applicable.
- Authorization precedes metadata lookup, signing, download, or deletion.
- Signed URLs are short-lived, action-specific, and tenant-bound.
- Cache lookup cannot reuse across a security boundary merely because content
  hashes match.
- Retention, legal hold, quarantine, and secure deletion are explicit states.
- Generic APIs return metadata and bounded previews, never unbounded source
  data.

## Quotas and Noisy-Neighbor Controls

Multi-tenant support requires shared-capacity controls, not only authorization.

The program must define and measure:

- request rate and concurrent connection limits;
- document, graph, plan, report, event, log, and artifact metadata sizes;
- concurrent submissions, runs, steps, streams, and retries;
- queue depth, lease count, and per-tenant dispatch fairness;
- planning CPU/time and registry query budgets;
- artifact preview bytes and signed-download issuance;
- policy, identity, secret-provider, and backend timeout budgets;
- tenant suspension and emergency kill switches.

Admission control happens before expensive parsing, planning, or backend work
where possible. Rate or quota provider failure is fail closed for new work.
Already-running work follows an explicit containment policy.

Fair scheduling and per-tenant execution capacity may be delegated to a
conforming external orchestrator, but the decision and resulting evidence must
remain observable through the control plane.

## Events, Audit, and Evidence

Run events and compliance-oriented audit evidence are different products.

Run/event stores provide resumable operational observation. Audit evidence
records security-sensitive actions and decisions, including:

- authentication and membership context;
- authorization and policy decision identifiers;
- tenant, workspace, environment, action, and resource revision;
- submission, cancellation, approval, promotion, acknowledgement, and
  administrative changes;
- plugin/provider approvals and execution-envelope verification;
- migration, retention, export, and deletion operations;
- correlation, causation, idempotency, and request identifiers;
- outcome and normalized failure category.

Audit records are append-only, integrity-protected, bounded, redacted, and
free of source rows and resolved secret values. Retention and export policy are
deployment configuration. Operational run reports do not automatically become
a compliance system of record.

SSE and broker events have tenant-scoped sequence or cursor semantics.
Consumers can resume without observing events from another tenant or silently
skipping an authorization change.

## Failure Behavior

| Failure | Required behavior |
|---|---|
| Identity provider unavailable | Reject protected requests; no anonymous fallback |
| Tenant/workspace mismatch | Deny without resource enumeration |
| Policy provider unavailable | Deny new privileged work; record safe diagnostic |
| Registry unavailable | Do not validate, plan, or submit against stale mutable state unless an explicitly authorized immutable revision is available |
| Submission transaction fails | Do not return `202` |
| Broker publish fails after commit | Recover from outbox; do not create another submission |
| Duplicate idempotency key, same request | Return the original authorized result |
| Duplicate idempotency key, different request | Reject conflict |
| Worker loses lease | Fence all later writes from that attempt |
| External commit outcome unknown | Require reconciliation or manual decision; do not claim safe retry |
| Event consumer falls behind | Resume from durable cursor or return an explicit retention gap |
| Artifact publication partially fails | Quarantine incomplete state and block authorization |
| Migration version is incompatible | Fail readiness/startup; never auto-repair production schema |
| Quota provider unavailable | Reject new work according to fail-closed admission policy |

Errors must be normalized, bounded, and redacted. Diagnostic code families for
control-plane identity, authorization, tenancy, durability, and quota failures
must be reserved before CP1 freezes public schemas.

## Availability, Backup, and Recovery

The project will not advertise HA, RPO, RTO, or an SLA from architecture alone.
Each supported deployment profile must publish measured expectations and
operational ownership.

Before 0.43 graduation:

- backup and point-in-time recovery are rehearsed for every reference store;
- restore verifies tenant scope, integrity, migration version, and event
  continuity;
- API replicas tolerate process loss without losing accepted submissions;
- broker and store outages have explicit degraded modes;
- regional or zonal claims include tested failover behavior;
- disaster recovery never replays a stale lease or duplicates committed
  external effects;
- maintenance and migration procedures define read-only, drain, rollback, and
  resume behavior.

## Security Verification Matrix

The conformance program must include at least:

- two-tenant read/write/list/search isolation for every repository method;
- two-workspace isolation inside one tenant;
- authorization tests for every action/resource pair;
- database row-policy bypass attempts where shared tables are supported;
- object-ID, cursor, timing, error, and event-stream enumeration tests;
- artifact, cache, report, checkpoint, and idempotency collision tests;
- forged or replayed execution-envelope rejection;
- stale lease and fencing races;
- cancellation, approval, promotion, and baseline-acknowledgement races;
- policy outage, identity outage, broker outage, and partial-commit injection;
- oversized request, graph, report, event, and stream-pressure tests;
- migration rollback, mixed-version, backup, and restore rehearsals;
- secret and regulated-field redaction across errors, logs, traces, events,
  reports, OpenAPI, and audit evidence;
- property-based scope propagation and authorization tests;
- static checks preventing unscoped repository APIs from entering the public
  surface.

At least one external security review and one independent deployment exercise
are required before 0.43. Findings need owners, remediation evidence, and an
explicit residual-risk decision.

## Performance and Scale Gates

Each supported deployment profile publishes reproducible baselines for:

- catalog and registry reads at representative tenant counts;
- validation and planning latency by graph size;
- submission latency through durable acceptance;
- event ingest and SSE resume throughput;
- authorization and policy decision overhead;
- fairness under one noisy tenant and many quiet tenants;
- repository pagination and impact-query bounds;
- worker lease/heartbeat load;
- backup and restore time.

The 0.43 exit record must name the tested envelope. “Multi-tenant” does not mean
unbounded tenants, users, pipelines, runs, or artifacts.

## Package and Ownership Model

| Concern | Planned owner |
|---|---|
| Canonical plans, run requests, reports, events, and provider protocols | `etlantic` core |
| HTTP routes, identity dependencies, OpenAPI, SSE, request context | `etlantic-fastapi` |
| Reference relational repositories and migrations | `etlantic-sqlmodel` |
| Queue, broker, identity, policy, and secret integrations | Optional provider packages or applications |
| Worker scheduling and backend execution | Orchestrators, execution hosts, and plugins |
| Deployment manifests and operations examples | Reference deployment package/docs |

No optional package may bypass core plan validation, plugin trust, redaction, or
security-domain rules.

## Delivery Gates

### CP1 — Typed API and identity foundation (0.39)

Deliver:

- versioned control-plane context and scoped resource references;
- typed API/SDK operations with stable operation IDs;
- authentication adapters and deny-by-default authorization boundary;
- workspace-scoped catalog, validate, plan, submit, observe, and cancel;
- durable-acceptance and idempotency contracts;
- non-enumerating errors, bounded pagination, and authorized event streams;
- protocol conformance fakes that require scope on every repository call.

Exit:

- OpenAPI and SDK fixtures are deterministic;
- every operation has an action/resource authorization test;
- the API embeds without owning application identity or lifespan policy;
- no heavy execution uses API-process background tasks;
- no production multi-tenant claim is made yet.

### CP2 — Registry and persistence isolation (0.40)

Deliver:

- tenant/workspace directory and immutable revision registry;
- compound-key repositories and supported isolation profiles;
- SQLModel reference stores with explicit migrations;
- registry, schema-history, artifact-metadata, report, event, and policy
  repositories;
- promotion, aliases, signatures, provenance, and tenant-scoped cursors;
- stable identity mappings for pipeline, step, run, attempt, input, output,
  contract, plan, schema-observation, and artifact revisions;
- optional outbound OpenLineage provider with tenant/workspace/environment
  scoping, design-time/runtime correlation, bounded delivery, and
  reconciliation;
- isolation and migration conformance suites.

Exit:

- two-tenant and two-workspace matrices pass every repository operation;
- authorization is applied before lookup and pagination;
- backup/restore preserves scope and integrity;
- a supported shared-service profile has a verified second isolation control;
- cross-tenant cache, artifact, cursor, and idempotency collisions fail closed.
- design-time and runtime metadata join on stable identities across local,
  compiled, and remote execution;
- outbound metadata contains neither resolved secrets nor source rows and
  cannot mutate authoritative registry state.

### CP3 — Durable execution coordination (0.41)

Deliver:

- transactional submission/outbox flow;
- broker/submitter and execution-host protocols;
- leases, fencing, heartbeats, cancellation, and attempt history;
- replay, resume, repair, backfill, reconciliation, and checkpoint evidence;
- per-tenant admission control and orchestrator capacity handoff;
- commit- and pull-request-qualified preview workspaces with bounded lifecycle,
  time-to-live, cleanup, quotas, and immutable base/candidate links;
- contract, graph, plan, schema, policy, cost, and environment diffs plus
  impacted-subgraph selection and explicitly authorized shadow runs;
- resumable durable events and disconnected-client behavior.

Exit:

- API and worker loss cannot lose an accepted request;
- duplicate requests do not create duplicate work;
- stale attempts cannot publish state or artifacts;
- unknown external commit outcomes never become automatic safe retries;
- preview cleanup is idempotent and cannot delete shared or production
  resources;
- preview evidence is invalidated when its code, dependencies, plan, policy, or
  target-environment identity changes;
- multi-worker chaos and recovery tests pass.

### CP4 — Policy, quota, audit, and release candidate (0.42)

Deliver:

- tenant-aware policy-provider integration and separation of duties;
- quotas, fairness, suspension, and emergency containment;
- integrity-protected audit evidence and retention/export controls;
- plugin, provider, secret, egress, residency, and classification policies;
- signed execution envelopes and supply-chain evidence;
- source-revision provenance, untrusted-fork restrictions, preview budgets,
  separation of duties, promotion approval, supersession, and rollback policy;
- operator dashboards, alerts, runbooks, and measured capacity profiles.

Exit:

- fail-closed identity/policy/quota outage behavior is demonstrated;
- audit evidence covers every privileged mutation without secrets or source
  rows;
- noisy-neighbor tests stay within published budgets;
- preview workspaces receive no implicit secret or production authority, and
  promotion revalidates the exact approved revision against current policy and
  environment state;
- security review and independent deployment exercise are complete;
- remaining risks are documented for the 0.43 graduation decision.

### CP-GA — First-class multi-tenant graduation (0.43)

The 0.43 claim requires all CP1–CP4 gates plus:

1. A frozen supported-isolation-profile matrix.
2. Public compatibility and migration policy for control-plane schemas.
3. Reproducible install, upgrade, rollback, backup, and restore exercises.
4. At least two API replicas and two execution hosts in failure-injection tests.
5. Cross-tenant access tests for every public operation and provider protocol.
6. Published capacity envelope and explicit non-SLA or SLA support terms.
7. Stable diagnostics and redaction verification across all output channels.
8. Operator documentation for identity, policy, migrations, keys, queues,
   stores, retention, suspension, incident response, and disaster recovery.
9. No unresolved critical/high isolation or authorization findings.
10. A release record that clearly separates supported profiles from
    experimental and adopter-owned integrations.
11. Stable outbound metadata identities and a reconciled design/runtime lineage
    scenario across local, compiled, and remote execution.
12. A preview-to-production workflow proving isolation, staleness detection,
    approval, promotion revalidation, rollback evidence, and bounded cleanup.

Failure of any mandatory gate keeps the feature in release-candidate status.
The project must not weaken the meaning of “multi-tenant” to ship on a date.

## Required Cross-Plan Alignment

This plan is authoritative for multi-tenant control-plane graduation:

- [FastAPI Integration Plan](FASTAPI_INTEGRATION_PLAN.md) owns the HTTP adapter
  and request lifecycle.
- [SQLModel Integration Plan](SQLMODEL_INTEGRATION_PLAN.md) owns the reference
  relational persistence implementation.
- [ETL Reliability and Recovery Plan](ETL_RELIABILITY_PLAN.md) owns normalized
  recovery evidence.
- [Schema Drift and Evolution Plan](SCHEMA_DRIFT_PLAN.md) owns observation and
  acknowledgement semantics.
- [Adoption, Connectivity, and Operations Plan](ADOPTION_ECOSYSTEM_PLAN.md)
  owns metadata interoperability, GitOps preview, operator-console, connector,
  migration, and provider-program gates.
- [Security Model](../02_FOUNDATIONS/SECURITY.md) owns current controls and the
  threat model.
- [Deployment](../06_EXECUTION/DEPLOYMENT.md) remains the current 0.36
  single-tenant boundary until CP-GA passes.

If another plan conflicts on release placement, isolation, durability,
authorization, or graduation criteria, this plan and the main roadmap must be
updated together before implementation proceeds.

## Open Decisions

These decisions block the indicated gates and cannot remain implicit:

| Decision | Owner role | Due |
|---|---|---|
| Freeze identity/scope model and non-enumeration policy | Core + security maintainers | Before CP1 schema freeze |
| Select supported isolation profiles and second controls | Security + persistence maintainers | Before CP2 implementation freeze |
| Select reference database and migration support matrix | SQLModel maintainers | Before CP2 conformance |
| Freeze metadata namespace, identity, and OpenLineage facet mappings | Registry + observability maintainers | Before CP2 conformance |
| Select durable broker/outbox and lease reference strategy | Runtime + integration maintainers | Before CP3 conformance |
| Define preview workspace lifecycle, cleanup, and untrusted-fork policy | Runtime + security maintainers | Before CP3 conformance |
| Define quota/fairness semantics and outage policy | Operations + security maintainers | Before CP4 release candidate |
| Define audit integrity, retention, and export profile | Security + operations maintainers | Before CP4 release candidate |
| Publish support envelope and 0.43 compatibility policy | Release + governance maintainers | Before CP-GA |

Every decision requires an ADR or an explicit roadmap decision record,
conformance updates, migration impact, and documentation changes.

## Key Principle

> Tenant context is data unless it is authenticated, authorized, propagated,
> persisted, and independently enforced at every boundary. A first-class
> multi-tenant claim is earned by integrated isolation and recovery evidence,
> not by adding `tenant_id` fields.
