# Medallantic Roadmap

> **Document role:** This roadmap owns Medallantic parity and migration scope.
> The [ETLantic roadmap](../../ROADMAP.md) owns shared release order, the
> [Planning Hub](../../docs/11_DEVELOPMENT/PLAN_INDEX.md) summarizes portfolio
> status, and the [current package guide](README.md) owns shipped behavior.
> Review this header for every release or parity-sequence change.

**Current release:** Medallantic **0.38.0**. M0 through M7 are shipped
(exit gate closed; released in the ETLantic 0.36 line). Planned phases describe
capability order, not release-date commitments.

Medallantic is the engine-agnostic medallion pipeline facade built on
[ETLantic](https://github.com/eddiethedean/etlantic). It provides one
bronze/silver/gold authoring model across local Python, Polars, Pandas, SQL,
and PySpark while delegating contracts, graph validation, deterministic
planning, execution coordination, reports, and plugin trust to ETLantic.

This roadmap defines “full parity” against both legacy SparkForge surfaces:

- `pipeline_builder` (PySpark/Sparkless)
- `sql_pipeline_builder` (SQLAlchemy/Moltres)

Parity means preserving supported user outcomes and semantics, not copying
the two legacy implementations or exposing backend objects in the portable
model.

## Product boundary

Medallantic owns:

- bronze, silver, and gold vocabulary and conventions
- the fluent medallion builder and declarative configuration
- layer-aware dependency defaults and quality policies
- migration from both SparkForge builders
- medallion-oriented run results, explanations, and documentation

ETLantic owns:

- typed pipeline contracts and the logical graph
- validation, diagnostics, plans, run requests, and normalized reports
- artifact, state, lineage, security, and plugin coordination
- backend-neutral execution and compilation contracts

Execution plugins own:

- dataframe and relational execution
- SQL dialect and database transaction behavior
- Spark session and cluster behavior
- Delta Lake and other storage-specific operations
- engine-native expression compilation and optimization

Medallantic will not recreate separate Spark and SQL builder hierarchies.
Unsupported behavior must fail with a capability diagnostic; it must never
silently change semantics or select another engine.

### Promoting capabilities into ETLantic

ETLantic may be extended whenever Medallantic reveals a capability that is
useful beyond medallion architecture. Promotion is expected for portable
concepts such as typed multi-output steps, state transitions, materialization
policies, transaction boundaries, plan diagnostics, or plugin capability
negotiation.

A capability belongs in ETLantic when it:

- has the same semantics outside bronze/silver/gold pipelines,
- must be shared by more than one facade or execution plugin,
- affects portable validation, planning, execution, reports, or security, and
- can be named without medallion or engine-specific terminology.

Layer names, layer defaults, medallion dependency conventions, and migration
compatibility remain in Medallantic. Each milestone may therefore include
prerequisite ETLantic work; those prerequisites should land with their own
core tests before Medallantic consumes them.

## Current baseline

The **0.34.0** baseline includes the former `etlantic-sparkforge` IR adapter,
native Medallantic authoring, portable quality and lifecycle semantics, and
the shipped PySpark/Delta and SQLAlchemy relational differential bridges,
plus M6 operations and production-readiness evidence. It provides:

- SparkForge medallion IR parsing
- bronze/silver/gold-to-ETLantic graph adaptation
- dependency validation and cycle rejection
- layer quality-threshold mapping
- write-intent and retry-policy mapping
- run-intent and run-selection mapping
- plan enrichment
- SparkForge result normalization with secret redaction
- Delta capability checks
- IR fixture parity tests without SparkForge or PySpark installed

The baseline began in **0.28** with the renamed IR adapter. **0.29–0.34**
shipped M1–M6: native authoring, quality rules, lifecycle/materialization,
PySpark/Delta differential parity, SQLAlchemy relational differential parity,
and operations evidence with production-readiness conformance. Migration
completion shipped in **0.35 / M7**.

## Joint 0.x foundation sequence

Medallantic milestones are release-gated with ETLantic's 0.x roadmap:

| ETLantic release | Medallantic phase | Joint focus |
|---|---|---|
| 0.27 | M0 (partial) | Rename, workspace/CI, first `medallantic` PyPI publish |
| 0.28 | M0 closeout | Quadruple-minor burn-in, Plugin `/1` freeze, facade boundary |
| 0.29 | M1 | Native medallion authoring and facade conformance |
| 0.30 | M2 | Portable quality/rule semantics |
| 0.31 | M3 | Execution, state, writes, and materialization |
| 0.32 | M4 | PySpark/SparkForge differential parity |
| 0.33 | M5 | SQLAlchemy/relational differential parity |
| 0.34 | M6 | Operations, evidence, and production readiness |
| 0.35 | M7 | Migration completion and joint freeze |
| 0.37 | — | Joint compatibility burn-in |
| 0.37 | — | Stable foundation |

The [ETLantic roadmap](../../ROADMAP.md) is authoritative for the core
capability promoted at each phase and the joint exit gate. This document is
authoritative for Medallantic feature parity and migration scope.

## Definition of full parity

Full parity is reached only when all required rows below have:

1. a public Medallantic API,
2. an explicit ETLantic mapping,
3. conformance tests shared by all applicable engines,
4. live PySpark and SQL integration tests where backend behavior matters,
5. migration documentation and a declared compatibility result.

“Equivalent” permits an intentional API improvement. “Plugin” means the
portable intent is in Medallantic/ETLantic and the physical behavior is
implemented by a capability-bearing plugin. “Do not carry forward” records
legacy behavior that would be unsafe or architecturally incorrect.

## Parity matrix

| Capability | Spark builder | SQL builder | Target | Priority |
|---|---:|---:|---|---|
| Fluent bronze/silver/gold builder | Yes | Yes | Native `MedallionPipeline`/builder | P0 |
| Partial pipelines (any layer subset) | Yes | Yes | Equivalent | P0 |
| Unique step names and construction-time validation | Yes | Yes | Equivalent diagnostics | P0 |
| Automatic dependency ordering | Yes | Yes | ETLantic deterministic planner | P0 |
| Cycle and missing-dependency detection | Yes | Yes | Fail closed with stable codes | P0 |
| Bronze source to silver wiring | Yes | Yes | Typed output references | P0 |
| Multiple silver inputs for gold | Yes | Yes | Named typed input ports | P0 |
| Prior silver result access | Yes | Yes | Run-scoped artifact context | P0 |
| Cross-schema reads and writes | Yes | Yes | Dataset bindings plus profiles | P0 |
| Layer descriptions and metadata | Yes | Partial | Portable metadata | P1 |
| Per-layer validation thresholds | Yes | Yes | Named medallion quality policy (**0.30**) | P0 |
| Multiple rules per column | Yes | Yes | Contract-backed quality gates (**0.30**) | P0 |
| Valid/invalid row separation | Yes | Yes | Typed accepted/rejected outputs (**0.30**) | P0 |
| Validation-only steps and runs | Yes | Yes | `RunIntent.VALIDATE`, no writes (**0.31**) | P0 |
| PySpark expression rules | Yes | No | PySpark compiler/plugin (**0.32**) | P0 |
| String rule shorthand | Yes | No | Medallantic DSL → `etlantic.quality/1` (**0.30**) | P0 |
| Moltres expression rules | No | Yes | SQL compiler compatibility (**0.33**) | P0 |
| SQLAlchemy expression compatibility | No | Yes | SQL migration adapter | P0 |
| Callable transforms | Yes | Yes | Backend implementation refs | P0 |
| Initial load | Yes | Yes | Initialize intent | P0 |
| Incremental load | Yes | Yes | Incremental strategy plus state | P0 |
| Full refresh | Yes | Equivalent | Refresh intent | P0 |
| Bronze incremental column | Yes | Yes | Watermark strategy | P0 |
| Silver watermark column | Yes | Yes | State strategy | P0 |
| Append writes | Yes | Yes | Portable write intent | P0 |
| Overwrite writes | Yes | Yes | Portable write intent | P0 |
| Partition overwrite | Yes | Backend-specific | Plugin capability | P1 |
| Merge/upsert | Delta | Database-specific | Keyed merge capability | P0 |
| Ignore/skip-if-exists | Yes | Partial | Portable write intent | P1 |
| Schema compatibility checks | Yes | ORM model | Contracts plus sink checks | P0 |
| Schema override/evolution policy | Yes | ORM model | Explicit mutation policy | P1 |
| Table create/drop/refresh | Yes | Yes | Storage plugin | P0 |
| Silver initial recreate | N/A/overwrite | Yes | Refresh policy | P0 |
| Gold replace on every run | Yes | Yes | Layer default, overridable | P0 |
| SQLAlchemy ORM model table creation | No | Yes | SQL plugin compatibility | P0 |
| Primary-key validation | No | Yes | Merge/publication validation | P0 |
| Moltres lazy DataFrame transforms | No | Yes | SQL compiler | P0 |
| SQLAlchemy `Select`/compound selects | No | Yes | SQL compiler | P0 |
| Sync SQLAlchemy sessions | No | Yes | SQL runtime | P0 |
| Async SQLAlchemy sessions | No | Yes | SQL runtime | P1 |
| Multi-database SQLAlchemy support | No | Yes | Dialect conformance matrix | P1 |
| Spark and Sparkless execution | Yes | No | PySpark plus local test backend | P0 |
| JDBC sources and targets | Yes | No | SQL/PySpark I/O plugins | P1 |
| SQLAlchemy sources and targets from Spark | Yes | No | Explicit bridge capability | P2 |
| Delta merge | Yes | No | Delta plugin | P0 |
| Delta optimize, vacuum, history | Yes | No | Delta plugin | P1 |
| Delta time travel | Yes | No | Delta source capability | P1 |
| Run one / run until | Yes | No | ETLantic run selection | P0 |
| Stateful debug session | Yes | No | Medallantic convenience facade | P1 |
| Runtime parameter overrides | Yes | No | ETLantic run request | P1 |
| Transform/rule overrides for debug | Yes | No | Scoped implementation overrides | P1 |
| Downstream invalidation and rerun | Yes | No | Artifact provenance/invalidation | P1 |
| Skip writes during debugging | Yes | No | No-write materialization policy | P0 |
| Retry attempts and delays | Yes | Shared base | ETLantic retry policy | P0 |
| Contextual pipeline/step logging | Yes | Yes | Structured lifecycle events | P0 |
| Normalized run and step reports | Yes | Yes | Medallantic result facade | P0 |
| Counts, duration, validation and table metrics | Yes | Yes | Normalized report fields | P0 |
| Persisted execution-log writer | Yes | Shared base | Observability provider | P1 |
| Log table create/append/read | Yes | Shared base | Provider conformance | P1 |
| Trend and quality analytics | Yes | No | Event consumer/reference provider | P2 |
| Anomaly detection queries | Yes | No | Observability integration | P2 |
| Parallel candidates/execution groups | Analysis | Async SQL claim | Planner explain plus executor | P1 |
| Dependency recommendations | Yes | Shared base | Structured lint findings | P2 |
| Development/testing/production presets | Yes | Shared base | Profile templates | P1 |
| Serialization of configuration/results | Yes | Yes | Stable versioned schemas | P0 |
| Detailed errors with suggestions | Yes | Yes | Stable diagnostics/remediation | P0 |
| Engine-explicit configuration | Partial | Partial | Required profile selection | P0 |
| Silent runtime/mock auto-detection | Yes | N/A | Do not carry forward | Never |
| Automatic cycle breaking | Legacy analyzer | Legacy analyzer | Do not carry forward | Never |
| Separate public builders per engine | Yes | Yes | Do not carry forward | Never |

## Delivery milestones

### M0 / ETLantic 0.27–0.28 — Rename, release hygiene, and M0 closeout

**Shipped in 0.27.0**

- [x] Rename distribution to `medallantic`.
- [x] Rename import package to `medallantic`.
- [x] Rename workspace paths, tests, documentation, extras, and release checks.
- [x] Preserve SparkForge-specific conversion helper names where they describe
  the legacy input format.
- [x] Publish the first `medallantic` distribution (`medallantic==0.27.0`).

**Shipped in 0.28.0 (M0 closeout)**

- [x] Publish final `etlantic-sparkforge` compatibility release depending on
  Medallantic with a deprecation warning.
- [x] Document facade-package release category and ongoing trusted-publishing
  evidence for `medallantic`.

Exit criteria: clean build, install, import, docs, lockfile, and adapter suite on
every release; core remains importable without Medallantic; no medallion
identifier in ETLantic wire schemas.

### M1 / ETLantic 0.29 — Native medallion authoring

**Shipped in 0.29.0**

- [x] Add `MedallionPipeline`, `MedallionBuilder`, `Bronze`, `Silver`, and
  `Gold` public surfaces.
- [x] Support fluent and declarative/serialized authoring.
- [x] Map every layer definition to ordinary ETLantic nodes, typed ports,
  quality gates, sinks, and policies.
- [x] Support partial pipelines, multiple branches, prior-result references,
  cross-schema bindings, descriptions, tags, and deterministic names.
- [x] Add stable `MDL1xx` construction and graph diagnostics.
- [x] Keep the current IR adapter as `medallantic.migrate.sparkforge`.

Exit criteria: representative SparkForge pipelines can be authored natively,
validated, planned, serialized, and explained without SparkForge installed.

### M2 / ETLantic 0.30 — Quality and rules parity

Aligned with [ROADMAP § 0.30](../../ROADMAP.md#030--portable-quality-and-rule-semantics)
work packages. Protocol: provisional `etlantic.quality/1` with ContractModel as
semantic authority. Engine bar: live Polars/Pandas (+ local) for the portable
core; SQL/PySpark advertise and fail closed at plan time (live core subset
when classified). Native Column / Moltres-only rules stay **0.32 / 0.33**.

- [x] **WP1 consumer:** lower Medallantic shorthand onto `etlantic.quality/1`
  (portable core: `not_null`, comparisons, membership, ranges, regex, length,
  uniqueness, custom contract rules) — core owns the versioned AST
- [x] Compile rules to ContractModel-backed ETLantic quality gates (no parallel
  schema/rule system)
- [x] Live Polars and Pandas rule compilers for the portable core; SQL and
  PySpark participate in capability ads and plan-time fail-closed (live core
  subset optional when classified in the compatibility matrix)
- [x] Return accepted and rejected typed artifacts (rejected retained via
  `{step}__rejected` no-write Load); diagnostics available from the portable
  evaluator
- [x] Implement named per-layer defaults; `evaluate_accept_rates` helper
  available for adopters (automatic threshold enforcement remains later)
- [x] Replace `MDL110` / `MDL111` unenforced passthrough with real gate lowering
  (or keep `MDL111` only for transform_ref until **0.31**)
- [x] Make validation cost and unsupported-rule fallback visible in plans

Exit criteria: shared fixtures produce equivalent pass/fail decisions,
accepted/rejected counts, and diagnostics on every engine that advertises a
rule; unsupported required rules fail at plan/analysis; medallion thresholds
remain Medallantic policy; SQL/PySpark coverage is classified and CI-gated.

Tracking: [EXIT_GATE_0_30.md](../../docs/11_DEVELOPMENT/EXIT_GATE_0_30.md).

### M3 / ETLantic 0.31 — Execution and materialization parity

- [x] Execute native callable transforms through ETLantic implementation
  references.
- [x] Implement initial, incremental, refresh, standard, and validation-only
  behavior.
- [x] Map incremental columns and watermarks to atomic ETLantic state
  transitions.
- [x] Implement append, replace, keyed merge, skip-if-exists, and partition
  replacement with capability checks.
- [x] Implement layer defaults for bronze preservation, silver refresh, and
  gold publication without hard-coding them into ETLantic core.
- [x] Support retries only when the planned operation is safely retryable.
- [x] Normalize run, step, validation, artifact, write, and state results.

Exit criteria: engine-neutral conformance fixtures pass for local, Polars,
Pandas, SQL, and PySpark where each engine advertises support.

Tracking: [EXIT_GATE_0_31.md](../../docs/11_DEVELOPMENT/EXIT_GATE_0_31.md).

### M4 / ETLantic 0.32 — PySpark/SparkForge parity

**Shipped in 0.32.0**

- [x] Add a live migration bridge for `PipelineBuilder` definitions.
- [x] Support PySpark Column validation expressions and transform callables.
- [x] Support real PySpark and Sparkless test modes explicitly.
- [x] Cover schema/catalog management, cross-schema access, caches, JDBC I/O,
  and Spark-native metrics through plugins.
- [x] Add Delta capabilities for merge, optimize, vacuum, history, schema
  evolution, and time travel.
- [x] Reproduce run-one, run-until, no-write, parameter override, transform
  override, rerun, and downstream invalidation workflows.
- [x] Compare logical order, writes, validation outcomes, and normalized
  reports against frozen SparkForge fixtures.

Exit criteria: every supported `pipeline_builder` fixture has a documented
`equivalent`, `plugin-dependent`, or `intentionally rejected` result.

Tracking: [EXIT_GATE_0_32.md](../../docs/11_DEVELOPMENT/EXIT_GATE_0_32.md).

### M5 / ETLantic 0.33 — SQL pipeline-builder parity

**Shipped in 0.33.0**

- [x] Add a live migration bridge for `SqlPipelineBuilder` definitions.
- [x] Accept Moltres DataFrames/expressions and SQLAlchemy ORM, `Select`, and
  compound-select sources during migration.
- [x] Preserve lazy relational execution and avoid unnecessary table
  round-trips between steps.
- [x] Support model-driven table creation and primary-key validation.
- [x] Match initial/incremental silver behavior and gold replacement defaults.
- [x] Support sync and async SQLAlchemy execution with transaction rollback.
- [x] Validate missing sources, ambiguous/duplicate columns, invalid transform
  results, conversion failures, and write failures consistently.
- [x] Establish dialect tiers and live CI for SQLite and PostgreSQL, followed
  by additional SQLAlchemy dialects.

Exit criteria: the SQL parity matrix passes on SQLite and PostgreSQL, with
other dialect support accurately capability-gated.

Tracking: [EXIT_GATE_0_33.md](../../docs/11_DEVELOPMENT/EXIT_GATE_0_33.md).

### M6 / ETLantic 0.34 — Operations, observability, and production readiness

- [x] Provide medallion-oriented structured explain output.
- [x] Emit normalized lifecycle events with pipeline, layer, step, attempt,
  plan, run, and backend context.
- [x] Add durable run-history provider conformance for create/append/read.
- [x] Port trend, quality, performance, and anomaly analytics as optional
  event consumers rather than core storage logic.
- [x] Add development, testing, and production profile templates.
- [x] Complete redaction, plugin allowlist, schema-mutation, concurrency,
  cancellation, timeout, and recovery tests.
- [x] Publish compatibility, security, performance, and production-readiness
  documentation with explicit support tiers.

Exit criteria: Medallantic meets ETLantic’s production profile requirements
and has no undocumented fallback or mutation behavior.

### M7 / ETLantic 0.35 — Migration completion

**Shipped in 0.35.0** (exit gate closed in-tree)

- [x] Ship an automated scanner that inventories a SparkForge project and
  emits a migration report.
- [x] Generate native Medallantic definitions where conversion is safe.
- [x] Produce stable diagnostics for manual conversion points.
- [x] Maintain golden before/after plans and run reports.
- [x] Publish versioned deprecation timelines for legacy imports.
- [x] Remove transitional adapters only in a major release (scheduled, not done).

Exit criteria: both legacy builders have documented, tested migration paths
and all claimed parity rows are backed by conformance evidence.

Tracking: [EXIT_GATE_0_35.md](../../docs/11_DEVELOPMENT/EXIT_GATE_0_35.md).

## Test strategy

The parity suite will have four layers:

1. **IR tests** — no SparkForge, SQLAlchemy, or PySpark dependency.
2. **Semantic conformance** — one logical fixture and normalized assertions
   across local, Polars, Pandas, SQL, and PySpark.
3. **Legacy differential tests** — run frozen SparkForge and Medallantic
   fixtures and compare graph order, validation, writes, and reports.
4. **Backend integration tests** — real SQLite/PostgreSQL, PySpark, and Delta
   environments for physical semantics.

Every parity claim must identify its fixture, engines, capability requirements,
and normalized assertions. Unit-test coverage alone cannot establish backend
parity.

## Compatibility policy

- SparkForge names may remain in migration-only APIs and serialized legacy IR.
- New authoring APIs use Medallantic names exclusively.
- Diagnostic codes and serialized fields already consumed externally remain
  stable until a documented major-version migration.
- Backend-specific expressions are accepted only as implementation details;
  portable definitions use contracts, rule AST nodes, and typed references.
- A capability gap is an explicit diagnostic, never an implicit fallback.

## Release gates

A release may claim full parity only when:

- every P0 matrix row is complete,
- all P1 rows are complete or explicitly deferred with a documented support
  limitation,
- both legacy differential suites pass,
- SQLite, PostgreSQL, PySpark, and Delta integration suites pass,
- package build/install/import and documentation checks pass,
- security/redaction and schema-mutation gates pass,
- the compatibility table is generated from test evidence.
