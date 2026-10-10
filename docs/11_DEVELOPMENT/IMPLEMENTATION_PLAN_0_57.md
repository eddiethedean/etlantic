---
title: ETLantic 0.57 Implementation Plan
description: Transport-independent managed backend, schedule commands, schema inspection, and runtime supervision for 0.57.0.
plan_status: current
plan_last_reviewed: 2026-10-08
---

# ETLantic 0.57 Implementation Plan

**Planned for 0.57.0; source implementation is in place and qualification is
pending.** This phase fully implements GitHub issues #278–#282. It replaces the former 0.57
brownfield phase, whose complete scope moves to [0.58](IMPLEMENTATION_PLAN_0_58.md).
The console, enterprise provider packs, and TransformationModel incubation move
to 0.59, 0.60, and 0.61 respectively. No release date is implied.

## Outcome and baseline

An independent consumer can construct one authorized backend, invoke its run
and schedule services, and create scheduler, run-worker, and action-worker roles
without FastAPI or application-owned ETL wiring. An HTTP adapter reuses those
same services. Deployment consumers can inspect provider schema compatibility
and supervise roles through public, redacted, read-only status and cooperative
drain contracts.

The source baseline is `b0a50467ea6c8a80426805c6039036ae905b93d6`, pulled from
`origin/main` on 2026-10-08; published distributions are 0.56.2. The five issues
were opened on 2026-10-08 and were open with no comments at planning time.
Findings below are confirmed by source inspection; this plan does not claim
new installed-wheel or live-database observations.

| Issue | Confirmed gap and primary implementation seams |
|---|---|
| [#278](https://github.com/eddiethedean/etlantic/issues/278) | `packages/etlantic-fastapi/src/etlantic_fastapi/managed.py` owns the backend handle, SQL graph, and HTTP configuration. Its backend requires `context_factory`; `ETLanticAPI.enable_managed_execution()` constructs the shared service. |
| [#279](https://github.com/eddiethedean/etlantic/issues/279) | `packages/etlantic-fastapi/src/etlantic_fastapi/schedule_routes.py` owns command authorization, workload binding, policy fingerprinting, timing, amendment checks, and preparation/claim/submit/link orchestration. |
| [#280](https://github.com/eddiethedean/etlantic/issues/280) | Standard construction omits the existing `SQLModelScheduleStore` and has no scheduler factory. `src/etlantic/runtime/scheduler_service.py` discovers preparation and recovery from `run_submitter.__self__`. |
| [#281](https://github.com/eddiethedean/etlantic/issues/281) | `packages/etlantic-sqlmodel/src/etlantic_sqlmodel/migrations/__init__.py` supplies read-only `current_version()`, but no complete public schema requirements/compatibility result. Construction checks only marker presence and head version. |
| [#282](https://github.com/eddiethedean/etlantic/issues/282) | Scheduler readiness is `not draining`; the run worker has drain but no status contract; the action worker has neither public drain nor status. Tick counts cannot distinguish standby, idle, or outage. |

The [#273](https://github.com/eddiethedean/etlantic/issues/273) gateway-import
and read-only-version fixes are already shipped. Preserve their tests and
extend them; do not re-file or describe those fixed defects as open.

## Ownership and constraints

- Core ETLantic owns transport-independent service, backend-handle, collaborator,
  context-validation, and runtime-role contracts. Core gains no FastAPI,
  SQLAlchemy, SQLModel, deployment-orchestrator, or vendor dependency.
- `etlantic-sqlmodel` owns the concrete relational graph, schema requirements,
  compatibility inspection, and SQL engine/session lifetime.
- `etlantic-fastapi` owns HTTP authentication/context derivation, wire parsing,
  representation, status/headers, and error translation. It adapts an existing
  backend and delegates compatibility constructors to the provider factory.
- Consumers such as ShuETL choose deployment configuration, trusted service
  scope, unique owner identities, process signals, poll loops, execution threads,
  HTTP probes, freshness policy, grace periods, and cleanup. Forced termination
  and restart remain supervisor responsibilities. ETLantic has no consumer import.
- Preserve full accepted principal/issuer/kind, tenant/workspace, environment,
  security domain, and resource-owner authority. Runtime lease identity remains
  separate from accepted execution authority. Validate contexts before store or
  provider access; validation never authenticates an arbitrary supplied principal.
- Preserve production trust allowlists, authorization/disclosure behavior,
  optimistic concurrency, immutable occurrence identity, durable preparation,
  fencing, and unknown-effect handling. Status and schema evidence contain no
  credentials, raw connection exceptions, secret values, or source rows.
- Schema creation and upgrade remain explicit operator migrations. Existing
  multi-commit preparation/claim/accept/link recovery is retained; this phase
  makes no cross-store atomicity or exactly-once external-effect claim.

## Public contract freeze

The contract is frozen in [ADR-026](adr/ADR-026-MANAGED-BACKEND-INDEPENDENCE-AND-SUPERVISION.md).
The public names and current ownership are:

| Public surface | Proposed shape and required behavior |
|---|---|
| Core backend | `etlantic.control_plane.ManagedBackend` exposes the managed and schedule services, shared stores, role factories, and `close()`. It does not depend on an HTTP API. Role construction uses lazy imports. |
| Provider configuration | `etlantic_sqlmodel.SQLModelBackendConfig` carries store, profile, action, event, input, and retention controls. Its database URL and other sensitive settings are excluded from repr. |
| Concrete composition | `etlantic_sqlmodel.create_managed_backend(config, *, authorizer, planning_context_factory=None, engine=None)` constructs the graph without Request, HTTP context factory, or principal dependency. A factory-created engine is owned; an injected engine remains caller-owned. |
| HTTP composition | `etlantic_fastapi.adapt_managed_backend(core_backend, *, context_factory, ...)` adds HTTP identity/context inputs to an existing core handle. Legacy constructors remain facades over the same provider graph and preserve `backend.api`. |
| Schedule service | `etlantic.service.ScheduleApplicationService` accepts canonical schedule models and explicit `ControlPlaneContext`; supplies create/amend/pause/resume/preview/trigger/get/list/list-firings. Timing uses an injected callable or clock object. |
| Occurrence collaborator | `ScheduledOccurrenceService` defines prepare, submit, and recovery. Standard scheduler construction requires the complete collaborator. Callback-only low-level execution requires `allow_callback_only=True`. |
| Provider inspection | `etlantic_sqlmodel.schema_requirements()` and `inspect_schema(engine)` return immutable requirements/results, including version, compatibility state, safe reason codes, and missing object/column/constraint identifiers. |
| Role supervision | Scheduler, run-worker, and action-worker handles expose local `status()` and idempotent nonblocking `request_drain()`. Status separates activity, admission, prerequisite facts, reason codes, in-flight count, observation time, and capabilities. |

Use existing `ControlPlaneContext`, `ScheduleSpec`, `ScheduleRecord`,
`FiringRecord`, and service errors rather than introduce competing wire models.
Retain existing routes, operation IDs, response shapes, and supported low-level
APIs. Freeze any intentional incompatibility and migration guidance explicitly.

## Workstreams and completion gates

### 057-B — Extract the shared backend (#278)

1. Inventory every store/service option and role-factory dependency in
   `etlantic_fastapi.managed` and `ETLanticAPI.enable_managed_execution()`.
   Freeze a configuration propagation matrix covering defaults and non-default
   profile, quotas, policy, approvals, audit, attestations, input resources,
   planning context, actions, events, reports, and artifact retention.
2. Extract core handle/options and canonical context validation. Reuse model
   validation and authorize every service operation; test invalid scope and
   malformed trusted-context dimensions before any I/O. HTTP context derivation
   stays adapter-owned, followed by the same canonical validator.
3. Move relational graph construction into `etlantic-sqlmodel`; construct shared
   services directly. Wire all stores to one engine and the correct shared
   `store_id`, report scope, input owner, and policy providers. Add the schedule
   store when 057-Q is ready, without creating a second graph.
4. Adapt `ETLanticAPI` to injected canonical services; legacy enable/construction
   paths delegate to the shared builder. Compatibility wrappers preserve existing
   `.api.managed_service`, configuration, app lifespan, and role factory access.
5. Make resource ownership explicit: internally created engines are owned;
   injected engines remain caller-owned. Partial-construction failures dispose
   only owned resources. Close is idempotent, blocks future role construction,
   and cannot dispose resources under an active tick or retained execution.
   Close during active work returns a stable busy result/error; drain and join
   remain consumer responsibilities. Track active role use with a core lifecycle
   guard; do not hold its lock across execution or database I/O.

**Exit:** built-wheel headless construction, authorized service calls, and all
three roles work in a clean environment without FastAPI installed. Gateway
imports and construction load no run/action execution modules. Headless/HTTP
callers share the actual service graph and equivalent records/decisions.

### 057-S — Move authorized schedule commands into services (#279)

1. Characterize all existing schedule routes and errors before moving them.
   Extract command parsing/validation into transport-independent canonical types;
   HTTP deserialization uses those types rather than domain algorithms.
2. Move operation/object authorization, filtered listing, opaque denials,
   workload binding permissions, definition-revision pinning, parameter/secret
   reference validation, policy fingerprinting, and clock calculations into the
   shared service. Authorize binding before resolving references or persisting.
3. Require `expected_revision_id` for safe amendment and preserve store CAS;
   reject missing/stale revisions identically through Python and HTTP.
   Preserve pause/resume semantics and preview bounds/time-zone handling.
4. Centralize trigger preparation, immutable occurrence snapshot, claim,
   recovery lookup, submission, and link. Keep accepted firing and submission
   identities stable through duplicate triggers, lost responses, retries, and
   restart. A retry uses stored occurrence evidence, never a newer definition,
   workload binding, parameter snapshot, or policy fingerprint.
5. Make route handlers delegate to this service. Retain scheduler/worker health
   routes as transport projections of the eventual role facts where applicable;
   command extraction must not force optional reference callers into a managed
   runtime. Document and test their preserved capability limits.

**Exit:** service-level conformance covers every command and authorized read;
HTTP parity covers decisions, safe errors, filtering, revisions, conflicts,
canonical records, firing and submission identity. No headless client needs a
Request, route function, direct store access, or duplicated schedule algorithm.

### 057-Q — Supply the complete scheduler graph (#280)

1. Construct the existing `SQLModelScheduleStore` on the shared provider engine
   and durable store identity. Expose it on the core handle and HTTP facade.
2. Add `backend.create_scheduler(*, owner_id, ...)` using canonical service scope,
   profile/trust validation, clock, lease settings, and the complete occurrence
   collaborator. Reject missing collaborators and invalid/empty owner identities
   during construction; standard callers supply no semantic callbacks.
3. Make scheduler preparation and recovery explicit. Remove bound-method
   inference from the standard path; if legacy inference is temporarily kept,
   isolate it in a documented compatibility adapter. Advanced callers receive
   an explicit collaborator or explicit preparer/submitter/recoverer contract;
   supplying a wrapper cannot silently downgrade managed recovery.
4. Reuse the canonical occurrence path from 057-S and existing managed helpers.
   Preserve leadership fencing, revision races, catch-up/skip semantics, and
   reconciliation of accepted unlinked firings before admitting new work.
5. Inject crashes after preparation, claim, acceptance, and linking, including
   link acknowledgement loss. Run two independent scheduler processes and
   workers against the same PostgreSQL store; amend definitions/schedules
   between attempts to prove pinned occurrence authority.

**Exit:** manual and scheduled runs share canonical preparation/admission;
two schedulers cannot produce duplicate accepted occurrences. Restart recovers
unlinked accepted firings without blind replay or rebound execution authority.
Low-level non-managed paths retain explicit support limits.

### 057-I — Publish provider-owned schema inspection (#281)

1. Add a versioned provider requirements manifest for managed-backend schema
   objects and their runtime-critical columns/keys/constraints. Migration modules
   remain operator-owned; consumers never duplicate table names, migration chains,
   version-row layout, or internal SQL. Verify manifest drift in migration tests.
2. Inspect metadata and version-row integrity through a connection-only,
   bounded read path. Do not call migration helpers, `create_all`, DDL, explicit
   commit, or a write transaction. Ordinary constructors and store initializers
   must preserve the same no-DDL/no-commit boundary.
3. Return these states with safe reasons: `fresh`, `behind`, `compatible`,
   `unknown_or_ahead`, `partial_or_corrupt`, and `unreachable`. A current marker
   with missing required objects is corrupt. Missing/empty version markers in
   a partially populated ETLantic schema are not fresh. Validate expected marker
   columns, exactly one valid version row, and recognized revision integrity.
   Failed or unauthorized metadata access cannot yield `compatible`.
4. Keep database facts distinct from a consumer's qualified PostgreSQL server
   version, topology, or deployment policy. Bound/normalize observed metadata;
   report stable codes rather than connection URLs, SQL parameters, or raw errors.
5. Reuse inspection in standard backend construction. Reject incompatible or
   unreachable schemas before services accept work; point to explicit operator
   migration/recovery. Preserve `current_version()` as its existing public API.
6. Cover all states on SQLite and applicable PostgreSQL fixtures. On real
   PostgreSQL use a separate runtime login with CONNECT, schema USAGE and
   required DML only: no CREATE, ownership, inherited migrator role, or privileged
   memberships. Capture statements and schema snapshots, then separately execute
   normal runtime DML through the backend to prove useful least-privilege access.

**Exit:** public inspection and ordinary construction are provably read-only;
requirements and compatibility belong to the provider. Neither consumer SQL nor
an upstream constructor-DDL workaround is necessary.

### 057-R — Add runtime status and cooperative drain (#282)

1. Freeze independent status dimensions: role kind; `idle/active/standby` activity
   (standby where supported); `accepting/draining/stopped` admission; prerequisite
   `unknown/usable/unusable` facts; bounded safe reasons and observation time;
   in-flight count and supported supervision capabilities. Workload outcome and
   process liveness are separate. Initial health is unknown; zero work is not a
   successful health check. Leader contention is standby, while provider failure
   is unusable/unknown according to the actual observation.
2. Implement thread-safe snapshots across scheduler, run worker and action
   worker. Status reads cached/local observations without claiming work,
   acquiring/renewing leases, resolving execution secrets, or changing durable
   state. If a public prerequisite probe is needed, make it separately explicit,
   bounded and read-only. Consumers own observation freshness and probe transport.
3. Implement a nonblocking, monotonic, idempotent drain request and checks before
   each new claim/dispatch. Describe the claim already in progress when drain
   wins: either safely finish/release it using existing fencing or retain it as
   in-flight work that must finish/recover. Never orphan a claim or fabricate a
   terminal result to report shutdown. Prevent new claims within multi-item ticks.
4. Drain-only is the standard stop mode: in-flight execution, heartbeat/fencing,
   cancellation checks, deadline enforcement, and result publication continue.
   Do not equate process drain with an authorized workload-cancel command. If a
   role advertises an additional cooperative cancel mode, require separate
   capability and qualification; unsupported cancellation is explicit.
5. A consumer runs blocking ticks on its own execution thread and can inspect
   status/request drain concurrently. Document one active tick per role instance,
   reject concurrent ticks safely, and avoid lifecycle locks over I/O. Drain
   reports stopped only after all dispatched work and owned monitors settle.
6. Test repeated drain, idle/active/standby, provider outage and recovery, lease
   loss, long-running runs/actions/preparation, and scheduler claim races. When
   supervisor grace expires, retain truthful active/draining status; forced
   process death leaves fenced recoverable work. Restart creates a fresh role
   and uses durable recovery. Never dispose an engine beneath active execution.

**Exit:** every role has a documented safe supervision path and redacted status.
Long work does not block a supervisor's status/stop requests. Outage, standby,
process liveness and workload success cannot be conflated.

## Delivery sequence and reviewable increments

| Gate / increment | Depends on | Deliverable and required proof |
|---|---|---|
| A — Contract and characterization | Current 0.56.2 baseline | ADR, exports/signatures, import/config/context/lifecycle inventory, schedule HTTP characterization, issue-to-evidence ledger. |
| B — Provider inspection | A | 057-I public requirements/results, construction guard, SQLite state matrix and real PostgreSQL least-privilege proof. |
| C — Headless backend extraction | A, B for final constructor | 057-B core/provider graph and compatibility facade; clean-wheel no-FastAPI and gateway-isolation proof. |
| D — Schedule commands | A, C for standard wiring | 057-S service and HTTP delegation; authorization/CAS/trigger-recovery parity. |
| E — Complete scheduler | C, D | 057-Q explicit collaborator/factory; two-process PostgreSQL and interrupted-link recovery proof. |
| F — Runtime supervision | A, C; E for scheduler integration | 057-R role status/drain, lifecycle guard, race/outage/grace/restart proof. |
| G — 0.57.0 release | B–F | Complete installed-artifact qualification, upgrade/compatibility guidance, public docs and all five issue acceptance ledgers passed. |

Inspection and core contract development can proceed independently after A;
supervision can be implemented alongside schedule extraction after interfaces
are frozen. Integration gates run in the order above. Each increment includes
its relevant regression tests; one issue does not close merely because its
first extraction commit merged.

## Qualification and evidence

Use existing fixtures as the regression base:

- Backend and compatibility: `tests/fastapi/test_managed_backend_0_56.py`,
  `test_managed_consumer_0_56.py`, `test_managed_application_0_56.py`, and
  `test_managed_import_isolation_0_56.py`; move reusable headless fixtures into
  service/provider test modules that do not import or skip on FastAPI.
- Schedules: `tests/fastapi/test_schedule_routes_0_47.py`, `tests/schedule`,
  `tests/sqlmodel/test_schedule_store_0_47.py`, and
  `tests/fastapi/test_managed_postgresql_process_0_56.py`. Add genuinely headless
  multi-process cases rather than require an HTTP fixture to prove independence.
- Workers: action/preparation, control-race, provider-matrix, fencing and recovery
  cases in `tests/fastapi`, `tests/runtime`, and `tests/control_plane`.
- Schema: `tests/sqlmodel/test_cp1_migrations_0_51.py` and existing #273 tests;
  add requirement-manifest, corrupt-head, statement-capture, and connection-failure
  cases through only the public inspector.

The acceptance ledger must cover every bullet in each linked issue. Include at
least the following integrated cases in `evidence/phase_0_57/`:

| Case | Mandatory observation |
|---|---|
| I278-H | Clean core/provider wheels; FastAPI absent; construct backend, submit authorized work, run both workers, construct/tick scheduler; no Request/context-factory workaround. |
| I278-G | Fresh-interpreter public gateway import and construction without execution modules; existing compatibility imports/call signatures and non-default option propagation. |
| I278-L | Shared graph identity, partial-failure cleanup, owned/borrowed engine close, repeated close, active-work close rejection. |
| I279-P | Every schedule command/read through Python and HTTP; matching authorization/disclosure/filtering, revisions, conflicts, records and canonical occurrence identities. |
| I279-R | Concurrent duplicate trigger, response loss, cross-scope/workload denial, stale amendment, and interrupted linking; no secret resolution before authorization. |
| I280-M | Manual/scheduled admission parity and explicit prepare/submit/recover wiring, including a wrapped collaborator with unchanged capabilities. |
| I280-C | Two real scheduler processes; crash/restart at each commit boundary; pinned occurrences and recovery of accepted unlinked firings on one PostgreSQL store. |
| I281-S | Public SQLite/PostgreSQL inspection state matrix; malformed marker and current marker/missing table; no DDL or explicit commit during inspection/construction. |
| I281-P | Real restricted PostgreSQL role without CREATE/ownership/inherited migration privileges; statements and schema snapshots plus separate useful runtime DML. |
| I282-T | All roles: idle/active/standby where applicable, repeated drain, stop-versus-claim races, concurrent supervisor response during long work, provider outage/recovery and lease loss. |
| I282-X | Grace expiry, forced process death and restart; truthful in-flight state, recovery/fencing, no synthetic completion, no engine disposal under execution. |

Build matching 0.57.0 wheels and test core-only, core+SQLModel without FastAPI,
gateway adapter, and full scheduler/workers in clean subprocess environments.
Qualify supported Python 3.11–3.13 and relevant SQLite/PostgreSQL/platform CI
combinations; record exact limits. Extend `.github/workflows/checks.yml` so
required live and installed-wheel cases cannot silently skip in release gates.
Reuse `ETLANTIC_SQLMODEL_TEST_URL` only with disposable isolated test resources;
never write URLs/credentials into evidence.

Each evidence row records issue acceptance bullet, case, commit, wheel hashes,
Python/OS/provider/database versions, topology, reproducible command, expected
invariant, observed result, redacted artifact, timestamp, and passed/failed/blocked
decision. Evidence starts pending. Fakes do not substitute for mandatory real
PostgreSQL and installed-process observations.

Run targeted tests during implementation, then the relevant full regression
groups and existing quality gates: Ruff check/format, Pyright, plugin manifests,
surface inventory, diagnostic stability, protocol freeze, docs checks, strict
docs build, and release checks. Update generated OpenAPI snapshots only for an
intentional reviewed change; preserved schedule routes should remain compatible.

## 0.57.0 packaging, migration and release closure

1. During implementation, keep 0.56.2 as published/current. During
   candidate preparation align core `_version.py`, project/package versions,
   dependency floors, lock data, plugin manifests and compatibility declarations
   using existing release tooling. New extracted API users require 0.57.0; do not
   weaken historical 0.56 matched-minor constraints to make imports work.
2. Decide from schema diff whether a migration is required. Extraction alone
   must not create a new revision marker. If new persistent fields are actually
   necessary, add an explicit versioned migration and 0.56→0.57 fixtures before
   construction accepts that schema. Qualify persisted definitions, schedules,
   accepted firings, actions, runs, and recovery obligations across upgrade.
3. Publish migration examples for legacy FastAPI constructors, new headless
   construction, adapting an existing backend, explicit scheduler collaborators,
   public schema inspection, and supervisor drain/join/close. Explain any legacy
   inference deprecation and unchanged external-effect limits.
4. Add 0.57 release notes, migration and exit-gate pages, API/config/CLI references
   where affected, provider/readiness/stop contracts, supported dependency matrix,
   surface inventory and examples. Core/SQL optional boundaries remain enforced.
5. Update release facts to candidate and finally published only at the appropriate
   release stage; retain immutable 0.56 evidence and truthful support-line claims.
   Build/install rehearsals and all I278–I282 cases must pass before v0.57.0.
6. Close #278–#282 only with links to merged implementation and passing acceptance
   evidence from the final candidate. No required acceptance bullet is deferred
   into 0.58. Brownfield and later phases consume these public contracts and do
   not reconstruct the graph, inspect internal schema, or duplicate ETL state.

**Release blockers:** FastAPI required by headless construction; HTTP-owned
schedule semantics; implicit managed recovery discovery; incomplete schedule
graph; constructor/inspection DDL or commit; corrupt schema reported compatible;
unsafe role drain/close; missing mandatory live/installed evidence; leaked
credentials; or any unimplemented acceptance bullet in #278–#282.
