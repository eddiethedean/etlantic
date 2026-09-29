---
title: ETLantic 0.56 Implementation Plan
description: Complete application ETL backend with full specification and run control.
plan_status: current
plan_last_reviewed: 0.55.0-rc-source
---

# ETLantic 0.56 — Complete Application ETL Backend

**Status: planned; no implementation or qualification is claimed.** This phase
follows 0.55 inferred-model authoring. Brownfield bridges move to 0.57, the
operator console to 0.58, managed-runtime/provider packs to 0.59 and
TransformationModel incubation to 0.60. Their existing scope is preserved.

Read the [source review](FINDINGS_0_56.md) for the exact 0.55 candidate baseline,
the [execution sequence](EXECUTION_PLAN_0_56.md) for work dependencies, and the
[shared delivery contract](FORWARD_IMPLEMENTATION_PLANS.md) for release rules.
The source review identifies twelve integration/coverage gaps. Every gap is
required work in this phase; priorities determine ordering, not optionality.

## Outcome and ownership

An application can author a pipeline, supply trusted identity and references,
choose supported ETL settings, request actions, and observe results. ETLantic
and independently installable backend providers perform preparation,
extraction, transformation, validation, loading, scheduling, retries, recovery
and result publication. A standard deployment needs no application-supplied
ETL runner, transfer loop, compiler, fingerprint calculator or service sequence.

| Owner | Responsibilities |
|---|---|
| Application developer | Business intent; canonical definitions; parameters; source/target selections; transform and quality specifications; supported execution policies; schedules; run commands; business approvals and external workflow coordination |
| ETLantic core/services | Specification semantics; validation/planning; preparation/admission; effective configuration; authorization orchestration; durable state machines; execution coordination; recovery; public schemas and diagnostics |
| Independent backend providers | Connector I/O, engines/compilers, resource and secret access, storage, deployment/runtime integrations, provider-specific capabilities and implementation |
| HTTP/CLI/composition adapters | Identity adaptation, transport, deployment wiring, lifecycle and presentation of the same public services |

The dependency direction remains application → optional composition layer →
ETLantic → declared providers. ETLantic and its standard providers must install,
run and qualify without ShuETL, Data Mover or another consuming application.
Applications may use ETLantic directly. Identity and credential-store bridges
are permitted integration seams and do not transfer ETL ownership to the app.

### Full developer control

The reference transfer is a minimum acceptance example, never the complete
product language. Preserve every qualified public specification field,
provider option, execution control, query and extension path. Developers can
generate definitions programmatically, import/export them, choose execution
engines, use portable or explicitly selected native implementations, orchestrate
business workflows and install private extensions without a core code change.

Operator policy and actual provider/runtime capability bound execution. Each
restriction must identify its source and an actionable reason. Presets cannot
silently remove upstream controls. Unknown semantic fields fail explicitly;
namespaced extension data round-trips according to its registered schema.
No public publication or central plugin registry approval is required for a
private package; operator trust policy and conformance still apply.

## Reuse and compatibility decisions

- Evolve `PipelineDefinition`, `RunRequest`, authoring catalog, control-plane
  context, CP1–CP4, connector protocols and runtime/report models. Do not create
  a competing definition, run, plan, authorization or scheduling authority.
- Extract/reuse authoritative logic from HTTP closures and the reference
  authoring service. Keep the non-CP demo explicitly distinguished from the
  durable production service.
- Use public exports and versioned schemas. Proposed names in implementation
  discussions become public only after the contract review. Freeze exact
  signatures, sync/async behavior, ownership and compatibility at Gate A.
- Preserve explicit portable execution and native extension paths. Adaptive
  `/2` stays opt-in and governed by its own admission/evidence contracts;
  qualify the managed path for an exact supported tuple rather than bypassing
  admission or treating skipped checks as support.
- Keep optional engine/vendor dependencies out of core. Standard local and
  PostgreSQL deployment recipes must construct the provider graph from
  configuration; advanced explicit provider injection remains available.
- Preserve 0.55 package versions and release evidence while this is a plan.
  Version bumps, migrations and availability claims belong to implementation
  and release qualification. The final 0.55 tag is the compatibility baseline.

## Workstreams

| ID | Required delivery | Existing authority to reuse | Review gaps |
|---|---|---|---|
| 056-SVC | Authorized transport-neutral services and standard construction/lifecycle | ControlPlaneContext, authorizer, stores, ETLanticAPI, AuthoringService | F056-01/12 |
| 056-SPEC | Complete schemas, discovery, typed effective run configuration | PipelineDefinition, RunRequest, AuthoringCatalog, plugin capabilities | F056-02 |
| 056-ADMIT | One resumable prepare/admit/accept command | Validation/planner, CP4 policy, CP1/CP3 identity/outbox | F056-03 |
| 056-WORKER | Real managed runtime adapter, bounded execution, fencing and recovery | ExecutionHost, local/adaptive runtime, leases/checkpoints/effects | F056-04 |
| 056-RESULT | Durable status, reports, artifacts, lineage and resumable events | Runtime reports, artifact/event providers, scoped queries | F056-05 |
| 056-ACTION | Isolated connection/catalog/schema/preflight/preview/provision actions | Connector SDK, inference, readiness checks | F056-06 |
| 056-SECRET | Authenticated resource scope, version and credential lifecycle | SecretRef and secret-provider protocols | F056-07 |
| 056-RESOURCE | Immutable staged inputs and retention/lease management | Workspace roots, file/landing and artifact/storage providers | F056-08 |
| 056-SCHEDULE | Manual/scheduled/external trigger equivalence | ScheduleSpec, occurrence identity, durable schedule stores | F056-09 |
| 056-CONTROL | Allowed actions and executable retry/replay/resume/repair/backfill | RunRequest, durable command and reliability primitives | F056-02/10 |
| 056-PROVIDER | Foundry package, PostgreSQL and CSV transfer qualification | Connector source/sink/storage and compiler contracts | F056-11 |
| 056-QUALIFY | Extensions, security, migration, clean-wheel and live evidence | Public conformance SDK and release tooling | F056-02/11/12 |

## Required behavior

### One preparation and acceptance path

The public submission command owns this sequence, including any asynchronous
continuations:

1. Authenticate/adapt trusted context and authorize the operation and resources.
2. Recover an existing operation/submission for the scoped idempotency key and
   canonical intent; conflicting intent gets a stable conflict. Authorization
   is rechecked without re-running live probes or charging quotas twice.
3. Resolve the definition/revision selector once, bind resources/parameters and
   compute canonical effective settings and backend fingerprints. Fingerprints
   include every execution-relevant choice and exact qualified dependencies.
4. Validate and plan with existing semantic authorities; run explicitly selected
   bounded live preflight in an action executor. A pure validate/plan call does
   not resolve secrets, run user transformations or write to providers.
5. Evaluate current policy, quotas, approvals, plugin trust and environment
   evidence. Bind approvals to scope, effective specification/plan and expiry.
   Caller-supplied hashes cannot establish trust. A reviewed plan reference is
   usable after backend verification of content, provenance and freshness.
6. Commit one immutable execution envelope plus its durable handoff. Publish
   admission events through recoverable outbox handling. Return canonical
   operation/submission/run identities and a queryable status.

Long preparation returns an operation identity, not a recipe for app callbacks.
Cancellation, failure and process restart have explicit preparation states;
the backend resumes or terminates them without asking the app to reconstruct
the sequence. Preparation receipts distinguish static facts, observed live
evidence, expiry and unknown/unavailable checks. Admission verifies that evidence
is still usable; preflight is not a promise that future external I/O succeeds.

CP1 and CP3 must share a transaction where the provider supports one, or use a
documented durable handoff/reconciliation protocol with equivalent observable
guarantees. No accepted command may become orphaned. Retry of an accepted
request remains discoverable during provider outages or later revision changes.

### Effective specification and control coverage

Publish a machine-readable coverage inventory of public field/command/query →
Python service → transport schema → persisted representation → runtime consumer
→ evidence case. Include defaults, override precedence, types, constraints,
sensitivity, provider/version requirements and unavailable reasons.

Coverage includes source/target selectors and bindings; all writer modes and
keys; parameters; contracts and schema policy; transforms/quality/quarantine;
node/partition/run selection; intent; incremental cursors and checkpoints;
engine/compiler/native implementation; materialization/cache/invalidation;
retry/backoff, timeout, cancellation; resource/concurrency/row/byte budgets;
preview/no-write; schedules; governance/approvals; and registered extensions.
Use existing canonical models where each concept already exists.

Store requested settings, resolved defaults and effective values with their
provenance. Snapshot queued/accepted work immutably. Supported amendments create
an audited command and a new configuration generation applied at a declared
safe boundary; they never rewrite historical attempts. Explain which settings
require a new run and which can change while queued, paused or running.

### Managed execution and results

The standard worker resolves the accepted envelope and runs the authoritative
runtime. Gateway code never holds live provider credentials or performs ETL
I/O. CPU/blocking work runs in a role that can enforce its advertised isolation,
limits and cancellation; mere async method signatures are insufficient.

Worker readiness fails if no real execution adapter exists. A plugin returning
normally or a no-op callback cannot establish completed ETL. Use typed runtime
outcomes, effect receipts and durable result publication. Define execution,
publication and cleanup statuses separately so a committed target plus lost
report acknowledgement cannot be misreported as either a clean rollback or a
safe whole-run retry.

Renew leases while work runs, poll cancellation, fence stale attempts, bound
resource use and drain explicitly. Reclaim expired work even after its outbox
item was published. Recovery consults checkpoints and effects before retrying.
Unknown external commits require reconciliation or an authorized repair;
never blindly repeat a possibly committed write. Cleanup is scoped, idempotent
and resumable, with its own observable outcome.

Expose actual run/attempt/stage/node/partition state, counters, quality/schema
findings, timings, diagnostics, plan/effective-config references, effects,
lineage and artifact metadata. Preserve dynamic-child and branch identities.
Authorize every query, pagination cursor, download and event subscription.
Support resumable events, history fallback and explicit cursor-gap semantics.
Bound and redact result data; ordinary reports contain no secret values or
unbounded source rows.

### Provider actions, credentials and input resources

Connection tests, paginated catalog/branch/table/dataset/file discovery, schema
inspection and live preflight are first-class authorized operations with stable
identities and bounded execution. Preview uses a separately authorized bounded
data result with explicit retention/redaction. Provisioning requires its own
permission, idempotency, effect and cleanup contract; never create a target as
a side effect of ordinary validation, planning or browsing.

Carry trusted workload/principal, tenant/workspace and resource owner, action
purpose, run/attempt and policy context into providers. Never trust owner IDs
from an arbitrary payload. Resolve exact secret versions or a deliberately
authorized late-bound alias, recording the actual version without the value.
Define rotation, revocation, lease renewal, expiry, outage and scoped cache
semantics; missing context cannot fall back to ambient global credentials.

Uploads use staged → finalized immutable → leased → retained/deleted states.
Verify checksum/length, owner, media/format and allowed storage location before
acceptance. Workers receive authorized durable references, not web upload
objects, mutable local paths or arbitrary user-controlled URLs. Declare how
checksums/manifests and immutable external versions bind a source snapshot.
Retention cannot delete inputs needed by accepted work, supported retries or
replay; expired inputs produce a stable diagnostic. Abort/orphan cleanup is
bounded and scope-safe. Local and remote stores implement the same contract.

### Scheduling, run actions and business workflows

Scheduled firings, manual runs, external event triggers and external workflow
tools use the same prepare/admit/accept service. A schedule declares pinned or
latest-approved revision policy, effective parameter rules, timezone, DST,
misfire, catch-up, overlap and concurrency behavior. Resolve a firing once and
persist its selected revision/identity; a later edit cannot change it. Workload
identity, policy and credential access are re-evaluated at the required boundary.

Expose allowed actions by caller, current state, policy and provider, including
preconditions and reasons. Authorize again on execution to handle races. Retry,
rerun, replay, resume, repair and backfill are runnable commands with explicit
new-run versus new-attempt semantics, idempotency and source/parent lineage.
A generated repair plan is not evidence that a repair executed.

Include queued cancellation and in-flight cancellation, supported pause/resume,
and audited amendments. Provider limitations must be truthful; pause may only
be offered at a qualified checkpoint/quiescence boundary. External business
approvals and workflows remain app-controlled; the app requests backend
commands and observes outcomes, while ETLantic owns ETL retries, checkpoints,
effect reconciliation and step execution.

### Required provider delivery

| Provider/input | Required 0.56 scope |
|---|---|
| PostgreSQL | Live source/sink/schema/catalog/test/preflight qualification; append, keyed upsert and atomic replacement with explicit table/schema/index/constraint/grant behavior; bounded reads and staged writes; permissions, overlap, cancellation, commit uncertainty and cleanup |
| Foundry | Independent generic optional provider package; source/sink/storage and test/catalog/schema/preflight; datasets/branches, multi-file manifests and safe relative paths, destination file replacement and explicit empty-dataset provisioning where supported; transactional/effect/reconciliation capability declared accurately |
| CSV uploads | Immutable staged reference consumed by the worker; encoding/delimiter/header/type policies, bounded parsing, validation, malformed-input outcomes and cleanup |
| Existing execution providers | Preserve qualified explicit SQL/PySpark and other engine/compiler controls, portable quality/transforms, native extensions and dynamic/incremental/streaming semantics in the managed service matrix |

MSS and MCS-COP are two Foundry configurations. Qualification must cover distinct
endpoints, credentials and namespaces, including same-provider transfers, with
no product imports. The minimum adopter matrix has four source configurations
(two Foundry, PostgreSQL, CSV) × three destinations (two Foundry, PostgreSQL):
**12 pairings**, expanded by each destination's advertised write modes. Reject
unsafe source/target overlap before mutation, including aliases to the same
resource. Support declarations must distinguish available, unavailable and
unqualified combinations without disguising an unimplemented required row.

The mandatory transform/quality path includes select/drop/rename, casts,
filters, scalar derivations, deterministic deduplication and schema/not-null/
range/membership validation with declared reject/quarantine behavior. It is a
release floor; joins, unions and every other qualified public operation remain
accessible. Generic Foundry and PostgreSQL delivery are owned by this phase;
the broader enterprise cloud/runtime portfolio remains in 0.59.

## Acceptance criteria

All criteria below must have named evidence in the release index. Conditional
behavior is tied to real capability declarations; it cannot waive the mandatory
provider matrix or substitute a stub for an implemented service.

| ID | Required acceptance evidence | Owner |
|---|---|---|
| AC056-001 | The same register/edit/validate/plan/submit/query commands work headlessly and through HTTP with identical semantic results and errors, without a synthetic request or private imports | 056-SVC |
| AC056-002 | Per-operation authorization precedes lookup; explicit disclosure policy, cross-tenant/workspace/owner isolation and concurrent calls are equivalent across adapters | 056-SVC |
| AC056-003 | Configuration constructs a standard backend; explicit resource ownership, shared lifespans, partial-start cleanup and shutdown preserve accepted durable work | 056-SVC |
| AC056-004 | Every qualified public field, command and query has a coverage-map row through storage to runtime; omitted/downgraded controls fail qualification | 056-SPEC |
| AC056-005 | Typed request import/export preserves overrides and extension data; defaults/precedence and effective-setting provenance are deterministic and inspectable | 056-SPEC |
| AC056-006 | Installed-provider discovery supplies schemas, types, constraints, defaults, sensitivity and compatibility; unknown semantic options are rejected with a stable reason | 056-SPEC |
| AC056-007 | One command resolves revisions/resources and derives plan/effective fingerprints; forged hashes/revisions cannot bypass planning, policy or approval binding | 056-ADMIT |
| AC056-008 | Identical scoped retries recover the same receipt before live work or quota charging; changed intent conflicts, including concurrent requests | 056-ADMIT |
| AC056-009 | Long preparation survives process death and supports query/cancel by operation ID, without app-side sequencing or secret exposure | 056-ADMIT |
| AC056-010 | Failure at every CP1/CP3/outbox boundary leaves a discoverable accepted command or a recoverable, explicit rejection; no orphan or duplicate execution | 056-ADMIT |
| AC056-011 | Static checks remain pure; live preflight uses bounded executors; policy, approvals, quotas and evidence freshness are checked against the final effective plan | 056-ADMIT |
| AC056-012 | A packaged worker performs real ETL from a submitted canonical definition without a caller runner; missing execution support fails closed | 056-WORKER |
| AC056-013 | Long work renews leases, reacts to in-flight cancellation and fences stale owners; advertised row/byte/time/memory/concurrency limits are enforced | 056-WORKER |
| AC056-014 | Crash after outbox publication, lease expiry, worker death and restart recover safely with stable attempt identities | 056-WORKER |
| AC056-015 | Unknown commits, lost acknowledgements and partial multi-sink effects require reconciliation; no automatic duplicate write or invented rollback | 056-WORKER |
| AC056-016 | Checkpoint/cursor advancement follows durable publication semantics; cleanup/drain/interruption are idempotent, scoped and observable | 056-WORKER |
| AC056-017 | Public status/report/lineage/artifacts reflect actual runtime work with stable run/submission/attempt/node/partition links; no acceptance stub masquerades as completion | 056-RESULT |
| AC056-018 | Commit-success/report-failure recovers publication without rerunning ETL; result and cleanup state truthfully represent remaining obligations | 056-RESULT |
| AC056-019 | Event resume, duplicates, cursor gaps, pagination, retention and artifact authorization pass reconnect and isolation cases | 056-RESULT |
| AC056-020 | Test/catalog/schema/preflight actions run outside the gateway with action authorization, pagination, deadlines, redaction and scoped receipts | 056-ACTION |
| AC056-021 | Preview executes only in a qualified bounded action role, isolates credentials, limits/redacts returned data and enforces separate retention | 056-ACTION |
| AC056-022 | Explicit provisioning has permission, idempotency, effect and cleanup evidence; ordinary inspection does not create or mutate targets | 056-ACTION |
| AC056-023 | Trusted owner/workload/scope/purpose reaches each worker/action secret and resource access; tampered references and cross-owner cache reuse are rejected | 056-SECRET |
| AC056-024 | Exact-version and authorized late-binding modes cover rotation/revocation/expiry/outage; actual version is auditable without leaking values | 056-SECRET |
| AC056-025 | Finalized uploads bind immutable version/checksum/length/owner; workers reject tampering, unsafe paths and unsupported format/resource locators | 056-RESOURCE |
| AC056-026 | Leases protect accepted/retry/replay inputs from retention; aborted uploads, orphans and expired inputs have bounded cleanup and stable outcomes | 056-RESOURCE |
| AC056-027 | Manual, scheduled and external triggers produce equivalent effective plans, authorization and admission for the same declared intent | 056-SCHEDULE |
| AC056-028 | Pinned/latest-approved selection, workload identity and parameter policy are recorded once per occurrence and survive concurrent edits/restarts | 056-SCHEDULE |
| AC056-029 | DST/timezone/misfire/catch-up/overlap/concurrency and scheduler outage cases preserve occurrence idempotency and firing-to-run linkage | 056-SCHEDULE |
| AC056-030 | Allowed actions reflect caller/state/provider with stable reasons; commands reauthorize and enforce state preconditions despite concurrent transitions | 056-CONTROL |
| AC056-031 | Retry/rerun/replay/resume/repair/backfill enqueue and execute qualified work, with distinct command identity, idempotency and parent/run/attempt lineage | 056-CONTROL |
| AC056-032 | Cancel, qualified pause/resume and safe amendments have tested boundaries; accepted snapshots and old attempts remain immutable | 056-CONTROL |
| AC056-033 | Live PostgreSQL append/upsert/replace, key/schema validation, permissions, overlaps, staged failure and commit/reconciliation cases pass | 056-PROVIDER |
| AC056-034 | Live Foundry dataset/branch/file operations, all declared write modes, overlap and effect/reconciliation cases pass in an isolated account/project | 056-PROVIDER |
| AC056-035 | Immutable CSV inputs exercise parsing/type/encoding choices, empty/malformed/oversize data and resource retention through the real worker | 056-PROVIDER |
| AC056-036 | All 12 minimum source/destination pairings and advertised modes have success/failure evidence, including two independently scoped Foundry configurations | 056-PROVIDER |
| AC056-037 | An independently built private provider installs without an adopter or core edit; its schema/options/native references survive authoring, submission and execution | 056-QUALIFY |
| AC056-038 | Issue #150 disclosure regression and the complete multi-tenant/owner redaction campaign pass for services, HTTP, actions, events and artifacts | 056-QUALIFY |
| AC056-039 | Real PostgreSQL control-plane persistence passes multi-process accept/race/restart/backup/restore and failure campaigns; memory/SQLite remain separately labelled | 056-QUALIFY |
| AC056-040 | Built wheels install in a clean environment; package/export/schema/OpenAPI compatibility, migrations, version skew and upgrade/rollback behavior are recorded | 056-QUALIFY |
| AC056-041 | Mandatory transforms/quality and every advertised engine/native/dynamic/incremental/streaming combination retain their semantics through the managed path; unsupported combinations explain their real limit | 056-QUALIFY |
| AC056-042 | Existing 0.55 definitions/runs/stores migrate; legacy incomplete payloads cannot execute under fabricated fingerprints or silently receive new semantics | 056-ADMIT |
| AC056-043 | At least one exact managed adaptive tuple passes authoritative `/2` admission/runtime and observed qualification; all other tuples remain truthful and fail closed | 056-QUALIFY |
| AC056-044 | A generated-spec consumer performs optional review/approval and external business orchestration using public commands alone, with no ETL implementation in its application path | 056-CONTROL |

## Release gates and required evidence

The [execution plan](EXECUTION_PLAN_0_56.md) defines Gates A–F. The release index
must join each AC ID to its case, environment, provider/version tuple, result
and immutable evidence artifact. A skipped required case is an unmet gate.

Required artifacts are the frozen public API/control-coverage inventory;
ownership/state-machine ADRs; schema and package compatibility report;
authorization/redaction report; durable failure/recovery campaign; live
PostgreSQL/Foundry/CSV pairing matrix; transform/quality and advanced-control
matrix; private-extension example; generic headless and HTTP consumer examples;
deployment/operations runbook; migration/rollback report; and signed release
decision with exact supported versus Experimental/unavailable claims.

The generic consumer must work from released/built artifacts without importing
ShuETL or Data Mover. Downstream adoption can provide additional evidence but
cannot become a prerequisite for ETLantic's independent build or qualification.
No gate closes on plans, accepted receipts, fake-provider success or callback
return alone. If a required gap remains, record it as an open release blocker.
