# Adoption, Connectivity, and Operations Plan

> **Status: planned first-class feature program; not available in ETLantic
> 0.36.0.** This plan assigns the adoption capabilities that were previously
> scattered across Future design pages to explicit 0.x phases and graduation
> gates.
>
> **Authority:** The
> [main roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md)
> owns release order; this plan owns the shared ecosystem graduation gates.
> Use [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md) for shipped
> behavior and the [Planning Hub](PLAN_INDEX.md) for portfolio status.
>
> **Review trigger:** Update this boundary whenever a program gate passes or
> the main roadmap changes its sequence.

## Decision

ETLantic will treat production connectivity, application-pipeline testing,
metadata interoperability, brownfield migration, GitOps previews, operator
experience, and managed provider integrations as first-class product
capabilities.

These are not convenience add-ons. They are the path from a correct logical
model to a deployable workload in an existing data platform.

“First-class” means each program has:

- an assigned 0.x phase or mandatory multi-phase gate;
- a public boundary with explicit stability status;
- at least one separately installable reference implementation;
- capability-driven conformance and compatibility tests;
- security, redaction, failure, upgrade, and rollback evidence;
- runnable documentation with expected outputs;
- a support and maturity matrix that distinguishes experimental, preview, and
  supported integrations.

The
[main roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md)
is authoritative for ordering. This plan is authoritative for the shared
adoption and ecosystem gates described below.

## Program Map

| Phase | First-class outcome | Claim allowed at exit |
|---|---|---|
| 0.35 | Application-pipeline testing API and fixtures | Public testing preview |
| 0.36–0.37 | Cross-engine and upgrade burn-in for pipeline tests | Stable pipeline-testing foundation |
| 0.38 | Data connectivity and connector SDK | Supported connector protocol and reference set |
| 0.40 | Metadata identity and OpenLineage interoperability | Tenant-aware metadata export preview |
| 0.41–0.43 | GitOps previews, promotion evidence, and graduation | Supported preview-to-production workflow |
| 0.46 | Incremental and CDC source semantics | Supported change-stream contract |
| 0.47 | Kubernetes and managed execution reference providers | Conforming remote execution profiles |
| 0.49 | Brownfield adoption bridges | Supported import/compiler compatibility matrix |
| 0.50 | Operator console | Supported control-plane operations UI |
| 0.51 | Enterprise provider packs | Supported cloud provider matrix |
| 0.52 | TransformationModel incubation | Independently useful modeling package |

No capability in this table is available merely because its phase is planned.
Each claim begins only after the corresponding exit gate passes.

## Product Boundaries

ETLantic owns logical contracts, deterministic plans, capability negotiation,
normalized execution evidence, and provider conformance. It does not become a
warehouse, replication service, scheduler, catalog, identity provider, secret
manager, cluster provisioner, or browser-based data editor.

The following boundaries are mandatory:

- Pipeline definitions retain logical assets. Environment profiles and
  authorized providers own physical endpoints.
- Plans, reports, diagnostics, lineage events, migration reports, and UI state
  never contain resolved secret values.
- Registry, schema-history, catalog, and control-plane records never retain
  arbitrary source rows.
- Production plugin and provider discovery is allowlisted and fails closed
  before importing untrusted entry points.
- Heavyweight or vendor-specific integrations ship as optional distributions;
  they do not become ETLantic core dependencies.
- [ODCS](../03_DATA_CONTRACTS/ODCS.md),
  [DTCS](../04_TRANSFORMATIONS/DTCS.md), and
  [DPCS](../05_PIPELINES/DPCS.md) remain the semantic authorities at their
  respective boundaries.
- Bronze/silver/gold policy remains in Medallantic or SparkForge, never in
  ETLantic core.

## AP — Application-Pipeline Testing { #application-pipeline-testing }

### Outcome

Users can test an ordinary ETLantic pipeline with small, explicit fixtures
without connecting to production systems or implementing a plugin conformance
suite.

This program extends `etlantic.testing`; it does not replace the existing
provider and compiler conformance suites.

### Deliver

- typed pipeline-case and expected-result models with deterministic
  serialization;
- static input fixtures for logical source bindings and expected rows,
  diagnostics, artifacts, quality results, and normalized reports;
- bounded fake source, sink, secret, resource, event, clock, and run-identity
  providers;
- plan, lineage, diagnostic, and report snapshot helpers with explicit update
  workflows;
- selective step and dependency-closure execution for test profiles;
- fault, cancellation, timeout, retry, checkpoint, replay, repair, and
  backfill scenarios using the same normalized runtime evidence as production;
- multi-implementation and cross-engine comparison helpers;
- pytest-native assertions plus JUnit, JSON, and SARIF result adapters;
- fixture redaction and size limits;
- examples that show the expected passing and failing output.

Exact convenience names remain provisional until 0.35 freezes them.

### Gates

The testing foundation graduates at 0.37 only when:

1. A user pipeline can be tested end to end using only public imports.
2. The same eligible case produces equivalent normalized results on Polars,
   Pandas, SQL, and PySpark for their advertised capability intersection.
3. A failed write, cancellation, retry, and unknown external-effect outcome
   can be simulated without a real external system.
4. Snapshot updates are explicit and reviewable rather than automatic.
5. Test artifacts contain neither resolved secrets nor unbounded source rows.
6. The helpers work from an isolated installed wheel and do not import private
   core modules.
7. An independently maintained project uses the public testing API in CI.

## DC — Data Connectivity and Connector SDK { #data-connectivity-and-connector-sdk }

### Outcome

Logical extract and load assets can bind to production storage and warehouse
systems through one capability-driven provider model.

The 0.38 program graduates the storage/source/sink boundary from a design study
into a supported plugin family. It does not put vendor APIs or credentials into
pipeline definitions.

### Deliver

- versioned source, sink, and storage provider protocols with static manifests
  and pre-import trust checks;
- typed, secret-free binding configuration and deterministic plan snapshots;
- capability vocabulary for batch snapshot, partitioned access, incremental
  cursor, predicate/projection pushdown, schema discovery, append, merge,
  replace, atomic publication, transactions, idempotency, reconciliation, and
  cleanup;
- connector development kit with reusable configuration validation,
  checkpoint, retry, pagination, rate-limit, observability, packaging, and
  documentation helpers;
- capability-selected fake and live conformance suites;
- connector maturity levels with measurable promotion and demotion criteria;
- compatibility records covering ETLantic, provider, service API, file/table
  format, and Python versions;
- bounded schema and statistics inspection that never retains source rows;
- at least one independently maintained third-party connector.

### Reference set

The 0.38 exit candidate must include:

- one local reference connector suitable for deterministic CI;
- one S3-compatible object-storage path with Parquet;
- one open table-format path using Iceberg or Delta;
- one cloud warehouse path using Snowflake or BigQuery;
- one relational path proving transaction, rollback, and unknown-outcome
  semantics.

Reference selection is an implementation decision, not permission to make
every listed dependency part of core.

### Gates

1. One logical pipeline runs against a local reference, object storage, and a
   warehouse without changing its authoring model.
2. Unsupported write, transaction, schema, or pushdown semantics fail during
   planning instead of degrading silently.
3. Incremental resume cannot advance a cursor after an uncommitted write.
4. Partial object-store publication cannot appear as a committed dataset.
5. Connector configuration, diagnostics, plans, and reports remain
   secret-free.
6. Production profiles reject unapproved connector packages before import.
7. Live-system tests publish cost, account-isolation, cleanup, and rate-limit
   controls.

## MI — Metadata and Catalog Interoperability { #metadata-and-catalog-interoperability }

### Outcome

ETLantic exports stable design-time and runtime metadata to existing lineage
and catalog systems without becoming a second metadata system of record.

### Deliver

- optional `etlantic-openlineage` provider built on the shipped observability
  protocol;
- stable mappings for pipeline, step, run, attempt, input, output, contract,
  plan, implementation, quality, schema-observation, and artifact identities;
- design-time metadata events for declared lineage and runtime events for
  observed execution;
- facets carrying ETLantic schema versions, fingerprints, capability evidence,
  policy decisions, and normalized backend references;
- documented namespace and identity rules that remain stable across retries,
  promotion, and execution hosts;
- optional outbound adapters or recipes for OpenMetadata and DataHub;
- delivery, retry, buffering, ordering, and duplicate-event semantics;
- reconciliation tooling for mapping or delivery failures.

### Gates

1. A design-time graph and its runtime executions join without heuristic name
   matching.
2. Airflow-compiled, local, and remote runs preserve the same logical ETLantic
   identities.
3. Duplicate or reordered events do not corrupt the receiving lineage graph.
4. Tenant, workspace, environment, and security-domain scope is preserved.
5. Events contain no resolved secrets, source rows, or unrestricted previews.
6. Export is outbound-first; catalog state cannot silently mutate an
   authoritative ETLantic contract or plan.

## GP — GitOps Preview and Promotion Workflow { #gitops-preview-and-promotion-workflow }

### Outcome

A proposed pipeline change can be validated in an isolated workspace,
compared with its base revision, reviewed, and promoted using durable evidence.

### Deliver

- commit- and pull-request-qualified preview workspace identities;
- bounded lifecycle, time-to-live, cleanup, suspension, and quota rules;
- base-versus-candidate contract, graph, plan, policy, cost, schema, and
  environment diffs;
- impacted-subgraph selection and explicitly authorized shadow execution;
- immutable preview evidence linked to source revision, dependency lock,
  profile revision, provider identities, and plan fingerprint;
- approval, separation-of-duty, promotion, rollback, and supersession flows;
- status-check output suitable for CI systems without making ETLantic a source
  control host;
- production promotion that revalidates policy and environment rather than
  trusting preview authorization.

### Gates

1. Preview workspaces cannot read or enumerate another tenant or workspace.
2. Cleanup is idempotent and cannot delete shared or production resources.
3. A passing preview cannot be promoted after its code, plan, policy,
   dependencies, or target environment changes.
4. Shadow runs are visibly non-authoritative and cannot publish production
   effects.
5. Promotion and rollback produce durable, secret-free audit evidence.
6. Fork-origin and untrusted-contributor policies default to no secret or
   production access.

## BA — Brownfield Adoption Bridges { #brownfield-adoption-bridges }

### Outcome

Teams can introduce ETLantic alongside existing dbt and orchestrator projects
with a precise inventory, compatibility report, and incremental migration
path.

### Deliver

- versioned dbt `manifest.json` reader covering models, tests, sources,
  exposures, metrics, groups, selectors, and dependency maps;
- import to an ETLantic migration model with explicit unsupported, lossy, and
  externally owned semantics;
- generated contract and pipeline skeletons that never overwrite user files
  without an explicit target and review;
- semantic diff between source artifacts and generated ETLantic definitions;
- optional Dagster Definitions compiler;
- expanded Prefect compile/deployment adapter distinct from the shipped local
  `ExecutionScheduler` MVP;
- Argo Workflow compiler based on validated plans;
- side-by-side validation and normalized report comparison;
- maintained compatibility fixtures for every supported upstream artifact
  version.

### Gates

1. Importing metadata does not execute arbitrary project Python or Jinja.
2. Unsupported macros, dynamic graph construction, sensors, or platform
   semantics are reported rather than guessed.
3. Generated files have deterministic provenance and reviewable diffs.
4. dbt-owned transformations may remain external while ETLantic imports their
   contracts and lineage.
5. Every compiler rejects a plan whose required semantics it cannot preserve.
6. At least one real project migrates incrementally without a flag-day rewrite.

## OC — Operator Console { #operator-console }

### Outcome

Operators can understand and safely act on the graduated control plane without
assembling raw API calls.

This is Phase 5 of the cross-cutting
[User Interface and Experience Plan](UI_UX_PLAN.md). Its local, read-only
precursor is Phase 3: a generated dashboard and visual comparisons over
durable reports and history.

### Deliver

- a separately deployable web application using a generated, version-pinned
  control-plane client;
- read-only-first views for definitions, revisions, plans, diffs, runs,
  attempts, lineage, partitions, checkpoints, quality, schema drift, repairs,
  backfills, quotas, policies, approvals, audit evidence, providers, and
  deployment health;
- resumable live event views and durable history fallback;
- explicit privileged actions for cancel, retry, replay, repair, approve,
  acknowledge, promote, suspend, and contain;
- bounded, sampled, redacted artifact previews;
- tenant/workspace/environment scope that is visible on every screen;
- accessibility, localization readiness, latency budgets, and large-workspace
  pagination/virtualization;
- operator workflows and screenshots generated from maintained fixtures.

### Gates

1. The console never becomes an independent source of truth.
2. Every mutation uses the same typed API, authorization, idempotency, policy,
   and audit path as non-UI clients.
3. Unauthorized objects do not leak through search, counts, links, errors,
   caches, browser history, or event streams.
4. A browser refresh or reconnect cannot duplicate a privileged action.
5. Preview limits and redaction hold for hostile schemas, logs, and artifacts.
6. Core ETLantic remains installable and usable without frontend dependencies.

## EP — Managed Runtime and Enterprise Provider Packs { #managed-runtime-and-enterprise-provider-packs }

### Outcome

Common cloud environments have maintained, separately installable providers
that pass the same public trust, lifecycle, recovery, and conformance rules as
local implementations.

### Deliver

- reference OCI images and Helm deployment profiles for the control plane and
  execution hosts;
- Kubernetes Job remote-execution provider with workload identity, resource
  limits, cancellation, log/event correlation, cleanup, and terminal-state
  reconciliation;
- managed Spark providers for Databricks, EMR, and Spark Connect with truthful
  capability profiles;
- secret-provider packages for AWS Secrets Manager, Azure Key Vault, Google
  Cloud Secret Manager, and HashiCorp Vault;
- cloud storage and warehouse providers promoted from the 0.38 connector
  program through live production conformance;
- short-lived identity and credential flows where supported;
- Terraform or equivalent deployment recipes only when maintained and tested;
- provider-specific support, deprecation, cost, quota, and regional
  availability matrices.

### Gates

1. Every provider is independently installable and versioned.
2. Workload identity is preferred; static credentials are never serialized
   into plans, reports, deployment manifests, or examples.
3. Secret providers resolve only at authorized runtime boundaries and prove
   redaction, rotation, missing-secret, and outage behavior.
4. Managed execution loss produces a normalized known or unknown external
   effect outcome before retry.
5. Kubernetes cleanup is bounded to provider-owned, fully scoped resources.
6. Live conformance runs use isolated accounts/projects and prove cleanup.
7. No provider-specific type becomes mandatory in ETLantic core.

## Shared Maturity Model

Every new integration publishes one of these levels:

| Level | Required evidence | Supported claim |
|---|---|---|
| Experimental | Basic fixtures; no compatibility promise | Evaluation only |
| Preview | Public protocol; conformance; known limitations; migration notes | Bounded pilots |
| Supported | Live conformance; security review; upgrade/rollback; performance and support envelope | Documented production profile |
| Deprecated | Replacement and removal phase; migration tooling | Existing users during stated window |

A connector or provider cannot self-declare a higher maturity level. Promotion
requires a release record with the applicable gates. Repeated conformance,
security, or compatibility failures may demote an integration.

## Cross-Program Acceptance Scenario

Before the program is considered complete, one maintained scenario must prove:

1. Import a dbt manifest without executing project code.
2. Generate and review ETLantic contract and pipeline skeletons.
3. Test the pipeline with static fixtures and an injected write failure.
4. Bind the same logical assets to a local connector and a supported cloud
   connector.
5. Open a preview workspace, compare the candidate plan with its base, and run
   only the impacted subgraph.
6. Export design and runtime lineage through OpenLineage.
7. Promote the exact approved revision through the multi-tenant control plane.
8. Execute it through a Kubernetes or managed runtime provider.
9. Observe, cancel or repair, and audit the run through the operator console.
10. Verify that all retained evidence is tenant-scoped, bounded, and free of
    resolved secrets and arbitrary source rows.

## Success Measures

Release records must publish measured results rather than aspirational claims:

- median time from installation to a tested local pipeline;
- time and manual edits required to integrate a new connector;
- percentage of connector capabilities covered by conformance fixtures;
- percentage of representative dbt resources imported exactly, lossily, or
  unsupported;
- preview startup and cleanup latency;
- metadata-event delivery lag and reconciliation rate;
- operator-console interaction latency at documented workspace sizes;
- provider upgrade, rollback, cancellation, and cleanup success rates;
- number of independently maintained integrations passing public conformance.

Metrics must not include secret values, source rows, sensitive identifiers, or
cross-tenant aggregates that violate policy.

## Non-Goals

This program will not:

- build a hosted connector marketplace as part of core;
- promise every source, warehouse, orchestrator, catalog, or cloud provider;
- execute arbitrary migration inputs during inspection;
- replace dbt, Airflow, Dagster, Prefect, Argo, OpenLineage, OpenMetadata,
  DataHub, Kubernetes, or a cloud control plane;
- make the operator console a scheduler or a second authorization system;
- grant preview environments implicit production access;
- treat a generated adapter, contract, or migration as approved without human
  review and normal policy gates;
- weaken the stable-foundation compatibility promise to accelerate an
  integration.

## Required Cross-Plan Alignment

- [Multi-Tenant Control Plane Plan](MULTI_TENANT_CONTROL_PLANE_PLAN.md) owns
  tenant isolation, durable preview state, promotion, authorization, and the
  0.43 graduation claim.
- [ETL Reliability and Recovery Plan](ETL_RELIABILITY_PLAN.md) owns normalized
  checkpoint, retry, repair, reconciliation, and unknown-outcome semantics.
- [Schema Drift and Evolution Plan](SCHEMA_DRIFT_PLAN.md) owns observations,
  baselines, acknowledgement, and schema-change impact.
- [TransformationModel Incubation Plan](TRANSFORMATIONMODEL_PLAN.md) owns the
  0.52 package boundary and graduation.
- [Security Model](../02_FOUNDATIONS/SECURITY.md) owns threat-model changes and
  mandatory controls.
- [Dependency Strategy](DEPENDENCY_STRATEGY.md) owns package isolation and
  adopt/wrap/build decisions.

If this plan conflicts with the main roadmap or a domain plan, the documents
must be reconciled in the same change before implementation proceeds.

## Open Decisions

| Decision | Owner role | Due |
|---|---|---|
| Freeze connector protocol split and capability vocabulary | Core + integration maintainers | Before 0.38 schema freeze |
| Select the 0.38 local, object, table-format, warehouse, and relational reference set | Integration maintainers | Before 0.38 implementation freeze |
| Freeze OpenLineage namespace, identity, and facet mappings | Observability + registry maintainers | Before CP2 conformance |
| Define preview workspace lifecycle and untrusted-fork policy | Control-plane + security maintainers | Before CP3 conformance |
| Select supported dbt artifact and orchestrator versions | Migration + orchestration maintainers | Before 0.49 preview |
| Select operator-console frontend architecture and support matrix | API + UI maintainers | Before 0.50 implementation |
| Select supported cloud regions, identity modes, and live-test accounts | Provider + security maintainers | Before 0.51 preview |

Every decision requires an ADR or explicit roadmap decision record,
conformance changes, compatibility impact, and documentation updates.
