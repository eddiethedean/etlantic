---
title: ETLantic 0.61 Implementation Plan
description: Staged AWS Scheduler/Lambda delivery and ECS/Fargate execution with shared-runtime prerequisites and independent qualification.
plan_status: implementation_complete_qualification_deferred
plan_last_reviewed: 2026-10-14
---

# ETLantic 0.61 Implementation Plan

Phase 0.61 implements optional `etlantic-aws` with independent scheduling and
execution capabilities. The package and shared-runtime seams are implemented in
the workspace and pass local contract, type, and fault tests. Live AWS
qualification and a production support decision remain open. The [AWS domain
plan](ETLANTIC_AWS_PLAN.md) owns service boundaries and the [package consolidation
plan](PACKAGE_SCOPE_CONSOLIDATION_PLAN.md) applies F02/F09/F12. Enterprise
provider candidates follow in [0.65](IMPLEMENTATION_PLAN_0_65.md) under demand
gates.

## Outcome

EventBridge Scheduler delivers runtime triggers through a qualified HTTPS relay;
one ECS/Fargate adapter executes canonically accepted work with durable correlation,
recovery, and publication. Scheduling can use a different executor, and AWS
execution can receive work admitted from another scheduler.

## Prerequisites And Non-Goals

- Reuse the public 0.59 managed backend, durable stores, trigger contracts and
  outbound policy plus 0.56–0.58 admission, execution/fencing and effect recovery.
  The shared dispatch generalization is implemented in the existing core and
  SQLModel owners. The AWS package has no dependency on Prefect, Connect, FastAPI
  or Data Mover; AWS SDKs remain optional and no `etlantic-runtime` wheel is
  assumed.
- The [0.59 exit record](EXIT_GATE_0_59.md) defers external qualification.
  The [0.60 preview release](EXIT_GATE_0_60.md) supplies local adapter experience,
  not qualified AWS transport or durable-store evidence. Carry relevant inherited
  gaps into the AWS evidence matrix; distribution does not close them.
- Initial scope is static-batch `/1` with PostgreSQL durable state. Broader
  plan/runtime support requires separate evidence, never inferred compatibility.
- Do not promise direct arbitrary HTTPS delivery from EventBridge Scheduler.
  Qualify Scheduler → scoped Lambda relay → receiver as the initial transport.
- ECS/Fargate is the sole initial executor. Batch, event-bus/API-destination
  relay variants and other AWS services are unscheduled demand-gated candidates.
  No S3 data access, Secrets Manager, general infrastructure provisioning or
  second runtime is absorbed into this package. Broader provider packs stay in 0.65.

## Implemented Shared Contracts And Local Evidence

The following changes are present in the workspace. Gate A still freezes their
public contracts and versions for the live campaign; that review and AWS
qualification are not implied by local tests.

| Concern | Implemented contract | Remaining qualification |
|---|---|---|
| Trigger wire | `etlantic.control_plane` envelope/1 and receipt/1 are reused. The relay rejects unknown/missing event fields and derives occurrence identity only from Scheduler's nominal UTC slot. | Live Scheduler/Lambda duplicates, delay, redrive and receipt recovery. |
| Admission and timer | `ScheduleApplicationService.trigger_external` remains the canonical admission boundary. Schedule schema/3 persists a stable start anchor and opaque timer-binding SHA-256; external resume advances the owner generation and re-anchors. | Live nominal-sequence equivalence, pause/resume, delay, misfire and overlap against PostgreSQL. |
| Dispatch records/routes | Dispatch schema/5 and reconciliation schema/3 register only `prefect:` and `ecs:` routes. Generic `remote_run_id` carries ECS task ARNs; Prefect aliases and historical codecs remain readable. Unknown kinds fail closed. | Installed Prefect/ECS upgrade and rollback matrix. |
| Dispatch operations | Memory and SQLModel stores use the same durable transitions for route lifecycle, reservations, pending/reconciliation selection, lease/link/rearm and operator authorization. | Multi-process PostgreSQL response-loss and stale-observation campaign. |
| Accepted work and execution | `AcceptedExecutionReference` lives in core. Prefect retains its legacy reference schema; the optional AWS worker installs without Prefect and calls public targeted managed execution. | Built-wheel isolation and live execution/publication on pinned Fargate. |
| Transport | `ScheduledTriggerRelay` reuses `etlantic-rsconnect`'s bounded HTTPS transport and receipt contract. AWS SDK use is optional in `etlantic-aws[aws]`; core has no AWS dependency. | Real DNS/connect/TLS/read enforcement, Lambda failure destination and authorized redrive. |

Accepted/skipped receipts use HTTP 200; pending preparation uses 202 and is not
yet accepted work. An accepted receipt need not immediately contain a run ID.
Validate schema, occurrence and correlation before recording delivery; follow
only authorized status references under the same outbound policy. Scheduler
delivery, relay completion, durable admission, remote task state and canonical
ETL result remain separately observable.

## AWS Facts And Initial Support Candidate

The following official sources were reviewed on 2026-10-14. They establish
platform constraints; they do not replace qualification of the selected tuple.

- Scheduler supplies schedule ARN and nominal scheduled time separately from
  execution/attempt identifiers. Use scheduled time for occurrence derivation;
  execution and attempt identifiers are delivery observations.
  [Scheduler context attributes](https://docs.aws.amazon.com/scheduler/latest/UserGuide/managing-schedule-context-attributes.html).
- Scheduler invokes Lambda asynchronously. Scheduler target delivery and Lambda
  function execution therefore have separate failure handling. A successful
  handoff to Lambda does not prove HTTPS acceptance.
  [Scheduler/Lambda invocation](https://docs.aws.amazon.com/lambda/latest/dg/with-eventbridge-scheduler.html).
- Lambda asynchronous delivery can duplicate events and retry function failures;
  configure its event age/retries and failure capture explicitly, independently
  of Scheduler's retry/DLQ configuration.
  [Lambda asynchronous errors](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-error-handling.html),
  [Scheduler DLQ](https://docs.aws.amazon.com/scheduler/latest/UserGuide/configuring-schedule-dlq.html).
- Scheduler provides 60-second invocation precision even with flexible windows
  disabled. Local-time cron skips nonexistent spring slots and fires once for a
  repeated autumn slot; a rate day is a 24-hour duration.
  [Schedule types](https://docs.aws.amazon.com/scheduler/latest/UserGuide/schedule-types.html).
- ECS `RunTask` idempotency is cluster-scoped and requires the same token and
  request parameters. Its retention is limited to the smaller of 24 hours and
  task lifetime plus one hour. AWS token retention cannot replace durable
  ETLantic reconciliation.
  [ECS idempotency](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ECS_Idempotency.html).

Start with one account/region, one owned schedule group and pinned Lambda
version, an explicit HTTPS receiver, and one Linux Fargate deployment using
on-demand capacity, a pinned platform version, task-definition revision and
image digest. Use a framework-neutral receiver and independently installed worker
against PostgreSQL. The schedule-only path first targets an existing independent
worker whose exact tuple is qualified in that campaign; execution-only admission
bypasses Scheduler/Lambda. Qualify their combined
path only after the independent paths pass; it does not imply Data Mover support.

The first recurring candidate is a UTC whole-minute interval with explicit
anchor and flexible window `OFF`. Gate A must demonstrate exact nominal-sequence
equivalence to the canonical schedule, including start/end, pause/resume, delay,
missed slots and overlap. Whole-minute granularity alone is insufficient.
Sub-minute schedules, arbitrary cron translation, local-time/DST variants,
catch-up modes, Spot, Windows, cross-account/region failover and adaptive `/2`
remain unsupported until separately scoped and qualified. Negative fixtures
prove that unsupported combinations fail before remote activation.

## Scheduling, Relay And Lifecycle Rules

1. Create remote schedules disabled. Persist owned resource identity, immutable
   revision/generation, target version, recurrence and delivery-policy digest
   through a public durable ownership journal. Freeze that owner/codec at Gate A;
   process-local locks or AWS tags alone cannot coordinate concurrent operators.
   Read back the complete intended configuration before activation.
2. Populate target input with the bound ETLantic references and Scheduler context
   placeholders. Validate schedule ARN against the trusted account/region/group
   and binding, canonicalize nominal time, then derive the occurrence using the
   public helper. Payload ARN is a correlation check, not authentication; IAM and
   the bound receiver workload identity authorize delivery. Manual invocation
   without authorized occurrence context fails closed.
3. Preserve revision, generation and nominal slot across Scheduler retry, Lambda
   duplicate/retry, HTTP retry and operator redrive. Never reconstruct a retry's
   slot from wall time or the receiver's now-advanced cursor. Persist any relay
   recovery state through the journal; existing receipt authority stays canonical.
4. Freeze numerical limits for Scheduler event age/retries, Lambda event
   age/retries/concurrency/timeout, credential resolution, HTTP attempts,
   connect/read deadlines, bytes, polling and redrive retention. Bound the total
   delivery budget, including queue delay; pending, response loss and malformed
   receipts are recoverable states rather than an invented acceptance result.
5. Capture Scheduler target-delivery failures and Lambda execution/delivery
   failures separately. One scoped SQS failure-capture recipe may support those
   paths, with explicit message formats, redaction, retention and authorized
   redrive. This is delivery support, not an SQS ETL executor. Test failure to
   write the failure destination itself and reconcile undelivered occurrences.
6. Use canonical compare-and-swap revision and timer-owner fencing for updates,
   pause/resume, deletion and migration. Disable old delivery before enabling a
   replacement; reconcile lost mutation responses and queued old events. Pause
   or delete rejects new admission at the canonical boundary but preserves
   admitted work and history. Rollback uses a valid new revision/generation.
   Resolve gaps according to canonical misfire policy; never invent catch-up slots.
7. Compare remote readback with the durable intended state. External edits,
   concurrent operators and uncertain creates block blind overwrite. Cleanup
   checks ownership and outstanding references; deletion of a schedule or relay
   does not cancel admitted ETL. Run cancellation is a separate authorized action.

## ECS Dispatch, Execution And Recovery Rules

- Bind account, region, cluster, task definition, image, platform/architecture,
  task/execution roles, container entry point, network and resource limits in
  trusted immutable configuration. Runtime task identity must match the accepted
  dispatch and deployment binding. Deny caller-supplied image, command, role,
  backend factory, environment, endpoint or network overrides; only the bounded
  accepted reference is variable launch input.
- Persist dispatch intent before `RunTask(count=1)`. Derive an explicit bounded
  client token from the durable dispatch identity/generation and freeze the full
  request digest. Store the opaque task identity through shared `remote_run_id`;
  keep AWS request details in adapter-owned versioned binding/journal metadata.
- On response loss, reuse the same token and parameters only within its safe
  reconciliation window. Inspect both `tasks` and `failures`, including HTTP 200
  with no task, token conflicts, eventual visibility and truncated observations.
  An expired token or unavailable task record never proves no task ran. Retain
  uncertain/reconciliation-required state until authorized evidence permits
  linking or rearming; do not mint a replacement token to escape uncertainty.
  [RunTask response contract](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_RunTask.html).
- After ECS confirms a linked task is `STOPPED` and the canonical execution lease
  is inactive, recovery may start a new dispatch generation while preserving
  attempt history. The managed host first recovers its durable report; without
  one, it records an unknown effect and fails closed before rerunning the
  pipeline. A stopped task never establishes ETL success.
- If a worker commits terminal canonical state before the `RunTask` response is
  linked, first run canonical terminal cleanup, including quota release and
  outbox acknowledgement. Settle the unlinked dispatch only after a terminal
  attempt is durable and both dispatch and execution leases are inactive. Keep
  the record discoverable while cleanup is pending. Result publication and
  unknown-effect evidence remain governed by their own workload counts.
- The worker resolves the immutable accepted envelope, verifies fingerprints,
  scope, route/binding and remote dispatch identity, then uses public targeted
  execution, heartbeat, effect recovery and fenced publication. Launch races
  before task linkage must use the same shared validation/recovery rule as
  Prefect. Duplicate tasks cannot create concurrent effectful attempts.
- Polling is sufficient for initial recovery; any callback is authenticated and
  correlated to the same scope, dispatch generation and task. No new event-bus
  relay is required. Missing, duplicate or stale observations cannot publish a
  result or rearm claimed work. A stopped task or zero container exit code alone
  never establishes canonical ETL success.
- Record canonical cancellation before cooperative stop and bounded `StopTask`
  escalation. Exercise pre-launch, startup, active-effect and post-publication
  races, including failed stop and expired leases. Task loss, timeout or forced
  stop with uncertain writes retains unknown-effect evidence for reconciliation;
  provider/container restarts cannot bypass canonical retry authority.

## Identity, Network And Resource Ownership

Separate deployer, Scheduler invocation, Lambda relay, ECS task execution,
worker task and operator identities. Scope `iam:PassRole` and service trust to
approved roles/resources; verify exact Lambda-version invocation and ECS
task-definition/cluster permissions. Workload credentials use runtime identity
or existing secret-reference protocols, never values in target input, task
overrides, plans or journals. IAM permission does not grant application scope.

Specify actual receiver/store reachability, TLS trust, DNS/connect enforcement,
egress and private-network exceptions. Use shared outbound conformance for relay
HTTP, including redirect/auth leakage, bounded reads and credential rotation.
Workers apply production plugin/resource/optimization/schema-registry allowlists
where enabled. Retain references to bounded protected diagnostics; reports,
failure messages and logs contain neither credentials nor source rows.

Operators provision IAM, networking, registry, database and failure destinations
from a reviewed recipe. The adapter owns only explicitly recorded schedules and
dispatch tasks; shared infrastructure is not swept during cleanup. Record exact
retention, orphan inventory, quotas, concurrency/cost limits and teardown evidence.

## Workstreams

| ID | Workstream | Local implementation | Qualification still required |
|---|---|---|---|
| 061-S | Scheduling | Disabled-first lifecycle, durable timer-binding digest, stable recurrence anchor, readback and generation fencing | Anchor/boundary/misfire equivalence, update/pause/delete races, rejected unsupported timezone/DST cases |
| 061-H | HTTPS relay | Scheduler-context validation, shared outbound transport, pending/receipt recovery, bounded retry policy | Separate live Scheduler/Lambda failure capture, real outbound enforcement and authorized redrive |
| 061-E | ECS/Fargate | Pinned task binding, immutable accepted reference, installed targeted worker and durable recovery operations | Live ETL effects/publication, task loss, cancellation and recovery |
| 061-D | Durable dispatch | Generalized route/record/store/reference seams, Prefect codec compatibility and canonical reconciliation | Installed Prefect/ECS parity, codec/upgrade/downgrade guards, response loss, expired-token uncertainty and stale observations |
| 061-I | Identity and operations | Explicit roles, workload identity, private-network binding and scoped adapter ownership | Cross-scope denial, revoked credentials, outage, quotas and cleanup proof |
| 061-Q | Qualification | Optional package and local contract/fault tests | One isolated account/region qualification for each path and their composition |

## Delivery Sequence And Review Gates

| Gate | Reviewable change | Current status | Evidence required to advance |
|---|---|---|---|
| A — contract freeze | Initial tuple, recurrence mapping, role/network model, journal owner, retry budgets and decision register | Local contracts are documented; owner freeze before remote mutation remains open. | Public contract fixtures and operation mapping; unsupported cases and migration approach recorded before remote mutation. |
| B — shared dispatch | Shared route, reference and dispatch transitions | Implemented and locally tested. | Prefect fixtures/aliases remain compatible; unknown backends rejected; both memory and SQLModel use one transition authority; pre-ECS binaries reject incompatible ECS state safely. |
| C — local adapter | Optional package, disabled schedule lifecycle, relay and ECS API adapters, installed targeted worker | Implemented; wheel-isolation check is part of this change. | Built-wheel isolation, deterministic bindings, wire parity and local fault simulations pass. Scheduling and execution modes install/configure independently. |
| D-S — scheduling | One live Scheduler/Lambda path to a non-FastAPI receiver and existing independent worker | Deferred; no AWS campaign run. | Nominal-time/lifecycle, both failure channels, HTTP recovery, redrive and outbound enforcement pass over PostgreSQL. |
| D-E — execution | Manual canonical admission to one installed Fargate worker | Deferred; no AWS campaign run. | Actual effects/publication, response loss/token expiry, cancellation, worker loss, security and Prefect regression evidence pass independently of D-S. |
| E — support decision | Compose the passed paths; publish support matrix, operations/cleanup and evidence index | Deferred until D-S and D-E evidence exists. | Per-AC results and inherited gaps resolved or explicitly deferred. No production claim for any incomplete gate; broader hosts/services remain unsupported. |

Deliver these as separate changes. Shared-runtime generalization is a prerequisite
for ECS integration, not for local schedule/relay design. Gate C can be completed
without AWS access using SDK stubs, controlled HTTP servers, subprocesses and
installed-wheel tests. A preview may be distributed after its local build,
contract, security, lint/type and documentation checks pass and release owners
record truthful disabled/experimental boundaries. External campaigns qualify
activation and support separately; they are not implicit distribution blockers.
Local implementation is complete for the stated candidate matrix. D-S, D-E and
the production support decision remain deferred until their live evidence is
recorded; package installation alone does not qualify AWS support.

## Production Support Acceptance

- **AC061-001:** Optional installation keeps AWS SDKs out of core and supports
  schedule-only and execution-only configuration independently.
- **AC061-002:** Schedule retries/relay retries/redrive preserve occurrence
  identity and authorization; unsupported recurrence fails before activation.
- **AC061-003:** The one ECS/Fargate adapter executes actual accepted pipelines
  through pinned installed workers and publishes canonical effects/results.
  The same generic dispatch operations serve Prefect and ECS without per-vendor
  core fields or a copied managed runtime. Both workers use the common reference
  seam; legacy Prefect data and public entry points retain their stated window.
- **AC061-004:** Lost submit responses, crashes, stale callbacks, and remote
  retry defaults cannot cause unfenced publication or blind repeated effects.
- **AC061-005:** Cross-scope identity/override attempts fail; secrets resolve only
  at authorized runtime boundaries and remain absent from persistent artifacts.
- **AC061-006:** Live cancellation, polling recovery, resource cleanup, upgrades,
  and service outages preserve durable evidence within the advertised matrix.

AC061-002 includes trusted nominal-time provenance, independent Scheduler/Lambda
failure channels and delayed redrive after cursor advancement. AC061-004 includes
expired ECS idempotency tokens, eventual task visibility, loss before task linkage,
and effect/publication races. AC061-006 includes schedule drift, concurrent
operators, queued old events and rollback/downgrade guards, not just API success.

## Evidence Matrix

| Family | AC coverage | Required cases / environment |
|---|---|---|
| E061-PKG | 001, 003 | Installed wheel with workspace imports disabled; schedule-only/execution-only composition without Prefect/Connect/FastAPI/Data Mover, core without AWS SDK, pinned worker image manifest and dependency/version matrix. |
| E061-WIRE | 001, 002, 005 | Frozen /1 corpus; exact fields, size/version errors, wrong correlation, pending/skipped/accepted and absent run ID; controlled receiver and installed independent consumer. |
| E061-OCC | 002, 004 | Trusted context, duplicate Lambda invocation, delayed HTTP retry/redrive after cursor advancement, missing slots, unsupported recurrence, owner transfer and stale revision/generation; live Scheduler/Lambda plus PostgreSQL concurrency. |
| E061-LIFE | 002, 006 | Disabled create/read/update/pause/resume/delete/reconcile, lost mutation responses, drift, competing operators, queued events, failure-destination failure and scoped cleanup; isolated AWS resources with durable journal. |
| E061-DIS | 003, 004, 006 | Prefect legacy/generic codec parity, ECS route/reference validation, upgrade/downgrade guards, lost RunTask response, tasks/failures, token expiry/conflict, orphan/missing task and concurrent dispatcher leases; local simulations plus live ECS/PostgreSQL campaign. |
| E061-EXEC | 003, 004, 006 | Real portable static-batch /1 ETL effects/results from installed Fargate worker; kill before claim, during write and before publication, heartbeat loss, cancel/stop race, unknown effects and stale observations; independent receiver/dispatcher/worker processes. |
| E061-SEC | 001, 002, 005 | Cross-scope/binding/role/override denial, forged context/callback, rotation/revocation, IAM trust/PassRole, TLS/DNS/connect/redirect/byte bounds, trusted private destination and artifact/log redaction; live identities plus controlled network endpoints. |
| E061-OPS | All | Exact account/region/service/runtime/dependency tuple, source/wheel/image hashes, outage/throttle/quota drills, cost limits, retention/backup/restore, orphan inventory and cleanup runbook; independent scheduling/execution/composed support decisions. |

Record case ID, AC/workstream/F02/F09/F12 links, relevant inherited E059 cases,
source revision, wheel/image hashes, exact versions/store/process topology,
expected and observed outcomes, immutable redacted artifact reference and
pass/fail/unavailable/deferred status. Required skips remain incomplete. Fakes
establish local correctness only; closing one AWS case does not silently close
all deferred 0.59 campaigns or qualify the Data Mover composition in 0.62.

## Decision Register

| Decision | Accountable owner | Due / required record |
|---|---|---|
| D061-CONTRACT | Runtime + persistence + Prefect | Gate A/B: public route/reference/dispatch owner, registered backend mapping, codec versions, alias window and rejection/downgrade behavior; no copied worker/runtime. |
| D061-TIMER | Schedule/runtime + AWS | Gate A: exact nominal sequence/anchor and context provenance, lifecycle/misfire mapping, ownership journal/serialization, stale-event and migration policy. Unsupported mappings prevent activation. |
| D061-DELIVERY | Transport + security + AWS | Gate A: numerical combined retry/queue/credential/network/byte budgets, Scheduler versus Lambda failure disposition, receipt recovery, redrive authorization and retention. Gate D-S proves real connection enforcement. |
| D061-ECS | Runtime + AWS | Before ECS integration: pinned launch tuple/request digest, token derivation/expiry horizon, trusted task identity and pre-link race, reconciliation/stop policy. Gate D-E supplies real effects. |
| D061-IDENTITY | Security + operations | Before live mutation: per-role action/resource/trust matrix, IAM-to-application identity mapping, secret references, network paths, infrastructure ownership and bounded teardown. |
| D061-RELEASE | Packaging + release + phase owners | Gate C/E: adapter dependency/release ranges, local preview disposition, inherited evidence gaps and independently qualified scheduling/execution/composed tuples. No unmeasured compatibility range or implied production claim. |

## Required Release Evidence And Decisions

Map AC061-001–006 to E061-PKG/WIRE/OCC/LIFE/DIS/EXEC/SEC/OPS and the decision
register. Publish separate local implementation and production qualification
records with cost/quota, failed/pending/unknown delivery, token-expiry, cancellation,
credential rotation, upgrade/rollback and cleanup runbooks. Re-review on AWS API,
SDK, runtime/store contract, identity or deployment changes. A scheduler gate
cannot close the ECS execution gate; documentation alone closes neither.
Batch may be considered only for a named workload ECS cannot adequately serve,
with an owner, dependency/operational cost decision and its own live/failure gates.
It has no assigned release and is not a 0.61 completion requirement. Any expansion
requires the roadmap and owning plans to be updated first.
