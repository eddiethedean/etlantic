---
title: ETLantic Package Scope Review — 2026-10-12
description: Evidence-based review of all workspace distributions, shared responsibilities, and package simplification opportunities.
plan_status: review
plan_last_reviewed: 2026-10-12
---

# ETLantic Package Scope Review — 2026-10-12

## Recommendation

**Consolidate managed-runtime ownership before adding more adapters. Keep the
engine and vendor boundaries, and avoid creating packages for small shared
helpers.** The strongest signs of scope creep are in core and application
composition, rather than in every optional integration.

The existing separation of heavy engine dependencies, provider credentials,
HTTP hosting, and medallion vocabulary is useful. Preserve it. Durability,
authorization, idempotency, fencing, and effect reconciliation are necessary
complexity for the promised managed service; removing those mechanisms would
not be a safe simplification. Reduce the number of implementations,
configuration surfaces, and advertised deployment combinations instead.

Recommended decisions:

1. Recast planned `etlantic-runtime` as the single owner of shared **managed
   execution implementation**, with a staged extraction and compatibility plan.
   Do not add another set of run, schedule, receipt, and result authorities.
2. Keep FastAPI as an HTTP adapter, SQLModel as the relational persistence
   provider, and Prefect/Connect/AWS as platform adapters. Centralize duplicated
   backend settings and generalize existing dispatch contracts before AWS work.
3. Consider `etlantic-testing` as a later consolidation of conformance tooling
   and reference fakes. Start by organizing existing modules; do not launch a
   new distribution until it can replace existing ownership and packaging work.
4. Narrow the first AWS delivery to scheduling plus one execution backend.
   Preserve separate Connect/FastAPI packages and optional `fastapi-posit` use.
5. Fix misleading capability/version metadata and close the deprecated
   SparkForge redirect lifecycle before increasing the package count.

The recommendations are accepted into the
[package consolidation plan](PACKAGE_SCOPE_CONSOLIDATION_PLAN.md) and owning
0.59–0.66 roadmap/domain plans. Implementation remains pending: planning changes
do not refactor code or retire installed packages. The observations below retain
the original review baseline. `etlantic-quarto` does not
exist and must not be created or planned.

## Coverage And Confidence

Reviewed **all 25 workspace distributions**: core `etlantic`, 23
`etlantic-*` companions, and `medallantic`. The inventory includes all manifests,
package READMEs, entry points, dependencies/extras, and AST imports across all
604 Python source files. Targeted source reading covers public factories,
compiler helpers, runtime and persistence boundaries, adapter composition,
fake/live selection, and the newly planned packages.

Baseline: Git `d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6`, plus the working-tree
0.59–0.66 planning changes. Source links below use that immutable Git revision.
The [machine-readable inventory](PACKAGE_SCOPE_INVENTORY_2026-10-12.json)
records every package, dependencies, module sizes, import locations, and source
hashes. Counts are physical Python lines including blanks, comments, and
docstrings; they exclude tests, documentation, and non-Python assets. They are
triage signals, not measures of defects or runtime cost.

| Measurement | Observation |
|---|---:|
| Total Python source | 187,000 lines |
| Core distribution | 136,533 lines; 73.0% of total |
| Core runtime / control plane / application services | 20,188 / 17,952 / 6,409 lines |
| Core inference / testing | 15,325 / 8,589 lines |
| FastAPI / SQLModel / SQL packages | 6,604 / 9,073 / 9,268 lines |
| K8s + Spark Connect + Kafka + MCP reference distributions | 684 lines combined |

This is a portfolio architecture review, not an exhaustive line-by-line bug or
security audit. No live cloud, Connect, broker, database-service, or production
load campaign was run. Import observations include lazy and type-checking
imports; they do not imply dependencies load during ordinary core import.

## Findings

Priority is implementation order: **P1** before expanding the affected platform
surface; **P2** during the next simplification pass; **P3** a conditional future
improvement. It is not a claim that every finding is a production incident.

### F01 — P1: Managed execution has too many places to grow

**Observed.** Core already owns `ManagedBackend`, `ManagedApplicationService`,
`ExecutionHost`, `ManagedExecutionAdapter`, `SchedulerService`, schedule records,
dispatch records, and durable stores. SQLModel constructs the shared service
graph; FastAPI wraps it; Prefect supplies deployment/dispatch/worker integration.
The new runtime plan proposes another package of schedule, trigger,
accepted-reference, and result interfaces. See [core backend](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/src/etlantic/control_plane/managed_backend.py#L59),
[application service](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/src/etlantic/service/managed.py#L182),
[managed execution](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/src/etlantic/runtime/managed_execution.py#L250), and
[the proposed runtime scope](ETLANTIC_RUNTIME_PLAN.md#ownership-and-dependencies).

**Risk.** A contracts-only wrapper could leave all current ownership in place
while adding another API vocabulary and compatibility layer. Every new adapter
would then need to decide which of several similar contracts is authoritative.
This is a planning risk; that new package has not been implemented.

**Recommendation.** Make 0.59 a consolidation gate. Map each proposed type and
operation to its existing owner first. Retain existing value contracts where
possible; add only the missing external timer/HTTP-delivery concepts. Extract
shared managed role construction, supervision, dispatch coordination, and
reconciliation into `etlantic-runtime` only through public seams. Embedded
pipeline execution stays in core. Do not move the whole `runtime/` directory.

**Done when.** There is one implementation for each managed operation, a
before/after ownership map, no new parallel state machine, and installed
headless/HTTP/Prefect parity plus restart/effect-recovery tests still pass.

### F02 — P1: Prefect-specific dispatch details leak into shared core

**Observed.** Core's route pattern accepts only `local` or `prefect:<sha256>`;
`DispatchRecord` and reconciliation records contain `prefect_flow_run_id`.
Durable protocols, memory storage, SQLModel storage, and the application service
carry that naming and behavior. The service exposes
`rearm_exhausted_prefect_dispatch`. See [route and dispatch models](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/src/etlantic/control_plane/durable_models.py#L58),
[durable protocol](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/src/etlantic/control_plane/durable_protocols.py#L231),
[route handling](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/src/etlantic/control_plane/durable_memory.py#L648), and
[service operation](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/src/etlantic/service/managed.py#L651).

**Assessment.** This is understandable in the deliberately bounded 0.58
qualification. It is now a concrete obstacle to reusing that machinery for AWS.
The absence of a Prefect SDK import in core does not make these contracts
provider-neutral.

**Recommendation.** Evolve existing dispatch records toward a validated backend
kind, immutable deployment binding, and opaque remote-run ID. Keep vendor API
calls, remote-state translation, and deployment validation in the adapter.
Use a versioned migration and compatibility decoder for accepted Prefect work;
do not loosen the route regex to arbitrary caller-controlled strings or invent
one record/store family per vendor.

**Done when.** Existing Prefect work survives upgrade/rollback and the same
dispatch operations serve a second concrete adapter without AWS-specific fields
in core. Unknown backend kinds still fail before effects.

### F03 — P1: Backend configuration is duplicated at the HTTP boundary

**Observed.** `ManagedBackendConfig` in FastAPI and `SQLModelBackendConfig` share
**25 fields**; FastAPI adds only `title` and `version`. Both perform configuration
validation, followed by a field-by-field conversion. FastAPI also wraps the core
backend and checks configuration changes. The root `managed` extra installs
`etlantic-fastapi[managed]`, although a headless SQLModel constructor exists.
See [FastAPI configuration](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/packages/etlantic-fastapi/src/etlantic_fastapi/managed.py#L90),
[provider configuration](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/packages/etlantic-sqlmodel/src/etlantic_sqlmodel/managed.py#L41),
[conversion and adaptation](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/packages/etlantic-fastapi/src/etlantic_fastapi/managed.py#L505),
and [root extras](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/pyproject.toml#L48).

**Recommendation.** Prefer `adapt_managed_backend(existing_backend, ...)` as
the canonical HTTP path. Use the provider configuration directly plus separate
HTTP settings. Keep the old constructor as a compatibility adapter whose
translation is checked against the canonical schema. Add an explicit headless
installation recipe/extra; migrate the ambiguous `managed` extra deliberately
rather than removing HTTP dependencies from existing users silently.

**Done when.** Each shared setting has one default and validator, HTTP settings
cannot configure worker behavior independently, and headless installation does
not require FastAPI. Existing HTTP/headless parity tests remain mandatory.

### F04 — P2: SQLModel combines model conversion with a full persistence backend

**Observed.** Of 9,073 lines, 6,390 are control-plane stores and 1,382 are
migrations. The root module exports both contract conversion and the backend,
stores, migrations, and schema inspector. Durable persistence serializes private
`MemoryDurableWorkStore` fields and reloads them before applying shared semantics.
See [public exports](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/packages/etlantic-sqlmodel/src/etlantic_sqlmodel/__init__.py#L1)
and [snapshot persistence](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/packages/etlantic-sqlmodel/src/etlantic_sqlmodel/control_plane/durable_stores.py#L89).

**Assessment.** Sharing transitions with the memory reference is valuable; do
not replace it with two independently implemented state machines. The problem
is implicit coupling to another package's private representation and the broad
root import surface. Snapshot-per-mutation design is also a potential scaling
constraint, but this review did not measure contention or prove a bottleneck.

**Recommendation.** Keep one distribution for now. Separate public
`modeling`, `stores`, `schema`, and `managed` namespaces; retain old imports as
compatibility exports. Give persistence a versioned public snapshot codec or
transition boundary. Compare existing `dump/load` coverage before reusing it;
do not assume it includes every SQLModel-persisted entity. Benchmark realistic
concurrent workloads before redesigning storage layout.

**Done when.** SQLModel no longer serializes core private dictionaries directly,
schema inspection remains read-only, and store conformance/recovery tests cover
the shared transition boundary. A new `etlantic-persistence` package is deferred
until a second persistence implementation needs the same implementation.

### F05 — P2: Engine-specific fusion logic lives inside core execution

**Observed.** Core `fused_execution.py` imports Polars exceptions and
`etlantic_polars` fusion/storage helpers. Adaptive admission imports Polars
classes and checks exact implementation types and installed versions.
See [fused execution](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/src/etlantic/runtime/fused_execution.py#L45) and
[admission checks](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/src/etlantic/runtime/adaptive_admission.py#L660).

**Assessment.** These are intentional restrictions for one qualified fusion
shape, not evidence that ordinary `import etlantic` requires Polars. Removing
the checks would broaden support without evidence. However, repeating this
pattern for every engine would make core the owner of vendor execution details.

**Recommendation.** Move Polars-specific execution and inspection behind one
qualified plugin capability. Keep core responsible for admission, trust,
fingerprints, scope, and lifecycle. Preserve the exact current support matrix
and rejection behavior during the move. No new engine-base package is needed.

**Done when.** Core calls a validated provider capability without importing a
concrete engine class, and existing qualified/rejected fusion cases are unchanged.

### F06 — P2: Small fake-only distributions create maintenance surface

**Observed.** The registered K8s, Spark Connect, Kafka, and MCP factories return
in-process fakes. K8s and Spark Connect reject their opted-in live paths; MCP
has no actual SDK/stdio host. These four distributions total 684 source lines.
See [K8s](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/packages/etlantic-k8s/src/etlantic_k8s/provider.py#L1),
[Spark Connect](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/packages/etlantic-spark-connect/src/etlantic_spark_connect/provider.py#L1),
[Kafka](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/packages/etlantic-kafka/src/etlantic_kafka/connectors.py#L50), and
[MCP](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/packages/etlantic-mcp/src/etlantic_mcp/server.py#L79).

**Recommendation.** Classify them as reference/test artifacts until an actual
integration is qualified. Consolidate reusable fakes under `etlantic.testing`
first, or eventually `etlantic-testing`; keep short-lived compatibility packages
where published entry points must survive. Do not silently replace existing
provider identities or make importing test fixtures register production plugins.
Keep separate vendor distributions when they gain real transports/SDKs.

**Done when.** A user can distinguish a working integration from a contract
example before installation, and any consolidation reduces maintained release
units after compatibility retirement rather than adding a permanent wrapper.

### F07 — P1: Fake/live metadata is not always tied to the implementation

**Observed and reproduced.** Iceberg factories still construct
`FakeIcebergCatalog`, and Snowflake factories construct
`FakeSnowflakeConnection`. Their metadata uses SDK availability to decide the
`fake` flag. In a controlled local probe that made the availability predicate
return true, both still used fake backends while reporting `fake: false`.
See [Iceberg selection](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/packages/etlantic-iceberg/src/etlantic_iceberg/connectors.py#L86)
and [Snowflake selection](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/packages/etlantic-snowflake/src/etlantic_snowflake/connectors.py#L89).

**Recommendation.** Report implementation identity, live capability, and
qualification separately. Derive fake/live identity from the instantiated
backend, never merely an importable SDK. Fail explicitly when an unimplemented
live backend is requested. Apply the same check to S3's `force_fake` flag and
all future adapter factories.

**Done when.** SDK present/absent × fake/live requested × actual backend cases
produce truthful metadata. This is a concrete correctness issue, separate from
the architectural preference to consolidate test packages.

### F08 — P2: Several compiler helpers are copied, but engine packages should stay separate

**Observed.** An AST comparison, ignoring locations and leading docstrings,
found identical function bodies for `_parameter_names` in Pandas/Polars/PySpark;
`unwrap_literal_value` in those three; `constant_python` in those three plus
SQL; and `normalize_output` in Pandas/Polars. See
[parameter walk](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/packages/etlantic-pandas/src/etlantic_pandas/compiler.py#L389),
[literal helpers](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/packages/etlantic-polars/src/etlantic_polars/lowering/expr.py#L37),
and [output normalization](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/packages/etlantic-pandas/src/etlantic_pandas/__init__.py#L193).

**Recommendation.** Move these small, behaviorally identical utilities into
existing public `etlantic.transform` / `etlantic.dataframe.helpers` modules,
checking [DTCS](../04_TRANSFORMATIONS/DTCS.md) ownership first. Keep null, type, timezone, aggregation, dialect,
and lazy/eager semantics in each engine compiler. Do not build a universal
compiler superclass or merge engine distributions to save a few helper functions.

**Done when.** Identical helpers have one implementation and engine conformance
remains unchanged. This review found targeted duplication, not wholesale proof
that the compilers are redundant.

### F09 — P2: Shared HTTP policy exists, but transport adapters enforce their own subsets

**Observed.** Core provides `OutboundPolicy` and URL/DNS policy evaluation.
Foundry implements a separate HTTPX2 client with its own URL/timeout/redirect
rules; the schema registry uses urllib with its own host allowlist and byte
budget. Neither source file references core outbound policy. New Connect/AWS
delivery would add more clients. See [shared policy](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/src/etlantic/outbound.py#L41),
[Foundry client](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/packages/etlantic-foundry/src/etlantic_foundry/connectors.py#L319),
and [registry client](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/packages/etlantic-schemaregistry/src/etlantic_schemaregistry/http.py#L23).

**Recommendation.** Consolidate policy application and conformance, starting
with the existing outbound module. Keep provider auth, request construction,
pagination, effect-aware retry decisions, and error translation in adapters.
A narrowly scoped `etlantic-http` is a conditional option if a shared optional
HTTP client implementation is adopted by at least two real consumers; it is
not needed merely to share URL validators.

**Done when.** Existing clients agree on configured destinations, redirects,
timeouts, byte limits and redaction, while preserving explicit trusted private
deployment support. Verify DNS/connect behavior end to end: invoking a URL
validator alone is not proof against rebinding. This finding is policy
fragmentation, not a claim of a demonstrated exploit.

### F10 — P2: Some dependency and release surfaces are broader than their stated use

**Observed.** `etlantic-sql` installs psycopg even for SQLite-only use. Core
installs Typer/Click even for SDK-only consumers. First-party requirements mostly
allow any later core release (`etlantic>=0.59.0`), while installation guidance
requires matching versions and rejects cross-minor support assumptions.
See [SQL dependencies](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/packages/etlantic-sql/pyproject.toml),
[core manifest](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/pyproject.toml), and
[install policy](../10_REFERENCE/OPTIONAL_PACKAGES.md#install-pins).

**Recommendation.** Keep SQL execution, SQL compilation, PostgreSQL connector
actions, and target inspection together while they share one SQL stack; put the
PostgreSQL driver behind an explicit extra with compatibility handling. Align
dependency ranges with the actual supported policy. Keep CLI dependency
extraction low priority unless a measured SDK deployment benefit justifies it.
Do not immediately add `etlantic-postgresql` or `etlantic-cli` distributions.

**Done when.** Supported installation combinations resolve predictably and a
SQLite-only install can avoid the PostgreSQL driver. Dependency-size and startup
claims require measurement; neither was benchmarked in this review.

### F11 — P2: Metadata and deprecation drift show the cost of the portfolio

**Observed.** Workspace manifests say 0.59.0, while K8s, Spark Connect, MCP, and
Kafka provider metadata still contains 0.56.0. Several README headings retain
older release labels. The SparkForge redirect README says “Final release,” yet
the workspace and release workflow still build/version/publish it in lockstep.
See [provider version](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/packages/etlantic-k8s/src/etlantic_k8s/provider.py#L16),
[redirect declaration](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/packages/etlantic-sparkforge/README.md#L4), and
[release build](https://github.com/eddiethedean/etlantic/blob/d0708ba4ebbf9f98cbdf9a9142aa780ce4c241e6/.github/workflows/release.yml#L104).

**Recommendation.** Generate package version metadata from one source, distinguish
protocol versions from distribution versions, and check registered factories
against installed metadata. Give the redirect an explicit final compatibility
version and migration window; remove it from routine releases only after that
window. Do not break old installations or delete historical distributions.

**Done when.** Scope/version/capability inventories derive from actual factories
and manifests, and the redirect has an enforceable sunset rather than an
indefinitely repeated “final release.”

### F12 — P1: The new roadmap needs a smaller first platform matrix

**Observed.** The new 0.61 plan requires both ECS/Fargate and Batch live execution
qualification in addition to scheduling and a Lambda relay. The 0.59 plan adds
proposed scheduling/execution contracts before mapping every existing runtime
contract. The broader roadmap separately plans enterprise providers and a
TransformationModel extraction. See [0.59](IMPLEMENTATION_PLAN_0_59.md),
[0.61](IMPLEMENTATION_PLAN_0_61.md), [0.65](IMPLEMENTATION_PLAN_0_65.md), and
[0.66](IMPLEMENTATION_PLAN_0_66.md).

**Recommendation.** Keep the phase slots but revise their scope deliberately:
0.59 consolidates and freezes missing seams; 0.60 proves one explicit-URL Connect
trigger topology; 0.61 proves schedule-only delivery plus one execution backend
(ECS/Fargate as the default proposal); 0.62 proves one Data Mover composition and
optional URL discovery. Defer Batch until a concrete workload needs it. Do not
put S3 data access, Secrets Manager, all AWS orchestration, and infrastructure
deployment into `etlantic-aws` just because they share a vendor.

**Done when.** Each release has one bounded reference deployment, explicit
unsupported combinations, and gates that grow with demonstrated demand rather
than every imaginable backend. These recommendations have since been incorporated into the four phase plans;
the observation above describes their original review baseline. Platform
implementation and qualification remain pending.

## Package-by-Package Disposition

Line counts below are exact inventory measurements. “Keep” refers to package
ownership, not a new production-readiness claim. Every package remains subject
to its current qualification matrix.

| Distribution | Python lines | Appropriate responsibility and recommended disposition |
|---|---:|---|
| `etlantic` | 136,533 | Keep authoring, contracts, deterministic planning, public plugin protocols, embedded execution and shared policy. Consolidate/extract managed implementation in stages (F01–F02); remove concrete engine coupling (F05); do not split every namespace. |
| `etlantic-airflow` | 518 | Keep artifact compiler boundary. The operator intentionally fails closed unless demo-stub mode is enabled; do not advertise managed execution or grow a second ETL runtime. |
| `etlantic-datafusion` | 1,061 | Keep engine, native dependency, compiler and Arrow boundary together; retain its qualified/provisional scope. |
| `etlantic-duckdb` | 3,403 | Keep connection lifetime, SQL dialect/compiler, native handles and safe access policy together; engine-specific code is justified. Reuse small SQL helpers rather than merging SQL engines. |
| `etlantic-fastapi` | 6,604 | Keep routing, request identity, HTTP schemas, streaming and status representation. Consolidate configuration and delegate backend/worker authority (F03); retain the explicit reference-demo distinction. |
| `etlantic-foundry` | 2,544 | Keep Foundry dataset/file/transaction semantics and provider actions. Split the large module internally into transport, codecs, and connectors; share outbound policy where possible (F09). No package per source/sink/action. |
| `etlantic-iceberg` | 582 | Keep the Iceberg catalog/snapshot boundary for eventual live integration. Current factories are fake-backed; correct metadata first (F07), reuse testing fixtures, and avoid implying SDK installation supplies a live implementation. |
| `etlantic-k8s` | 80 | Reference fake today. Consolidate its fixture or freeze the package until actual provider work is scheduled (F06). Keep a distinct future live Kubernetes dependency boundary. |
| `etlantic-kafka` | 344 | Kafka source/sink and transaction/offset mapping belong together. Current factory is fake-backed; consolidate reference fixtures, not Kafka with schema registry or all streaming services. |
| `etlantic-keyring` | 95 | Keep. Small size is justified by isolating an OS/keyring dependency and credential resolution. Do not merge all secret providers into a mandatory dependency bundle. |
| `etlantic-lsp` | 421 | Keep LSP transport, editor protocol and pygls dependency; reuse core IDE analysis. This is a good thin adapter, not a candidate for a broader IDE platform package. |
| `etlantic-mcp` | 175 | Current in-process read-only fake, not a transport server. Consolidate fixture ownership or freeze until a real MCP host is qualified; keep analysis/authorization in existing shared services. |
| `etlantic-openlineage` | 195 | Keep outbound event mapping/export with injected transport. Do not let export become registry authority or combine it with orchestration. Narrow scope is appropriate even without a mandatory vendor SDK. |
| `etlantic-pandas` | 1,570 | Keep eager/index-neutral engine and compiler; centralize identical helpers only (F08). |
| `etlantic-polars` | 2,224 | Keep lazy engine, compiler, qualified fusion and Parquet snapshot implementation. Move matching vendor-specific core logic here without broadening support (F05). |
| `etlantic-prefect` | 2,270 | Keep direct and managed Prefect integration as distinct modes in one vendor distribution. Reuse shared managed dispatch and worker contracts; retain Prefect API/deployment behavior here (F02). Do not split `prefect-managed` yet. |
| `etlantic-pyspark` | 2,649 | Keep Spark realization, compiler and local provider with optional Delta support. Spark-specific behavior is not generic compiler duplication. Retain the separate remote-provider boundary. |
| `etlantic-s3` | 809 | Keep S3-compatible data source/sink/storage semantics distinct from AWS scheduling. Current implementation is fake-backed; preserve explicit maturity and use a truthful backend selector. Do not absorb it into `etlantic-aws`. |
| `etlantic-schemaregistry` | 146 | Keep read-only registry transport separate from Kafka. Share HTTP policy (F09); avoid growing into schema mutation authority. |
| `etlantic-snowflake` | 560 | Keep native Snowflake connector semantics; correct fake/live reporting (F07). Do not merge with generic SQL merely because both use tables. |
| `etlantic-spark-connect` | 85 | Reference fake today. Consolidate fixture ownership or freeze; retain a future live remote-session provider boundary distinct from PySpark transformation realization. |
| `etlantic-sparkforge` | 110 | Compatibility redirect only. Finish documented deprecation; no new feature work and no indefinite lockstep “final” releases (F11). |
| `etlantic-sql` | 9,268 | Keep SQLAlchemy execution, compiler, PostgreSQL connectors/actions and SQL target adapters together for now. Modularize large files and make driver installation explicit (F10). Its 1,541-line Unicode table also shows why raw size alone is misleading. |
| `etlantic-sqlmodel` | 9,073 | Keep relational stores/schema/migrations and composition, with separate modeling namespace and a public transition/codec seam (F04). Do not invent a persistence framework preemptively. |
| `medallantic` | 5,681 | Keep medallion authoring and migration vocabulary outside core. The facade/lowering boundary is correct. Move medallion-specific test campaigns out of core testing if testing consolidation proceeds. |

## New Package Opportunities And Rejected Splits

### `etlantic-runtime` — recommend planning as consolidation, with a strict boundary

**Consumers:** FastAPI hosting, headless SQLModel composition, Prefect managed
execution, and future AWS execution. These are actual shared responsibilities,
not hypothetical users of a generic utility library.

**Own:** reusable managed role construction/supervision, canonical dispatch
coordination, accepted-reference handling and reconciliation implementation,
and the missing external-trigger bridge. Reuse existing durable transitions,
identities, policies and result models; retain a single source of truth.

**Exclude:** embedded DAG/engine execution, frontend/API transport, database DDL,
SQLModel schemas, platform SDK calls, provider credentials, Data Mover product
logic, and a replacement for DTCS, [DPCS](../05_PIPELINES/DPCS.md), or ContractModel. An external timer adapter
is not the existing ready-node `ExecutionScheduler`; document that distinction
instead of unifying different meanings of “scheduler.”

**Dependency direction:** runtime depends on public core; persistence and vendor
adapters consume runtime as needed; runtime receives stores/platform operations
through interfaces and must not import their concrete packages. Core must not
gain a mandatory runtime dependency. Compatibility re-exports of moved managed
APIs need explicit optional-install diagnostics and a documented migration
window; plain authoring/embedded execution imports must remain self-contained.
If this direction cannot be preserved, refactor namespaces first and defer the
wheel instead of creating a cycle.

**Packaging value gate:** approve the wheel only with named code moving out of
existing owners and named duplicate APIs being deprecated. A package consisting
only of new models layered over unchanged models does not pass. Minimal generated
trigger content should consume the wire contract without carrying the complete
ETL engine and provider environment into Connect.

### `etlantic-testing` — conditional consolidation candidate, after runtime cleanup

**Own:** reusable plugin conformance, fault injection, reference fakes and fixture
builders currently scattered through core testing and small fake distributions.
Do not include production provider discovery or automatically register fakes.

**Value:** core currently carries 8,589 testing lines, including optional plugin
and Medallantic imports. A testing wheel could give those development consumers
an honest dependency boundary and replace several reference-only release units.
Keep project-specific test files and release campaigns in the repository.

**Gate:** prove third-party conformance consumers can install it, preserve the
documented `etlantic.testing` surface through a migration, and retire/freeze
superseded fake distributions after compatibility support. Do not keep all old
owners permanently alongside the new package. Organizing shared fixtures within
`etlantic.testing` is the lower-risk first step.

### Other proposals

| Candidate | Decision | Reason / promotion trigger |
|---|---|---|
| `etlantic-http` | Conditional, not immediate | Share existing outbound policy first. A wheel earns its place only when two real adapters adopt one optional client implementation and duplicate transport code is removed. No business retries or auth policy engine inside it. |
| `etlantic-persistence` | Defer | Only one concrete SQLModel persistence portfolio was found; a new wrapper adds ownership rather than consolidating independent implementations. Use internal namespaces and a public codec first. |
| `etlantic-connectors` / `etlantic-compiler-base` | Do not add now | Public connector CDK and compiler/helper namespaces already exist in core. Small utility duplication is insufficient justification for two more protocols/distributions. |
| `etlantic-contracts` | Do not add now | Existing core models and DTCS/DPCS/ContractModel already own contracts. Reconsider only for a demonstrated independent, lightweight consumer and an acyclic extraction. |
| `etlantic-postgresql` / `etlantic-cli` | Defer | Extras/internal modularization are cheaper first steps. Require measured install isolation or independent release demand before splitting. |
| `etlantic-rsconnect` | Keep planned, narrow | Connect scheduling/deployment/HTTPS delivery only; no pipeline execution, FastAPI dependency, or automatic URL discovery authority. |
| `etlantic-aws` | Keep planned, narrow | AWS timer/relay and one initial executor; use shared managed dispatch. S3, cloud secrets, and all infrastructure provisioning are not automatically in scope. |
| `etlantic-fastapi-posit` | Do not add | Use a small optional adapter in the consuming integration once `fastapi-posit` public API is verified. Keep explicit URL configuration. |
| Dagster / Argo adapters | Demand-gated separate integrations | Vendor artifact/dependency boundaries can justify packages, but only qualified fidelity-preserving compilation; do not clone the runtime. |
| AWS/Azure/GCP/Vault secret providers | Keep optional, demand-gated | Distinct SDK/identity dependencies justify separate adapters. Share the existing secret protocol; do not install all vendors together by default. |
| `transformationmodel` | Keep 0.66 incubation conditional | Demonstrate an independent consumer and delete migrated authoring duplication. Do not create a second DTCS parser, canonicalizer, or normative validator. |
| Operator console | Keep separately deployable | Frontend isolation is appropriate; the console consumes authorized projections and does not acquire backend state or provider control. |
| Data Mover package inside core | Do not add | Data Mover is a consumer; reusable behavior belongs in runtime/HTTP adapters, not a product-named core dependency. |
| `etlantic-quarto` | Do not create or plan | Explicitly excluded. External Connect tooling is not a reason for an ETLantic package. |

## Suggested Implementation Order

| Order | Work | Owner | Acceptance evidence |
|---|---|---|---|
| 1 | Correct actual-backend fake/live flags and distribution-version metadata; reconcile README scope claims | Provider and release maintainers | Factory matrix with SDK present/absent; installed metadata consistency |
| 2 | Canonicalize shared backend settings and headless install guidance | Backend + FastAPI/SQLModel maintainers | 25 shared fields have one owner; no-default-drift and HTTP/headless parity |
| 3 | Generalize existing dispatch records with compatibility decoding; map runtime extraction | Runtime + Prefect + persistence maintainers | Existing accepted work and immutable bindings survive upgrades; second adapter uses the same operations |
| 4 | Extract a minimal managed-runtime slice only if the dependency/ownership gate passes | Runtime maintainer | Clean base/headless/HTTP/worker installs; no cycle; existing leases, fencing, effects and publication tests pass |
| 5 | Centralize small compiler helpers and outbound policy application | Compiler + connector maintainers | Existing differential/rejection behavior and network policy fixtures unchanged |
| 6 | Narrow 0.60–0.62 to the first real consumer topology | Platform + Data Mover maintainers | One explicit-URL trigger path, one AWS executor, truthful supported matrix and recovery proof |
| 7 | Consolidate/freeze fakes and retire the SparkForge redirect under a migration window | Testing + release maintainers | Fewer active release units after migration; no lost public conformance coverage |
| 8 | Revisit testing wheel, driver extras, and any further split after measurements | Package owners | Demonstrated install/release/consumer benefit, not package-count targets |

Do not combine the first runtime extraction with a new persistence schema,
engine support expansion, and multiple cloud backends in one change. Those
changes have different rollback and qualification boundaries.

## Rules For Preventing New Scope Creep

- Give each package one sentence describing its user and authority, plus an
  explicit list of responsibilities it delegates. Multiple related protocols
  for one vendor are acceptable; ownership of unrelated lifecycle state is not.
- Before adding a package, name the existing responsibilities/code it removes,
  the dependency it isolates, or the independent consumer it enables. Require
  actual reuse before abstracting vendor behavior into a new framework.
- Prefer an existing shared module for small utilities and an extra for an
  optional driver. A new wheel must offer more than a shorter module path.
- Keep one authoritative model/transition per concept. Adapter-specific remote
  observations are separate facts, not alternative ETL state machines.
- Preserve intentional differences among schedule occurrence, dispatch,
  execution attempt, external effect, and publication. Their separation avoids
  false success; it is not duplication to remove.
- Keep base-import tests and add focused ownership checks for provider-specific
  imports/fields and config parity where the audit found gaps. Do not enforce
  arbitrary line-count caps or a blanket prohibition on all optional imports.
- Tie platform support to actual implementations and evidence. SDK presence,
  fake conformance, or a successful HTTP receipt does not qualify execution.

## Validation Performed

1. Parsed all 25 manifests and AST-scanned all 604 Python source files; recorded
   counts, dependencies, entry points and cross-package imports in the inventory.
2. Compared function bodies of at least ten physical lines across distributions,
   ignoring docstrings/locations; inspected the concrete helper matches in F08.
   This was an exact-body scan, not a complete semantic duplication analysis.
3. Compared dataclass fields at runtime: 25 shared config fields, two
   FastAPI-only fields (`title`, `version`), zero SQLModel-only fields.
4. Reproduced Iceberg and Snowflake metadata mismatches by overriding only their
   SDK-availability predicate in a temporary Python process. No live provider or
   network operation was used; source files were not changed.
5. Ran the following existing focused boundary tests: **6 passed, 1 deselected**.
   The deselected test requires a configured live PostgreSQL role environment.

```bash
.venv/bin/python -m pytest -q \
  tests/control_plane/test_import_boundary.py \
  tests/control_plane/test_optional_deps_report.py \
  tests/fastapi/test_managed_import_isolation_0_56.py \
  -k 'not without_create_privilege'
```

These tests confirm useful existing import/worker-isolation boundaries. They do
not prove that all 25 distributions are production-ready or that every proposed
extraction is safe. Full runtime, migration, and live-platform qualification
belongs to the eventual implementation changes.
