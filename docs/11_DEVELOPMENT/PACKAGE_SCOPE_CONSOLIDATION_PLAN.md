---
title: Package Scope Consolidation Plan
description: Accepted package scope recommendations, ownership charters, phased delivery, and evidence gates.
plan_status: current
plan_last_reviewed: 2026-10-12
---

# Package Scope Consolidation Plan

**Status: recommendations accepted; 0.59 implementation in progress, with
qualification and later-phase work pending.**
This plan integrates all findings and package decisions from the
[2026-10-12 review](PACKAGE_SCOPE_REVIEW_2026-10-12.md). It governs consolidation
across phases 0.59–0.66. It does not change current package availability,
published versions, or historical qualification evidence.

Consolidate managed implementation before adding platform adapters. Preserve
engine and vendor dependency isolation, durable admission, authorization,
idempotency, fencing, and effect reconciliation. Simplification removes duplicate
owners, settings, and deployment combinations; it does not remove these guarantees.

## Findings To Delivery

Every finding has an owning workstream and evidence requirement. A recommendation
is not closed by this documentation change; release evidence must record its
implementation or its explicit conditional decision.

| Finding | Delivery / accountable maintainers | Owning plans | Completion evidence |
|---|---|---|---|
| F01: fragmented managed runtime | 0.59 059-B/M/T; runtime + backend | [Runtime](ETLANTIC_RUNTIME_PLAN.md), [0.59](IMPLEMENTATION_PLAN_0_59.md) | Before/after operation ownership; named implementation moved and duplicate API retired; installed headless/HTTP/Prefect parity, restart and effects |
| F02: Prefect-specific shared dispatch | 0.59 059-G; second backend proof in 0.61 061-D; runtime + Prefect + persistence | [Scheduler/Prefect](SCHEDULER_AND_PREFECT_PLAN.md), [AWS](ETLANTIC_AWS_PLAN.md) | Validated backend kind, immutable binding, opaque remote-run ID; accepted Prefect work survives upgrade/rollback; ECS uses the same operations without AWS fields in core |
| F03: duplicate backend configuration | 0.59 059-F; FastAPI + SQLModel | [FastAPI](FASTAPI_INTEGRATION_PLAN.md), [SQLModel](SQLMODEL_INTEGRATION_PLAN.md) | One default/validator for all 25 shared fields; checked legacy translation; explicit headless install without FastAPI; existing HTTP install migration |
| F04: persistence private coupling / broad root | 0.59 059-P; persistence + runtime | [SQLModel](SQLMODEL_INTEGRATION_PLAN.md) | Public modeling/stores/schema/managed namespaces and compatible exports; complete versioned codec/transition boundary; recovery conformance and measured contention before any storage redesign |
| F05: concrete Polars logic in core | 0.63 063-C; core runtime + Polars | [Portable transforms](PORTABLE_TRANSFORM_PLAN.md), [interchange](INTEROPERABILITY_FOUNDATION_PLAN.md) | One qualified plugin capability; no concrete engine imports at that seam; unchanged qualified/rejected fusion matrix |
| F06: fake-only release units | Classify/freeze in 0.59 059-V; organize in 0.63 063-F; testing + provider + release | [Testing](TESTING.md), [adoption](ADOPTION_ECOSYSTEM_PLAN.md) | Shared fakes first in existing testing modules; entry-point/identity migration; no fixture-driven production discovery; fewer release owners after retirement |
| F07: misleading fake/live identity | 0.59 059-V before adapter expansion; provider + qualification | [0.59](IMPLEMENTATION_PLAN_0_59.md), [adoption](ADOPTION_ECOSYSTEM_PLAN.md) | SDK present/absent × requested fake/live × actual backend; truthful Iceberg/Snowflake/S3 identity; unavailable live requests fail explicitly |
| F08: identical compiler helpers | 0.63 063-C; compiler + [DTCS](../04_TRANSFORMATIONS/DTCS.md) integration | [Portable transforms](PORTABLE_TRANSFORM_PLAN.md) | One public helper implementation after DTCS authority check; unchanged engine conformance; engine-specific semantics remain separate |
| F09: fragmented HTTP policy | Policy baseline in 0.59 059-A; consume in 0.60/0.61; existing-client alignment in 0.63 063-H; security + adapter | [Dependency strategy](DEPENDENCY_STRATEGY.md), [Connect](ETLANTIC_RSCONNECT_PLAN.md), [adoption](ADOPTION_ECOSYSTEM_PLAN.md) | Existing outbound policy/conformance shared; destination/redirect/timeout/byte/redaction parity; real DNS/connect tests and explicit trusted private deployment support |
| F10: dependency breadth / support mismatch | Range policy in 0.59 059-V; PostgreSQL extra and install measurements in 0.63 063-P; packaging + SQL | [Dependency strategy](DEPENDENCY_STRATEGY.md), [release process](RELEASE_PROCESS.md) | Resolver matrix matches qualified minor line; SQLite-only install avoids psycopg after documented migration; CLI split requires measured benefit |
| F11: version and sunset drift | Single version source / declared sunset in 0.59 059-V; final SparkForge compatibility release 0.62.0; routine retirement in 0.63 after migration evidence; release + provider | [Release process](RELEASE_PROCESS.md), [deprecation policy](DEPRECATION_POLICY.md) | Factory/installed metadata agree; protocol and distribution versions distinct; visible warnings through 0.62, tested migration, then routine release removal |
| F12: excessive initial platform matrix | 0.59–0.62 phase owners; runtime + Connect + AWS + application | [0.59](IMPLEMENTATION_PLAN_0_59.md), [0.60](IMPLEMENTATION_PLAN_0_60.md), [0.61](IMPLEMENTATION_PLAN_0_61.md), [0.62](IMPLEMENTATION_PLAN_0_62.md) | Consolidation first; one explicit-URL Connect topology; Scheduler/Lambda plus ECS/Fargate only; one Data Mover host; Batch demand-gated and unscheduled |

## Sequence And Scope Control

1. **0.59:** correct backend identity/version claims, canonicalize configuration,
   map existing operations, generalize dispatch with compatibility, then extract
   only shared managed implementation through public seams. Characterize the
   persistence codec before changing its consumer. Add only missing timer/HTTP
   concepts and reuse existing authoritative value models.
2. **0.60:** prove one explicit-URL Connect trigger topology using the shared
   policy and minimal wire contract. Generated content must not carry the full
   ETL engine/provider environment.
3. **0.61:** prove schedule-only Scheduler → scoped Lambda → HTTPS delivery and
   one executor, ECS/Fargate. Reuse generic dispatch; qualify it independently
   from scheduling. Batch has no assigned release or exit gate until a concrete
   workload justifies a reviewed scope decision.
4. **0.62:** qualify one Data Mover CP1/SQLModel/PostgreSQL host composition,
   one pinned executor, and timer variants individually. Optional public URL
   discovery adds no new package. Do not promise every timer × executor × host
   combination.
5. **0.63:** alongside bounded brownfield adoption, move qualified engine details
   and identical helpers to their owners, align existing HTTP clients, organize
   test fakes, modularize Foundry/SQL internally, and implement the driver extra.
   Remove compatibility release units only after their recorded windows. A
   testing wheel is a conditional decision after module organization and a real
   independent consumer prove replacement value.
6. **0.64–0.66:** keep the console a separate API consumer, select enterprise
   providers by actual demand and live evidence, and incubate TransformationModel
   only with an independent consumer and removal of migrated duplication.

Deliver these as separate reviewable changes. Do not combine runtime extraction,
persistence layout redesign, engine support expansion, and cloud qualification
in one change. Each phase records its exact reference deployment and unsupported
combinations; broadening a matrix requires additional evidence and a scope update.

## Charter For Every Existing Distribution

Each charter identifies the user's capability, its authority, and what it
delegates. Current qualification limits continue to apply.

| Distribution | Charter and accepted action |
|---|---|
| `etlantic` | Authors, contracts, deterministic plans, public protocols, embedded DAG execution and shared policy; delegate managed orchestration implementation conditionally to runtime and concrete engine work to plugins. Do not split every namespace. |
| `etlantic-airflow` | Compiles valid plans into Airflow artifacts; preserve fail-closed operator behavior outside explicit demo-stub mode and delegate ETL execution. No managed-runtime claim. |
| `etlantic-datafusion` | Owns the DataFusion engine/compiler/native dependency and Arrow boundary; retain its qualified/provisional matrix. |
| `etlantic-duckdb` | Owns DuckDB connection lifetime, compiler/dialect, native handles and access policy; reuse small helpers while retaining engine isolation. |
| `etlantic-fastapi` | Owns HTTP routing, request identity, schemas, event streaming and authorized projections; adapts an existing backend and delegates worker configuration/authority. Preserve the reference-demo boundary. |
| `etlantic-foundry` | Owns Foundry datasets/files/transactions and provider actions; split transport/codecs/connectors internally and share outbound policy, without source/sink/action wheels. |
| `etlantic-iceberg` | Owns catalog/snapshot adapter semantics; fix actual fake identity and reuse fixtures before any live claim. SDK installation is not qualification. |
| `etlantic-k8s` | Reference/test provider until live Kubernetes qualification; freeze fixture-only feature growth, share fakes, and preserve a separate future live SDK boundary. |
| `etlantic-kafka` | Owns Kafka source/sink, transactions and offsets; current fake is a reference fixture. Do not merge with registry or all streaming services. |
| `etlantic-keyring` | Isolates OS/keyring credential resolution through the existing secret protocol; its small size is justified and it remains optional. |
| `etlantic-lsp` | Thin editor/LSP/pygls host over shared analysis; no second IDE analysis authority or broad platform package. |
| `etlantic-mcp` | Current read-only in-process reference fake; freeze/consolidate fixtures until a real transport/host is qualified, delegating analysis and authorization. |
| `etlantic-openlineage` | Maps/exports outbound lineage with injected transport; registry and orchestration authority remain elsewhere. |
| `etlantic-pandas` | Owns eager/index-neutral execution and compiler semantics; share only identical helpers. |
| `etlantic-polars` | Owns lazy/compiler, qualified fusion execution/inspection and Parquet snapshots; absorb matching core vendor logic without widening support. |
| `etlantic-prefect` | Keeps direct and managed modes in one vendor wheel; owns API/state translation and deployment validation over shared generic dispatch. No managed-only companion wheel. |
| `etlantic-pyspark` | Owns Spark realization/compiler/local provider with optional Delta; remote-session provider remains a distinct dependency boundary. |
| `etlantic-s3` | Owns S3-compatible source/sink/storage independently of AWS orchestration; audit fake selection and preserve truthful maturity. |
| `etlantic-schemaregistry` | Owns read-only registry transport separately from Kafka; use shared outbound policy and never acquire mutation authority. |
| `etlantic-snowflake` | Owns native Snowflake connector semantics separately from generic SQL; fix actual backend identity and live rejection before promotion. |
| `etlantic-spark-connect` | Reference/test remote-session provider until live qualification; share fixtures/freeze while preserving separation from PySpark realization. |
| `etlantic-sparkforge` | Compatibility redirect only; no feature work. Declare a final version/window and stop routine releases after migration, preserving historic wheels and old installations. |
| `etlantic-sql` | Owns the shared SQLAlchemy execution/compiler/PostgreSQL action/target stack; modularize internally and migrate psycopg to an explicit extra. No immediate PostgreSQL wheel. |
| `etlantic-sqlmodel` | Owns relational models/stores/schema/migrations and persistence composition; separate public namespaces and consume one public codec/transition boundary rather than private dictionaries. |
| `medallantic` | Owns medallion facade, authoring and migration outside core; relocate domain-specific test campaigns to its repository test area during testing consolidation. |

## New Package Decision Gates

“Conditional” requires evidence before a distribution is created. Decisions
below do not reserve additional release phases.

| Candidate | Accepted decision | Evidence required to reconsider or create |
|---|---|---|
| `etlantic-runtime` | Conditional extraction in 0.59 | Named role construction/supervision, dispatch coordination, accepted-reference/reconciliation implementation moves; duplicate API retirement; public acyclic runtime → core dependency, injected stores/platform ops, no mandatory reverse dependency. If impossible, refactor namespaces and defer the wheel. |
| `etlantic-testing` | Conditional after module organization in 0.63 | Independent third-party conformance consumer, public testing migration, reusable fakes/fault injection, no production discovery, fewer maintained release units after compatibility retirement. Repository campaigns stay in the repository. |
| `etlantic-http` | Conditional after policy/client consolidation | Two real adapters adopt one optional client implementation and remove duplicate transport code. URL helper sharing alone is insufficient; provider auth, pagination, effect-aware retries and error mapping stay adapters. |
| `etlantic-persistence` | Defer | A second concrete persistence implementation shares actual implementation; namespaces and public codec come first. |
| `etlantic-connectors`, `etlantic-compiler-base` | Do not add now | Existing connector/compiler namespaces suffice; small helpers do not justify new protocols or wheels. |
| `etlantic-contracts` | Do not add now | A real independent lightweight consumer and acyclic extraction must justify replacing ownership; retain core and normative [DTCS](../04_TRANSFORMATIONS/DTCS.md)/[DPCS](../05_PIPELINES/DPCS.md)/ContractModel authority. |
| `etlantic-postgresql`, `etlantic-cli` | Defer | Try extras/internal modules first; measure SDK install/startup or independent release demand before splitting. |
| `etlantic-rsconnect` | Keep narrow, 0.60 | Connect deployment/scheduling/delivery only; no FastAPI dependency, discovery authority or ETL execution. |
| `etlantic-aws` | Keep narrow, 0.61 | Scheduler/relay and ECS/Fargate over shared dispatch; no S3, secret-manager or general infrastructure ownership. Batch is demand-gated. |
| `etlantic-fastapi-posit` | Do not add | Small optional consumer adapter using verified `fastapi-posit` public API; explicit URL fallback. |
| Dagster / Argo adapters | Demand-gated, 0.63 | A real adoption project, isolated vendor/artifact boundary and fidelity-preserving valid-plan compilation; no runtime clone. |
| AWS / Azure / GCP / Vault secret adapters | Optional and demand-gated, 0.65 | Concrete consumer, separate SDK/identity boundary, existing secret protocol and live/redaction qualification; no all-vendor default bundle. |
| `transformationmodel` | Conditional incubation, 0.66 | Independent consumer and named authoring duplication deleted; no second DTCS parser, canonicalizer or normative validator. |
| Operator console | Separate deployment, 0.64 | Authorized API projections only; no backend state or provider control implementation. |
| Data Mover package inside core | Do not add | Product remains a consumer; reusable code has shared runtime/HTTP ownership. |
| `etlantic-quarto` | Do not create or plan | Explicit user constraint. External platform tooling creates no ETLantic package requirement. |

## Rules For Future Scope Changes

- Every package proposal states one sentence for its user, authority and
  delegated owners, and justifies the wheel by existing responsibilities/code
  it removes, a dependency it isolates, or a real independent consumer it
  enables. Consolidation and extraction proposals additionally name the code/API
  retirement and compatibility window. A wrapper that leaves duplicate owners
  in place does not pass.
- Reuse existing public modules or extras for small helpers and driver choices.
  Keep one authoritative model/transition implementation. External timer
  scheduling and ready-node `ExecutionScheduler` are different responsibilities.
- Keep schedule occurrence, dispatch, execution attempt, external effect and
  publication distinct in contracts and evidence.
- Use focused import, shared configuration and vendor-field boundary checks;
  do not impose arbitrary line caps or ban all optional imports indiscriminately.
- Factory metadata distinguishes instantiated implementation, live capability,
  qualification and distribution/protocol versions. Live claims require the
  actual backend, not an installed SDK or a fixture.

## Release Evidence And Review Trigger

The phase evidence index links each F01–F12 row to reproducible evidence,
maintainer decisions and remaining conditional work. Update this plan and owning
plans together when a package charter, migration window or qualified topology
changes. Review before creating a wheel, promoting a fake-backed provider,
changing a dependency range, retiring an entry point, or adding another executor.
The [shared forward delivery contract](FORWARD_IMPLEMENTATION_PLANS.md) applies.
