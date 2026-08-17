---
title: ETLantic 0.51 Implementation Plan
description: Implementation-grade plan for managed-runtime and provider packs.
plan_status: current
plan_last_reviewed: 0.46.0
---

# ETLantic 0.51 Implementation Plan

Phase 0.51 packages qualified deployment and provider integrations without
turning any cloud, secret manager, runtime, or connector into a core dependency.
The [adoption ecosystem plan](ADOPTION_ECOSYSTEM_PLAN.md) governs provider
maturity and support claims.

## Outcome

Operators can deploy supported ETLantic control-plane/runtime profiles with OCI
images and Helm, use hardened Kubernetes and managed Spark execution, obtain
credentials through workload identity and optional secret-provider packs, and
select promoted cloud connector packs with explicit compatibility, cost, quota,
region, lifecycle, and cleanup behavior.

## Prerequisites And Non-Goals

- 0.43 qualification and 0.47 remote-provider **fake** conformance are
  mandatory ([IMPLEMENTATION_PLAN_0_47](IMPLEMENTATION_PLAN_0_47.md),
  [ADR-023](adr/ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md)). 0.47 ships
  `FakeKubernetes` (`etlantic-k8s`) and an in-process Spark Connect fake
  (`etlantic-spark-connect`); live Kind/cluster and live Databricks/EMR are
  this phase. The console from 0.50 may observe providers but does not own
  them.
- Provider packs are independently versioned, allowlisted in production, and
  capability-negotiated before plan acceptance.
- Long-lived cloud credentials are not embedded in plans, reports, artifacts,
  images, Helm values, examples, or test fixtures.
- Infrastructure recipes are maintained examples with tested support matrices,
  not claims that every topology or cloud service is supported.

## Workstreams

| ID | Workstream | Deliverables | Completion evidence |
|---|---|---|---|
| 051-D | Distribution | Versioned OCI images, SBOM/attestations, Helm chart, configuration schema, upgrade/rollback hooks | Clean install, signed-image verification, upgrade/rollback matrix |
| 051-K | Kubernetes hardening | Workload identity, network/storage policies, pod security, autoscaling, disruption, scoped cleanup | Isolated cluster, node-loss, policy, and orphan tests |
| 051-S | Managed Spark | Promoted provider(s), runtime images, capability/cost/region model, cancellation/recovery | Live isolated conformance and workload comparison |
| 051-X | Secret providers | AWS, Azure, GCP, and Vault provider packs; references, rotation, expiry, outage semantics | Missing/expired/rotated/outage and redaction suite |
| 051-C | Connector packs | Promoted cloud connectors with schema, state, reliability, effect, erasure/delete/anonymize proof, quota, and cleanup conformance | Per-provider live isolated qualification matrix |
| 051-E | Enterprise event providers | Qualified notification/escalation, dead-letter, and schema-registry provider packs where maintained demand justifies support | Live delivery/dedupe/redaction, DLQ/redrive, registry-outage, and compatibility matrix |
| 051-G | Governance | Compatibility/support tiers, region/cost/quota metadata, deprecation, incident and security lifecycle | Published support matrix and provider retirement drill |
| 051-I | Infrastructure recipes | Tested reference deployments, least-privilege identities, observability, backup/restore | Reproducible environment creation and recovery evidence |

## Delivery Sequence

1. Freeze package/version/support policy and the provider qualification matrix.
2. Build signed distribution artifacts and validate clean deployment lifecycle.
3. Harden the 0.47 Kubernetes (`etlantic-k8s`) and Spark Connect
   (`etlantic-spark-connect`) Experimental extras against live isolated
   conformance; promote Databricks/EMR packs only after that evidence.
4. Add secret-provider packs and credential-rotation/outage behavior.
5. Promote connector packs only after state, schema, reliability, effect,
   erasure, and cleanup conformance pass in isolated accounts/projects.
6. Promote notification/escalation, DLQ, and schema-registry packs only after
   live authorization, redaction, retry, outage, and reconciliation evidence.
7. Publish tested recipes, costs/quotas/regions, lifecycle policy, and runbooks.

## Exit Gates

- Every provider pack installs independently, is production-allowlisted
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
- No vendor SDK or managed-runtime dependency enters ETLantic core.

## Required Release Evidence

- Signed distribution and Helm lifecycle report.
- Per-provider support/conformance matrix.
- Workload-identity and credential lifecycle/redaction report.
- Failure, external-effect, and scoped-cleanup campaign.
- Reference deployment reproducibility and recovery transcript.
