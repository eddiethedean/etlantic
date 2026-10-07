---
title: ETLantic 0.56 Backend Gap Review
description: Source evidence and required follow-up for the complete application ETL backend phase.
plan_status: current
plan_last_reviewed: v0.55.0
---

# ETLantic 0.56 Backend Gap Review

## Review baseline and limits

Reviewed on **2026-09-29** against main commit
[`fb0dd748860cdbafceea473f315ed8934a329b27`](https://github.com/eddiethedean/etlantic/commit/fb0dd748860cdbafceea473f315ed8934a329b27),
which merged [the 0.55 release candidate, PR #212](https://github.com/eddiethedean/etlantic/pull/212).
At review time the newest tag was **v0.54.0**; 0.55 source and package metadata
were present, but a published 0.55 distribution was not reviewed.

This is a source and documentation audit, not a new execution qualification.
The observed [main CI run](https://github.com/eddiethedean/etlantic/actions/runs/36576572689)
had 40 successful check runs and two skipped adaptive observation checks.
That evidence does not qualify the application backend described below.
The [0.55 exit gate](EXIT_GATE_0_55.md) qualifies a scoped Experimental inference
surface, including SQLite reference target writes. It does not establish live
PostgreSQL/Foundry transfer or a complete durable application execution path.
Carry forward regression coverage for anything fixed after this source review,
and recheck any later maintenance commits before 0.56 implementation.

### Final 0.55 release reconciliation

The final [`v0.55.0` tag](https://github.com/eddiethedean/etlantic/releases/tag/v0.55.0)
points to commit `702efa58b1ed2263fe8fac00dd0cdb553d09c60f`. A targeted
comparison from the reviewed commit to that tag found no changes under the
control-plane, runtime, service, secrets or connectors source trees, nor in the
FastAPI and SQL packages cited by these findings. The final release did change
inference and storage foundations; Gate A must inventory their final public
contracts before freezing 0.56 schemas. The twelve backend gaps remain open at
the final tag. In particular, `require_authorized_run` still probes scoped
existence after an explicit `not_found` denial (F056-12), and the packaged
`ExecutionHost` still defaults to a no-op runner (F056-04). This reconciliation
is a source check, not live backend qualification or a claim about future code.

The question is whether an independent application can specify and control its
ETL through public contracts while ETLantic and independently installed providers
perform the entire ETL lifecycle. ShuETL and Data Mover supplied requirements;
neither becomes an ETLantic build, runtime, test, or optional dependency.

## Existing capabilities to retain

| Foundation | Evidence in the reviewed source | 0.56 consequence |
|---|---|---|
| Canonical definitions and authoring | [PipelineDefinition and TransformationDefinition](https://github.com/eddiethedean/etlantic/blob/fb0dd748860cdbafceea473f315ed8934a329b27/src/etlantic/authoring/definition.py), versioned import/export and editing | Extend existing schemas; do not create a second pipeline language |
| Rich local run control | [RunRequest](https://github.com/eddiethedean/etlantic/blob/fb0dd748860cdbafceea473f315ed8934a329b27/src/etlantic/runtime/request.py#L231) already carries selection, intent, materialization, retry, timeout, cancellation, parameter/asset/implementation overrides, invalidation and no-write | Preserve all these choices through durable submission and managed execution |
| Transforms and quality | [Portable transformations](../04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md) and [quality models](https://github.com/eddiethedean/etlantic/blob/fb0dd748860cdbafceea473f315ed8934a329b27/src/etlantic/quality/model.py) cover much more than copying rows | Reuse compilers, deterministic operations, quality and engine capability checks |
| Durable and governed control plane | CP1–CP4 include identity, scoped stores, revisions, leases/fencing, effects, checkpoints, approvals, quotas and audit | Compose the existing authorities into a complete service; store primitives alone are insufficient |
| Connector and secret protocols | [Connector protocols](https://github.com/eddiethedean/etlantic/blob/fb0dd748860cdbafceea473f315ed8934a329b27/src/etlantic/connectors/protocol.py), SecretRef version/purpose and secret-provider lifecycle capabilities | Add management actions and scope propagation around these primitives |
| Scheduling and extensions | Durable schedules and occurrence identities, plugin SDK, native implementation references, dynamic control and public conformance | Preserve supported semantics and private provider extensibility |

## Confirmed gaps and required disposition

All rows are **open at the final 0.55 baseline**. P1 means a blocker for the complete
application backend release claim, not a security severity label. Implementation
belongs to the [0.56 plan](IMPLEMENTATION_PLAN_0_56.md); its acceptance IDs are
the closure criteria. Issue state alone is not evidence of missing code.

### F056-01 — P1: Production services independent of HTTP

[`AuthoringService`](https://github.com/eddiethedean/etlantic/blob/fb0dd748860cdbafceea473f315ed8934a329b27/src/etlantic/service/__init__.py#L104)
is explicitly an in-memory, non-multi-tenant reference. Its submit method ignores
idempotency and executes synchronously; cancellation cannot interrupt work.
`ETLanticAPI` composes stores into route closures, rather than exposing the full
authorized service commands needed by a headless host.

**Add:** public per-operation-context application services shared by Python,
HTTP, CLI and scheduling. Keep store/provider injection as an advanced surface.
**Workstream:** 056-SVC. **Acceptance:** AC056-001–003.

### F056-02 — P1: Lossless configuration and capability discovery

[`RunSubmitBody`](https://github.com/eddiethedean/etlantic/blob/fb0dd748860cdbafceea473f315ed8934a329b27/packages/etlantic-fastapi/src/etlantic_fastapi/schemas.py#L63)
accepts an untyped payload. Existing
[`AuthoringCatalog`](https://github.com/eddiethedean/etlantic/blob/fb0dd748860cdbafceea473f315ed8934a329b27/src/etlantic/authoring/catalog.py#L151)
provides a useful schema structure and built-in node kinds, but its default
negotiation is not an installed-provider option catalog or an authorized,
state-specific run action catalog. Local RunRequest controls are not a complete
durable submission contract just because a payload can contain arbitrary JSON.

**Add:** versioned request serialization, effective-setting provenance, complete
option/command/query mapping and provider schemas; reject unknown semantic
fields rather than silently dropping them. Preserve qualified advanced and
native execution choices. **Workstreams:** 056-SPEC, 056-CONTROL, 056-QUALIFY.
**Acceptance:** AC056-004–006, 030, 037, 041, 043–044.

### F056-03 — P1: Authoritative preparation and durable acceptance

The [submit route](https://github.com/eddiethedean/etlantic/blob/fb0dd748860cdbafceea473f315ed8934a329b27/packages/etlantic-fastapi/src/etlantic_fastapi/routes.py#L434)
does not call the full validation/planning/preflight path. It takes a supplied
plan fingerprint/plan ID or falls back to the definition ID, and accepts a
payload revision ID. CP4 admission precedes accept/deduplication. CP1 and CP3
acceptance are separate writes with compensation, followed by event publication.
These are insufficient guarantees for an immutable, prepared, replay-safe
application command across failures.

**Add:** one preparation/admission authority, backend-derived fingerprints,
resolved revisions and effective settings, resumable preparation, idempotent
recovery before repeating live work, and a durable commit/outbox protocol.
Reuse [issue #121](https://github.com/eddiethedean/etlantic/issues/121) for unified
preflight rather than opening a duplicate. **Workstream:** 056-ADMIT.
**Acceptance:** AC056-007–011, 042.

### F056-04 — P1: Managed worker must execute real ETL and recover it

[`ExecutionHost`](https://github.com/eddiethedean/etlantic/blob/fb0dd748860cdbafceea473f315ed8934a329b27/src/etlantic/runtime/execution_host.py)
uses a no-op default runner and marks its normal return completed. It publishes
the outbox item before invoking the runner, polls only pending outbox items,
and provides no in-flight heartbeat/cancel loop or recovery sweep in this host.
The [worker CLI](https://github.com/eddiethedean/etlantic/blob/fb0dd748860cdbafceea473f315ed8934a329b27/src/etlantic/cli/cmds/schedule.py#L336)
constructs this host without a runner. Real local runtime execution exists;
the missing part is the packaged durable host-to-runtime connection and its
recovery contract. Arbitrary custom runner returns cannot prove ETL completion.

**Add:** the standard runtime adapter, attempt/result protocol, heartbeat,
in-flight cancellation, crash reclaim and effect-aware recovery. A missing
execution adapter must fail readiness/admission. **Workstream:** 056-WORKER.
**Acceptance:** AC056-012–016, 041, 043.

### F056-05 — P1: Durable results and status projection

The [report, artifact and lineage routes](https://github.com/eddiethedean/etlantic/blob/fb0dd748860cdbafceea473f315ed8934a329b27/packages/etlantic-fastapi/src/etlantic_fastapi/routes.py#L749)
return an explicit report stub, a synthetic acceptance receipt and a minimal
definition-to-run lineage edge. The SQLModel CP1 submission store exposes
acceptance/cancellation state, without a worker completion/report projection
path in that adapter. Runtime reports and artifact providers already exist.

**Add:** durable publication of actual runtime outcomes into authorized queries,
consistent identities and reconnectable events, including report-publication
recovery after a sink commit. **Workstream:** 056-RESULT.
**Acceptance:** AC056-017–019.

### F056-06 — P1: Isolated connector actions

[Source/sink/storage protocols](https://github.com/eddiethedean/etlantic/blob/fb0dd748860cdbafceea473f315ed8934a329b27/src/etlantic/connectors/protocol.py)
define static plans, batches, schema inspection and commit/reconciliation.
The reviewed public service/API lacks a complete owner-authorized job path for
connection tests, paginated catalogs, live preflight, preview and explicitly
requested provisioning. Inference and static compiler preflight do not provide
that execution boundary by themselves.

**Add:** typed action requests, isolated bounded executors and authorized
receipts, reusing inference and connector logic where suitable. Preview and
provisioning are capability-negotiated actions, never implicit validation side
effects. **Workstream:** 056-ACTION. **Acceptance:** AC056-020–022.

### F056-07 — P1: Carry authenticated resource scope to secret resolution

[`SecretResolutionContext`](https://github.com/eddiethedean/etlantic/blob/fb0dd748860cdbafceea473f315ed8934a329b27/src/etlantic/secrets/provider.py#L58)
has run/pipeline/step/purpose and optional metadata, but no required authenticated
control-plane scope contract. The
[runtime resolver](https://github.com/eddiethedean/etlantic/blob/fb0dd748860cdbafceea473f315ed8934a329b27/src/etlantic/runtime/orchestrator.py#L4826)
constructs it without that scope. SecretRef already supports versions and
purpose; adding another secret-reference system would not fix this integration.

**Add:** trusted principal/workload, tenant/workspace and resource-owner context
propagation, policy checks, scoped caching and explicit version/rotation rules
for workers and action executors. **Workstream:** 056-SECRET.
**Acceptance:** AC056-023–024.

### F056-08 — P1: Immutable uploaded input lifecycle

Workspace roots, file/landing connectors and durable inference bindings exist.
No complete public application service was found for staging/finalizing an
owner-scoped upload, pinning its immutable version/checksum into a run, leasing
it across worker retries and coordinating retention/deletion. A workspace path
or host web upload object is not that contract.

**Add:** the resource lifecycle and a worker-resolvable binding; reuse existing
artifact/storage providers. **Workstream:** 056-RESOURCE.
**Acceptance:** AC056-025–026, 035.

### F056-09 — P1: Scheduler and manual submission must share authority

[`SchedulerService`](https://github.com/eddiethedean/etlantic/blob/fb0dd748860cdbafceea473f315ed8934a329b27/src/etlantic/runtime/scheduler_service.py#L30)
uses a configured `plan_fingerprint` defaulting to `"plan"` and directly claims
firings. It does not call a shared prepared application command. Existing
clock, DST, misfire, catch-up and overlap primitives should be retained.

**Add:** the same revision/parameter/preflight/admission path as manual triggers,
with workload identity, occurrence idempotency and recoverable firing-to-run
linkage. **Workstream:** 056-SCHEDULE. **Acceptance:** AC056-027–029.

### F056-10 — P1: Executable run commands beyond plan/record helpers

[`DurableWorkStore`'s reference implementation](https://github.com/eddiethedean/etlantic/blob/fb0dd748860cdbafceea473f315ed8934a329b27/src/etlantic/control_plane/durable_memory.py#L709)
records replay and returns resume/repair/backfill plans; those methods alone do
not enqueue and execute the corresponding managed work. Existing local runtime
controls remain useful foundations.

**Add:** authorized, idempotent command execution and state/provider-specific
allowed actions; preserve run/attempt/command lineage and explicitly supported
amendment/pause boundaries. **Workstream:** 056-CONTROL.
**Acceptance:** AC056-030–032, 044.

### F056-11 — P1: Required provider coverage and qualification

The [SQL package](https://github.com/eddiethedean/etlantic/blob/fb0dd748860cdbafceea473f315ed8934a329b27/packages/etlantic-sql/README.md#L76)
documents Experimental PostgreSQL connector coverage with SQLite fake evidence.
The 0.55 inference write reference is SQLite. No Foundry connector package was
found in the reviewed `src`/`packages` tree. Data Mover's MSS and MCS-COP are
Foundry configurations, **not Microsoft SQL Server**.

**Add:** a generic independently installable Foundry provider and qualify live
PostgreSQL plus immutable CSV inputs through the complete managed path. Qualify
Foundry API contract behavior against the Semblance-backed local simulator; a
live Foundry account is not part of qualification. Cover all advertised
source/destination pairs
and modes, overlap, permissions, bounded batches, cleanup and uncertain commits.
Named product deployments are configuration fixtures; core must never import
Data Mover.
**Workstreams:** 056-PROVIDER, 056-QUALIFY. **Acceptance:** AC056-033–036, 039–041.

### F056-12 — P1: Preserve explicit opaque denial policy

[`require_authorized_run`](https://github.com/eddiethedean/etlantic/blob/fb0dd748860cdbafceea473f315ed8934a329b27/src/etlantic/control_plane/authz.py#L98)
honors an explicit `forbidden` override but still probes existence for explicit
`not_found`; an existing scoped run then returns 403. This is the already-filed
[issue #150](https://github.com/eddiethedean/etlantic/issues/150), an existence
disclosure defect, not demonstrated unauthorized data access.

**Fix:** honor both explicit disclosure decisions before probing and exercise
the same policy in headless and HTTP services. Keep the issue's regression even
if fixed in the final 0.55 release. **Workstreams:** 056-SVC, 056-QUALIFY.
**Acceptance:** AC056-002, 038.

## Qualification risks, distinct from absent features

- Adaptive `/2` is explicitly rejected by the reviewed CP submit route. A
  generic backend must preserve the opt-in capability and use the authoritative
  adaptive admission/runtime when its exact engine/provider tuple qualifies.
  Skipped observation checks are not qualification. 0.56 must publish an exact
  matrix and expose unavailable reasons for other tuples (AC056-043).
- SQL and PySpark, native extensions, dynamic maps/branches, incremental state,
  streaming and quality are existing capability families. The new service
  cannot reduce them to a copy-only pipeline or silently ignore their options.
  Advertised combinations require actual managed-path evidence (AC056-041).
- Open issues can outlive fixes. In particular, collection denial and request
  validation redaction changes appear in 0.55; this review does not reclassify
  them as missing solely because their issues remain open.
- Provider fakes remain useful deterministic checks. Required live provider,
  multi-process durability and clean-wheel evidence are separate release gates.
