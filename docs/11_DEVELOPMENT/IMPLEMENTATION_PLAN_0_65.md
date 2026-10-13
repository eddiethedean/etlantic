---
title: ETLantic 0.65 Implementation Plan
description: Demand-gated enterprise deployment and provider qualification over consolidated managed services.
plan_status: current
plan_last_reviewed: 2026-10-12
---

# ETLantic 0.65 Implementation Plan

Phase 0.65 packages qualified deployment and provider integrations without
turning any cloud, secret manager, runtime, or connector into a core dependency.
The [adoption ecosystem plan](ADOPTION_ECOSYSTEM_PLAN.md) governs provider
maturity and support claims.

## Outcome

Operators can deploy one selected reference control-plane/runtime profile and
its demand-backed provider set with explicit compatibility, identity, cost,
quota, region, lifecycle and cleanup behavior. OCI/Helm, Kubernetes, managed Spark,
secret and connector packs are portfolio candidates, not an obligation to ship
every vendor or topology in one release.

This phase moves from 0.61 to 0.65 after insertion of the
[0.59–0.62 scheduling and execution integration program](ETLANTIC_RUNTIME_PLAN.md).
The broader provider portfolio remains, with selection and package creation
gated by the accepted [scope consolidation plan](PACKAGE_SCOPE_CONSOLIDATION_PLAN.md).

## Prerequisites And Non-Goals

- 0.59–0.62 owns managed implementation consolidation and trigger seams, Connect
  scheduling, bounded AWS
  Scheduler/Lambda delivery, ECS/Fargate execution and one Data Mover composition.
  Batch is unscheduled and requires a concrete workload/scope decision first.
  This phase
  retains the broader enterprise portfolio and hardening scope, reusing those
  adapters where qualified rather than introducing competing execution paths.

- 0.56 owns the generic Foundry package and PostgreSQL/CSV application backend
  floor. This phase expands the enterprise portfolio and deployment hardening
  using those service, action, identity and recovery contracts.
- 0.57 owns complete headless role construction, provider compatibility
  inspection, and cooperative runtime supervision. Deployment packs configure
  and supervise these public contracts without duplicating schema or ETL logic.
- 0.58 owns the static-batch `/1` managed Prefect Process-worker adapter.
  Provider packs may add pool/cloud qualifications only with installed/live
  evidence for the same accepted-reference, dispatch, trust, fencing, and effect
  recovery contracts; Process qualification does not imply other pool support.
- 0.43 qualification and 0.47 remote-provider **fake** conformance are
  mandatory ([IMPLEMENTATION_PLAN_0_47](IMPLEMENTATION_PLAN_0_47.md),
  [ADR-023](adr/ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md)). 0.47 ships
  `FakeKubernetes` (`etlantic-k8s`) and an in-process Spark Connect fake
  (`etlantic-spark-connect`); live Kind/cluster and Databricks/EMR qualification
  belong to this phase only for selected providers. The console from 0.64 may
  observe providers but does not own them.
- Before implementation, name an adopter, one reference deployment and the
  minimum provider set it needs. All other listed vendors remain candidates;
  absent demand, record deferral rather than generating more wheels. Existing
  fake-only fixtures are not evidence of a live implementation.
- Provider packs are independently versioned, allowlisted in production, and
  capability-negotiated before plan acceptance.
- Long-lived cloud credentials are not embedded in plans, reports, artifacts,
  images, Helm values, examples, or test fixtures.
- Infrastructure recipes are maintained examples with tested support matrices,
  not claims that every topology or cloud service is supported.

## Workstreams

Apply each workstream to the selected reference deployment and provider set.
Record unselected platform workstreams as deferred in the release evidence.

| ID | Workstream | Deliverables | Completion evidence |
|---|---|---|---|
| 065-D | Distribution | One demand-backed deployment profile, OCI artifacts and Helm only where selected; SBOM/attestations and canonical config/upgrade hooks | Clean install, signed-image verification, upgrade/rollback matrix |
| 065-K | Kubernetes hardening | Workload identity, network/storage policies, pod security, autoscaling, disruption, scoped cleanup | Isolated cluster, node-loss, policy, and orphan tests |
| 065-S | Managed Spark | Promoted provider(s), runtime images, capability/cost/region model, cancellation/recovery | Live isolated conformance and workload comparison |
| 065-X | Secret providers | Selected optional vendor adapter(s) only; existing secret protocol, separate SDK/identity deps, references/rotation/expiry/outage | Missing/expired/rotated/outage and redaction suite |
| 065-C | Connector packs | Promoted cloud connectors with schema, state, reliability, effect, erasure/delete/anonymize proof, quota, and cleanup conformance | Per-provider live isolated qualification matrix |
| 065-E | Enterprise event providers | Qualified notification/escalation, dead-letter, and schema-registry provider packs where maintained demand justifies support | Live delivery/dedupe/redaction, DLQ/redrive, registry-outage, and compatibility matrix |
| 065-G | Governance | Compatibility/support tiers, region/cost/quota metadata, deprecation, incident and security lifecycle | Published support matrix and provider retirement drill |
| 065-I | Infrastructure recipes | Tested reference deployments, least-privilege identities, observability, backup/restore | Reproducible environment creation and recovery evidence |

## Delivery Sequence

1. Record actual adopter demand, one reference deployment, selected provider
   set, package isolation/value decisions and exact live qualification matrix.
   Do not require every cloud, Spark platform or secret manager.
2. Build signed distribution artifacts and validate clean deployment lifecycle.
3. Implement and qualify only selected Kubernetes/remote Spark providers against
   live isolated conformance. Preserve separate remote-session/PySpark realization
   boundaries; unselected Databricks/EMR/Connect paths stay deferred.
4. Add only selected optional secret adapters through existing protocols and
   prove rotation/outage behavior; no all-vendor default dependency bundle.
5. Promote connector packs only after state, schema, reliability, effect,
   erasure, and cleanup conformance pass in isolated accounts/projects.
6. Promote notification/escalation, DLQ, and schema-registry packs only after
   live authorization, redaction, retry, outage, and reconciliation evidence.
7. Publish tested recipes, costs/quotas/regions, lifecycle policy, and runbooks.

## Exit Gates

- The release decision names one reference deployment, a concrete adopter and
  qualified provider set, with unselected candidates explicitly deferred. No new
  wheel duplicates shared managed, schema-registry or secret authority.
- Every selected provider pack installs independently, is production-allowlisted
  explicitly, advertises versioned capabilities, and fails closed when missing.
- Credential references resolve through workload identity or a scoped provider;
  secret values never appear in persistent artifacts or diagnostics.
- Missing, expired, rotated, revoked, and unavailable credentials produce stable
  redacted outcomes and do not fall back to broader ambient authority.
- External effects use normalized pending/committed/failed/unknown state and
  provider cleanup is tenant/workspace scoped and idempotent.
- Each claimed provider passes live isolated conformance for identity, policy,
  schema, state, reliability, effects, cancellation, recovery, and cleanup.
- Distribution and recipes pass clean install, upgrade, rollback, backup/restore,
  region/limit documentation, and dependency/SBOM verification.
- No vendor SDK or mandatory managed-runtime dependency enters ETLantic core.
  S3 storage remains separate from AWS scheduling; provider-only dependencies and
  identities are isolated. Batch requires a separate demand/qualification decision.

## Required Release Evidence

- Signed distribution and lifecycle report for the selected reference deployment;
  include Helm install/upgrade/rollback evidence when that deployment uses Helm.
- Demand/selection record, package charters and per-selected-provider support/
  conformance matrix with unsupported combinations and deferred candidates.
- Workload-identity and credential lifecycle/redaction report.
- Failure, external-effect, and scoped-cleanup campaign.
- Reference deployment reproducibility and recovery transcript.
