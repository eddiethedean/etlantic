---
title: ETLantic Data Mover Integration Plan
description: Durable application composition with independent scheduling, execution, and optional Posit endpoint discovery.
plan_status: planned
plan_last_reviewed: 2026-10-12
---

# ETLantic Data Mover Integration Plan

**Status: planned; phase [0.62](IMPLEMENTATION_PLAN_0_62.md).** This is a consuming
application integration, not a Data Mover dependency in ETLantic. Source
provenance and shared boundaries are in the [runtime plan](ETLANTIC_RUNTIME_PLAN.md).

## Outcome And Ownership

Data Mover configures pipelines, credentials, schedules, execution placement,
run history, and results while ETLantic provides canonical admission and ETL
execution. An authenticated trigger produces a durable run and dispatch intent;
independent workers survive API application restarts and publish real results.

Data Mover owns application identity and authorization configuration, credential
references, storage deployment, and product views. Existing ETLantic backend
services/store adapters own ETL state and policy enforcement. The host wires
public factories; it must not implement another ETL scheduler, worker state
machine, provider factory graph, or result authority. PostgreSQL persistence
reuses qualified stores; any product projection is rebuildable from canonical
run/result records. Schema migration remains a separate authorized operation.

## Initial Reference Composition

The accepted [scope consolidation plan](PACKAGE_SCOPE_CONSOLIDATION_PLAN.md)
limits 0.62 to one host composition: existing CP1 FastAPI surfaces adapting the
canonical SQLModel backend, PostgreSQL durable stores and one separately
supervised installed durable worker. Use the 0.59 canonical backend settings and
existing-backend HTTP adaptation; Data Mover adds product settings only.

Manual, explicit-URL Connect and schedule-only AWS/Lambda delivery are timer
variants against this same receiver and worker, qualified individually. Optional
trusted public URL discovery is a configuration variant of this host. Managed
Prefect or ECS placement and other host/persistence combinations require concrete
consumer demand and their own composition evidence; their standalone qualification
does not imply Data Mover support. Do not test or promise every timer × executor
× host combination.

## Delivery Flow

1. An operator selects pipeline revision, schedule backend, and independent
   execution backend through authorized configuration. One backend owns the
   timer. Store endpoint, scope, credentials by reference, and versioned placement.
2. Connect or AWS sends the shared authenticated trigger. An optional receiver
   in existing `etlantic-fastapi` adapts it to the same headless services used
   for manual and 0.57 scheduled requests. It uses the CP1 host surface
   (`ETLanticAPI` / `include_router` / `create_app`), not `create_reference_app`.
3. Shared services authorize, validate, prepare, and atomically deduplicate/admit
   the occurrence and persist dispatch intent. Return a bounded receipt after
   commit. An API crash before or after the response cannot lose accepted work.
4. The one separately supervised installed durable worker consumes accepted
   work through the shared managed implementation. The
   API never executes long ETL in request handlers or `BackgroundTasks`.
5. Status/results flow through canonical stores and authorized projections.
   Authenticated callbacks are hints checked against scope and attempt fencing;
   reconciliation recovers missed, duplicated, stale, or out-of-order callbacks.

The same HTTP contract must work without Data Mover. It introduces no mandatory
FastAPI dependency into `etlantic-rsconnect` or `etlantic-aws`.

## Optional Public Endpoint Discovery

A small optional adapter in the consuming integration uses `fastapi-posit`;
no `etlantic-fastapi-posit` distribution is created. `fastapi-posit` is proposed
for determining a trusted
Connect public base URL. Verify its actual installed/public API before selecting
an adapter; `resolve_connect_app_url` from the conversation is illustrative and
must not be documented as a shipped function.

Posit documents the incoming `rstudio-connect-app-base-url` header for discovering
an application's public base URL behind its proxy. It is request-context
information, not a guaranteed startup value. See
[Posit FastAPI documentation](https://docs.posit.co/connect/user/fastapi/).

During authorized schedule configuration:

- Prefer an explicit administrator-configured HTTPS base URL when supplied.
  Otherwise resolve through the verified optional adapter in a trusted proxy
  request context; absence of either yields a configuration diagnostic.
- Validate HTTPS scheme, allowed origin/port, expected application path, and
  trusted proxy provenance. Reject userinfo, fragments, unexpected query data,
  spoofed forwarded headers, path traversal, and unapproved destinations.
- Append the receiver route while preserving Connect's application prefix and
  any configured router prefix; do not drop the base path with root-relative
  URL joining or duplicate prefixes.
- Persist the normalized endpoint and provenance with the schedule revision,
  not an ephemeral Request object. Startup and scheduler delivery use that
  validated configuration without needing an incoming request.
- Revalidate changes and require authorized schedule revision updates after
  redeployment, app-path changes, or origin changes. Ordinary requests cannot
  silently rewrite destinations. Absence of `fastapi-posit` preserves explicit
  URL configuration and non-Connect deployment.

## Acceptance Campaign

| Scenario | Required result |
|---|---|
| Duplicate/concurrent trigger or response lost after commit | One canonical occurrence/run mapping and recoverable dispatch |
| API process killed before/after acceptance | No false receipt before commit; accepted work executes after restart |
| Dispatcher or worker killed; remote submission response lost | Reconcile existing work, preserve fencing and known/unknown effects |
| Missed/duplicate/out-of-order callback | Poll/events converge to canonical status without invented success |
| Pipeline failure, partial write, timeout or cancellation | Distinct ETL/effect/publication evidence and safe retry/manual-review behavior |
| Schedule update/pause/delete and timer migration | No duplicate timer authority or silent resubmission of old occurrences |
| Cross-tenant replay or forged callback | Denied without resource enumeration or scope escape |
| Proxy spoofing, path prefixes, no request at startup | Trusted URL selection; correct route composition; explicit configuration works |
| Secret rotation/revocation and unavailable providers | Bounded redacted failures without ambient credential fallback |

Qualify manual/Connect/AWS admission equivalence with real PostgreSQL, separate
API/dispatcher/worker processes, and real CSV→PostgreSQL and PostgreSQL→PostgreSQL
effects/results. Exercise Connect-trigger and AWS/Lambda-trigger paths against
the same installed receiver/worker composition independently; executor swaps
and other hosting combinations remain unsupported until their own scoped
consumer demand and qualification gates pass.

Required evidence includes an installed host example, Data Mover consumer
integration trace, URL-discovery tests, multi-tenant failure campaign, migration
and rollback instructions, role health/drain/backup/recovery runbooks, and an
exact platform/version support table. The broader operator console remains 0.64.

Application/API maintainers own the host composition and route selection;
security/platform maintainers own trusted proxy/origin policy and optional
`fastapi-posit` API/version verification before implementation. Review this plan
when the consumer, runtime contract, or platform deployment shape changes.
