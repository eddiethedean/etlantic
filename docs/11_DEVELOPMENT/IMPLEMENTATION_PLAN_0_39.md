---
title: ETLantic 0.39 Implementation Plan
description: Implementation-grade plan for the control-plane API and identity foundation.
plan_status: current
plan_last_reviewed: 0.37.0
---

# ETLantic 0.39 Implementation Plan

Phase 0.39 establishes an embeddable, versioned control-plane API and canonical
request identity. It is the first implementation slice of the
[multi-tenant control-plane plan](MULTI_TENANT_CONTROL_PLANE_PLAN.md); it does
not claim production multi-tenant isolation.

## Outcome

Applications can embed an `etlantic-fastapi` router or app factory, authenticate
a caller, construct a typed request context, discover and validate definitions,
plan work, durably submit runs, follow resumable events, and retrieve scoped
status and artifacts through a generated OpenAPI client.

## Prerequisites

- [0.38](IMPLEMENTATION_PLAN_0_38.md) has closed its landing-zone, metadata,
  reliability, and conformance gates.
- Identity vocabulary for principal, tenant, workspace, environment, security
  domain, and request is approved before route implementation.
- Durable submission and event contracts are designed with 0.41 migration in
  mind; process-local `BackgroundTasks` are not an accepted implementation.

## Scope Boundaries

In scope: API contracts, request identity, authorization hooks, discovery,
validation, planning, durable submission, status, cancellation, reports,
artifacts, lineage, schema/reliability routes, SSE, and optional SQLModel-backed
reference stores.

Not in scope: the complete tenant registry, production isolation claim, durable
execution-host protocol, policy engine, quotas, or GA control-plane operations.

## Workstreams

| ID | Workstream | Deliverables | Completion evidence |
|---|---|---|---|
| 039-I | Identity and scope | Versioned identity models; request context; dependency-injection interfaces; correlation and idempotency keys | Serialization compatibility tests and two-tenant/two-workspace context fixtures |
| 039-A | API package | Separate `etlantic-fastapi` package; router and app factories; lifespan hooks; stable operation IDs; request/response models | Import-boundary tests, OpenAPI 3.1 snapshot, generated-client smoke tests |
| 039-R | Resource routes | Typed discovery, validation, planning, submission, status, cancel, report, artifact, lineage, schema, and reliability endpoints | Route matrix covering success, invalid input, absent resource, and capability rejection |
| 039-Z | Authorization | Authentication adapters; object-level authorization before lookup, pagination, search, count, or error disclosure | Non-enumeration suite across every resource operation |
| 039-D | Durable acceptance | `202 Accepted` submission contract; injected durable repository/queue boundary; scoped idempotency | API-restart and multi-worker tests showing accepted work and duplicate submission are preserved |
| 039-E | Events | Ordered event envelope; resumable SSE cursor; history fallback; optional WebSocket adapter | Disconnect/reconnect, cursor expiry, duplicate suppression, and authorization tests |
| 039-L | Landing-zone bridge | File-drop/watch sensors submit through the durable API using workspace-scoped references | End-to-end fixture proving watcher logic remains outside core and never embeds file contents in plans |
| 039-O | Operability | Stable errors, health/readiness, metrics hooks, redaction, examples, generated-client publishing | Diagnostics snapshots, redaction tests, and reference deployment smoke test |

## Delivery Sequence

1. Freeze identity and error envelopes before publishing routes.
2. Ship the package skeleton, dependency interfaces, lifespan, and OpenAPI
   generation pipeline.
3. Implement read-only discovery/validation/planning routes and authorization.
4. Add durable submission, status, cancellation, reports, and artifacts.
5. Add resumable SSE and landing-zone submission integration.
6. Run the full operation/authorization matrix and generated-client workflow.

## Exit Gates

- An existing FastAPI application embeds the router without replacing its
  lifespan, dependency graph, middleware, or exception handling.
- OpenAPI 3.1 is stable, has deterministic operation IDs, and generates a client
  that completes the reference workflow.
- Two API workers share durable submissions and event history; restarting either
  does not lose accepted work.
- Authentication and authorization precede existence lookup, count, search,
  pagination, artifact access, and event subscription.
- Every operation passes the two-tenant/two-workspace allow/deny and
  non-enumeration matrix.
- Live schema observations are labeled observations and cannot become contract
  authority through an API side effect.
- Optional SQLModel stores use request-scoped sessions and separate request,
  persistence, and response models.
- Release notes state clearly that CP1 is a foundation, not the production
  multi-tenant support claim reserved for 0.44.

## Required Release Evidence

- OpenAPI compatibility report and generated-client transcript.
- Operation-by-operation authorization/non-enumeration matrix.
- Multi-worker restart and SSE resume results.
- Dependency/import report proving FastAPI and SQLModel remain optional.
- Threat review for identity spoofing, idempotency collisions, artifact access,
  schema authority, and information disclosure.

