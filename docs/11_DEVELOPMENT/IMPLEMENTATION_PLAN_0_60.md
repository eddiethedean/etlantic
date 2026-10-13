---
title: ETLantic 0.60 Implementation Plan
description: Posit Connect scheduling and generic authenticated HTTPS triggers.
plan_status: planned
plan_last_reviewed: 2026-10-12
---

# ETLantic 0.60 Implementation Plan

Phase 0.60 builds optional `etlantic-rsconnect` for native Connect scheduling
and lightweight HTTPS triggers. The [rsconnect domain plan](ETLANTIC_RSCONNECT_PLAN.md)
owns platform boundaries. Former 0.60 console scope moves intact to
[0.64](IMPLEMENTATION_PLAN_0_64.md). All new capabilities remain planned.

## Outcome

Operators deploy and manage scheduled trigger content that calls any configured,
compatible HTTPS receiver. Receivers durably admit work and independent workers
execute ETL; Connect trigger success is reported separately from ETL success.

## Prerequisites And Non-Goals

- 0.59 supplies consolidated managed ownership, shared outbound policy and the
  missing versioned trigger/schedule seams, auth, identities, receipt
  semantics, and reference conformance; existing durable workers can be used
  before Data Mover integration in 0.62.
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

## Workstreams

| ID | Workstream | Deliverables | Completion evidence |
|---|---|---|---|
| 060-P | Platform characterization | Supported API/content/tool versions, recurrence and task metadata mapping | Recorded platform contract and versioned fixtures |
| 060-B | Trigger bundle | Minimal deterministic wire consumer, no full ETL environment, pinned explicit URL and credential references | Artifact inspection, reproducible deployment and clean install |
| 060-S | Schedule lifecycle | Create/read/update/pause/resume/delete, one timer owner, scoped content mapping | Live lifecycle, DST/misfire/overlap and drift tests |
| 060-T | HTTPS transport | Existing outbound policy/conformance, stable occurrence, auth/replay, bounded delivery retry and response validation | Non-FastAPI interoperability, response-loss and concurrent duplicate campaign |
| 060-R | Recovery and operations | Deployment idempotency, restart reconciliation, failed delivery, rollback/cleanup | Lost deployment response, process kill, orphan and credential-rotation drills |
| 060-Q | Qualification | Isolated live Connect campaign and truthful support matrix | Exact package/platform evidence; no fake-only support claims |

## Delivery Sequence

1. Freeze one explicit-URL content/receiver/worker topology, recurrence translation,
   occurrence derivation and explicit unsupported combinations.
2. Build and inspect the minimal trigger bundle against the 0.59 test receiver.
3. Implement explicit deployment and schedule lifecycle with durable correlation.
4. Qualify HTTPS failure/retry/security behavior and independent execution.
5. Run isolated live Connect lifecycle/recovery tests and publish operations docs.

## Exit Gates

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

## Required Release Evidence And Decisions

Map AC060-001–006 to live Connect transcripts, transport/conformance tests,
bundle/secret inspection, recurrence support tables, and deployment/cleanup
runbooks. Platform maintainers freeze Connect content topology and occurrence
metadata before implementation and re-review on API/tool changes. Record
platform Quarto prerequisites accurately without creating an ETLantic package.
The [consolidation plan](PACKAGE_SCOPE_CONSOLIDATION_PLAN.md) supplies F09/F12
traceability; one live topology suffices and broader combinations are not implied.
