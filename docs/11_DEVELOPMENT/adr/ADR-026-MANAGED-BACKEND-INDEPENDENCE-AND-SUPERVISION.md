# ADR-026: Managed Backend Independence and Runtime Supervision

**Status:** Accepted for 0.57.0
**Date:** 2026-10-08
**Issues:** [#278](https://github.com/eddiethedean/etlantic/issues/278), [#279](https://github.com/eddiethedean/etlantic/issues/279), [#280](https://github.com/eddiethedean/etlantic/issues/280), [#281](https://github.com/eddiethedean/etlantic/issues/281), [#282](https://github.com/eddiethedean/etlantic/issues/282)

## Context

The standard managed service graph and schedule command rules lived in the
FastAPI adapter. SQLModel backend construction did not include schedules, the
scheduler inferred recovery callbacks from bound methods, schema startup only
checked a migration marker, and worker roles exposed incomplete lifecycle
facts. Consumers need the same authorized services and durable graph without
installing or constructing an HTTP application.

## Decision

- Core owns `etlantic.control_plane.ManagedBackend`, canonical context shape
  validation, `etlantic.service.ScheduleApplicationService`, the
  `ScheduledOccurrenceService` protocol, and role lifecycle/status contracts.
- The SQLModel provider owns `SQLModelBackendConfig`,
  `create_managed_backend(config, *, authorizer, planning_context_factory=None,
  engine=None)`, `schema_requirements()`, and `inspect_schema(engine)`. A
  factory-created engine is owned by the returned handle; an injected engine
  stays caller-owned. Schema creation and migration remain explicit operations.
- The FastAPI adapter owns HTTP context derivation and wire representation.
  `adapt_managed_backend(core_backend, *, context_factory, ...)` adds that
  surface to an existing core handle. Legacy constructors remain facades over
  the provider-owned graph.
- Standard managed scheduling passes one complete occurrence collaborator
  with preparation, submission, and recovery methods. The scheduler does not
  infer behavior from a callback's bound owner. Low-level callback-only
  execution requires an explicit `allow_callback_only=True` declaration.
- Scheduler, run-worker, and action-worker handles expose local `status()` and
  idempotent nonblocking `request_drain()`. Status separates activity, work
  admission, prerequisite observations, capabilities, and in-flight work.
  Draining prevents new claims; the current tick settles under its existing
  lease/fencing rules. The consumer owns tick threads, grace periods, and forced
  termination.
- Schedule authorization, visibility filtering, workload binding, revision
  pinning, timing, and prepare/claim/recover/submit/link orchestration live in
  `ScheduleApplicationService`. HTTP routes parse requests and project its
  results. Existing paths and operation IDs remain stable.

## Consequences

Consumers can construct the SQLModel graph headlessly and may adapt that exact
handle to FastAPI. Database observations and role status use bounded public
records with safe reason codes. Existing multi-store recovery remains
idempotent, but this ADR makes no cross-store atomicity or exactly-once external
effect guarantee. PostgreSQL least-privilege, race, restart, HTTP-parity, and
installed-wheel evidence remains a release qualification requirement.
