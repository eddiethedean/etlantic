---
title: ETLantic 0.56 Execution Plan
description: Ordered delivery and release gates for the complete application ETL backend.
plan_status: current
plan_last_reviewed: v0.55.0
---

# ETLantic 0.56 Execution Plan

**Implementation in progress; release qualification remains open.** This
document sequences the [implementation contract](IMPLEMENTATION_PLAN_0_56.md).
Its acceptance criteria
are normative; this sequence does not narrow their scope. The
[findings ledger](FINDINGS_0_56.md) records the reviewed source, not a claim that
these features have shipped.

The [standalone compatibility reset](EXECUTION_PLAN_0_56_STANDALONE.md) is a
release-contract overlay: it replaces 0.55 upgrade/read compatibility with a
canonical 0.56 state boundary. Backend feature delivery and current 0.56
security, recovery, and provider qualification remain in force.

## Entry and release boundary

The 0.55.0 release is published. Implementation starts from the final
`v0.55.0` tag and the [final-tag reconciliation](FINDINGS_0_56.md#final-055-release-reconciliation).
Preserve its scoped inference qualification and recorded release evidence.
Review later maintenance commits as explicit 0.56 inputs, not as an assumed
change to the compatibility baseline.

0.56 owns the complete generic application backend, live isolated PostgreSQL
qualification, immutable CSV inputs, and Foundry API qualification against
Semblance loopback simulators. A live Foundry account is not required. Later
0.57 backend independence and supervision, 0.58 brownfield import, 0.59 console,
0.60 additional enterprise runtime/provider packs and 0.61 modeling incubation
consume this service. They cannot be used to defer a required 0.56 backend gap.

## Delivery sequence

| Gate | Work and dependency | Required exit evidence |
|---|---|---|
| A — Contract freeze | Reconcile 0.55; inventory public controls; choose service/envelope/action/identity interfaces and ownership | Reviewed ADRs, exact exports/schemas, coverage inventory and capability floor |
| B — Safe command boundary | Implement 056-SVC/SPEC/SECRET/RESOURCE and prepare/admit persistence; adapt HTTP to shared services | Headless/HTTP parity, isolation, immutable bindings, idempotent admission and migration fixtures |
| C — Real execution and recovery | Implement 056-WORKER/RESULT; join actual runtime to durable state and provider actions | Real bounded ETL, crash/fencing/cancel/effect/result-publication campaign |
| D — Complete control surface | Finish 056-ACTION/SCHEDULE/CONTROL and advanced setting propagation | Runnable actions, scheduler equivalence, all lifecycle commands and complete control map |
| E — Providers and independence | Deliver 056-PROVIDER and qualify private extensions/advanced engines | 12-pairing matrix through the real worker, using live PostgreSQL and Semblance-backed Foundry APIs; required modes, generic consumer and extension evidence |
| F — Release qualification | Complete 056-QUALIFY against built distributions and real stores | All AC rows evidenced, migration/recovery runbooks, support matrix and release decision |

Work can overlap after its prerequisite contracts are frozen. For example,
provider development and deterministic fixtures can proceed alongside worker
implementation, but end-to-end provider qualification depends on Gates C and D.

### Critical path and integration checkpoints

The critical path is contract freeze → authorized durable acceptance → real
worker/effect publication → executable controls → live PostgreSQL and simulated
Foundry provider matrix →
installed-wheel release decision. Run these integration checkpoints in order:

| Checkpoint | Required observable result | Limit of the checkpoint |
|---|---|---|
| B1 — accepted command | Headless and HTTP submit the same definition; the real relational store returns one scoped receipt across concurrent retry and restart | Acceptance does not claim ETL execution |
| C1 — complete reference run | A packaged worker executes a qualified local reference transfer, publishes a real report and effect receipt, and recovers after death between commit and publication | This does not qualify PostgreSQL or Foundry transfer |
| D1 — controlled run | The same run path supports an authorized action, a schedule firing and a runnable retry/repair case with stable lineage | Provider-specific limits remain explicit |
| E1 — provider transfer floor | Built provider packages execute all required pair/mode cases through the same acceptance, worker and result path; PostgreSQL uses an isolated live database and Foundry uses Semblance loopback simulators | Final support still requires Gate F security, migration and clean-wheel evidence |

Provider implementation begins after Gate A and supplies live PostgreSQL
control-store tests during Gate B. The reference run at C1 keeps the state
machine testable while the Semblance-backed Foundry and PostgreSQL connector
qualification proceeds.
No checkpoint changes the AC056-001–044 release floor.

### Gate A — Freeze exact public contracts

1. Audit the final 0.55 tag and every installed companion package used by the
   standard profile. Classify existing public support, incomplete integration,
   absent feature and unqualified deployment separately.
2. Name a maintainer role for every workstream and an evidence case for every
   acceptance criterion. Reuse issue #121 and issue #150; map any final fixes
   to regression evidence before creating additional implementation issues.
3. Record ADRs for service versus transport ownership, preparation/acceptance
   atomicity, immutable effective configuration, trusted scope propagation,
   provider actions and run/attempt/command lifecycle. Use existing authorities.
4. Freeze the state diagrams for preparation, submission, attempt, publication,
   cancellation/pause, action jobs, uploads and schedule firings. Specify
   transaction boundaries, recovery owners, idempotency scope and audit links.
   For each supported persistence topology, identify the single acceptance
   point and enumerate crash states before and after it. Compensation alone is
   insufficient once a command is reported accepted.
5. Publish exact Python exports, wire/schema versions, action identifiers,
   provider requirements, standard constructors and resource ownership. Cover
   all existing public controls, including provider-specific extension schemas.
6. Define upgrade treatment for historical payloads that lack verified plans or
   effective settings. They remain queryable and must never be silently promoted
   into new runnable work. Define offline migration versus lazy compatibility.

**Stop condition:** an adapter would need private imports, duplicated ETL
semantics, forged execution evidence or an application callback to complete
preparation. Resolve the upstream contract before implementing that adapter.

### Gate B — Build the authorized command path

- Extract service logic from route closures; every invocation takes trusted
  context. Object authorization and diagnostic disclosure are identical for
  HTTP and headless calls, including issue #150.
- Serialize existing canonical definition/run models losslessly and expose
  installed provider/configuration schemas. Persist effective settings and
  their provenance; semantic fingerprints come only from backend authority.
- Carry scope to secret/resource resolvers and define exact/late-bound version
  behavior. Add staged/finalized input references with leases and cleanup.
- Implement durable operation identity, canonical intent conflict checks,
  resumable preparation and single acceptance/handoff semantics. Bound policy,
  quota, approval and evidence refresh behavior across retries.
- Prove that retry finds the stored intent and receipt, and execution uses the
  accepted resolved revision. A later `latest-approved` edit cannot rebind an
  accepted receipt. Inject failure before and after the chosen acceptance
  point and run the reconciler.
- Qualify on the real relational provider early. Fakes remain unit fixtures;
  they cannot settle transaction, concurrency or restart semantics.

**Demonstration:** a minimal consumer authors, validates and submits a definition
through either adapter; duplicate requests recover one receipt across restart
and revision changes. Cross-owner resources are rejected before provider access.

### Gate C — Execute and recover actual work

- Replace default no-op completion with a packaged adapter to the authoritative
  runtime and a typed completion/effect contract. Keep explicit custom runtime
  integration available behind the same conformance requirements.
- Add in-flight heartbeat/cancel/budget enforcement, safe drain and fenced
  result/checkpoint writes. Scan durable recovery obligations, including work
  whose outbox item was already published.
- Publish actual reports, artifacts and lineage into the query/event surfaces.
  Recover publication separately from ETL effects and preserve unknown commit
  states until reconciliation establishes the outcome.
- Run effect/cleanup failure injection at every commit and acknowledgement
  boundary; distinguish rollback, committed, partial and unknown outcomes.

**Demonstration:** worker death after a write acknowledgement is lost cannot
cause a blind duplicate write. Worker death after commit but before report
publication can recover the report without replaying the transfer.

### Gate D — Complete actions, scheduling and developer control

- Implement test/catalog/schema/preflight, bounded preview and explicit
  provisioning as isolated action jobs with their own permissions and receipts.
- Route schedule firings and external triggers through the same command as
  manual runs. Persist occurrence/revision/parameter identity and clock policy.
- Turn retry/replay/resume/repair/backfill helpers into executable commands.
  Add state-aware action discovery, command lineage and safe amendments.
- Exercise every mapped option against the actual runtime. Include non-default
  retry/timeouts, selection/partitions, resource limits, quality/quarantine,
  write modes, incremental state, native implementations and private extension
  settings. An accepted option that is later ignored is a release blocker.
- Preserve advanced qualified paths: explicit SQL/PySpark and other engines,
  dynamic control, streaming and adaptive `/2` via authoritative admission.
  Capability restrictions must come from the selected provider/policy, not a
  fixed simplified application schema.

**Demonstration:** a consumer builds its own UI/workflow from public schemas,
requests supported non-default settings and run actions, and can inspect the
exact effective values and results without implementing ETL behavior.

### Gate E — Deliver providers and prove independence

- Package generic Foundry support independently; treat MSS and MCS-COP as two
  independently configured Semblance-backed simulator scopes. Vendor API
  integration and credential handling remain provider-owned. No live Foundry
  account is required for phase qualification.
- Qualify PostgreSQL append/upsert/atomic replacement against a live isolated
  database; explicitly verify keys, constraints, permissions, source/target
  overlap and reconciliation/cleanup semantics.
- Consume immutable CSV uploads in the worker with the declared parse/type
  controls and bounded failure behavior.
- Execute all 12 required pairings with each destination's advertised modes;
  add cancellation, failures, denied credentials, schema mismatch and overlap
  cases through the actual managed worker. Foundry endpoints use the local
  Semblance API simulator. Record actual provider capability limits rather than
  approximating atomicity across unrelated systems.
- Index each observation by source configuration, destination configuration,
  write mode, provider versions, scoped resources, worker attempt and effect
  receipt. Same-configuration transfers use distinct resources; aliases to the
  same resource exercise pre-mutation overlap rejection.
- Install an independently authored private provider with custom option schema
  and native implementation references. Exercise it through Python and HTTP
  without changing core or importing an adopter.
- Build a generic reference consumer from the standard configuration. It owns
  specifications, identity, presentation and business coordination only.

**Demonstration:** the same backend package set works under a small independent
consumer and under a composition facade. No app transfer loop, fingerprint
builder, worker callback or connector implementation is required.

### Gate F — Qualify and publish the exact release claim

- Close AC056-001–044 with immutable evidence from the release candidate.
  Record OS/Python, package, engine, provider, database and service topology.
- Exercise multiple real gateway/worker/scheduler processes, concurrent
  admission, lease loss, stale writes, restarts, backup/restore and retention.
- Run the isolation/redaction campaign across queries, action results,
  artifacts, event history, caches, denied lookups and uploaded references.
- Install wheels in clean environments and inspect public imports, generated
  schemas/OpenAPI, optional dependency boundaries and matched-minor packaging.
- Qualify clean initialization and current-state recovery. Reject 0.55 state
  before execution or mutation; qualify an offline converter only if Step 0 of
  the [standalone reset](EXECUTION_PLAN_0_56_STANDALONE.md) approves one. No
  automatic claim of downgrade safety.
- Publish per-feature and per-provider availability, limitations and diagnostics.
  Required live or adaptive observation cases cannot be converted to skips to
  obtain a green release decision.

## Required evidence index

Create a versioned release index during implementation, with one row per AC:

| Field | Required value |
|---|---|
| Identity | AC ID, findings/workstream links, case ID and maintainer role |
| Build | Commit, wheel hashes, exact package/provider versions and schema versions |
| Environment | Python/OS, store, engine, isolation profile and process topology |
| Observation | Command or scenario, expected invariant, actual result and timestamp |
| Artifact | Immutable log/report/trace reference with redaction applied |
| Decision | Passed, failed, blocked or genuinely inapplicable with reviewed capability rationale |

An evidence directory or exit-gate document created before execution must say
**pending**, never passed. Keep historical 0.55 evidence unchanged. Planning
checks for this phase are not runtime qualification.

## Closure rules

- Every finding F056-01–12 maps to passing acceptance evidence or an explicitly
  recorded open release blocker. No finding closes solely on merged code.
- The mandatory provider matrix, real worker, complete control map and generic
  consumer are release floors. Advanced support is advertised only for exact
  qualified combinations; optional providers can remain unavailable with a
  truthful explanation.
- Contract changes update implementation, roadmap, generated schemas, coverage
  inventory and downstream dependency notes together.
- A missing required service or simulator fixture blocks its qualification
  claim. Semblance is the required Foundry qualification target; no live Foundry
  account is required. No release date is implied by this plan.
