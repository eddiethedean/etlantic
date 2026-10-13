---
title: Forward Implementation Plans
description: Shared delivery contract and release sequence for ETLantic 0.39 through 0.66.
plan_status: current
plan_last_reviewed: 2026-10-12
---

# Forward Implementation Plans

This document is the delivery contract for ETLantic phases 0.39 through 0.66.
The [roadmap summary](ROADMAP_SUMMARY.md) defines product intent, while the
phase plans linked below define implementation order, evidence, and exit gates.
Integrated domain plans remain authoritative for cross-release architecture.

## Plan Set

| Phase | Outcome | Implementation plan | Governing domain plan |
|---|---|---|---|
| 0.39 | Control-plane API and identity foundation | [0.39](IMPLEMENTATION_PLAN_0_39.md) | [Multi-tenant control plane](MULTI_TENANT_CONTROL_PLANE_PLAN.md) |
| 0.40 | Tenant registry, workspaces, and persistence | [0.40](IMPLEMENTATION_PLAN_0_40.md) | [Multi-tenant control plane](MULTI_TENANT_CONTROL_PLANE_PLAN.md) |
| 0.41 | Durable submission, state, and reproducibility | [0.41](IMPLEMENTATION_PLAN_0_41.md) | [Multi-tenant control plane](MULTI_TENANT_CONTROL_PLANE_PLAN.md) |
| 0.42 | Policy, delivery objectives, privacy operations, quotas, audit, and supply-chain security | [0.42](IMPLEMENTATION_PLAN_0_42.md) | [Multi-tenant control plane](MULTI_TENANT_CONTROL_PLANE_PLAN.md) + [reliability](ETL_RELIABILITY_PLAN.md) |
| 0.43 | First-class multi-tenant graduation (CP-GA) | [0.43](IMPLEMENTATION_PLAN_0_43.md) | [Multi-tenant control plane](MULTI_TENANT_CONTROL_PLANE_PLAN.md) |
| 0.44 | Developer intelligence, LSP, and IDE surfaces | [0.44](IMPLEMENTATION_PLAN_0_44.md) | [UI/UX](UI_UX_PLAN.md) |
| 0.45 | Planner and optimization SDK | [0.45](IMPLEMENTATION_PLAN_0_45.md) | [Developer roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md) |
| 0.46 | Bounded dynamic control flow, streaming, and event pipelines | [0.46](IMPLEMENTATION_PLAN_0_46.md) | [Reliability](ETL_RELIABILITY_PLAN.md) |
| 0.47 | FastAPI scheduler/runner service and remote execution federation | [0.47](IMPLEMENTATION_PLAN_0_47.md) ([ADR-023](adr/ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md), [exit gate](EXIT_GATE_0_47.md) Met) | [Multi-tenant control plane](MULTI_TENANT_CONTROL_PLANE_PLAN.md) |
| 0.48 | Human-governed AI workflows | [0.48](IMPLEMENTATION_PLAN_0_48.md) ([ADR-024](adr/ADR-024-HUMAN-GOVERNED-AI.md) Accepted, [exit gate](EXIT_GATE_0_48.md) Met) | [Adoption ecosystem](ADOPTION_ECOSYSTEM_PLAN.md) |
| 0.49 | Full optional DuckDB engine package development | [0.49](IMPLEMENTATION_PLAN_0_49.md), [gate](EXIT_GATE_0_49.md), [epic #110](https://github.com/eddiethedean/etlantic/issues/110) | [Developer roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md) |
| 0.50 | Seven-engine baseline portable execution, DuckDB qualification, pushdown conformance, and requirement-level evidence for adaptive planning | [0.50](IMPLEMENTATION_PLAN_0_50.md) ([epic #102](https://github.com/eddiethedean/etlantic/issues/102)) | [Developer roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md) |
| 0.51 | Adaptive Profile, report compatibility, and closed `/2` wire foundation; no adaptive planning or execution | [0.51](IMPLEMENTATION_PLAN_0_51.md) ([ADR-025](adr/ADR-025-ADAPTIVE-EXECUTION-AND-PHYSICAL-DAG.md) accepted; [exit gate](EXIT_GATE_0_51.md) foundation published; [epic #30](https://github.com/eddiethedean/etlantic/issues/30)) | [Developer roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md) |
| 0.52 | Adaptive inventory, candidates, exact placement, physical lowering, and explain/diff | [0.52](IMPLEMENTATION_PLAN_0_52.md) | [0.51 adaptive program contract](IMPLEMENTATION_PLAN_0_51.md) |
| 0.53 | Whole-DAG admission and local adaptive physical execution | [0.53](IMPLEMENTATION_PLAN_0_53.md) | [0.51 adaptive program contract](IMPLEMENTATION_PLAN_0_51.md) |
| 0.54 | Adaptive conformance, qualification, and exact-matrix graduation | [0.54](IMPLEMENTATION_PLAN_0_54.md) | [0.51 adaptive program contract](IMPLEMENTATION_PLAN_0_51.md) |
| 0.55 | Optional data-first authoring with forward and target-guided inference across source, transformation, and target models | [0.55](IMPLEMENTATION_PLAN_0_55.md) | [Portable transformations](PORTABLE_TRANSFORM_PLAN.md) + [schema drift](SCHEMA_DRIFT_PLAN.md) |
| 0.56 | Complete application ETL backend with full specification and run control | [0.56](IMPLEMENTATION_PLAN_0_56.md), [execution](EXECUTION_PLAN_0_56.md), [review](FINDINGS_0_56.md) | [Control plane](MULTI_TENANT_CONTROL_PLANE_PLAN.md) + [adoption ecosystem](ADOPTION_ECOSYSTEM_PLAN.md) |
| 0.57 | Managed backend independence, schedule services, schema inspection, and runtime supervision (#278–#282); release 0.57.0 | [0.57](IMPLEMENTATION_PLAN_0_57.md) | [Control plane](MULTI_TENANT_CONTROL_PLANE_PLAN.md) + [adoption ecosystem](ADOPTION_ECOSYSTEM_PLAN.md) |
| 0.58 | Managed Prefect execution on the durable runtime (#290, #291–#298), direct compatibility, deployments, dispatch, schedules, and recovery qualification | [0.58](IMPLEMENTATION_PLAN_0_58.md) | [Scheduler and Prefect](SCHEDULER_AND_PREFECT_PLAN.md) + [adoption ecosystem](ADOPTION_ECOSYSTEM_PLAN.md) |
| 0.59 | Managed runtime consolidation and trigger contracts | [0.59](IMPLEMENTATION_PLAN_0_59.md) | [Managed runtime consolidation and trigger contracts](ETLANTIC_RUNTIME_PLAN.md) |
| 0.60 | Posit Connect scheduling and HTTPS triggers | [0.60](IMPLEMENTATION_PLAN_0_60.md) | [Posit Connect scheduling and HTTPS triggers](ETLANTIC_RSCONNECT_PLAN.md) |
| 0.61 | AWS scheduling and execution adapters | [0.61](IMPLEMENTATION_PLAN_0_61.md) | [AWS scheduling and execution adapters](ETLANTIC_AWS_PLAN.md) |
| 0.62 | Data Mover integration and optional Posit endpoint discovery | [0.62](IMPLEMENTATION_PLAN_0_62.md) | [Data Mover integration and optional Posit endpoint discovery](ETLANTIC_DATA_MOVER_INTEGRATION_PLAN.md) |
| 0.63 | Brownfield bridges and orchestration compilers; Prefect interoperability consumes 0.58 | [0.63](IMPLEMENTATION_PLAN_0_63.md) | [Adoption ecosystem](ADOPTION_ECOSYSTEM_PLAN.md) |
| 0.64 | Operator console | [0.64](IMPLEMENTATION_PLAN_0_64.md) | [UI/UX](UI_UX_PLAN.md) |
| 0.65 | Managed-runtime and provider packs | [0.65](IMPLEMENTATION_PLAN_0_65.md) | [Adoption ecosystem](ADOPTION_ECOSYSTEM_PLAN.md) |
| 0.66 | TransformationModel incubation | [0.66](IMPLEMENTATION_PLAN_0_66.md) | [TransformationModel](TRANSFORMATIONMODEL_PLAN.md) |

## Accepted Package Scope Contract — 0.59 Onward

The [package consolidation plan](PACKAGE_SCOPE_CONSOLIDATION_PLAN.md) adopts all
F01–F12 findings and the complete 25-package charter. Each phase evidence record
traces its assigned findings to implementation evidence or a documented
conditional/deferred decision; documentation adoption does not close code work.

- 0.59 consolidates existing managed operations/configuration/dispatch and public
  persistence seams before adding missing trigger concepts; runtime packaging is
  conditional on an acyclic extraction with named duplication removed.
- 0.60 qualifies one explicit-URL Connect topology; 0.61 qualifies Scheduler/Lambda
  and ECS/Fargate only, with Batch unscheduled; 0.62 qualifies one Data Mover
  CP1/PostgreSQL/worker host and timer variants individually.
- 0.63 owns targeted qualified engine/helper, existing-client, fixture and driver
  cleanup plus declared compatibility retirements; testing/HTTP wheels need real
  independent use, deleted implementations and fewer owners.
- 0.64 remains an API consumer, 0.65 selects providers by actual adopter demand,
  and 0.66 requires an independent consumer and removal of migrated authoring
  duplication without replicating [DTCS](../04_TRANSFORMATIONS/DTCS.md) authority.

Before a new wheel, record its user/authority/delegated owners and justify it by
consolidation, dependency isolation, or a real independent consumer. Consolidation
and extraction proposals also record named code/API retirement and a compatibility
window. Preserve core embedded imports and vendor/engine isolation; reject
helper-only wrapper splits.
Every release publishes one bounded reference deployment and unsupported
combinations rather than assuming a full timer/executor/host matrix. Broader
support needs evidence and an explicit scope update. Correct factory identity,
distribution metadata and support ranges before claiming more live adapters.

## Authority And Change Control

- The roadmap owns phase outcome and scope.
- The integrated domain plan owns architecture that spans releases.
- The phase implementation plan owns sequencing, acceptance evidence, and the
  release decision for that phase.
- If documents conflict, implementation pauses until the roadmap and governing
  domain plan are reconciled. A phase plan must not silently narrow a security,
  isolation, compatibility, or durability requirement.
- Additions to a phase must update its prerequisites, workstreams, gates,
  evidence matrix, and downstream dependency notes together.

## Shared Entry Criteria

A phase may begin only when:

1. The prior phase has a recorded release decision and no unresolved blocker
   required by the new phase.
2. Public contracts needed by the work have an owner and compatibility policy.
3. Optional package boundaries and extras are named before dependencies land.
4. Security, tenancy, persistence, and external-effect threat boundaries are
   reviewed when the phase touches them.
5. Test fixtures can be built without production credentials or source rows.

## Shared Definition Of Done

Every phase must produce:

1. Implemented public contracts with type checking and compatibility tests.
2. Unit, integration, conformance, and failure-path coverage proportional to the
   capability, including multi-process or multi-tenant tests where applicable.
3. Stable machine-readable diagnostics with redaction tests.
4. Documentation, examples, upgrade notes, and an explicit supported versus
   experimental capability table.
5. Benchmarks or service-level evidence for any stated performance claim.
6. A release evidence record mapping every exit gate to a reproducible command,
   artifact, or reviewed decision.
7. No unresolved critical or high-severity security, data-loss, isolation, or
   compatibility finding within the phase scope.

## Cross-Phase Invariants

- No secret value or source row is stored in a plan, report, contract, schema
  history, audit record, prompt bundle, or documentation fixture.
- Production plugin execution remains allowlist-based and fails closed.
- Stable CLI and SDK surfaces remain the integration boundary; optional systems
  do not become required core dependencies.
- Accepted durable work is never implemented as process-local background work.
- Schema observation is distinct from schema authority and contract mutation.
- Remote, streaming, preview, AI, UI, and provider surfaces cannot grant more
  authority than the underlying API and policy decision.
- Dynamic expansion and branching are explicit, bounded, replayable plan
  semantics; arbitrary runtime Python control flow never acquires implicit
  planning or execution authority.
- Delivery-objective, notification, dead-letter, schema-registry, and erasure
  evidence contains identifiers and bounded metadata only—never resolved
  secrets, subject values, or source/event payloads.
- Medallion bronze/silver/gold abstractions stay outside ETLantic core.

## Release Evidence Layout

Each release evidence record should contain:

- scope and supported/experimental matrix;
- gate-to-test traceability;
- compatibility and migration results;
- performance and failure-injection results where relevant;
- security and redaction review;
- known limitations and deferred work;
- final go/no-go decision with owners and date.
