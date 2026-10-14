---
title: ETLantic 0.60 Implementation Plan
description: Posit Connect scheduling and generic authenticated HTTPS triggers.
plan_status: implementation_complete_qualification_deferred
plan_last_reviewed: 2026-10-14
---

# ETLantic 0.60 Implementation Plan

Phase 0.60 delivers optional `etlantic-rsconnect` for Connect deployment,
scheduling, and lightweight HTTPS triggers. The package can be distributed as a
preview after the local release checks below; external services and live
qualification are not release prerequisites. The [rsconnect domain
plan](ETLANTIC_RSCONNECT_PLAN.md) owns platform boundaries. Former 0.60 console
scope moves intact to [0.64](IMPLEMENTATION_PLAN_0_64.md).

The optional package source covers deterministic Quarto bundle generation with
a verified source manifest, explicit-target publishing, preview-gated schedule
lifecycle, durable-store protocols, and bounded HTTPS delivery/reconciliation
over public 0.59 contracts. Focused package checks pass (44 tests), along with
lint, source type, and wheel-build checks. The preview release bar is local and
listed below. No AC060 production-support exit gate is closed:
the SDK schedule surface remains experimental, live Connect and durable
ownership/journal implementations are unqualified, and the documented Connect
invocation provides no trusted nominal-slot/retry identity. Generated content
therefore refuses delivery until a trusted occurrence provider is supplied.
These live qualification gaps limit support claims and activation; they do not
block distribution of the preview package.

## Preview Package Release

The package may be released as a preview when these repository-local checks pass:

- Build and install the wheel from the locked workspace; import the public
  package API without requiring Connect, Quarto, FastAPI, Data Mover, PostgreSQL,
  or a receiver/worker service.
- Pass the focused package and inherited public-contract tests, lint, type
  checks, lockfile validation, wheel build, and strict documentation build.
- Verify the generated bundle manifest and deterministic output; verify that
  secrets are represented only by references and that unbound content remains
  disarmed and refuses delivery.
- Publish documentation that labels schedule mutation as experimental and the
  generated trigger as inactive without a trusted occurrence-context provider.

These checks use local fixtures and tools already in the development workflow.
Live Connect, Quarto deployment tooling, real PostgreSQL, an independent
receiver/worker, vendor API decisions, and external qualification campaigns are
not prerequisites for this preview release. Release does not claim a qualified
Connect deployment, active scheduled delivery, or production support.

The release workflow verifies the preview package's metadata and module version
independently of the core tag. It builds, smoke-tests, and publishes the adapter
using its own artifact version, so preview `0.60.0` can accompany core `0.59.0`.

The [Connect simulation design](CONNECT_SIMULATION_DESIGN_0_60.md) records local
SDK, schedule, delivery, and recovery simulations with reproducible fault
scenarios. Those simulations exposed and now cover SDK recurrence normalization,
resume-anchor preservation, bounded credential resolution, verified TLS
deadlines, single-writer schedule claims, amendment preflight, and receipt
contract parity. The package is locally tested without external Connect
infrastructure; external qualification remains a support and activation
decision rather than a distribution requirement.

## Outcome

Operators deploy and manage scheduled trigger content that calls any configured,
compatible HTTPS receiver. Receivers durably admit work and independent workers
execute ETL; Connect trigger success is reported separately from ETL success.

## Prerequisites And Non-Goals

- 0.59 supplies consolidated managed ownership, shared outbound policy and the
  implemented versioned trigger/schedule seams, auth, identities and receipt
  semantics. Its [exit gate](EXIT_GATE_0_59.md) defers external qualification;
  publication is not proof of independent receiver/worker, real-store recovery
  or transport conformance. Qualify the seams used here before activating the
  live pilot; existing durable workers can precede Data Mover in 0.62.
- No `etlantic-fastapi`, `fastapi-posit`, or Data Mover package dependency.
  Explicit target configuration is sufficient.
- No direct Connect ETL executor and no `etlantic-quarto` package creation or
  planning. External Quarto tooling required by the chosen documented Connect
  content type is recorded in the platform matrix.
- The initial matrix is one selected script content type, one schedule per
  owned content item and one explicit-URL receiver/worker topology; extra hosting
  or content variants are demand-gated. Generated content consumes the wire
  contract without installing the full ETL engine/provider environment.
- Arbitrary cron conversion or shared content with independent schedules is not
  assumed; unsupported or ambiguous behavior fails closed.
- The initial durable reference is static-batch `/1` with PostgreSQL, a
  framework-neutral receiver and an existing installed worker in separate
  processes. Memory/SQLite and fixture-only results remain labelled references.
  No new executor, timer authority, receipt store or pipeline state machine.

## Implementation Baseline And Contract Handoff

The adapter consumes these public 0.59 owners. Freeze the source revision, wheel
hashes and schema fixtures for release; the names below describe implemented
surfaces, while Connect adapter operations remain preview or qualification-only
as indicated below.

| Concern | Implemented owner / constraint | 0.60 responsibility |
|---|---|---|
| Wire values | `etlantic.control_plane`: `TriggerEnvelope`, `TriggerReceipt`, `external_occurrence_id`, `trigger_envelope_json_schema`; schemas `etlantic.trigger_envelope/1` and `etlantic.trigger_receipt/1` | Generate a minimal consumer from frozen public fixtures, test byte/schema parity and reject incompatible versions. Do not import private modules or redefine authoritative wire semantics. |
| Envelope | Exact eight fields including `schema`; 16 KiB UTF-8 JSON maximum; duplicate and unknown fields rejected | Send registered references and correlation only; pipeline/profile/parameter payloads, execution routes and credential values are not trigger inputs. |
| Identity | Schedule ID + immutable schedule revision + canonical UTC nominal time derive `occ-` + SHA-256; generation authorizes the timer but does not change deduplication identity | Bind the actual scheduled slot before the first send; preserve it across process restart and response loss. Platform task IDs and delivery attempts are observations, not occurrence identity. |
| Admission | `ScheduleApplicationService.trigger_external` and `get_external_trigger_receipt`, trusted `ControlPlaneContext`, `schedule.trigger`/`run.submit` authorization and bound workload identity | Adapt HTTP authentication to the canonical services in the non-FastAPI harness. Reuse authorized receipt lookup and durable preparation/admission. |
| Timer lifecycle | Registered external owner/generation, atomic next-fire cursor, at most 60 seconds early for a new delivery; retained firings have no automatic compaction | Match the registered cursor without inferring a retry's slot from its current value. Preserve history and fence owner transfer through the canonical schedule service. |
| Outbound controls | Public `etlantic.outbound` policy decisions and response bounds | Reuse policy and conformance, enforce them on actual DNS/connect/redirect/read paths. A URL preflight alone does not qualify the transport. |

Accepted/skipped receipts use HTTP 200; pending preparation uses 202. A pending
receipt has no accepted submission yet, and even an accepted receipt need not
contain a run ID immediately. The existing non-Connect tests establish local
behavior, not the deferred E059-WIRE/OCC/SEC/REC campaigns. Any missing public
seam is resolved with its 0.59 owner before dependent adapter work.

## Production Qualification And Activation Blockers

The first content candidate is a Python script rendered through external Quarto
and published with `rsconnect-python`. Freeze one exact Connect/Python/Quarto/
deployment-tool tuple, default variant, auth mechanism and receiver/worker
deployment. Record build and server prerequisites separately; a lightweight
trigger still has platform dependencies. The domain plan records the
[official platform sources](ETLANTIC_RSCONNECT_PLAN.md#platform-facts-and-qualification-decisions).

The Posit Python SDK currently labels schedule create/update/delete as
experimental. Schedule observation/history is not proof of a stable mutation
surface, and render-output activation is not proof of timer pause/resume.
Production activation must identify a vendor-supported stable mutation path and
its exact pause/resume semantics. If none is available, retain automated
lifecycle as unsupported or preview-only with bounded versions and support
labels. A manually configured pilot cannot close AC060-004; SDK presence,
undocumented endpoints or suppressed warnings cannot imply support. This is a
support qualification rule, not a prerequisite for publishing the preview
package.

Connect may render on deployment or manual refresh. The bundle must reject
delivery when no authorized scheduled occurrence is bound. Disable deployment
rendering where supported and prove that build, deploy, preview, refresh and
rollback cannot accidentally submit ETL. Execution caching must not skip a
scheduled delivery; rendered output and logs must remain bounded and redacted.

Freeze the recurrence table before publishing: ETLantic spec and timezone,
Connect representation, nominal UTC sequence, DST fold/gap, start/end boundary,
queue delay, missed-slot and overlap behavior. Start with one UTC interval
candidate; only expand to local-time/cron cases after exact sequence equivalence
and live evidence. Reject unsupported misfire/catch-up combinations rather than
inventing extra slots. A platform task's start time, wall-clock rounding or
mutable `next_run` cannot establish its intended scheduled time.

The implemented receiver's `misfire="skip"` skips a new nominal occurrence that
arrives after that nominal instant; it does not provide an implicit lateness
grace period. Characterize a UTC interval with `fire_once` first, prove delayed
queue delivery and cursor progression, and document the exact supported policy.
Do not silently widen admission or promise catch-up from Connect's timer alone.

If script metadata cannot distinguish a scheduled invocation and its nominal
slot across retries/restarts, production activation must select and qualify a
durable mapping through public runtime/store seams, including its credential and
outage cost, or keep that mode inactive. Local files in an ephemeral Connect
process are insufficient. This does not block package distribution.
Platform render retries, transport retries and manual rerenders are separate
capabilities; do not assume Connect automatically retries failed delivery.

## Workstreams

| ID | Workstream | Deliverables | Completion evidence |
|---|---|---|---|
| 060-P | Platform characterization | API stability decision, exact content/tool tuple, recurrence/nominal-slot and scheduled-invocation mapping | D060-API/OCC decisions; no unresolved activation blocker |
| 060-B | Trigger bundle | Frozen wire consumer, minimal pinned dependency closure, explicit URL/credential references, disarmed build/deploy behavior | E060-PKG; reproducible source manifest and clean generated-content installation |
| 060-S | Schedule lifecycle | Proposed capability inspection and create/read/update/pause/resume/delete/reconcile operations; one fenced timer owner | E060-LIFE; full desired-state readback, concurrent mutation and external-drift cases |
| 060-T | HTTPS transport | Shared outbound policy/conformance, same-slot retry, pending/accepted/skipped response validation | E060-WIRE/SEC/OCC; actual network enforcement and independent receiver interoperability |
| 060-R | Recovery and operations | Durable deployment correlation, restart reconciliation, failed/unknown delivery, scoped rollback/cleanup | E060-REC; lost create/deploy responses, process kill and credential rotation |
| 060-Q | Production qualification | Installed/live bounded matrix, inherited 0.59 evidence and explicit support decision | E060-SUP; no fake-only, deferred or experimental production-support claims |

## Production Qualification Sequence (Deferred; Not A Package Release Gate)

1. Characterize the platform and freeze D060-API/OCC/PKG/SEC. Capture the exact
   public 0.59 contract corpus and required inherited qualification cases.
2. Build the minimal disarmed bundle; prove schema/identity/receipt parity and
   installed policy enforcement against an independent non-FastAPI receiver.
3. Add ownership records and proposed deployment/lifecycle operations. Prove
   failure recovery before enabling the first native schedule.
4. Activate one isolated live pilot only after the preceding gates pass. Exercise
   delivery/restart/cutoff failures and actual independent ETL execution.
5. Publish the matrix, evidence index, runbooks and explicit support decision;
   carry open evidence forward without converting it into a support claim. This
   sequence controls production qualification, not preview package release.

### Ordered Production Qualification Stages

| Gate | Required input | Exit artifact / stop condition |
|---|---|---|
| A — platform and contract characterization | Public 0.59 owners and exit-gate deferrals; Connect access if available | Exact tuple, API stability decision, recurrence table, nominal-slot provenance, ownership/dependency ADR. Unknown identity or mutation semantics keep dependent activation unavailable. |
| B — installed wire consumer qualification | Gate A schemas, credential/destination policy and package-local evidence | Clean bundle install; non-FastAPI receiver/worker; E060-PKG/WIRE/SEC and relevant E059 cases. No full ETL installation or policy preflight-only qualification. |
| C — recoverable lifecycle qualification | Gate B consumer and public durable ownership seam | E060-LIFE/REC; readback and lost-response reconciliation; fenced update/rollback; no unintended build/deploy admission. Ambiguous remote create blocks blind recreate. |
| D — live trigger and execution qualification | Gates A–C; isolated server, real PostgreSQL and installed independent worker | E060-OCC and live lifecycle/security/recovery campaign; real accepted work, effects and canonical results. Fixture-only or unavailable required cases remain incomplete. |
| E — production support decision | Completed case results where available, support exclusions and cleanup inventory | AC060-001–006 evidence index and operations recipes. Explicit deferrals leave affected capabilities unqualified. This stage does not authorize or block package distribution. |

## Delivery, Receipts And Retry Rules

Validate schema, exact fields, bounded body and schedule/revision/occurrence
correlation before trusting a receipt. Do not follow a returned status URL outside
the configured authorized receiver policy. Authentication supplies tenant/workspace
and workload identity; payload fields cannot supply or override trusted scope.

| Observation | Required adapter behavior |
|---|---|
| 200 + valid accepted receipt | Record durable admission and submission reference; stop delivery retries. Query canonical status separately for ETL/effects/publication. |
| 200 + valid skipped receipt | Record the exact firing reason, including failed preparation; no fresh occurrence or success claim for ETL. |
| 202 + valid pending receipt | Record preparation pending; bounded authorized receipt lookup or same-occurrence retry. Exhausted deadline remains pending/unknown, never accepted. |
| Timeout, disconnect or lost response | Acceptance may already exist. Reconcile the retained receipt or retry the identical semantic envelope; never derive a new slot or rerun pipeline effects. |
| 429 or eligible transient 5xx | Bounded same-occurrence retry with jitter; honor a valid bounded `Retry-After` within the total delivery deadline. Platform and client retry budgets compose into one ceiling. |
| 400/401/403/404/409/413/unsupported version | Stop automatic delivery and report a redacted operator action. Preserve conflict/stale/early distinctions; explicit recovery must revalidate the registered binding. |
| 2xx without a valid correlated receipt; oversized/malformed response | Invalid upstream observation, not admission success. Preserve possible acceptance and use bounded authorized reconciliation; never invent a replacement occurrence. |

The package freezes delivery at 10 attempts, 60 seconds per request, 300 seconds
total elapsed, 1 MiB of response data, and 60 seconds maximum `Retry-After`.
Defaults are 3 attempts, 10 seconds per request, 30 seconds total, 64 KiB, and
5 seconds. Platform and client retry budgets still require a live combined-ceiling
qualification before production support. Replay/retention follows 0.59 durable firings; any later compaction
requires tombstone/horizon qualification before activation. Secret resolution
occurs at an authorized runtime boundary; rotation may change credentials without
changing the accepted semantic intent or occurrence identity.

## Deployment Ownership And Recovery

Persist only bounded ownership/correlation metadata: trusted scope, logical
adapter binding, Connect server/content GUID/default variant, bundle hash,
registered schedule revision/generation, desired recurrence, operation identity,
observed remote task references and reconciliation outcome. Reuse public durable
store seams; credential values and source rows never enter these records.
Define the versioned record/migration owner before introducing storage.

- Journal mutation intent before a remote call. Recover lost content-create,
  bundle-upload/deploy and schedule-update responses through verified scoped
  readback. Connect calls are not assumed idempotent. Multiple or unprovable
  matches require reconciliation; never delete or adopt content by display name.
- Preflight and stage content without a deliverable occurrence. Verify the
  resulting bundle/configuration and canonical external timer binding before
  enabling its native timer. Partial failures retain enough correlation to
  reconcile or clean up only proven owned resources.
- Pause/delete the canonical schedule first to deny new admissions, then stop
  the remote timer. Recover already linked/pending firings through canonical
  services. Remote stop failure is visible; accepted work remains queryable and
  follows explicit run cancellation, not content deletion.
- Updates create immutable schedule revisions; use public compare-and-swap and
  owner-generation fencing. Disable old delivery before enabling replacement,
  inspect outstanding firings and prove crash recovery at each boundary.
  Rollback rebinds a prior bundle through a valid new revision/generation;
  it cannot resurrect an invalidated revision or stale owner.
- Readback detects external edits to recurrence, variant, URL or bundle.
  Unexplained drift blocks activation/automatic overwrite. Concurrent operations
  use durable serialization or fencing; an in-process lock is insufficient.

## Production Support Acceptance

- **AC060-001:** Installed adapter targets a non-FastAPI receiver without either
  FastAPI or Data Mover installed and without shipping pipeline code/credentials
  or pulling the complete ETL engine/provider stack into generated content.
- **AC060-002:** Every advertised recurrence preserves required semantics;
  unsupported recurrence or uncertain occurrence identity prevents activation.
- **AC060-003:** Platform retries, trigger restarts, and lost HTTP responses
  preserve one occurrence/run linkage under concurrent delivery.
- **AC060-004:** Live schedule and content updates, pause/resume, rollback,
  reconciliation, and deletion affect only owned resources and retain run history.
- **AC060-005:** Auth, TLS, endpoint policy, malformed responses, replay, and
  credential rotation produce bounded redacted outcomes under shared outbound
  policy, including actual DNS/connect and trusted private-deployment tests.
- **AC060-006:** Accepted work completes or fails in an independent executor
  after API restart; trigger success cannot overwrite ETL failure/unknown effects.

AC060-004 includes lost remote mutation responses, concurrent operators, external
drift, rollback fencing and proof that build/deploy/manual refresh submits no
unbound work. AC060-002 includes a documented API stability/support decision and
nominal-time equivalence, not merely successful creation of a native timer.

## Evidence Matrix

| Family | AC coverage | Required cases / environment |
|---|---|---|
| E060-PKG | 001, 005 | Built adapter and generated bundle installed separately; dependency tree and file manifest, reproducible hashes, secret/row/log/render inspection; no FastAPI/Data Mover/ETL engine stack in content. |
| E060-WIRE | 001, 003, 005, 006 | Frozen /1 corpus; version skew, duplicate/unknown fields, byte limits, wrong correlation, pending/skipped/accepted, missing run ID and hostile status references; independent non-FastAPI receiver and worker. |
| E060-OCC | 002, 003 | Platform task/nominal provenance, concurrent duplicates, delayed retry after next cursor advances, lost response, process restart, DST fold/gap where claimed, misfire/overlap and manual rerender; live Connect plus PostgreSQL races. |
| E060-LIFE | 002, 004 | Create/read/update/pause/resume/delete/reconcile; stop failures, external edits, stale owner/revision, concurrent mutation, cutoffs and scoped cleanup; isolated real Connect resources. |
| E060-SEC | 001, 005 | Revoked/rotated and cross-scope credentials, explicit trusted private destination, TLS, redirect/auth leakage, actual DNS/connect rebinding, timeout and streaming byte bounds; controlled network servers and live credential injection. |
| E060-REC | 003, 004, 006 | Kill before/after remote create/deploy, before/after durable admission and receipt recording; pending recovery, executor loss, failed ETL and unknown effects, fenced rollback, orphan inventory; real PostgreSQL and independent installed worker. |
| E060-SUP | All | Exact source/wheel/dependency/platform tuple, per-operation API stability, qualified/preview/unsupported matrix, install and upgrade/rollback report, production support decision and cleanup runbook. |

Record case ID, AC/workstream/F09/F12 and inherited E059 case references, source
revision, wheel/bundle hashes, exact server/tools/receiver/store/worker topology,
expected and observed result, immutable artifact reference and
pass/fail/unavailable/deferred status. Required skips are incomplete. Reuse
existing qualified worker evidence only for its exact tuple; qualify the newly
composed Connect path independently. Closing relevant inherited cases here does
not silently close every deferred 0.59 campaign.

## Decision Register

| Decision | Accountable owner | Due / required record |
|---|---|---|
| D060-API: platform/content and lifecycle support | Connect/platform + release | Gate A: exact server/tools/default variant, API/SDK stability and operation mapping, deployment-render controls, pause/resume semantics; stable support or explicit preview/deferral. |
| D060-OCC: recurrence and invocation provenance | Schedule/runtime + Connect | Gate A: supported nominal sequences, metadata or durable mapping owner, retry/misfire/overlap/cutoff behavior; ambiguous identity blocks activation. |
| D060-PKG: minimal content and public reuse | Packaging + runtime/transport | Gate A: adapter/content dependency graphs, generated consumer provenance, shared policy reuse and schema-update strategy; no copied policy authority or speculative HTTP wheel. |
| D060-SEC: credential and delivery budget | Security + transport | Gate A: deployment versus runtime identities, secret injection/resolution/rotation, receiver/status-reference policy and numerical retry/network/byte limits. Gate B proves actual connection enforcement. |
| D060-STATE: ownership and rollback | Persistence + Connect | Before Gate C mutation: public durable record owner/version, operation fencing, uncertain-create lookup and cutoff/revision rollback procedure; no implicit schema mutation. |
| D060-SUP: production support scope | Release + phase owners | Stage E: inherited evidence disposition, exact installed/live matrix, unavailable cases and explicit deferrals; endpoint discovery handoff to 0.62 without broader platform claims. |

## Deferred Production Support Evidence And Decisions

Map AC060-001–006 to E060-PKG/WIRE/OCC/LIFE/SEC/REC/SUP and the decision register.
Platform maintainers re-review on API/tool changes. Publish build/deploy,
credential rotation, failed/pending/unknown delivery, drift, rollback and scoped
cleanup runbooks. Record Quarto prerequisites accurately without creating an
ETLantic package. The exit record must retain any relevant inherited 0.59
qualification deferral and must not mark it passed from documentation alone.
The [consolidation plan](PACKAGE_SCOPE_CONSOLIDATION_PLAN.md) supplies F09/F12
traceability; one live topology suffices for the corresponding bounded support
claim and broader combinations are not implied. None of this external evidence
is required to distribute the preview package; the local release bar is above.
