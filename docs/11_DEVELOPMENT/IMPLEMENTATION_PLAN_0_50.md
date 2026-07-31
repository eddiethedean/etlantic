---
title: ETLantic 0.50 Implementation Plan
description: Implementation-grade plan for the separately deployable operator console.
plan_status: current
plan_last_reviewed: 0.37.0
---

# ETLantic 0.50 Implementation Plan

Phase 0.50 delivers a separately deployable, read-only-first operator console.
It consumes the versioned control-plane API through a generated client and uses
the shared artifact language from the [UI/UX plan](UI_UX_PLAN.md).

## Outcome

Authorized operators can inspect definitions, revisions, plans, diffs, runs,
attempts, events, lineage, partitions, checkpoints, quality, schema, repairs,
backfills, delivery objectives, deadline/escalation state, erasure operations,
dynamic expansions and branches, dead-letter/redrive state, schema-registry
compatibility, quotas, policy, approvals, audit, providers, and health.
Privileged actions reuse API policy, idempotency, approval, and audit paths
exactly.

## Prerequisites And Non-Goals

- 0.43 API/auth/event support and 0.44 artifact/interaction contracts are stable;
  0.46–0.49 capabilities appear only where the server advertises them.
- The console owns no source of truth, authorization rule, execution path, policy
  engine, schema authority, or provider credential.
- The core and API packages never depend on frontend code or its toolchain.
- Preview rendering is bounded and hostile content is treated as data, not markup
  or executable instruction.

## Workstreams

| ID | Workstream | Deliverables | Completion evidence |
|---|---|---|---|
| 050-F | Frontend foundation | Separate package/deployment, pinned generated client, session/bootstrap, capability negotiation, routing | Clean build/deploy and client/server compatibility matrix |
| 050-R | Read surfaces | Scoped list/detail views for definitions through health; stable URLs and breadcrumbs | View fixture matrix, pagination, empty/error/loading states |
| 050-E | Live events | Resumable run/event views, cursor persistence, history fallback, reconnect and duplicate suppression | Refresh/disconnect/cursor-expiry tests |
| 050-A | Privileged actions | Cancel, retry, repair, backfill, approve, promote, authorize/retry erasure, suspend, containment actions through public API | Policy/idempotency/approval/audit equivalence traces |
| 050-D | Objectives and dynamic execution | Deadline timelines, breach/escalation/recovery state, map/reduce children, branch decisions, stable identities, bounds, and capability explanations | Clock/reconnect/dedupe fixtures plus large bounded expansion and branch-state tests |
| 050-P | Privacy and stream errors | Erasure request/plan/provider/reconciliation views plus payload-free DLQ/redrive and schema-compatibility views | No-subject/no-payload browser-state tests and partial/unsupported outcome fixtures |
| 050-S | Security/privacy | Object authorization, non-enumeration, cache partitioning, bounded previews, CSP, hostile-content redaction | Two-tenant/two-workspace UI leakage campaign |
| 050-U | Usability/accessibility | Keyboard/screen-reader flows, localization readiness, responsive layouts, latency budgets | WCAG-oriented audit, locale/pseudo-localization, performance report |
| 050-T | Test fixtures | Deterministic generated-client mocks plus integrated API fixtures for all capability states | CI visual/interaction tests without production credentials |
| 050-O | Operations | OCI image, configuration, health, telemetry, upgrade/rollback and incident runbooks | Deployment, version-skew, failover, and rollback drill |

## Delivery Sequence

1. Freeze console information architecture, threat model, and generated-client
   version policy.
2. Implement read-only registry, plan, run, quality, schema, delivery-objective,
   erasure, dynamic-control, dead-letter, and operations views.
3. Add resumable live events, bounded previews, deadline/escalation timelines,
   dynamic child/branch navigation, and lineage/partition navigation.
4. Add privileged actions only through existing API commands and approvals.
5. Complete accessibility, localization, hostile-content, isolation, and
   performance qualification.
6. Publish deployment artifacts and the supported server/client matrix.

## Exit Gates

- The console contains no independent database, authorization decision, schema
  mutation, run scheduler, secret resolver, or provider control path.
- Every mutation produces the same policy, idempotency, approval, state-machine,
  and audit evidence as the equivalent API operation.
- Unauthorized scope cannot leak through counts, search, links, error shape,
  browser/server caches, history, event streams, downloadable artifacts, or
  timing-sensitive pagination behavior.
- Refresh and reconnect resume events without duplicating attempts or actions.
- Hostile names, diagnostics, payloads, and artifact previews are bounded,
  escaped, redacted, and covered by content-security policy.
- Erasure and dead-letter views never place data-subject values or event
  payloads in browser state, URLs, telemetry, caches, logs, or fixtures, and
  cannot report completion while required effects remain unknown or
  unreconciled.
- Critical workflows pass keyboard and screen-reader review, localization
  readiness, responsive layouts, and published latency budgets.
- The console deploys, upgrades, rolls back, and version-negotiates independently
  from ETLantic core and the control-plane API.

## Required Release Evidence

- Generated-client compatibility and deployment report.
- Full view/action-to-API traceability matrix.
- Cross-tenant UI leakage and hostile-content report.
- Event reconnect/refresh results.
- Accessibility, localization, and performance audits.
