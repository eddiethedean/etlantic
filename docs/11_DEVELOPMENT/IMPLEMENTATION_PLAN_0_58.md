---
title: ETLantic 0.58 Implementation Plan
description: Managed Prefect execution on ETLantic's durable runtime, qualified within an explicit candidate support scope.
plan_status: qualified
plan_last_reviewed: 2026-10-12
---

# ETLantic 0.58 Implementation Plan

**Implementation and qualification are scoped to the tested candidate matrix below.** Phase 0.58 owns
[#290](https://github.com/eddiethedean/etlantic/issues/290) and its implementation
issues #291–#298. The optional `etlantic-prefect` package gains managed execution
alongside its existing direct `PrefectScheduler` contract. The
[scheduler and Prefect plan](SCHEDULER_AND_PREFECT_PLAN.md) governs scheduler
boundaries; [ADR-023](adr/ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md),
[ADR-027](adr/ADR-027-MANAGED-PREFECT-EXECUTION.md), and the
[adoption ecosystem plan](ADOPTION_ECOSYSTEM_PLAN.md) govern durable execution
and qualification.

The issue baseline was reviewed on 2026-10-11. The epic records source findings
against `de68100942a993a7f1751a078e29a560cf447296` and the 0.57.2 direct package;
these findings are planning inputs, not proof of new managed capabilities.
Local source was additionally reviewed at
`16322f94bf2e38b666f1e559b99618db94f12429` while refining this plan. ADR-027
freezes the worker reference, trusted backend reconstruction, targeted
execution, and canonical status/cancellation seams. The contracts below define the release bar. The final candidate decision and its
gate-to-evidence map are recorded in the phase evidence ledger.

## Outcome

A host application accepts an authorized ETLantic run durably, dispatches its
immutable accepted reference to a versioned Prefect deployment, and observes or
cancels execution in a separate worker process. ETLantic retains pinned plans,
scope, policy, quotas, leases, fencing, retry safety, effect reconciliation,
reports, artifacts, and result publication. Prefect owns remote orchestration
and infrastructure supervision.

The new [0.59–0.62 integration program](ETLANTIC_RUNTIME_PLAN.md) follows this
phase and reuses its qualified public runtime contracts. Brownfield bridges,
operator console, managed-runtime/provider packs, and TransformationModel
incubation move from their former 0.59–0.62 slots to 0.63–0.66. Their future
package and support matrices follow the accepted
[scope consolidation plan](PACKAGE_SCOPE_CONSOLIDATION_PLAN.md).
Brownfield Prefect interoperability consumes this
phase's managed adapter; it does not introduce a Prefect DAG compiler or a
second execution authority. This qualification does not set a public release date.

## Prerequisites And Non-Goals

- [0.56](IMPLEMENTATION_PLAN_0_56.md) supplies canonical prepared acceptance,
  `ExecutionEnvelope`, real managed execution, effect recovery, and durable
  publication. [0.57](IMPLEMENTATION_PLAN_0_57.md) supplies `ManagedBackend`,
  headless schedule services, complete role factories, provider schema
  inspection, and public status/drain. #278–#282 are closed foundations.
- The existing `ExecutionHost.tick()` polls work. Freeze a narrow public
  targeted-execution interface that claims exactly the referenced submission
  through the same ownership, heartbeat, cancellation, recovery, and publication
  machinery. The plugin must not copy that state machine or call private APIs.
- Core stays Prefect-free. Preserve direct `etlantic.scheduler/1`, discovery,
  `Profile(orchestrator="prefect")`, report metadata, and direct deployment
  rejection. Managed execution is a separate adapter and capability matrix.
- The initial managed matrix is static-batch `etlantic.plan/1`, installed
  packages, a self-hosted Prefect server, Process workers, and a shared
  PostgreSQL backend. Publish exact qualified Python, Prefect, ETLantic,
  provider, connector, and environment versions before a support claim.
- Plan family and envelope schema are separate version axes. The existing
  `etlantic.execution_envelope/2` carries supported `/1` plans; rejecting
  adaptive `etlantic.plan/2` must not reject that envelope schema.
- Adaptive `/2`, maps/branches/compensation, streaming, Prefect Cloud, Docker,
  Kubernetes, and other pools need separate qualification. Existing unsupported
  requirements fail before connector I/O; direct `PMADP500` remains compatible.
- A managed flow runs ETLantic's local executor within managed ownership; it
  does not nest a `PrefectScheduler`, re-plan to current definitions, or serialize
  a live runtime, callable, dataset, or credential.
- No new submission, authorization, schedule, or report authority is introduced.
  Required durable dispatch metadata belongs in canonical public/provider
  contracts with explicit migration and compatibility rules.
- FastAPI and Posit Connect host the API. Dispatchers, timers, and execution
  workers are separately supervised; handlers, `BackgroundTasks`, and API
  lifespan never own their work loops or call `serve()`.
- Disable automatic outer retries, caching, and ETL payload persistence even
  when ambient Prefect defaults enable them. Unknown external effects require
  reconciliation. Remote completion/cancellation is not ETL success/rollback.
- Production selection and worker reconstruction require compatible allowlisted
  plugins and scoped runtime credentials. References and remote IDs are never
  authorization; secrets and source rows stay out of control artifacts.

## Qualification Boundary

The release bar is limited to reproducible in-repository evidence for the
candidate profile: static-batch `etlantic.plan/1`, installed candidate wheels,
a self-hosted Prefect 3.7.8 API with Process workers, PostgreSQL 16.15, Ubuntu
24.04, CPython 3.11.15/3.12.13/3.13.16, and the tested CSV-to-PostgreSQL and
PostgreSQL-to-PostgreSQL replace-mode paths. The blocking matrix and live
PostgreSQL/Prefect campaigns are the qualification evidence for this profile.

An independent adopter, external identity provider, production or third-party
connector/backend, and live Posit Connect deployment are not evidence
requirements. Posit Connect remains a documented recipe. Other runtimes,
providers, connectors, pools, plan families, and hosts are outside this support
scope; they do not hold the 0.58 release gate open and receive no inherited
support claim.

The 30-day post-retirement cleanup age remains the runtime default. A frozen
clock test at the exact boundary plus a bounded live cleanup using a test-only
zero-age override satisfies the phase evidence requirement; no 30-day wall-clock
wait is required. Other time-window behavior is checked with controlled clocks
or bounded fixtures; qualification does not wait for a production interval to
elapse. These scope boundaries require no evidence from external organizations
or services beyond the repository's blocking CI.

## Release Scope And Source Seams

The minimum release is one usable managed path from authorized acceptance to
durable results, including cancellation, scheduled admission, and recovery.
Direct hardening alone, a deployment registration demo, or fake-only dispatch
does not satisfy this phase. Native Prefect scheduling is optional; the
ETLantic-timer path is mandatory. Rejection and documentation tests still apply
to optional/unqualified configurations.

| Surface | Required in 0.58 | Boundary of the claim |
|---|---|---|
| Existing direct scheduler | Compatible discovery/profile/report behavior plus #291 hardening | Managed routing does not reinterpret `Profile(orchestrator="prefect")` or remove direct deployment rejection |
| Managed execution | Static-batch `/1` through the canonical `/2` envelope, targeted execution, local executor, installed packages | Every advertised engine, transform, run control, connector, and writer mode is enumerated and qualified; static topology alone is not sufficient support evidence |
| Remote infrastructure | Self-hosted Prefect server and Process pool; PostgreSQL control-plane stores | Publish tested Python/Prefect/server/client/provider versions; Cloud and other pools receive no inherited claim |
| Effectful pilot | Immutable CSV input to PostgreSQL and PostgreSQL to PostgreSQL, using existing 0.56 qualified provider modes | Demonstrate real normalized output, quality, effect and report evidence; add writer modes only with their own recovery fixtures |
| Recurrence | ETLantic timer, fresh canonical admission, immutable occurrence and route | Native Prefect triggers are disabled/rejected unless their separately listed semantics pass |
| Hosts | Runnable headless and existing FastAPI composition with separately supervised dispatcher/worker roles | Posit Connect ASGI publishing is a documented recipe; live hosting qualification is outside the 0.58 support profile |

These source seams establish where extension work belongs. They are not public
imports for consuming applications.

| Existing seam | Confirmed baseline | Required extension / owner |
|---|---|---|
| `packages/etlantic-prefect/src/etlantic_prefect/plugin.py` | Instance-owned task correlation; dynamically nested flow; deployment rejection | #291 isolates direct state; #293 adds separate importable managed entrypoints in the optional package |
| `src/etlantic/control_plane/execution_envelope.py` | Verified canonical envelope, schema `etlantic.execution_envelope/2` | #292 references this authority and checks each independent version/fingerprint axis |
| `src/etlantic/control_plane/managed_backend.py` | Public backend handle and execution/action/scheduler factories | #292/#293 add narrow public construction/targeted contracts; trusted configuration supplies worker resources |
| `src/etlantic/runtime/execution_host.py` | Polling, leases, cancellation, attempt/effect recovery, quota release, result publication and retention | #292/#293 share this execution path between polling and targeted invocation; #295 adds route-aware eligibility without copying it |
| `src/etlantic/control_plane/durable_protocols.py` and SQLModel `control_plane/durable_stores.py` | Canonical accepted-work outbox, execution leases, attempts, effects, and publication records | #292/#295 extend public/provider contracts for dispatch ownership and correlation; migrations/inspection stay provider-owned |

## Contract Freeze Required Before Worker Proof

#292 must record the following decisions in the ADR and typed public contracts.
Behavioral rules here are fixed; names and storage representation remain subject
to implementation review. A decorator/client spike cannot substitute for this
freeze.

| Contract | Required rule | Freeze evidence |
|---|---|---|
| Accepted reference | Closed versioned payload with an opaque accepted-work locator and integrity/version selectors; resolve scope and envelope from trusted canonical records | Exact byte/string/collection limits, unknown-field handling, schema compatibility, tamper checks, and tests at each bound and immediately above it |
| Authority and resources | Authorize before scoped lookup; worker identity resolves accepted authority and runtime-only credentials; verify policy/revocation before effects | Check ordering for accept, dispatch, claim and execution; no caller-selected factories/endpoints/scopes; shared input/artifact/report storage accessible after submitter exit |
| Managed route | Explicit authorized route independent of direct scheduler selection; bind backend/deployment configuration and fingerprint durably before remote creation | Route-aware polling and targeted claim use the same eligibility rules; old records have an explicit compatibility/backfill rule; schedule occurrences inherit a reviewed route |
| Targeted execution | Claim only the authorized target and reuse ordinary host attempt, heartbeat, fencing, quota, recovery and publication behavior | Public result variants for executed, already-owned, terminal, cancelled/revoked, unsupported and reconciliation-required; no unrelated execution or unbounded queue sweep |
| Dispatch identity | Scoped accepted-work identity plus authorized dispatch generation, immutable reference digest, deployment binding and opaque creation key | CAS/lease semantics for dispatch ownership distinct from execution leases; same identity/different payload conflicts; response-loss retry retains identical creation parameters |
| Acknowledgement | Remote creation/linkage acknowledges delivery only; canonical execution work and result-publication recovery remain durable | Remote creation alone cannot call execution `mark_published`, finish an attempt, release accepted quota/input leases, or claim ETL completion; losing dispatch owners cannot overwrite current correlation |
| Deployment revision | Accepted work binds immutable executable configuration, not merely a mutable Prefect deployment ID/name | Registration detects updates/conflicts; queued old work remains runnable using its original binding; drift fails before effects; explicit retention/drain/retirement and rollback rules |
| Recovery and rerun | Retrying ambiguous dispatch is transport recovery; effectful retry/replay needs canonical authorization and recovery evidence | No new generation on each network retry; duplicate/terminal references cannot acquire a new effectful attempt; unknown writes stay reconciliation-required; recovery preserves the accepted plan |
| Status and commands | Read bounded authorized projections; keep remote observation timestamps/staleness separate; cancellation is durable before remote coordination | Reviewed mapping below; any persisted refresh/reconciliation is an explicit supervised operation, not a hidden side effect of a status read |
| Provider and version compatibility | Runtime construction/inspection is read-only; deployment provisioning and schema migrations are explicit operations | Migration upgrade/rollback policy, old-record behavior, least-privilege PostgreSQL grants, core/direct import isolation, package version pins and diagnostics |

The execution route is stored atomically with canonical acceptance. The
dispatcher’s bounded durable scan discovers accepted Prefect work even when no
dispatch record exists, so submitter survival is not required to create
dispatch intent. Route changes or deliberate redispatch require an authorized
transition with audit evidence; they cannot silently redirect pending work to
a newer deployment or plan.

The initial outcome mapping must satisfy these rules. These are projection and
adapter behaviors, not a second ETL state machine or proposed new core enums.

| Observed condition | Authoritative behavior | Permitted Prefect/host presentation |
|---|---|---|
| Accepted, dispatch pending/unavailable | Durable queued work retains ownership and admission evidence | Pending/outage with queue age; never ETL success |
| Duplicate invocation while another worker owns the target | No second authorized effectful owner; preserve current attempt | Explicit duplicate/already-owned receipt; remote completion of that duplicate proves no ETL outcome |
| Already terminal reference | Return existing bounded authorized evidence without new effects | Explicit terminal/no-op receipt linked to the existing outcome |
| ETL succeeded and required publication completed | Canonical successful result and report references remain authoritative | Successful managed flow, with separately attributable remote correlation |
| Failed/cancelled/timed-out ETL with known effects | Retain actual effects, final report and canonical recovery eligibility | Explicit matching unsuccessful flow behavior; returning a report must not hide failure |
| Lease lost, unknown write, or publication incomplete | Block unsupported effect replay; canonical reconciliation/publication recovery owns progress | Unresolved/recovery-required; never fabricated success or rollback |
| Prefect crashed/cancelled/missing, ETL evidence incomplete | Reconcile remote observation with canonical leases/effects/publication | Remote observation plus its age and unresolved ETL status |
| Late Prefect state conflicts with a published terminal result | Do not rewrite ETL terminal/effect facts | Show discrepancy and observation time through authorized status |

## Workstreams And Issue Traceability

| ID | Issue | Deliverables | Completion evidence |
|---|---|---|---|
| 058-D | [#291](https://github.com/eddiethedean/etlantic/issues/291) | Per-invocation direct correlation; verified flow/task IDs; failure, concurrency, selection, retry, cancellation, and timeout behavior | Barrier-controlled overlapping success/failure runs; compatible reports and truthful capability findings |
| 058-C | [#292](https://github.com/eddiethedean/etlantic/issues/292) | ADR; bounded accepted reference; trust/version/routing contracts; public targeted execution; retention and diagnostics | Tampering, drift, scope, revocation, unsupported-schema, and installed-import tests before I/O |
| 058-W | [#293](https://github.com/eddiethedean/etlantic/issues/293) | Importable managed flow; trusted backend reconstruction; local execution under canonical claim/heartbeat/fencing; explicit outcome mapping | Installed subprocess runs after submitter exit, executes only its target, and publishes durable evidence |
| 058-P | [#294](https://github.com/eddiethedean/etlantic/issues/294) | Typed versioned deployment specification; explicit preview/registration; Process-pool routing; guarded overrides; update/rollback | Distinct live worker process, configuration/code fingerprints, repeat registration, conflict and drift tests |
| 058-Q | [#295](https://github.com/eddiethedean/etlantic/issues/295) | Durable bounded dispatcher; scoped idempotent creation; correlation record; routing and orphan recovery | Two dispatchers; crashes around create/link/ack; lost responses; duplicate delivery; outage and conflict traces |
| 058-S | [#296](https://github.com/eddiethedean/etlantic/issues/296) | Authorized status/cancel/reconciliation; distinct orchestration, execution, effect, and publication facts | Cross-scope denial and cancellation at queue, claim, staging, publication, and terminal boundaries |
| 058-T | [#297](https://github.com/eddiethedean/etlantic/issues/297) | Canonical recurring admission; one timer authority; immutable firing/revision identity; optional native-trigger parity | DST/misfire/catch-up/overlap/revision/restart fixtures, duplicate triggers, and authority-transfer proof |
| 058-R | [#298](https://github.com/eddiethedean/etlantic/issues/298) | Real PostgreSQL/Prefect recovery campaign; blocking installed/live CI; headless/FastAPI examples; Posit Connect recipe | Exact version/support matrix, crash/effect/publication evidence, API restart parity, explicit live versus recipe claims |

### Adjacent Work Included In This Phase

These are required extensions of the issue workstreams, not an independent
platform program. Build their fixtures alongside implementation and include
them in #298's integrated release gate.

| ID | Scope and owner | Required evidence |
|---|---|---|
| 058-A1 | Deployment lifecycle and retention (#292, #294, #298): keep accepted code/envelope/artifact dependencies available through queued and running work; durably stop new admissions before drain; retain the immutable deployment through retirement; explicit update/rollback ownership; bounded cleanup only after route/reference checks | Old accepted work survives deployment replacement and submitter exit; route retirement waits for canonical work and live schedule references to drain, retains the paused binding, and reactivation checks the exact fingerprint; live PostgreSQL multiprocess evidence covers concurrent route compare-and-swap, Prefect API restart while the route remains draining, process death after remote pause but before the retired-state CAS, recovery without reopening admissions, and exact-binding rollback after SQLModel store reopen. Explicit orphan cleanup checks the configured retention cutoff, zero canonical submission history and schedule references, a paused exact binding, and no Prefect flow-run history; `retired -> cleanup_pending -> cleaned` fences reactivation across delete-response loss. A real unused deployment was retired and deleted against the local PostgreSQL-backed Prefect server; a frozen-clock contract denies cleanup one second before the configured 30-day boundary and passes at the exact cutoff before exercising delete-response recovery. The live deletion uses a zero-second test override. This boundary test is sufficient; elapsed wall-clock retention is not required. |
| 058-A2 | Dispatch supervision and backpressure (#295, #296, #298): public role status/drain consistent with 0.57; queue-age/outage/stale-correlation metrics; bounded retries, remote lookup, and reconciliation | Live PostgreSQL-backed outage coverage repeats four bounded failed ticks with 32 accepted submissions, then drains that backlog one item per tick and completes every target once ([32-submission campaign](evidence/phase_0_58/LIVE_POSTGRES_32_SUBMISSION_OUTAGE_RECOVERY.json)). The blocking installed-wheel Prefect/PostgreSQL suite includes this test and passes all 48 tests without skips on the declared Python matrix ([final CI evidence](evidence/phase_0_58/CI_INSTALLED_WORKER_PYTHON_MATRIX_2026-10-12.json)). The public provider-free `PrefectDispatcher.diagnostics()` snapshot reports process-local tick failures, Prefect API failures, remote create attempts, uncertain creates, missing/failed remote-run observations, and queue-age high water without identifiers or payloads. A concurrent failure trace holds a Process worker after its sink effect/report/event commit while a separate dispatcher process holds a second route lease before remote creation; both processes then hard-exit. Worker recovery publishes without a second effect, and dispatcher recovery reuses the same creation key. A deterministic dispatcher/close race proves backend shutdown requests drain and refuses engine disposal while the adapter tick remains active. The connector-commit outage trace passed locally and in the installed-wheel Python matrix; the matrix runs all 48 Prefect/PostgreSQL tests without skips on CPython 3.11.15, 3.12.13, and 3.13.16 ([CI evidence](evidence/phase_0_58/CI_INSTALLED_WORKER_PYTHON_MATRIX_2026-10-12.json)). The bounded backlog and outage/restart campaigns satisfy the 0.58 capacity and outage evidence scope; sustained production capacity and prolonged outage claims are excluded. The bounded backlog, diagnostics, simultaneous fault, and drain evidence pass for the supported profile. Higher sustained capacity, prolonged outages, and untested concurrent fault combinations are outside the support claim. |
| 058-A3 | Trust and admission parity (#292, #293, #295, #296, #297): same accepted authority across headless/HTTP/schedules, worker identity and credential rotation, least-privilege provider storage grants | Two-tenant/two-workspace non-enumeration; revoke/expire/rotate between accept, dispatch, and claim; ambient retry/cache/persistence overrides; inspection without startup DDL. The Process-worker test now covers an approval revoked after acceptance but before dispatch, another revoked after dispatch but before claim, and a valid approval expiring at claim; each path fails before sink/effect writes. The live local PostgreSQL campaign passes these boundaries with separate Process workers and a PostgreSQL-backed Prefect API. Blocking installed-wheel Prefect/PostgreSQL CI run 38282493355 on the final candidate passed all 48 tests without skips on each exact Python patch, including these authority boundaries; wheel digests and JUnit reports are in the [matrix evidence](evidence/phase_0_58/CI_INSTALLED_WORKER_PYTHON_MATRIX_2026-10-12.json). The full workflow completed with 45 successful checks, 2 expected Adaptive 0.54 skips, and no failures. Core and SQLModel tests verify that an approved request stops satisfying policy at expiry after store reopen. Approval revocation before dispatch and before claim, approval expiry before claim, and sink-credential rotation after durable dispatch and before claim pass. The accepted snapshot contains only the credential alias; external identity providers and untested combinations are outside the support claim. |
| 058-A4 | Reproducible qualification and adoption (#291, #298): reusable direct/managed conformance fixtures, version-skew and upgrade rehearsal, runnable authenticated host recipes, capability and diagnostic documentation | Clean installed wheels; exact supported/rejected candidate matrix; every retained gate linked to a command/artifact; fakes and skips identified separately. An independent consumer and live Posit Connect hosting are out of scope; the Posit recipe remains documented. Passed. The candidate matrix, reproducible commands, scope limits, and host recipes are recorded in the evidence ledger and package documentation. |

## Delivery Sequence (completed)

1. #291 and #292 established direct-state isolation, the frozen ADR and
   accepted-reference contract, trust checks, routing, retention, and provider
   storage rules.
2. #293 proved installed worker independence: the submitter exits, the worker
   reconstructs trusted runtime, targets only accepted work, and publishes
   fenced evidence. Duplicate delivery leaves one canonical owner.
3. #294 added versioned Process-pool deployment registration, guarded
   configuration, queued-work retention, and explicit update/rollback.
4. #295 and #296 qualified durable acceptance, ambiguous-create recovery,
   status/cancellation, and the associated effect/publication recovery paths.
5. #297 kept ETLantic as timer authority and verified firing identity, outage
   recovery, and guarded route transfer; native Prefect triggers fail closed.
6. #298 and 058-A1–A4 completed the installed/live integration matrix,
   operational recipes, and final gate-to-evidence release decision.

Dependency order follows the epic: #293 depends on #291/#292; #294 on
#292/#293; #295 on #292/#293/#294; #296 on #292/#293/#295; #297 on
#292/#294/#295/#296; #298 on all preceding issues. Public API names are
frozen by [ADR-027](adr/ADR-027-MANAGED-PREFECT-EXECUTION.md) for its stated
scope; the bounded operator rearm path is exposed through managed CP1 at
`POST /v1/dispatches/{submission_id}/reconcile`. Additional reconciliation
surfaces remain outside the reviewed contract.

## Implementation Progress

The 0.58 candidate at commit `0881db594604fbea52c5ee4895c4cba461b1ddb0` is
qualified for the bounded support profile in this plan. GitHub Actions run
[38282493355](https://github.com/eddiethedean/etlantic/actions/runs/38282493355)
passed all 48 installed-wheel Prefect/PostgreSQL tests without failures,
errors, or skips on CPython 3.11.15, 3.12.13, and 3.13.16. Installed-wheel
headless/FastAPI parity passed on all three patches. The full workflow finished
with 45 successful checks, two expected historical Adaptive 0.54 skips, and
no failures. The [matrix evidence](evidence/phase_0_58/CI_INSTALLED_WORKER_PYTHON_MATRIX_2026-10-12.json)
records exact package versions, manifests, JUnit results, wheel digests, and
artifact hashes.

The complete direct scheduler suite passed 18 tests locally. The installed
matrix also executes the ready-branch concurrency and ambient retry/cache/
persistence checks in its 48-test suite. The combined [final decision](evidence/phase_0_58/FINAL_QUALIFICATION_DECISION_2026-10-12.json)
maps AC058-001–010, 058-A1–A4, and every acceptance checkbox in #290–#298 to
their evidence. It records the bounded support claim, external evidence
exclusions, and controlled-clock retention result. No independent adopter,
external provider or identity-provider, live Posit Connect, or elapsed
wall-clock retention evidence is required.

| Workstream | Code now present | Qualification outcome |
|---|---|---|
| #291 | Per-invocation correlation; actual Prefect IDs distinguished from fallbacks; no automatic retries/cache/result persistence; failed ETL reports fail the flow; barrier overlap/failure, caller and Prefect API cancellation, effect-boundary cancellation with reconciled committed receipt, run/step timeout propagation, selection dependency closure, ETLantic retry behavior, resolved ready-branch concurrency, ambient retry/cache/persistence isolation, and unsupported cancellation-policy findings are tested | Passed on the exact installed-wheel matrix, including both added direct-scheduler gates; see the final decision and matrix evidence. |
| #292 | ADR-027; bounded immutable-reference schema; envelope and plan fingerprint checks; trusted acceptance route pinning and route-aware targeted host polling; accepted-principal run-submit/resource/input authorization and current pre-execution policy/approval are rechecked before resource reads or connector effects; a distinct worker principal must hold run.execute; fingerprinted work fails closed if its current policy provider is missing; approved policy requests expire before worker effects even when approval occurred before dispatch; a mismatched worker runtime version is rejected and remote environment drift blocks dispatch before claim; a restricted PostgreSQL role with no DDL authority registers a versioned Process deployment, accepts routed work, and completes remote create/link under table DML grants | Passed. Admission, authority, credential, runtime drift, and least-privilege evidence are mapped in the [release index](evidence/phase_0_58/RELEASE_INDEX.json). |
| #293 | Importable worker flow; trusted installed backend factory; targeted canonical host execution; durable dispatch-intent and binding checks; ordinary host polling leaves Prefect-routed accepted work untouched; a separate submitter subprocess exits before a Process worker executes its target over shared PostgreSQL storage; two distinct Prefect Process runs on separate workers race for one accepted reference and produce one canonical attempt/report; real Process child crashes before adapter effects, during a prepared but uncommitted PostgreSQL transaction, immediately after a replace DELETE inside an open transaction, after the connector receipt but before host finalization, after the durable report event append but before adapter return, and after PostgreSQL commit but before ETLantic receives the receipt; worker-time policy denial, submitter revocation, distinct worker-principal denial, revoked approval after dispatch, and a missing current policy provider block effects; recovery retries known-no-effect, partial and rolled-back writes once, republishes after the effect receipt once, and preserves the lost connector receipt as unknown without replay; a live Process test now recovers a failed terminal report-store write from durable result evidence without repeating the connector effect; a Process worker hard-killed after the durable result-publication row commits but before artifact-bearing report publication returns is recovered from that snapshot, with durable artifact files verified and no second PostgreSQL effect; a separately installed test backend independently commits one PostgreSQL row before worker death, and recovery preserves the partial row while recording an unknown effect without replay; clean-wheel Process-worker suite passes with core, Prefect, FastAPI, SQL, SQLModel, and separately built test backend wheels installed in a fresh environment | Passed. Targeted worker execution and report/event/artifact recovery cuts are mapped in the [release index](evidence/phase_0_58/RELEASE_INDEX.json). |
| #294 | Typed versioned spec; runtime/source/lock fingerprints; read-only preview; explicit Process-pool registration; guarded worker environment; verification before resume; a PostgreSQL-backed queued revision-1 submission remains bound after revision 2 is registered, revision 2 cannot claim it, and a real Process worker completes it through revision 1; re-registering the prior immutable specification restores its existing binding as an explicit rollback without retargeting accepted work; unexpected remote environment fields are rejected before dispatch claim; a real Process worker rejects remote configuration drift introduced after dispatch before creating an ETLantic attempt or connector effect; durable active/draining/retired/cleanup-pending/cleaned route lifecycle blocks new admissions, counts durable schedule reservations and historical canonical submissions before cleanup, retains the paused binding, and supports verified reactivation only before cleanup starts; two spawned processes now race live PostgreSQL retirement and converge on the retained paused revision; a process killed after the remote pause but before retired-state persistence leaves the route draining and paused, and a retry completes retirement; a reopened SQLModel backend reactivates the exact prior binding while leaving revision 2 unchanged; restarting the Prefect API while the route is draining preserves the two deployments and closed admission gate; the frozen-clock contract covers the default 30-day cleanup boundary and delete-response recovery, while a local live Prefect/PostgreSQL campaign deletes an unused binding | Passed. Version retention, drain, rollback, controlled-clock cleanup, and bounded live deletion are mapped in the [release index](evidence/phase_0_58/RELEASE_INDEX.json). |
| #295 | Durable route-scoped polling; stable create identity; fenced correlation; uncertain-create backoff; supervisor status/drain; queue-age receipts and a provider-free process-local diagnostics snapshot for outage, create, and stale-remote observations; remote preflight; live PostgreSQL-backed Prefect response-loss test confirms retry deduplicates and links the original run; overlapped live dispatchers produce one claim and one linked flow run; a submitter exits after atomic routed acceptance and before dispatch-record creation, then the bounded scan discovers its work; separate dispatcher processes crash after claim/before remote create, after remote create/before link, and after durable link/before tick acknowledgement; all three targets recover and complete once, and the post-link retry creates no second flow run; after-effect worker-crash recovery preserves one connector effect-ledger record and publishes the canonical report; a terminal remote failure before any ETL attempt is conditionally rearmed under a new bounded creation generation and completes once; a linked run that remains missing beyond a 300-second grace can also rearm, guarded by exact flow-run identity, bounded generations, and absence of ETL lease/attempt/effect/publication; automatic generation exhaustion now becomes durable `reconciliation_required`, blocks dispatcher claims, appears with the remote observation in authorized status, and can only be rearmed by an authorized exact-generation operator action through the headless service or `POST /v1/dispatches/{submission_id}/reconcile`; installed-wheel HTTP coverage proves opaque cross-tenant denial, evidence redaction, stale-request conflict, and audit emission; a live PostgreSQL SQLModel test proves exhausted-generation persistence, exact generation/flow-run CAS, audit-history reconstruction, and refusal of automatic claims; a route-scoped cursor advances through bounded reconciliation pages so persistent early records do not starve later dispatches | Passed. Ambiguous create, reconciliation, bounded outage/backlog, and restart recovery are mapped in the [release index](evidence/phase_0_58/RELEASE_INDEX.json). |
| #296 | Authorized canonical status/cancellation first; separate timestamped Prefect observation and cooperative cancellation result; contract tests cover cross-tenant opaque denial, lost cancellation response, a late remote terminal state, and a remote Failed observation after canonical completion; status reports the conflict without changing the completed submission or attempt; live Process-worker tests cover cancellation after dispatch but before claim with no sink effect, during source-batch staging before the transformation is released, after a committed sink effect and successful durable report but before host finalization, while a terminal report-store write is paused after connector commit, and while a prepared PostgreSQL transaction is paused at commit; source staging cancellation publishes a cancelled report with no sink effect, report-store failure recovers the completed report without repeating the effect; a worker killed after the durable result snapshot commit leaves the report pending, then host recovery publishes it with retained artifact files and no second effect; commit-boundary cancellation commits once with a cancelled report; a forced live Prefect Failed state conflicts with the completed ETL record without rewriting its report or effect, and a mid-execution Prefect API restart preserves canonical status across an unavailable remote observation; a separate live trace commits a PostgreSQL sink exactly once while the Prefect API is stopped at the connector-commit boundary, leaves the result unpublished, then completes after API restart | Passed. Canonical status, cancellation, remote disagreement, authority checks, and publication recovery are mapped in the [release index](evidence/phase_0_58/RELEASE_INDEX.json). |
| #297 | ETLantic timer remains the sole recurrence authority; schedule snapshots pin the route and include it in their admission policy fingerprint; duplicate same-occurrence admission returns the original firing and submission even after a route default change; deterministic tests cover DST gaps/folds, bounded catch-up, misfire skip, overlap skip, and effective windows; a live PostgreSQL leader-recovery trace retains the Prefect route through an accepted but unlinked firing; two independent live scheduler instances race for the PostgreSQL leader lease and admit one firing; a Process worker completes that firing with checked sink output; registrar rejects a managed deployment after a native Prefect schedule is added; explicit guarded transfer waits for active firing drain, leaves the old accepted submission on route A, and persists route B plus its new revision across a store/process restart before admitting new work | Passed. Timer authority, occurrence replay, leader recovery, transfer, and live worker execution are mapped in the [release index](evidence/phase_0_58/RELEASE_INDEX.json). |
| #298 | Focused direct/managed contract tests, a separately supervised Prefect server backed by PostgreSQL, a graceful API restart with persisted flow-run/deployment reads, live deployment-revision retention through an old-revision Process worker, a live scheduled Process-worker execution, dual-dispatcher single-create and duplicate-worker single-ownership evidence, Process-worker recovery before effects, after fully staged but uncommitted writes, and after effects, unknown-effect handling after lost connector receipt, dispatcher recovery after create-before-link process death, worker-side deployment drift rejection, native-trigger rejection and prior-version rollback, memory/SQLite route drain-retire-reactivation and cleanup-fence contracts, live multiprocess PostgreSQL retirement including API restart while draining, process death after Prefect pause, store-reopen rollback, and deletion of an unused live Prefect deployment after PostgreSQL route retirement; report-store publication recovery after cancellation including a Process hard kill after durable result-snapshot commit; Process-flow pilots for CSV→PostgreSQL and PostgreSQL-to-PostgreSQL replace mode; restricted-role deployment registration plus durable dispatch create/link; standard FastAPI configuration that pins the reviewed Prefect route at durable acceptance; a Posit Connect ASGI deployment recipe; package/host supervision guidance; and a blocking CI Prefect job that builds and installs core, Prefect, FastAPI, SQL, SQLModel, and a separate backend-plugin wheel. The final candidate matrix passed all 48 installed-wheel Prefect/PostgreSQL tests without skips on CPython 3.11.15, 3.12.13, and 3.13.16; run 38282493355 and its artifacts are recorded in the final matrix evidence. |

## Exit Gates

Gate IDs are stable traceability keys. Passing a gate requires evidence from
the final candidate on its declared matrix; issue closure alone is insufficient.

- **AC058-001 — Direct compatibility:** overlapping calls cannot mix run correlation;
  dependencies and concurrency remain correct; failed ETL reports do not make
  the outer flow successful; unqualified cancellation/timeouts are rejected.
  Direct report keys, discovery, import isolation, and `/2` rejection survive.
- **AC058-002 — Worker independence:** installed workers execute pinned accepted input
  after the caller exits, without live closures, private imports, FastAPI,
  re-planning, unrelated polling, or a second Prefect scheduler.
- **AC058-003 — Trust before effects:** scope, fingerprints, resource/code revisions,
  versions/allowlists, policy/approval, worker authority, and expiry/revocation
  are checked before connector I/O. Caller parameters cannot override trusted
  factories, import paths, endpoints, images, credentials, or infrastructure.
- **AC058-004 — Durable dispatch:** multiple dispatchers and response-loss/crash/duplicate
  cases converge using the same scoped creation identity. Conflicting payloads
  fail. Routing prevents ordinary host polling from racing Prefect-owned work;
  canonical execution fencing remains authoritative if extra remote runs exist.
  The execution route is atomic with acceptance, and accepted work with no
  dispatch record remains discoverable; delivery acknowledgement cannot consume
  execution or publication recovery.
- **AC058-005 — Effect and publication safety:** worker death before effects,
  during an unsettled or partial write, after commit with a lost connector
  acknowledgement, and after effects before publication preserves
  known/unknown evidence. No blind replay, lost report, fabricated success, distributed
  transaction, or exactly-once external-effect claim is permitted.
- **AC058-006 — Truthful status and cancellation:** reviewed mappings cover queued,
  running, failed, cancelling/cancelled, crashed/missing, stale, timed-out,
  reconciliation-required, and publication-failed states. Cancellation is
  durably authorized before best-effort remote cancellation; late remote states
  cannot rewrite terminal outcomes. Status reads are bounded and side-effect free.
- **AC058-007 — Schedule authority:** each firing obtains fresh canonical admission;
  replay resolves the same occurrence. One timer owns each schedule, including
  revision and authority changes. Unsupported native-trigger parity fails closed.
- **AC058-008 — Lifecycle and isolation:** accepted inputs survive deployment changes;
  queue/retry/retention limits and drain are tested; cross-tenant reads and
  cancellation are denied before lookup; telemetry and Prefect payloads expose
  no rows/secrets under hostile ambient configuration.
  Old queued work cannot follow a mutated deployment binding. Dispatch roles
  use explicit bounded retry/scan budgets and public status/drain; quota and
  resource ownership survive outages and drain.
- **AC058-009 — Bounded candidate qualification:** live Process-worker and
  PostgreSQL tests, installed subprocesses, HTTP/headless parity, and API
  restart/recovery pass on the exact candidate matrix. Fakes and skips do not
  establish the tested profile. Evidence from an independent consumer, external
  service, or live Posit Connect deployment is not required; Posit Connect
  remains a documented recipe, and configurations outside the candidate
  matrix are unsupported.
- **AC058-010 — Contract and provider compatibility:** #292 freezes every
  contract decision before the worker proof. Provider-owned migrations and
  route/dispatch schema inspection work with existing data and runtime grants
  lacking DDL authority; legacy local polling/direct execution remain compatible.
  Reference, envelope, plan, package, client/server, and deployment versions are
  independently negotiated or rejected before effects.

## Qualification Campaign And Evidence Ledger

These campaigns use fixtures owned by their implementation issues. Their
barrier-controlled concurrency and explicit fault points establish the causal
ordering of dispatch, effects, and publication; sleeps and eventual green status
are not used as evidence.

| Campaign | Issues / gates | Required assertions |
|---|---|---|
| Direct compatibility | #291; AC058-001, 008 | Same scheduler instance, distinct runtimes/run IDs, overlapping success/failure; disjoint observed correlation; correct dependency closure/concurrency; ambient retries/cache/persistence cannot alter execution |
| Installed target proof | #292/#293; AC058-002, 003, 010 | Build/install wheels in a clean subprocess without checkout imports; submitter exits; target A executes while accepted B stays untouched; duplicate target workers cannot both own effects; worker can access retained immutable inputs and publish actual reports |
| Installed-wheel final regression | #298; AC058-001–010; 058-A1–A4 | Fresh core, Prefect, SQL, SQLModel, FastAPI, and backend-plugin wheels install into clean environments with `PYTHONPATH` unset and pytest's configured pythonpath disabled. All 46 Prefect/PostgreSQL tests and the headless/FastAPI parity test pass on exact CPython 3.11.15, 3.12.13, and 3.13.16. [The blocking matrix campaign](evidence/phase_0_58/CI_INSTALLED_WORKER_PYTHON_MATRIX_2026-10-12.json) records all three tuples. Other operating systems, Python and Prefect versions, pools, and hosting combinations are explicitly outside the support claim, not pending evidence. |
| Acceptance and dispatch faults | #294/#295; AC058-004, 008 | Route is atomic with canonical acceptance; a submitter exits before dispatch-record creation and a bounded scan discovers the work; two dispatchers; stop before remote create, after server accepts before response, and after correlation before acknowledgement; restart converges on the same creation identity and delivery record without consuming execution work; terminal failure and aged missing-run recovery create bounded generations only before canonical execution evidence exists; route-scoped reconciliation pages advance beyond the first bounded result set |
| Prefect create-response loss | #295; AC058-004 | A real Prefect server accepts the first create while the caller loses its response; after backoff the retry reuses the same creation key and parameters, receives the original flow-run ID, and links it durably without executing the target twice |
| Worker and publication faults | #293/#295/#296; AC058-005, 006 | Real process death before effects, during an unsettled or partial write, after commit with a lost connector acknowledgement, after effect commit before publication, and during delayed report/event/artifact publication; inspect real sink and durable attempt/effect/quota records; no blind replay; stale owners cannot publish. Installed Process-worker traces cover death before adapter effects, immediately after a replace DELETE but before inserts within an open transaction, during a fully staged but uncommitted PostgreSQL transaction, after a durable pending report and `run.completed` event append but before host finalization, after PostgreSQL commit but before ETLantic receives the connector receipt, after result-snapshot commit but before report-store publication, during a partial artifact staging write before atomic replacement, and after a test backend independently commits one row before worker death. Recovery publishes the durable snapshot without repeating the PostgreSQL effect, preserves one event per attempt, removes the abandoned artifact staging file and rewrites a complete artifact before executing once, or records the lost or partial effect as unknown without replay. The 0.58 support claim is limited to the tested PostgreSQL-backed modes; other connectors are outside this phase. |
| Cancellation and remote disagreement | #296; AC058-003, 005, 006 | Before dispatch and after create/before claim; cancellation during source-batch staging is observed before release, then publishes a cancelled report with no sink/effect-ledger write; cancellation after a durable successful report and committed effect but before host finalization preserves completed status; cancellation observed at a prepared PostgreSQL commit boundary preserves the cancelled report and committed connector effect; cancellation during a blocked terminal report-store write is durably recorded; a transient store failure recovers the completed report without a second effect; a Process hard kill after result-snapshot commit leaves the report pending and host recovery publishes it from the durable snapshot without repeating the effect; both controlled-client and live Prefect Failed observations conflict with canonical completed without rewriting submission, attempt, report, or effect; lost cancel response is idempotent; report publication, tested authority revocation/expiry and outage races pass; Prefect completed/crashed/missing/unreachable never overwrites canonical facts |
| Schedules and lifecycle | #294/#297; AC058-007, 008 | Fresh admission per firing; duplicate firing keys; DST/misfire/catch-up/overlap/revision boundaries; pause/resume and authority transfer; deploy revision B while revision A work is queued/running; bounded drain/retirement/rollback. Guarded schedule amendments can explicitly transfer to the currently trusted Prefect route after active firings drain; prior accepted occurrences stay pinned, and the new revision/route survive PostgreSQL process restart. |
| Live multiprocess retirement and rollback | #294/#298; AC058-008; 058-A1 | Two spawned processes retire one PostgreSQL-backed route after accepted work drains; admissions stay closed, the immutable deployment remains paused and retained, the competing revision stays intact, and reopening SQLModel state permits exact-fingerprint rollback without retargeting accepted work. A process killed after remote pause but before durable retirement leaves the route draining and paused; restarting the Prefect API at that exact boundary preserves both revisions and closed admissions, and retry safely completes the lifecycle CAS. The same live PostgreSQL/Prefect campaign now retires and deletes a second unused deployment; a frozen-clock contract denies cleanup one second before the default retention boundary and permits it at that exact boundary, while focused tests cover route references, cleanup fencing, reactivation denial, and response-loss retry. The live campaign uses a zero-second retention override; the frozen-clock boundary is accepted evidence; no elapsed 30-day wait is required. |
| Bounded route cleanup | #294/#297/#298; AC058-007–009; 058-A1 | The clean-wheel campaign runs 43 Prefect/PostgreSQL tests with no skips and installed headless/FastAPI parity. A durably reserved schedule reference blocks retirement until service deletion releases it; live PostgreSQL retirement then removes only an unused, paused exact deployment after route-reference checks. [Campaign evidence](evidence/phase_0_58/CLEAN_WHEEL_ROUTE_CLEANUP_QUALIFICATION.json). The test overrides retention to zero for live deletion while the frozen-clock test verifies the exact configured 30-day cutoff; elapsed wall-clock retention is not required. |
| Live Prefect API outage and backlog recovery | #295/#296/#298; AC058-004, 005, 006; 058-A2 | With the API stopped, four bounded ticks leave 32 PostgreSQL-backed submissions accepted, unclaimed, and without attempts or sink effects. After API restart, 32 one-item ticks dispatch the backlog, and separate Process-worker runs complete every target with one effect receipt and report. The same campaign still covers a worker held after committing its sink effect and successful report but before host finalization; authorized status preserves canonical facts while the remote projection is unavailable, and restart lets the worker publish once. [Campaign evidence](evidence/phase_0_58/LIVE_POSTGRES_32_SUBMISSION_OUTAGE_RECOVERY.json). This bounded burst is the phase's backlog/outage evidence; sustained production capacity and long-duration outage claims are out of scope. |
| Simultaneous dispatcher/worker process failure | #295/#296/#298; AC058-004, 005, 008; 058-A2 | A Process flow-run process is held after the connector effect, successful report, and completion event are durable. Concurrently, a separate dispatcher process is held after taking a durable dispatch lease but before Prefect creation. Both processes hard-exit; the worker recovers by publishing the existing result without a second effect, and the dispatcher reuses its creation key and completes the other target once. A backend close race also proves active dispatcher lifecycle registration prevents shared-engine disposal until the tick settles. [Campaign evidence](evidence/phase_0_58/LIVE_DISPATCH_WORKER_BACKPRESSURE_AND_DISPOSAL_2026-10-12.json). Other concurrent fault combinations and sustained high-volume backpressure are outside the 0.58 support claim, not evidence gates. |
| Schedule firing idempotency and route transfer | #297; AC058-007, 008 | Replaying the same revision and nominal time returns one firing and one canonical submission; a later service default route change cannot retarget it. An explicit route transfer is CAS-guarded, rejected while a firing is active, preserves the prior submission's route, and admits the amended revision on the new route after a PostgreSQL store/process restart. |
| Connector commit during API outage | #293/#296/#298; AC058-005, 006; 058-A2 | A real Process worker pauses before PostgreSQL connector commit; the Prefect API is stopped, the connector commits one row and one durable effect while canonical status remains running with result publication not yet recorded, and an authorized status read reports remote/reconciliation unavailable. Restarting the API lets that same worker complete and publish once. [Local campaign evidence](evidence/phase_0_58/LIVE_CONNECTOR_COMMIT_DURING_PREFECT_API_OUTAGE_2026-10-12.json). The installed-wheel matrix also passes the same trace on all three exact Python patches ([CI evidence](evidence/phase_0_58/CI_INSTALLED_WORKER_PYTHON_MATRIX_2026-10-12.json)). This is a bounded recovery test and does not establish prolonged outage or sustained capacity. |
| Isolation and provider upgrade | #292/#295/#296/#298; AC058-003, 008, 010 | Two tenants and two workspaces; unauthorized read/cancel before lookup; one live environment-backed sink credential rotation after dispatch and before claim, with only the alias stored in the accepted snapshot; the supported revoke/expire/rotation boundaries pass; old records and read-only startup grants; independent version drift; redacted control payloads/logs/telemetry |
| Live pilot and host parity | #298; AC058-009 plus all applicable gates | Self-hosted server, real Process workers and PostgreSQL; CSV→PostgreSQL and PostgreSQL→PostgreSQL output/quality/report checks; HTTP/headless equivalence; restart API after acceptance; separately supervised roles retain progress |

Core implementation and qualification are complete for the declared support profile.
The [final decision](evidence/phase_0_58/FINAL_QUALIFICATION_DECISION_2026-10-12.json)
maps AC058-001–010, 058-A1–A4, and each #290–#298 acceptance checkbox to its
evidence. The [release index](evidence/phase_0_58/RELEASE_INDEX.json) records
no remaining gates.

Run fast contract/direct/rejection fixtures on ordinary changes. Installed
worker and live Process/PostgreSQL campaigns are blocking integration checks
for the affected program and release candidate, with provisioned test services
and isolated fixture data. In-memory stores, mocked clients, and synthetic
fault fixtures are useful development evidence but cannot replace the live
campaign. An unavailable required service is a failed/incomplete gate, not a
passing skip.

The planned release ledger lives under
`docs/11_DEVELOPMENT/evidence/phase_0_58/`, indexed by `RELEASE_INDEX.json`.
Each AC058 gate and each acceptance item in #291–#298 must map to a campaign,
reproducible command, source/wheel/configuration digests, exact dependency and
service versions, expected assertions, observed outcome, and bounded redacted
artifact references. Record test deadlines, concurrency/queue limits, reference
limits, retention windows, and cleanup checks in the campaign configuration.
Describe skips and optional claims separately. Do not create placeholder
passing evidence before the implementation exists.

#298's final decision records all AC058-001–010 gates and 058-A1–A4, unsupported
findings, direct-mode regression results, migration/upgrade compatibility, and
the exact support matrix. New optional claims require additional evidence;
they cannot substitute for or delay the mandatory path without an explicit
scope change to the roadmap and governing plans.

## Required Release Evidence And Downstream Boundaries

- ADR and public-contract compatibility report, including provider migration,
  read-only inspection, routing, retention, and diagnostic decisions.
- #291–#298 and 058-A1–A4 acceptance-to-test/artifact matrix; direct scheduler
  regression and managed installed/live-worker qualification results.
- PostgreSQL multi-process crash, lost-response, fencing, cancellation, effect
  reconciliation, publication, schedule, upgrade/rollback, and drain traces.
- Trust/revocation, two-scope isolation, least-privilege, and redaction report.
- Exact supported versus rejected/experimental version and feature table;
  reproducible CI commands, environment setup/cleanup, and final go/no-go record.
- Updated package README, Prefect example, scheduler plan, capabilities,
  diagnostics, upgrade notes, authenticated headless/FastAPI recipes, supervisor
  configuration, and Posit Connect ASGI/dependency/reachability recipe.

[0.63 brownfield bridges](IMPLEMENTATION_PLAN_0_63.md) reuse this adapter for
fidelity and incremental migration; broader plan families need their own
conformance before support expands. [0.64 console](IMPLEMENTATION_PLAN_0_64.md)
projects authorized correlation and reconciliation facts through the API.
[0.65 provider packs](IMPLEMENTATION_PLAN_0_65.md) may qualify other pools and
cloud infrastructure without weakening these contracts. A future application
wrapper consumes public composition APIs and owns no ETL state machine.

Review this plan when #292 freezes the ADR, the Prefect/version matrix changes,
or any qualification gate passes. Planned scope never becomes a shipped claim
solely because an issue closes or a roadmap number is assigned.
