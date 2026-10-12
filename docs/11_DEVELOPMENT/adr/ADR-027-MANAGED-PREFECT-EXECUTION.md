# ADR-027: Managed Prefect Execution

Date: 2026-10-11
Status: Accepted for the 0.58 implementation; production qualification remains open

## Context

The optional `etlantic-prefect` package already supports local direct scheduling.
Managed Prefect workers must reconstruct execution from canonical durable
acceptance while ETLantic continues to own admission, authorization, effects,
leases, reports, and publication. See [phase 0.58](../IMPLEMENTATION_PLAN_0_58.md),
[#290](https://github.com/eddiethedean/etlantic/issues/290), and
[ADR-018](ADR-018-DURABLE-SUBMISSION-AND-STATE.md).

## Decisions

- Direct scheduling remains `etlantic.scheduler/1`. Managed execution is a
  separate optional-package entrypoint and does not change the meaning of
  `Profile(orchestrator="prefect")` or deployment rejection.
- A Prefect parameter is a closed `etlantic.prefect.managed_reference/1`
  mapping with only a scoped submission locator, plan fingerprint, and SHA-256
  digest of the immutable accepted envelope. Its encoded size is limited to
  4096 bytes. Unknown or missing fields, malformed digests, unsupported plan
  families, and any canonical mismatch fail before execution.
- The worker resolves its `ManagedBackend` and `ControlPlaneContext` from one
  uniquely installed `etlantic.prefect_worker_backends` entry point named by
  trusted deployment environment configuration. A flow parameter cannot
  select code, endpoint, tenant, credentials, or backend configuration.
- Before resource reads or connector I/O, the worker reauthorizes the accepted
  principal for `run.submit`, every planned resource, and every leased input,
  then reevaluates current pre-execution policy and approval state. If the
  worker's trusted principal differs from the accepted principal, it must also
  hold `run.execute` for the accepted definition. Fingerprinted accepted work
  fails closed when its current policy provider is unavailable.
- Worker execution is restricted to static-batch `etlantic.plan/1` inside the
  existing `etlantic.execution_envelope/2`. The worker delegates one scoped
  submission to `ManagedBackend.execute_submission`; the public targeted host
  method gives each invocation a distinct host owner identity and reuses the
  normal durable lease, fencing, cancellation, recovery, and publication path.
  Direct and managed execution use the same outbox, so a
  targeted invocation may safely lose the claim race and return a delivery
  no-op; it must never start a second effectful attempt.
- Every durable submission pins an execution route. The compatibility default
  is `local`; a Prefect route is `prefect:<64-character binding fingerprint>`
  selected only by trusted service configuration. Ordinary execution-host
  polling selects `local` work only. A managed flow requires its trusted
  `ETLANTIC_PREFECT_ROUTE_ID` to match the canonical accepted route before it
  claims work. Route selection is included in both CP1 acceptance payloads and
  CP3 idempotency checks, so retries and lifecycle children keep the original
  binding. Existing records without the optional field resolve to `local`.
- Prefect retries, caching, and persisted task/flow results are disabled for the
  direct and managed execution functions. The managed flow returns only bounded
  identifiers, terminal status, and report digest. ETL failure raises from the
  flow while canonical ETL evidence remains authoritative.
- Status and cancellation adapters resolve the same scoped accepted reference
  and use the canonical managed service authorization before contacting
  Prefect. The response keeps canonical ETL status separate from the
  timestamped orchestration observation. Durable ETLantic cancellation is
  recorded before a non-forced Prefect `CANCELLING` request; rejection,
  disappearance, or outage never rewrites ETLantic state.
- A scoped, fenced dispatch record persists the stable Prefect creation key and
  linked flow-run ID. Uncertain creates retry with the same key and bounded
  backoff. The worker verifies that its flow run has a matching durable
  dispatch intent and that remote deployment/pool configuration still matches
  the binding. Remote creation or flow completion acknowledges delivery only;
  neither acknowledges ETL execution or result publication.
- The dispatcher reconciles a bounded page of linked runs on each tick. It may
  open a new creation generation after Prefect reports a failed or crashed run
  only when the canonical submission remains accepted and an atomic durable
  check finds no active execution lease, attempt, effect, or result publication.
  New generations use distinct creation keys and are capped at three. Missing
  or ambiguous remote runs and failures after ETLantic execution begins remain
  reconciliation cases. At the automatic generation ceiling, the durable
  dispatch enters `reconciliation_required`, remains visible in authorized
  status, and cannot be claimed again automatically. A principal with
  `execution.dispatch.reconcile` may authorize a new generation only against
  the exact exhausted generation and flow-run ID, with an evidence note; the
  durable store rechecks that the route is active and no active ETL lease,
  attempt, effect, or publication exists. It records the actor and evidence
  digest in dispatch history and appends an audit event without persisting the note.
  Stale requests conflict. The acceptance remains queued and route retirement
  remains blocked until the dispatch is explicitly rearmed or cancelled. CP1
  exposes the same service operation at
  `POST /v1/dispatches/{submission_id}/reconcile`; the HTTP layer adds no
  separate authorization or recovery authority.
- Managed schedules pin the configured execution route when created. Each
  occurrence uses that route even after the service's default route changes;
  ETLantic's timer remains the only recurrence authority.
- A durable store keeps a store-wide lifecycle for each Prefect execution
  route. Missing legacy lifecycle state means `active`; `active -> draining`
  closes new acceptance atomically while previously accepted work continues;
  `draining -> retired` is refused until canonical submissions, attempts,
  dispatch intents, unresolved effects, pending result publications,
  unacknowledged outboxes, and durable schedule reservations are clear. Schedule
  creation reserves its route in the same durable lifecycle store before the
  schedule is written; deletion or route transfer releases that reference only
  after the schedule record changes. Route record, transition, and lifecycle
  projections use schema `/2`; pre-existing SQLModel snapshots without the
  reference collection remain readable and require no DDL migration.
- Retirement pauses and retains the exact immutable deployment and its history.
  Reactivation verifies the binding and Process pool and resumes the deployment
  before reopening acceptance. Explicit orphan cleanup requires the default
  30-day retention, zero historical canonical submissions and schedule
  references, a paused exact deployment, and no Prefect flow runs in any state.
  It uses `retired -> cleanup_pending -> cleaned`; cleanup-pending cannot be
  reactivated, and a lost delete response is resolved by retrying the exact
  deployment deletion. Prefect flow-run history is never deleted. Route
  transitions are revisioned and recorded with the acting principal. Finalized
  cancellation closes a pending or exhausted pre-claim dispatch, while leased
  and ambiguous creates remain outstanding until their remote state is
  resolved.

## Consequences and open work

This decision establishes the reference, worker reconstruction, route-aware
targeted host, versioned Process deployment registration, durable route
ownership and lifecycle, fenced dispatch/correlation, explicit scoped orphan
cleanup, and separate status/cancellation projections. It does not make a
managed deployment production-ready by itself. Cross-process dispatch/effect
recovery, live lifecycle/rollback and cleanup qualification, provider review,
recurrence fault coverage, clean-wheel consumer proof, and the self-hosted
Process-worker/PostgreSQL campaign remain in phase 0.58. A local Process-worker
smoke covers replace-mode CSV-to-PostgreSQL and PostgreSQL-to-PostgreSQL
transfers against PostgreSQL-backed ETLantic stores, but does not close those
release gates.

The currently implemented worker path therefore remains experimental and must
not be advertised as qualified managed orchestration. Qualification will use
the exact package, Prefect, server, provider, Python, and connector versions in
the phase evidence ledger.
