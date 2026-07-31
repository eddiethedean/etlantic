# Roadmap

> **Document role:** This roadmap is authoritative for capability order and
> cross-program dependencies. It is not current API documentation. Use the
> [Planning Hub](docs/11_DEVELOPMENT/PLAN_INDEX.md) for plan status and
> [Capabilities](docs/01_GETTING_STARTED/CAPABILITIES.md) for what ships now.
> Review this header for every release or sequence change.

**Current release:** ETLantic **0.37.0** (Beta); **0.37** stable foundation is
gate-ready for tag/publish rehearsal (not yet tagged/published). Milestones
**0.25** (burn-in first slice) through **0.36** (joint compatibility burn-in)
are shipped. **0.35** closed migration completion and joint freeze /
Medallantic M7.

| Horizon | Release | Outcome | Status |
|---|---:|---|---|
| Current | 0.37 | Stable foundation | Gate-ready for tag/publish |
| Previous | 0.36 | Joint compatibility burn-in | Gate-ready / shipped evidence |
| Next | 0.38 | Data connectivity and connector SDK | Planned |
| Foundation | 0.36–0.37 | Joint burn-in → stable foundation | Gate-ready (0.37) |
| Post-foundation | 0.38–0.51 | Connectivity → control plane → developer intelligence → federation, governed AI, adoption, operations, providers, and modeling incubation | Planned |

For foundation evidence, see
[What's New in 0.37](docs/01_GETTING_STARTED/WHATS_NEW_0_37.md) and the
[0.37 exit gate](docs/11_DEVELOPMENT/EXIT_GATE_0_37.md). Prior burn-in:
[What's New in 0.36](docs/01_GETTING_STARTED/WHATS_NEW_0_36.md) and the
[0.36 exit gate](docs/11_DEVELOPMENT/EXIT_GATE_0_36.md). See the
[roadmap summary](docs/11_DEVELOPMENT/ROADMAP_SUMMARY.md) for the short
adopter-facing view, the
[Planning Hub](docs/11_DEVELOPMENT/PLAN_INDEX.md) for the status and ownership
of each domain plan, and the
[Adoption, Connectivity, and Operations Plan](docs/11_DEVELOPMENT/ADOPTION_ECOSYSTEM_PLAN.md)
for the cross-phase ecosystem gates, and the
[User Interface and Experience Plan](docs/11_DEVELOPMENT/UI_UX_PLAN.md) for
the phased CLI, visualization, authoring, operator, and hosted experience.

This roadmap sequences ETLantic from a typed modeling library into a
stable, secure orchestration model and plugin platform.

It is a direction and dependency plan, not a release-date commitment. Version
numbers describe capability milestones. A milestone is complete only when its
acceptance scenarios, documentation, tests, and security requirements pass.
All roadmap milestones remain in the 0.x series; no 1.0 or 1.x phase is
planned.

## Product Outcome

ETLantic will provide one portable model for:

- ContractModel-compatible, [ODCS](docs/03_DATA_CONTRACTS/ODCS.md)-aligned
  data contracts
- Type-driven, [DTCS](docs/04_TRANSFORMATIONS/DTCS.md)-aligned transformations
- Typed, [DPCS](docs/05_PIPELINES/DPCS.md)-aligned pipeline composition
- Deterministic validation and planning
- References to prior step outputs without mandatory table materialization
- External execution through interchangeable plugins
- Structured logging, lifecycle extension points, and normalized run reports
- Contract, lineage, documentation, and visualization generation

ETLantic owns the logical model and coordination contracts. It does not
become a dataframe engine, distributed scheduler, storage system, secret
manager, or medallion framework. Medallantic is the first-party,
engine-agnostic medallion facade that evolves alongside ETLantic while keeping
bronze/silver/gold vocabulary and policy out of core. Its detailed parity plan
lives in the
[Medallantic roadmap](packages/medallantic/ROADMAP.md).

## Delivery Principles

### Build vertical slices

Each milestone must produce something usable from the public API. A subsystem
is not complete merely because its internal types exist.

Every implementation milestone should prove:

```text
Authoring
→ validation
→ planning
→ backend realization
→ normalized results
→ generated contracts and lineage
```

### Stabilize semantics before backends

Execution plugins must consume a stable logical model and `PipelinePlan`.
Backend work must not define the core semantics accidentally.

### Preserve one logical pipeline

SQL, Polars, Pandas, PySpark, Local Python, Airflow, and later runtimes are
realizations of the same pipeline. Backend selection must not require a
different authoring model.

### Make behavior inspectable

Validation, implementation selection, dependency closure, materialization,
optimization, security decisions, and backend capability fallbacks must be
explainable before execution.

### Treat documentation as executable design

Examples begin as design fixtures and become executable acceptance tests as
their features are implemented. Documentation must clearly distinguish planned
APIs from released APIs until those tests pass.

## Cross-Cutting Release Gates

Every milestone must satisfy all applicable gates.

### API and semantics

- Public behavior has an explicit owner and documented contract.
- Models and serialized artifacts are deterministic.
- Diagnostics use stable codes and actionable messages.
- Backend-specific behavior does not leak into the core model.
- New behavior is reflected in terminology, reference docs, and examples.

### Quality

- Unit, integration, conformance, and acceptance tests pass.
- Documentation examples for delivered features execute successfully.
- Golden artifacts are deterministic across supported Python versions.
- Performance-sensitive paths have a baseline benchmark.
- Optional backends remain optional dependencies.

### Security

- New trust boundaries are added to the
  [Security Model](docs/02_FOUNDATIONS/SECURITY.md).
- Parsing, traversal, and resolution work is bounded.
- Plans, reports, diagnostics, and logs do not serialize secrets.
- Plugin loading and remote access fail closed under production policy.
- Optimizations preserve authorization, tenancy, residency, and masking
  boundaries.
- Security tests are release gates, not optional suites.

### Compatibility

- Public schemas carry explicit versions.
- Compatibility behavior is tested against the previous milestone.
- Breaking changes include migration guidance.
- Plugins declare core, SDK, plan-schema, and capability compatibility.
- Dependency additions and tier changes follow the
  [Dependency Strategy](docs/11_DEVELOPMENT/DEPENDENCY_STRATEGY.md).

### ETLantic–Medallantic co-evolution

- Every Medallantic phase identifies the ETLantic capabilities it consumes,
  the domain-neutral gaps it exposes, and the owner of each change.
- A capability is promoted into ETLantic only when its semantics are useful
  outside medallion architecture and belong to portable modeling, validation,
  planning, runtime, evidence, security, or plugin coordination.
- Medallion layer types, naming conventions, quality defaults, dependency
  conventions, and legacy SparkForge migration behavior remain in
  Medallantic.
- Promoted capabilities land with ETLantic-native tests and documentation
  before Medallantic depends on them.
- Every joint milestone runs ETLantic core compatibility gates plus
  Medallantic semantic conformance and, where applicable, legacy
  differential tests.

## Workstreams

The releases below combine eight continuing workstreams:

| Workstream | Responsibility |
|---|---|
| Modeling | Contracts, transformations, pipelines, steps, ports, and references |
| Analysis | Validation, diagnostics, graph operations, lineage, and compatibility |
| Planning | Profiles, bindings, capabilities, execution regions, and plan IR |
| Runtime | Lifecycle, resources, middleware, callbacks, events, reports, and state |
| Backends | Local Python, Polars, Pandas, SQL, PySpark, and orchestrators |
| Tooling | CLI, generated artifacts, visualization, docs, and plugin SDK |
| Assurance | Security, testing, benchmarks, release policy, and migration |
| Developer experience | IDE protocols, source maps, LSP, previews, refactoring, and debugging |

## Cross-Cutting User Interface and Experience Sequence

User experience is a cross-cutting delivery program, not a parallel semantic
layer. Every interface consumes the same public definitions, plans,
diagnostics, reports, lineage, authorization decisions, and audit evidence.

| Phase | Focus | Roadmap alignment |
|---|---|---|
| 1 | Human CLI renderer, actionable diagnostics, target discovery, and progressive onboarding | Stable-foundation tooling follow-up; prerequisite for 0.44 |
| 2 | React architecture spike, then an interactive, accessible, self-contained pipeline HTML workspace | Visualization/tooling precursor to 0.44 |
| 3 | Local run dashboard and visual plan/report comparisons | Read-only precursor to 0.50 |
| 4 | Watch mode, LSP, editor previews, and profile/impact explanations | 0.44 Developer Intelligence |
| 5 | Hosted, governed product experience | 0.39–0.43 control-plane substrate; 0.50 Operator Console |

Phases may land incrementally, but later phases cannot bypass earlier
consistency, accessibility, redaction, safe-I/O, or bounded-rendering gates.
The hosted experience cannot precede the applicable multi-tenant isolation,
authorization, idempotency, policy, audit, and recovery gates. See the
[detailed UI/UX plan](docs/11_DEVELOPMENT/UI_UX_PLAN.md).

## 0.1 — Typed Modeling Kernel

**Status: shipped** (superseded by later milestones; retained for history).

### Deliver

- `DataContractModel` integration boundary
- `Transformation`
- `Input[T]`, `Output[T]`, and `Parameter[T]`
- Multiple named outputs
- `Pipeline`, `Source[T]`, `Step`, `Sink[T]`, and subpipelines
- Typed `OutputRef[T]` values tied to concrete step instances and output ports
- Stable pipeline, node, port, contract, and implementation identities
- Deterministic graph construction
- Cycle, missing-reference, duplicate-identity, and incompatible-port diagnostics
- Read-only graph inspection and basic Mermaid output

### Acceptance scenarios

- A multi-source, multi-output pipeline can be declared without installing an
  execution backend.
- A downstream step can reference `upstream.result` directly rather than the
  entire source table.
- Two instances of the same transformation remain distinguishable.
- Invalid wiring identifies both endpoints and explains the incompatibility.
- Repeated introspection produces the same logical graph.

### Exit gate

The public authoring model can represent all domain-neutral structure required
by the initial end-to-end and SparkForge parity fixtures.

## 0.2 — Contract Interoperability

**Status: shipped in 0.2.0**

### Deliver

- ContractModel integration for data-contract operationalization
- Supported ODCS version policy and adapter boundary
- DTCS generation and loading for transformations
- DPCS generation and loading for pipelines
- Code-first and contract-first normalization
- Deterministic contract bundles and reference identities
- Contract diff and compatibility integration points
- Source-aware contract diagnostics
- Safe, bounded YAML and JSON loading

### Acceptance scenarios

- A Python pipeline generates stable ODCS, DTCS, and DPCS artifacts.
- Loading those artifacts reconstructs an equivalent logical model.
- Existing ContractModel workflows remain independent and unchanged.
- Unknown versions and unresolved references fail with structured diagnostics.
- No executable object serialization is used.

### Exit gate

Code-first and contract-first inputs converge on one canonical logical model
with explicit provenance and no domain semantics duplicated in ETLantic.

## 0.3 — Validation and Pipeline Plan IR

**Status: shipped in 0.3.0**

### Deliver

- Unified top-level authoring primitives:
  `Data`, `Transformation`, and `Pipeline`
- `Data` as ETLantic's thin public facade over ContractModel, without
  duplicating data-contract semantics or implementation
- Compatibility acceptance for existing ContractModel subclasses wherever a
  `Data` type is accepted
- Deprecation path for the uneven ETLantic-facing `DataContractModel` name
  before the stable foundation
- Multi-phase structural, reference, semantic, policy, and capability validation
- Named validation and quality-gate policies
- Valid and invalid output declarations
- `Profile` model with development, test, and production templates
- Serializable `SecretRef` model and secret-provider capability declarations
- Plugin, implementation, binding, and provider registries
- Capability negotiation and fallback diagnostics
- Stable source spans and symbol identities for models, steps, ports, contracts,
  bindings, profiles, and diagnostics
- Machine-readable diagnostic actions and safe edit suggestions that future IDE
  integrations can expose as quick fixes
- JSON Schemas for project configuration, profiles, and portable artifacts
- Versioned normalized-schema representation, deterministic fingerprints,
  `SchemaObservation`, `SchemaChange`, and `SchemaChangeSet`
- Separate contract-drift and operational-drift comparison paths, delegating
  data-contract compatibility meaning to ContractModel
- Drift-impact vocabulary covering informational, compatible, conditional,
  breaking, and unknown changes
- Portable freshness, partition-completeness, reconciliation, write-intent,
  materialization-intent, idempotency, retry-safety, backfill, repair, and
  reliability-evidence models
- Optional SQLModel adapter protocols for table metadata, `Data` mapping, and
  deterministic Python source generation
- Deterministic identities for logical pipelines, resolved environments,
  selected implementations, quality metrics, and statistical observations
- Immutable, versioned, secret-free `PipelinePlan`
- Logical-to-physical identity mappings
- `OutputRef` to runtime `ArtifactRef` resolution rules
- In-memory, lazy, durable, and external artifact representations
- Execution-region formation and materialization boundaries
- Graph slicing, dependency closure, run-one, and run-until planning
- Structured `plan explain` output
- Security-domain-aware artifact and cache identities

### Acceptance scenarios

- A complete pipeline can be authored with one coherent import:

  ```python
  from etlantic import Data, Pipeline, Transformation
  ```

- `Data`, `Transformation`, and `Pipeline` feel like three parts of one
  modeling language while ContractModel remains the authority behind `Data`.
- Existing classes authored directly against ContractModel work without
  conversion, wrapping, or loss of ODCS behavior.
- Planning is pure: it performs no user transformation, network, storage, or
  secret-resolution work.
- The same model and profile produce byte-stable canonical plans.
- A selected step includes only its required upstream closure.
- Direct prior-step results remain lazy or in memory when the boundary allows
  it, and become durable references only when required.
- Unsupported capabilities either produce an explicit safe fallback or fail
  closed.
- Optimizations cannot combine regions across declared security boundaries.
- Diagnostics identify their originating file and symbol and include related
  producer or consumer locations when relevant.
- Equivalent backend schemas normalize to the same logical fingerprint, while
  meaningful physical differences remain namespaced metadata.

### Exit gate

Every supported runtime can consume `PipelinePlan` without inspecting pipeline
class definitions or inventing missing semantics. The primary authoring
experience consistently presents `Data`, `Transformation`, and `Pipeline` as
the three top-level models.

## 0.4 — Local Runtime and Operational Model

**Status: shipped in 0.4.0**

### Deliver

- Async-first local orchestration with transparent `def` and `async def`
- An IDE-safe local run and debug protocol that can select a step, dependency
  closure, profile, parameters, and materialization policy
- Structured breakpoint events at validation, pre-step, post-step, failure, and
  publication boundaries
- Dependency-aware DAG concurrency
- `RunIntent`, `RunSelection`, and `RunRequest`
- Full, initial, incremental, refresh, validation, backfill, and replay intents
- Run-one, run-until, rerun, and downstream-invalidation workflows
- Run-scoped parameter, binding, and implementation overrides
- Explicit materialization, retry, timeout, and cancellation policies
- Runtime, run, and execution-region lifespan
- Deterministic run, step, and provider middleware
- Hierarchical resource injection with scoped caching and yield cleanup
- Secret Provider protocol with runtime-only `SecretValue` resolution
- Environment and mounted-file providers for explicit compatibility use
- Bounded secret caching, version selection, rotation, lease, renewal, and
  revocation lifecycle
- Outcome callbacks and typed outbound event declarations
- Immutable lifecycle and security events
- Structured contextual logging with central secret redaction
- Normalized run, step, artifact, validation, and transition results
- Explicit preflight, source, output, and pre-publication schema-observation
  hooks
- Profile-scoped `SchemaDriftPolicy` decisions for record, warn, notify,
  approve, quarantine, adapt, or block behavior
- Local freshness and partition-completeness checks
- Incremental invalidation and minimum-safe-repair planning
- Conditional idempotency analysis and retry-safety enforcement
- `BackfillRequest`, repair, reconciliation, and explicit no-write execution
  paths
- Versioned `PipelineRunReport`
- Text, JSON, and HTML report renderers
- Cancellation-safe cleanup and partial-run reporting

### Acceptance scenarios

- A pipeline runs locally using the same plan intended for external
  orchestrators.
- Independent branches execute concurrently while dependencies remain ordered.
- Lifespan cleanup runs after success, failure, or cancellation.
- Middleware ordering is deterministic and observable.
- Resource providers are scoped, cached, and cleaned up exactly once.
- Planning never resolves a secret, and runtime resolution reaches only the
  declared resource consumer.
- Secret-provider failures fail closed without plaintext fallback.
- Every run returns a report containing status, timing, row or record metrics
  where available, validation outcomes, artifacts, diagnostics, lineage, and
  failure context.
- Secrets are absent from logs, reports, events, and serialized plans.
- IDE-triggered runs use the same `RunRequest`, security policy, execution
  semantics, and report format as CLI and API runs.
- Reports distinguish declared, previously observed, and currently observed
  schemas and record the applied drift-policy decision.

### Exit gate

The local runtime is a complete reference implementation of ETLantic
runtime semantics, not a simplified test-only path.

## 0.5 — Dataframe Execution

**Status: shipped in 0.5.0**

### Objective

Prove that a single typed transformation contract can execute efficiently
against multiple in-process dataframe engines without leaking dataframe types
into contracts or weakening the runtime guarantees established in 0.4.

Polars is the reference backend and must deliver the complete vertical slice.
Pandas is the compatibility backend and must prove that the protocol is not
accidentally shaped around Polars.

### Scope boundaries

0.5 owns bounded, in-process dataframe execution. It does not add:

- SQL compilation, database relations, or query pushdown; those belong to 0.6.
- Distributed execution, Spark sessions, or streaming state; those belong to
  0.7.
- External scheduling or DAG compilation; those belong to 0.8.
- Backend-specific types in `Data`, `Transformation`, DTCS, DPCS, or logical
  pipeline definitions.
- Implicit engine changes, silent eager collection, or conversion fallbacks
  that are absent from the resolved plan and run report.

### Deliver

#### Dataframe execution protocol

- Versioned dataframe execution protocol with explicit input materialization,
  implementation invocation, output normalization, validation, metrics, and
  cleanup phases
- Public capability vocabulary for eager and lazy execution, Arrow import and
  export, zero-copy eligibility, schema inspection, invalid-row separation,
  cancellation, and thread-safety
- Planner integration that selects a dataframe implementation and records
  engine, plugin version, capabilities, conversion boundaries, validation
  policy, and collection points in `PipelinePlan`
- Runtime integration that consumes the resolved plan without reselecting an
  engine or inspecting pipeline classes
- Independently installable backend packages with no Polars, Pandas, PyArrow,
  or NumPy dependency added to the core package

#### Polars reference plugin

- Eager `DataFrame` execution as the required baseline
- `LazyFrame` preservation across adjacent compatible steps, with collection
  only at an explicit validation, conversion, materialization, or publication
  boundary
- Contract-to-Polars dtype mapping and Polars-to-normalized-schema inspection,
  including nullability, nested values, temporal types, decimal precision, and
  explicitly diagnosed unsupported types
- Native Polars implementation invocation with sync and async callable support
- Valid, invalid, and side-output production without losing row provenance
- Deterministic translation of Polars failures into ETLantic diagnostics and
  partial run reports

#### Pandas compatibility plugin

- Eager `DataFrame` execution through the same dataframe protocol
- Contract-to-Pandas dtype mapping and Pandas-to-normalized-schema inspection,
  with explicit handling of nullable extension dtypes, object dtype ambiguity,
  timezone-aware values, categoricals, and index semantics
- Copy-on-write and mutation isolation rules that prevent one branch or retry
  from changing data observed by another
- Feature and capability declarations that fail planning when a pipeline
  requires unsupported lazy or zero-copy behavior

#### Interchange and ownership

- Canonical record-batch and Arrow interchange boundary for cross-engine
  transfers when PyArrow is installed
- A documented non-Arrow fallback for supported values, with a diagnostic and
  report entry whenever the fallback copies or loses physical metadata
- Explicit ownership states for borrowed, shared, copied, and consumed
  dataframe artifacts
- Branch, retry, callback, cache, and publication rules that prevent mutation
  of an artifact still visible to another consumer
- Conversion fidelity checks for nulls, decimals, timestamps, timezones,
  nested values, categorical values, and stable field order

#### Validation, observation, and evidence

- Configurable input and output contract validation with fail, reject,
  quarantine, warn, and observe-only outcomes supported where the backend can
  identify invalid rows
- Schema observation before transformation invocation and before output
  publication, using the normalized schema model shipped in 0.3
- Equivalent Polars, Pandas, Arrow, and Python-record schemas producing the
  same logical fingerprint when their semantics match
- Structured row-count, invalid-count, rejected-count, schema, timing,
  conversion, collection, and memory-estimate metrics
- Reconciliation evidence and implementation-parity fixtures that compare
  logical values rather than backend object equality
- Initial quality-history observations for null, invalid, duplicate, rejection,
  cardinality, and volume metrics, without making a durable history service
  part of this milestone

#### Developer experience and assurance

- Installation and compatibility documentation for supported Polars, Pandas,
  PyArrow, Python, and ETLantic versions
- Runnable Polars and Pandas examples using the same pipeline definition and
  separate implementations
- Plugin conformance kit covering discovery, planning, invocation, validation,
  schema inspection, conversion, cancellation, diagnostics, and cleanup
- Golden plan and run-report fixtures for eager, lazy, conversion, invalid-row,
  and failure paths
- Correctness and performance benchmarks with published dataset shapes,
  environment details, warm-up policy, and regression thresholds

### Required execution paths

The release must support and test these paths:

| Path | Required behavior |
|---|---|
| Polars eager → Polars eager | No interchange conversion |
| Polars lazy → Polars lazy | Preserve laziness until an explicit boundary |
| Pandas eager → Pandas eager | Enforce documented ownership and copy rules |
| Python records → dataframe | Validate conversion against the input contract |
| Dataframe → Python or storage binding | Validate before publication |
| Polars ↔ Pandas | Use planned Arrow interchange when available |
| Valid + invalid outputs | Preserve output roles and record counts |
| Parallel sibling branches | Prevent cross-branch mutation |
| Retry after failure | Start from an artifact state allowed by ownership policy |

### Acceptance scenarios

- One pipeline definition selects Polars or Pandas from the profile without
  changing its data, transformation, or pipeline contracts.
- Equivalent implementations produce contract-valid, semantically equivalent
  results across Polars and Pandas for the conformance corpus, including null,
  decimal, temporal, timezone, categorical, and nested-value cases supported by
  both engines.
- A chain of compatible Polars lazy transformations reaches its first declared
  collection boundary without an earlier hidden collection.
- Every engine conversion, eager collection, copy, invalid-row split, and
  validation decision is visible in the plan explanation or run report.
- Equivalent logical schemas observed through Polars, Pandas, Arrow, and Python
  records produce the same normalized fingerprint; ambiguous or lossy mappings
  produce structured diagnostics instead of guessed compatibility.
- A branched pipeline and a retried step cannot observe mutations performed by
  another consumer of the same upstream artifact.
- Missing backend packages, unsupported versions, unavailable capabilities, and
  incompatible implementation signatures fail during discovery, validation, or
  planning rather than midway through execution.
- Backend exceptions retain pipeline, step, transformation, implementation,
  engine, attempt, and source context without exposing dataframe values or
  secrets.
- Installing `etlantic` alone does not install or import a dataframe engine;
  installing either supported plugin does not require the other.
- The documented Polars and Pandas examples run in CI from clean environments.

### Release artifacts

- Versioned dataframe protocol and capability documentation
- Polars and Pandas plugin packages with declared compatibility ranges
- Conformance suite reusable by third-party dataframe plugins
- Runnable parity example and benchmark report
- Migration notes for any 0.4 implementation-registration or profile changes
- Known-limitations page covering unsupported dtypes, lazy boundaries,
  conversion costs, validation limits, and mutation guarantees

### Exit gate

The complete Polars vertical slice passes the conformance, correctness,
security, and performance gates; Pandas passes the compatibility subset; and
the same logical pipeline can switch between them through profile and plan
selection without changing contract meaning, hiding materialization, or
corrupting shared artifacts.

## 0.6 — SQL-Native Execution

**Status: shipped in 0.6.0**

### Outcome

Run eligible relational pipelines inside a database from source relation to
published relation, without materializing intermediate rows in Python and
without introducing a SQL-specific pipeline authoring model.

The milestone proves one production-shaped reference dialect end to end. Other
dialects may implement the same protocols, but broad database coverage is not
an exit condition for 0.6.

### Scope boundary

0.6 owns relational planning, safe SQL compilation, database execution, and
normalized evidence. The core package owns portable relation, expression,
write-intent, capability, and plan models. Independently installable plugins
own drivers, dialect syntax, catalog access, transaction behavior, and
dialect-specific optimization.

The following are not part of this milestone:

- A general-purpose ORM, query builder, migration framework, or database
  administration layer
- Arbitrary user SQL parsing, rewriting, or claims of safety for untrusted raw
  SQL
- Distributed Spark execution, streaming execution, or Airflow compilation
- Transparent cross-database joins or distributed transactions
- Automatic schema migration beyond explicitly planned create-table behavior
- Silent emulation of unsupported merge, transaction, isolation, or locking
  semantics

### Deliver

#### Portable relational model

- Versioned protocols for SQL implementations, relations, expressions,
  compilers, executors, catalogs, connections, and dialect plugins
- Logical relation references that identify catalog, namespace, object, and
  optional version without containing credentials or live connection objects
- A closed, typed expression model for column references, literals,
  parameters, predicates, projections, joins, grouping, aggregation, ordering,
  limits, and supported scalar operations
- Explicit escape hatch for trusted SQL fragments, disabled by production
  policy unless the selected plugin declares and enforces a safe usage model
- Optional SQLModel table descriptors translated into ordinary relation and
  schema metadata without sessions, ORM instance materialization, or a
  SQLModel dependency in the core package

#### Planning and capability negotiation

- SQL plugin, driver, compiler, catalog, transaction, and dialect capability
  vocabulary with declared core, protocol, and plan-schema compatibility
- Planner selection of SQL implementations and formation of maximal compatible
  SQL regions without crossing engine, connection, security-domain,
  validation, retry, or publication boundaries
- Planned Python/dataframe-to-SQL and SQL-to-Python/dataframe materialization
  boundaries with format, ownership, validation, and size policy recorded
- Pre-execution diagnostics for unsupported expressions, types, write modes,
  isolation levels, identifier rules, parameter styles, and catalog features
- Deterministic compiled-statement identities and logical-to-physical mappings
  that retain every source, step, output port, and sink identity after fusion

#### Safe compilation and execution

- SQL-to-SQL execution whose eligible intermediate relations remain in the
  database and are never fetched into the ETLantic process
- Dialect-owned identifier quoting and validation; values use driver parameter
  binding and are never interpolated into statement text
- Separate compiled statement text, redacted parameter metadata, and runtime
  parameter values so plans, logs, diagnostics, and reports remain secret-free
- Connection acquisition at runtime through provider references, with bounded
  concurrency, cancellation, timeouts, cleanup, and normalized driver errors
- Transaction scopes aligned with declared atomicity and publication
  boundaries, including explicit behavior for dialects with transactional DDL
  limitations
- Retry decisions gated by retry-safety, idempotency, transaction outcome, and
  write-intent evidence; an unknown commit outcome must not be retried blindly

#### Relational optimization and semantic preservation

- Predicate, projection, join, and aggregation pushdown for operations
  represented by the portable expression model
- Safe adjacent-step query fusion when implementation, validation,
  observability, retry, security, and materialization semantics remain intact
- Deterministic fallback to separate statements or materialized relations when
  fusion is unsupported or would erase an observable boundary
- SQL lineage and plan explanation showing pushed operations, fused logical
  steps, materialization points, parameter sources, capability decisions, and
  fallback reasons
- Optional database query-plan capture as runtime evidence, bounded and
  disabled by default where explain operations may execute or lock data

#### Publication and reliability

- Portable append, replace, insert-select, create-table-as, and merge intents,
  with insert-only, snapshot, replace-partition, delete-propagation, and slowly
  changing dimension semantics represented explicitly where supported
- A required atomic-publication strategy for replace and snapshot operations;
  plugins must diagnose when rename, swap, staging, or transactional guarantees
  cannot preserve it
- Contract-aware target compatibility checks before writes, with schema drift
  policy applied to observed catalog metadata rather than inferred sample rows
- SQL-native row-count, affected-row, reconciliation, uniqueness, freshness,
  partition-completeness, and write-result evidence normalized into the run
  report
- Idempotency keys, target identities, statement identities, transaction
  outcomes, and reconciliation results recorded without query values or
  credentials

#### Inspection, plugins, and assurance

- Catalog, relation, and result-schema inspection through metadata APIs, with
  dialect-specific details preserved separately from normalized logical schema
- One independently installable reference SQL plugin and reference dialect,
  with driver dependencies kept out of the core package
- Plugin conformance kit covering discovery, planning, compilation, binding,
  identifiers, catalogs, transactions, cancellation, writes, evidence,
  diagnostics, cleanup, and compatibility rejection
- Golden plan, compiled-SQL, lineage, diagnostic, and run-report fixtures whose
  dialect-sensitive portions are explicitly separated from portable semantics
- Correctness, injection-resistance, transaction-failure, concurrency, and
  bounded-resource tests against an isolated database environment

### Required execution paths

The release must support and test these paths:

| Path | Required behavior |
|---|---|
| SQL relation → SQL steps → SQL sink | No intermediate Python row materialization |
| SQL source → Python or dataframe step | Planned, validated materialization at the region boundary |
| Python or dataframe source → SQL region | Planned load into an explicitly managed staging relation |
| Fused SQL region | Preserve logical identities, lineage, diagnostics, and validation boundaries |
| Non-fusible adjacent SQL steps | Emit separate statements or an explicit materialization boundary |
| Append or insert-select | Bind values and report affected-row evidence |
| Replace or snapshot | Publish atomically or fail capability negotiation |
| Merge or replace-partition | Execute native declared semantics or fail before mutation |
| Transaction failure before commit | Roll back and report a known non-committed outcome |
| Connection loss during commit | Report an unknown outcome and suppress unsafe automatic retry |
| Catalog schema inspection | Use metadata facilities without reading source rows |

### Acceptance scenarios

- The same data, transformation, and pipeline contracts used by the local and
  dataframe runtimes select SQL implementations through a profile; no
  SQL-specific `Pipeline` subclass is required.
- An eligible source-to-sink relational pipeline executes entirely inside the
  reference database, and instrumentation proves that intermediate rows were
  not fetched into Python.
- Malicious or malformed parameter values cannot alter statement structure;
  identifiers outside the dialect policy fail before execution, and generated
  statements contain placeholders rather than interpolated values.
- Fusion and pushdown produce the same contract-valid logical results as an
  unfused reference execution while preserving step attribution, lineage,
  validation gates, retry boundaries, and security domains.
- Every fusion, pushdown, materialization, transaction, write strategy, and
  capability fallback is visible in plan explanation or run evidence.
- Unsupported merge, replace-partition, isolation, transactional DDL, or
  atomic-publication requirements fail during validation or planning before
  the target is mutated.
- A failure before commit rolls back all writes in its declared atomic scope;
  a lost connection during commit produces an explicit unknown-outcome report
  and does not trigger an unsafe retry.
- Catalog-backed schema inspection normalizes supported types without
  executing arbitrary queries or reading rows; ambiguous, lossy, and unknown
  types produce structured diagnostics instead of guessed compatibility.
- Plans, logs, diagnostics, compiled artifacts, and reports contain no
  credentials or bound secret values, including on driver and compiler failure
  paths.
- Installing `etlantic` alone installs and imports no SQL driver, ORM, or
  database client; the reference plugin passes the published dialect
  conformance suite in a clean environment.

### Release artifacts

- Versioned SQL execution, relation, expression, compiler, and dialect protocol
  documentation
- Reference SQL plugin with declared driver, database, core, and protocol
  compatibility ranges
- Dialect conformance suite reusable by third-party SQL plugins
- Runnable SQL-to-SQL, mixed-boundary, transactional-write, and failure-recovery
  examples
- Security test corpus for values, identifiers, trusted fragments, redaction,
  connection failures, and bounded query-plan inspection
- Known-limitations page covering supported operations and types, transaction
  guarantees, write modes, catalog behavior, fusion barriers, and fallback
  costs

### Exit gate

The reference plugin passes the protocol conformance, semantic-equivalence,
injection-resistance, transaction-failure, security, and resource-bounding
gates; a complete eligible pipeline runs inside the database with explainable
planning and normalized evidence; and unsupported semantics fail before target
mutation. SQL is thereby proven as a first-class realization of the shared
logical pipeline, not a special pipeline type.

## 0.7 — Distributed Spark Execution

**Status: shipped in 0.7.0** (Structured Streaming APIs experimental)

### Deliver

- PySpark dataframe plugin
- Spark provider and environment model
- Lazy Spark execution regions
- Native-expression preference and UDF capability diagnostics
- Spark schema and contract validation
- Valid and invalid Spark artifacts
- Partition, cache, checkpoint, and materialization policies
- Delta-compatible portable write intents
- Partition completeness, controlled backfill, and idempotent Delta publication
  semantics
- Structured Streaming foundation: triggers, checkpoints, watermarks, state,
  and bounded-output semantics
- Spark plan and metric normalization into `PipelineRunReport`
- Spark, Delta, and Structured Streaming schema inspectors, including nested
  fields, nullability, precision, partition metadata, and evolution evidence

### Acceptance scenarios

- Adjacent compatible steps remain one lazy Spark region while retaining
  logical identities.
- Spark and Delta observations identify lossy or unknown normalization instead
  of guessing compatibility.
- A Spark pipeline reports plan, stage, validation, and artifact evidence
  through provider-neutral result models.
- Batch-only transformations are rejected from streaming regions.
- Cluster credentials and configuration are resolved at runtime and never
  embedded in plans.

### Exit gate

Batch Spark execution is production-capable, and streaming APIs are explicitly
marked stable or experimental rather than implied.

## 0.8 — External Orchestration

**Status: shipped in 0.8.0**

### Deliver

- Stable orchestrator-plugin and compilation protocols
- Airflow reference compiler
- Schedule, dependency, retry, timeout, resource, and state mapping
- Retry-safety and idempotency validation
- Portable repair, backfill, reconciliation, and write-intent mapping
- External artifact transport and size policies
- Submission, cancellation, polling, and status result models
- Remote lifecycle-event and report correlation
- Backend capability-loss diagnostics
- Generated-artifact import tests

### Acceptance scenarios

- One pipeline definition runs locally and compiles into a valid Airflow DAG.
- Airflow and local runs produce comparable normalized reports.
- Large results cross task boundaries through durable artifacts rather than
  inline metadata channels.
- A requested semantic Airflow cannot preserve fails compilation visibly.

### Exit gate

External orchestration is proven as compilation and coordination, not as an
alternate source of pipeline truth.

## 0.9 — Tooling, SDK, and Ecosystem Readiness

**Status: shipped in 0.9.0**

### Deliver

- CLI for inspect, validate, plan, explain, run, compile, generate, diff, and
  plugin operations
- CLI and public result models for `schema inspect`, `schema check`,
  `schema diff`, `schema history`, `schema impact`, `schema acknowledge`,
  `schema propose`, and `schema monitor`
- Schema-history provider protocol with canonical-file, local, and future
  registry-backed implementations
- Stable drift diagnostic codes, SARIF output, notification deduplication, and
  drift evidence in reports
- CLI and result models for freshness, partition checks, repair explanation,
  backfill preview, reconciliation, implementation comparison, plan and
  environment diff, quality trends, and statistical drift
- Provider protocols for quality history, statistical observations,
  reconciliation evidence, and environment inventories
- Cross-backend parity and write-semantics conformance suites
- Initial `etlantic-sqlmodel` package, model-generation CLI, metadata
  comparison, and integration conformance suite
- Language-server foundations for workspace discovery, incremental document
  indexing, source maps, diagnostic publication, and graph previews
- Editor-neutral command and result schemas for validate, plan, explain,
  generate, selected execution, and report retrieval
- Optional IPython display adapters for pipelines, plans, diagnostics, lineage,
  artifacts, and run reports, with plain-text and HTML representations
- Optional notebook session helpers that make the active profile, run
  selection, and generated artifacts explicit rather than relying on hidden
  kernel state
- A canonical, vendor-neutral set of AI coding workflows for inspecting,
  validating, planning, testing, documenting, and safely modifying ETLantic
  projects
- Generators for repository guidance and workflow files used by Codex, Claude
  Code, and Cursor, including `AGENTS.md`, `CLAUDE.md`, Codex `SKILL.md`
  packages, and scoped Cursor project rules and commands
- Drift checks that verify generated agent guidance still matches the current
  public API, CLI, security policy, and documentation
- Stable Plugin SDK protocols and capability vocabulary
- Plugin conformance and compatibility suite
- Entry-point discovery plus production allowlists and version pinning
- Plugin distribution and naming conventions
- Mermaid, Graphviz, HTML, lineage, and documentation generation
- Generated API reference
- JSON, text, GitHub, and SARIF diagnostic renderers
- Observability and notification provider protocols
- Secret Provider conformance suite and reference `keyring` integration
- Standard Python logging, JSON console, and OpenTelemetry integrations
- Durable report-store and run-history provider interfaces
- Report retrieval, comparison, and regression APIs
- Plan and artifact schema migration tools
- Executable documentation verification in CI

### Acceptance scenarios

- A third party can implement and test a plugin using public SDK imports only.
- Production configuration can reject an unapproved installed plugin.
- CI can validate contracts and plans and publish SARIF diagnostics.
- A run report can be persisted, retrieved, rendered, and compared without
  backend-specific classes.
- An editor integration can consume public commands and schemas without
  importing ETLantic internals or executing a pipeline during analysis.
- A notebook can inspect and render a pipeline without installing an execution
  backend, and restarting the kernel does not change the serialized model or
  plan.
- Generated Codex, Claude Code, and Cursor guidance expresses the same
  workflows and security boundaries through each tool's native file format.
- Schema observations can be recorded, compared, acknowledged, and rendered
  without storing source rows or silently updating a contract.

### Exit gate

The ecosystem can grow outside the core repository without relying on internal
modules or weakening security defaults.

See [Schema Drift and Evolution Plan](docs/11_DEVELOPMENT/SCHEMA_DRIFT_PLAN.md) for the cross-phase
observation, history, policy, impact, and remediation design.
See [ETL Reliability and Recovery Plan](docs/11_DEVELOPMENT/ETL_RELIABILITY_PLAN.md) for freshness,
repair, retries, writes, reconciliation, backfills, parity, drift, and quality
tracking.
See [SQLModel Integration Plan](docs/11_DEVELOPMENT/SQLMODEL_INTEGRATION_PLAN.md) for optional
contract mapping, typed control-plane persistence, FastAPI reuse, and migration
support.

## 0.10 — SparkForge Migration Preview

**Status: shipped in 0.10.0**

This milestone begins only after Local Python, SQL, PySpark, reporting, and the
Plugin SDK have stable integration surfaces.

### Deliver

- SparkForge-to-ETLantic adapter
- Mapping of medallion steps to ordinary ETLantic nodes and profiles
- Mapping of debug sessions to run selections and intents
- Mapping of direct step results to `OutputRef` and `ArtifactRef`
- Mapping of validation thresholds to named quality-gate policies
- Mapping of SparkForge run output to `PipelineRunReport`
- SQL, Spark, Delta, retry, and write-policy compatibility mappings
- Representative migration fixtures and semantic parity tests
- Deprecation path for duplicated SparkForge execution engines

### Acceptance scenarios

- Existing representative SparkForge pipelines generate equivalent dependency
  closures, execution groups, validation decisions, writes, and run summaries.
- SparkForge retains medallion terminology and defaults in its own package.
- ETLantic receives no bronze, silver, or gold concepts.
- SparkForge can progressively replace its SQL and Spark engines without an
  all-at-once user migration.

### Exit gate

SparkForge can depend on ETLantic as its underlying model, planner, and
coordination engine while remaining the medallion-focused facade.

See [SparkForge Feature Adoption](docs/11_DEVELOPMENT/SPARKFORGE_ADOPTION.md) for the detailed
feature assessment and adapter sequence.

## 0.11 — Portable Authoring and Transformation Plan

**Status: shipped in 0.11.0.**

**DTCS readiness gate: satisfied upstream.** DTCS 3.0 and `dtcs` 0.13 publish
`dtcs.transform-plan/2` (v1 readable), Portable Relational profiles, Rich
Portable Analytics families, structured expressions including bounded lambdas,
serialization, validation, and conformance support. ETLantic consumes those
public models without forking their semantics. Profiles remain Candidate or
Experimental until later phases graduate them with two independent compilers.

**Scope:** full portable **authoring** → validated `dtcs.transform-plan/2` IR.
No compilers and no runtime execution in this milestone.

### In scope

- `@Transformation.portable` symbolic definition registration
- PySpark-inspired DataFrame, Column, Window, and `functions as F` facade
- immutable `FrameExpr`, `ColumnExpr`, `GroupedData`, and bounded lambda
  authoring helpers over public `dtcs` models
- `etlantic.transform/1` authoring profile that emits **only**
  `dtcs.transform-plan/2` for new definitions (v1 remains readable for
  fixtures and migration)
- facade → registered `dtcs:` Semantic Action / Function mappings for:
  - `dtcs:profile/portable-relational-kernel/1` and `/2`
  - `dtcs:profile/portable-relational/1` and `/2`
  - Rich Portable Analytics: `portable-string-advanced/1`,
    `portable-conversion/1`, `portable-statistics/1`,
    `portable-complex-values/1` (including lambdas), `portable-reshape/1`,
    `portable-relational-extended/1`, `portable-temporal-iana/1`,
    `portable-nondeterministic/1`, `portable-window/2`
  - readable aliases for 2.0 `portable-window/1` and
    `portable-complex-types/1`
- profile requirement emission, portable typing, column resolution, inference,
  and output-contract validation
- bounded canonical serialization and deterministic fingerprints
- `PMXFORMxxx` diagnostics with expression source paths
- golden IR corpus and compatibility fixtures **per profile family**

### Explicitly deferred

- compiler discovery, capability descriptors, and selection policy
- Pipeline Plan portable-implementation fields used for compiler choice
- Polars, PySpark, Pandas, and SQL lowering or execution
- two-compiler “Standard” graduation of Candidate/Experimental profiles

### Acceptance scenarios

- every claimed facade method round-trips to a stable canonical fingerprint;
- joins, unions, grouping, aggregation, windows, complex values, advanced
  strings, conversions, statistics, reshape, IANA temporal, and declared
  nondeterministic constructs serialize under the correct profile
  requirements;
- a portable definition validates without source data or backend access;
- every declared output maps to exactly one typed relational expression;
- unknown or unsupported constructs, hostile depth/node/literal budgets,
  executable objects, raw SQL, and secret capture fail closed;
- null, missing, and invalid remain distinct through authoring and
  canonical serialization;
- ETLantic core imports no backend libraries.

### Exit gate

Portable definitions generate validated, inspectable `dtcs.transform-plan/2`
artifacts for the full published authoring surface, but do not execute through
an engine plugin.

## 0.12 — Portable Planning and Polars Kernel Compiler

**Status: shipped in 0.12.0.**

**DTCS readiness gate: satisfied upstream.** DTCS 3.0 / `dtcs` 0.13 define
exact profile, action, function, operator, type, mode, and limit claims.
Authoring IR already exists from 0.11; this phase adds planning integration and
the first Polars **kernel** compiler vertical slice.

**Locked decisions:** default `portable_transform_policy="prefer"` (no silent
fallback); embed bounded canonical `dtcs.transform-plan/2` + fingerprint in
`PipelinePlan` (external IR refs later); explicit
`kind: portable_compiled | native` descriptors; separate
`etlantic.transform_compilers` entry point for Polars; private kernel fixtures
in 0.12 (public conformance suite stays 0.14).

Sequenced inside one release:

### 0.12a — Planning integration

- compiler discovery and operation-level `TransformCapabilities` / analyze
  reports
- `Profile.portable_transform_policy`: `require`, `prefer`, or `native`
- portable/native selection with diagnosed fallback only when policy allows
- plan schema fields: implementation kind, embedded IR, IR fingerprint,
  compiler identity/version/protocol, profile requirements, support-decision
  summary
- `plan explain` (and plan JSON) render compiler selection, IR fingerprint,
  requirements, and fallback reason
- fail-closed unsupported ops/modes with expression-path diagnostics
  (`PMXFORM3xx`)
- cache/artifact identities include definition and compiler fingerprints

### 0.12b — Polars kernel vertical slice

- `etlantic-polars` compiler via `create_transform_compiler` claiming **only**
  `dtcs:profile/portable-relational-kernel/1`, plus plan-v2 `/2` metadata
  compatibility where kernel IR already uses plan/2
- must **not** claim `portable-relational/1`, Rich Portable Analytics, windows,
  or complex-value families
- native `pl.Expr` lowering for kernel actions (project, filter, with_fields,
  rename/drop, scalar ops covered by kernel golden fixtures)
- eager and lazy input support; `LazyFrame` preservation until a declared
  collection boundary
- output-role, validation, ownership, metrics, and materialization hooks
  already used by the native Polars dataframe plugin

### Explicitly deferred

- to **0.13:** full `portable-relational/1` (+ `/2`) compiler claims on Polars;
  PySpark compiler; two-engine differential execution
- to **0.14:** public `etlantic.testing.portable_transform_conformance`
- broader lineage/report UX polish beyond the explain fields above

### Acceptance scenarios

- a kernel-shaped portable pipeline (project/filter/with_fields/rename/drop/
  scalar ops) executes on Polars without a Polars-specific transformation
  callable;
- adjacent portable Polars kernel steps remain lazy until a declared boundary;
- requirements outside the advertised kernel claim set fail during planning
  with an exact expression path;
- plans and explain output show `portable_compiled`, IR fingerprint, compiler
  identity, and any allowed native fallback reason;
- serialized plans contain no compiled closures, Polars objects, parameter
  values, source rows, or resolved secrets.

### Exit gate

Planning treats portable compilation as a first-class, deterministic
implementation kind, and Polars executes end-to-end for its **advertised
kernel claim set** only.

## 0.13 — Relational Compiler Claims (Polars) and PySpark Compiler

**Status: shipped in 0.13.0.**

**DTCS readiness gate: semantics and authoring published.** Joins, unions,
grouping, aggregation, sorting, deduplication, and limit determinism are
authored in 0.11 IR. This phase proves compiler fidelity for
`dtcs:profile/portable-relational/1` on Polars and PySpark.

**Locked decisions:** sequence **0.13a → 0.13b**; claim
`portable-relational/1` only (plus kernel `/1`); treat plan requirements for
`portable-relational/2` as metadata-compatible aliases of `/1` (no candidate
`/2` extensions); PySpark must claim kernel `/1` + relational `/1`; keep
`portable_transform_policy` prefer/require/native with **no silent fallback**;
portable Spark path **forbids** Python/Pandas UDF fallback (native Spark UDF
policy stays separate); private differential fixtures under `tests/` (public
`etlantic.testing.portable_transform_conformance` stays **0.14**); default CI
uses **sparkless** for Spark suites plus private compiler/differential jobs,
with a gated real-PySpark env for Catalyst visibility;
relational `analyze()` rejects unsupported **modes** with action/expression
paths; portable Spark `execute()` uses the provider session from execution
context (no region UDF fusion); differential compare uses stable
normalization (column order, unordered-agg sort keys, SQL-null); IR-in-
`CompiledTransform` + lower-at-execute remains acceptable; three-state
missing/invalid literals stay deferred.

### Exact relational claim matrix (both engines)

Actions beyond the kernel: `dtcs:join`, `dtcs:union`, `dtcs:aggregate` (with
`groupBy`), `dtcs:sort`, `dtcs:distinct`, `dtcs:deduplicate`, `dtcs:limit`.

Modes that must pass `analyze()` exactly (fail closed, not “supports join”):

- Join types: `inner`, `left`, `right`, `full`, `semi`, `anti`, `cross`
- Join: `nullSafe`, `collisionPolicy` (`fail` in 0.13; other modes deferred)
- Union: `byName` / `byPosition`, `allowMissingColumns`
- Sort: direction + null placement
- Aggregates: `count_all`, `count`, `count_distinct`, `sum`, `average`,
  `min`, `max` + empty-input rules
- Deduplicate: deterministic key retention as authored today

### 0.13a — Polars relational vertical slice

- `etlantic-polars` claims `portable-relational/1` (+ keep kernel `/1`)
- native `pl.Expr` / frame lowering for the claim matrix above
- relation-scoped column resolution and collision diagnostics at analyze time
- private fixtures under `tests/polars_compiler/` and
  `tests/fixtures/portable/relational_*.json`

### 0.13b — PySpark compiler and differentials

- `etlantic-pyspark` `etlantic.transform_compilers` entry point claiming
  kernel `/1` + `portable-relational/1`
- native Spark DataFrame / Column lowering; no automatic UDF fallback
- session from provider/execution context; portable steps outside region UDF
  fusion
- private Polars↔PySpark differential corpus; gated real-PySpark Catalyst /
  no-UDF acceptance

### Explicitly deferred

- to **0.14:** public `etlantic.testing.portable_transform_conformance`;
  Pandas compiler
- to **0.15:** safe SQL lowering for kernel + `portable-relational/1`
- to **0.17** (historically 0.15 continuation): Rich Portable Analytics /
  windows / complex-values / reshape / relational-extended / conversion claims
- three-state missing/invalid literal fidelity beyond SQL-null

### Acceptance scenarios

- one portable multi-input aggregate pipeline produces contract-equivalent
  results on Polars and PySpark;
- Spark plans remain Catalyst-visible (real PySpark gate) and contain no
  undeclared UDF fallback;
- join null matching, duplicate columns, sort null placement, and empty
  aggregates follow the normative portable semantics;
- unsupported relational modes fail during planning with exact action paths.

### Exit gate

Two independent lazy compilers prove that the portable model is neither
Polars-specific nor merely a PySpark wrapper.

## 0.14 — Pandas Compiler and Conformance SDK

**Status: shipped in 0.14.0.**

**DTCS readiness gate: foundation published upstream.** `dtcs` 0.13 publishes
validation and conformance support. ETLantic exposes a public compiler suite
that consumes 0.11 IR and capability-selected fixtures without plugin
dependence on ETLantic internals.

### Deliver

- `etlantic-pandas` compiler for every honestly supported kernel and relational
  capability
- index-neutral, eager execution semantics and explicit ownership copies
- nullable dtype and optional Arrow interchange handling
- public `etlantic.testing.portable_transform_conformance` suite
- capability-selected mandatory fixtures for operations, functions, types, and
  semantic modes
- property tests for canonicalization, type promotion, and three-valued logic
- differential datasets covering nulls, NaN, extremes, decimals, Unicode,
  timestamps, ordering, joins, and empty inputs
- third-party compiler documentation and compatibility policy

### Acceptance scenarios

- Pandas passes every fixture associated with each capability it advertises;
- unsupported lazy or type semantics fail at planning rather than degrading;
- plugin CI fails when a capability is claimed without its conformance cases;
- normalized results remain comparable across Polars, PySpark, and Pandas.

### Exit gate

Portable compiler conformance becomes a public SDK contract suitable for
third-party engines.

## 0.15 — Safe SQL Lowering

**Status: shipped in 0.15.0.**

**Headline:** lower already-shipped portable claims (kernel +
`portable-relational/1`) into the existing typed `etlantic.sql/1` IR, with
PostgreSQL via `etlantic-sql` as the reference dialect. Polars, PySpark, and
Pandas remain the three dataframe/distributed compilers; SQL becomes the
fourth realization for that claim intersection.

**Second 0.15 theme (authoring vocabulary):** prefer `Extract` / `Load` /
`asset=` and `Profile.assets` while retaining plan/DPCS/plugin wire names
(`binding`, source/sink kinds). Legacy `Source` / `Sink` / `binding=` warn in
0.15 and are removed in 0.16. See
[Migration 0.14 → 0.15](docs/11_DEVELOPMENT/MIGRATION_0_14_TO_0_15.md). This
theme does **not** replace the Safe SQL Lowering exit gate below.

**Companion 0.15 runtime workstream:** extract the current local runner behind
one explicit scheduler boundary and preserve `Pipeline.run()` / `arun()`
semantics through a small built-in `LocalScheduler`. Prefect, Airflow, Dagster,
and other orchestrators remain optional plugins; none becomes a core dependency
or automatic default. This workstream establishes the boundary and private
conformance corpus, plus a Prefect feasibility spike. It does **not** replace or
delay the Safe SQL Lowering exit gate unless a scheduler defect threatens SQL
semantic safety. See the
[Local Scheduler and Prefect Integration Plan](docs/11_DEVELOPMENT/SCHEDULER_AND_PREFECT_PLAN.md).

**DTCS readiness:** rich facade authoring for Candidate/Experimental families
already exists in 0.11 IR. Those families are **not** part of the 0.15 exit
gate; they graduate later under
[0.17](#017--portable-coverage-expansion-platform--multi-family-graduation)
(historically
[0.15 Profile Graduation Work Package](#015-profile-graduation-work-package)).

### Goals

- Lower `etlantic.transform/1` / `dtcs.transform-plan/2` into the existing
  typed ETLantic SQL IR (not a competing SQL-shaped portable dialect)
- Bound parameters and validated identifiers only — no literal interpolation
- Dialect capability mapping; unsupported ops fail in `analyze()` / planning
- SQL region / CTE fusion with logical step and expression attribution retained
- Forbid trusted raw SQL fragments in portable definitions
- Extend public `etlantic.testing` conformance so SQL claims are fixture-gated
  like Polars / Pandas / PySpark
- Document the SQL column in the portable compiler matrix and draft
  0.14 → 0.15 migration / What’s New notes when the slice ships

### Non-goals

- Production readiness, SLA, HA, or multi-tenant isolation (remain
  stable-foundation work)
- Graduating window, complex-value, reshape, statistics, or related advanced
  families in the 0.15 exit gate
- Replacing native `@implementation("sql")` as the supported SQL path until
  portable SQL claims pass
- Inventing portable SQL semantics outside DTCS
- Managed cloud Spark providers or SQL dialects beyond the documented
  reference set
- Embedding Prefect or another general orchestrator in core, or making one the
  implicit production default

### Exit gate (all must be true)

1. Kernel + `portable-relational/1` portable definitions compile to
   parameterized SQL IR and match the shared semantic corpus against
   PostgreSQL reference fixtures.
2. Security corpus (injection payloads, hostile identifiers, parameter
   redaction) fails closed; no literal or parameter value is interpolated into
   generated SQL.
3. Dialect gaps produce planning diagnostics (`PMXFORM*`); never raw SQL or
   UDF approximation of portable semantics.
4. `portable_transform_policy=require` fails when SQL cannot claim the needed
   profile; `prefer` may select an **explicit native** SQL implementation,
   never silent portable emulation via pushdown fallbacks.
5. Native SQL implementations remain selectable and tested.
6. Docs and matrix updated: SQL claims in the portable compiler matrix;
   CAPABILITIES / What’s New / migration notes for 0.14 → 0.15.

### Acceptance scenarios

- A portable kernel + relational `/1` definition plans and runs on SQL with
  the same fixture outcomes as the Polars/Pandas/PySpark corpus intersection.
- Hostile identifier and injection fixtures never produce interpolated SQL.
- An unsupported dialect capability under `require` fails at planning with a
  stable diagnostic; under `prefer`, an explicit native SQL impl may be chosen
  when registered.
- `PipelinePlan` embeds bounded portable IR and compiler identity without live
  compiled objects or secrets.

See the
[Portable Transformation Implementation Plan](docs/11_DEVELOPMENT/PORTABLE_TRANSFORM_PLAN.md).
The required standards work is detailed in the
[DTCS 2.0 Portable Relational Publication Record](docs/11_DEVELOPMENT/DTCS_PORTABLE_SPEC_PROPOSAL.md)
and
[DTCS 3.0 Rich Portable Analytics Publication Record](docs/11_DEVELOPMENT/DTCS_3_0_SPEC_PROPOSAL.md).

### 0.15 Profile Graduation Work Package

**Status: superseded by [0.17](#017--portable-coverage-expansion-platform--multi-family-graduation).**
Historical ownership of rich portable family graduation after the 0.15 SQL
exit gate. Not a separate minor number and not part of the 0.15 exit gate.

Candidate/Experimental families remain expressible in authored IR. Each
family graduates only when:

- DTCS normative semantics and capability identifiers are published;
- shared conformance fixtures exist;
- **two independent compilers** pass those fixtures;
- migration / compatibility notes are published.

Historical suggested order (0.17 now assigns Wave 1 / Wave 2 / continuation):

| Family | Status relative to 0.15 exit gate |
|---|---|
| `portable-window/1` (+ `/2` when normative) | Not in 0.15 exit gate |
| `portable-string-advanced/1` | Not in 0.15 exit gate |
| `portable-conversion/1` | Not in 0.15 exit gate |
| `portable-complex-types/1` | Not in 0.15 exit gate |
| `portable-complex-values/1` | Not in 0.15 exit gate |
| `portable-statistics/1` | Not in 0.15 exit gate |
| `portable-reshape/1` | Not in 0.15 exit gate |
| `portable-relational-extended/1` | Not in 0.15 exit gate |
| `portable-temporal-iana/1` | Not in 0.15 exit gate |
| `portable-nondeterministic/1` | Not in 0.15 exit gate (policy-gated) |

### Continuation exit rule (per family)

Compiler claims ship only with normative semantics, two compiler
implementations, capability vocabulary, shared fixtures, and a short
native-to-portable migration note. Until a family graduates, keep native
`@implementation(...)` for that behavior. Active sequencing lives under
[0.17](#017--portable-coverage-expansion-platform--multi-family-graduation).

## 0.16 — Authoring Vocabulary Cleanup and Optional Prefect Scheduler

**Status: shipped in 0.16.0.**

0.16 has two **independent** gates. Vocabulary cleanup (Gate A) must ship and
must not wait on Prefect. Optional `etlantic-prefect` (Gate B) may ship in the
same minor when ready, but it does not block Gate A. Portable profile
graduation is owned by [0.17](#017--portable-coverage-expansion-platform--multi-family-graduation)
(historically tracked as the
[0.15 Profile Graduation Work Package](#015-profile-graduation-work-package)),
not 0.16.

**Prerequisites already shipped in 0.15:** `ExecutionScheduler` /
`etlantic.scheduler/1`, built-in `LocalScheduler`, private scheduler
conformance corpus, and a Prefect feasibility spike. See the
[Local Scheduler and Prefect Integration Plan](docs/11_DEVELOPMENT/SCHEDULER_AND_PREFECT_PLAN.md)
and
[Prefect Feasibility Spike notes](docs/11_DEVELOPMENT/PREFECT_SPIKE_NOTES.md).

**Protocol distinction:** Prefect is a direct-execution **scheduler** plugin
(`ExecutionScheduler`). Airflow remains an external **compiler** plugin
(`OrchestratorPlugin` / `compile_plan`). Prefect must not become a DAG/artifact
compiler like Airflow.

### Gate A — Authoring vocabulary cleanup (hard)

#### Deliver

- remove public `Source`, `Sink`, `binding=`, `.binding`,
  `Profile(bindings=...)`, mirrored profile JSON `bindings`, and
  `RunRequest.binding_overrides` per the
  [0.16 deletion checklist](docs/11_DEVELOPMENT/MIGRATION_0_14_TO_0_15.md#016-deletion-checklist)
- keep plan/DPCS/plugin **wire** names unchanged (`binding`, source/sink
  node kinds, storage `binding=` parameters)
- publish `docs/11_DEVELOPMENT/MIGRATION_0_15_TO_0_16.md`
- migrate README, docs, and examples still showing deprecated authoring names
  to `Extract` / `Load` / `asset=` and `Profile.assets`

#### Non-goals

- renaming plan/DPCS/plugin wire vocabulary
- changing logical graph semantics beyond removing authoring shims

#### Acceptance scenarios

- importing or constructing `Source`, `Sink`, or `binding=` authoring paths
  fails with a clear migration error rather than a silent alias
- validated pipelines and plans continue to use wire `binding` / source/sink
  kinds where those names are protocol-owned
- migration guide and What’s New notes cover every removed public surface

#### Exit gate

No public 0.15 authoring-vocabulary compatibility layer remains; docs and
tests use `Extract`, `Load`, and `asset=` only.

### Gate B — Optional Prefect `ExecutionScheduler` MVP (independent)

#### Deliver

- honor `Profile(orchestrator=...)` (and production plugin allowlisting) on the
  run path instead of hard-coding `LocalScheduler()` when a non-local
  scheduler is selected
- publish optional `packages/etlantic-prefect` implementing
  `ExecutionScheduler` / `etlantic.scheduler/1` (not `OrchestratorPlugin`)
- map one Prefect task per selected **logical node**, with the same dependency
  closure as `LocalScheduler` (fusion-driven `physical_units` scheduling remains
  post-0.16)
- support local direct invocation only for the MVP path
- correlate ETLantic run/node identities with Prefect flow/task-run identities
- preserve ETLantic-owned validation, retry safety, materialization, output
  normalization, redaction, and `PipelineRunReport`
- publish a **minimal** shared public scheduler conformance suite for semantics
  that already overlap with `LocalScheduler`
- keep `LocalScheduler` as the development, test, notebook, and embedded
  default
- keep `etlantic-airflow` as the reference external artifact compiler
- require explicit profile selection and plugin allowlisting for production
  Prefect use

#### Non-goals

- adding Prefect to ETLantic core dependencies
- requiring Prefect Cloud or a Prefect server for the basic local plugin path
- making Prefect the automatic `production` profile orchestrator
- Prefect deployment/serve or durable scheduling (post-0.16 Prefect follow-on)
- fusion-driven `physical_units` as the Prefect (or local) execution grain
  (post-0.16 / before stable-foundation runtime work)
- the full scheduler conformance corpus from the scheduler plan (later)
- treating Prefect as an Airflow-style `compile_plan` / DAG artifact compiler
- passing large datasets through scheduler control payloads
- allowing Prefect retries or task boundaries to weaken ETLantic transaction,
  validation, security, or materialization semantics
- replacing Airflow compilation
- portable profile graduation ([0.17](#017--portable-coverage-expansion-platform--multi-family-graduation))
- production-default orchestrator selection or the full stable-foundation
  security matrix

#### Acceptance scenarios

- one resolved plan produces equivalent logical results and report shape under
  `LocalScheduler` and Prefect
- independent ready nodes run through the selected Prefect task runner without
  dependency changes
- retries occur once, under resolved ETLantic retry-safety policy
- unsupported durable scheduling, cancellation, timeout, or artifact behavior
  fails during analyze/planning with a stable diagnostic
- plans, Prefect parameters, diagnostics, and reports contain no resolved
  secrets or source rows
- Prefect is absent from imports and installation for the default local path
- `Profile(orchestrator="prefect")` without the optional package (or without
  allowlisting in production) fails closed

#### Exit gate

`etlantic-prefect` passes the minimal public scheduler conformance suite as an
optional plugin; `LocalScheduler` remains the zero-service default; Airflow
remains the external compiler. Gate B does not block Gate A.

## 0.17 — Portable Coverage Expansion (Platform + Multi-Family Graduation)

**Status: shipped in 0.17.0.**

0.17 has three **sequenced** gates. Gate A (platform and truthful
discoverability) must ship. Gates B and C graduate declared DTCS profile
families under the existing two-compiler rule. Families not listed in Gates B
or C remain in the
[0.17 Coverage Graduation Work Package](#017-coverage-graduation-work-package)
and do not block the
0.17 exit gate.

**Prerequisites already shipped:** Polars, Pandas, SQL, and PySpark ship the
kernel and `portable-relational/1` baseline with public conformance and
cross-engine differentials. Rich-family authoring and fixtures exist; compiler
claims remain baseline-only until Gates B and C graduate them. Profile
graduation ownership moves here from
[0.15 Profile Graduation Work Package](#015-profile-graduation-work-package).

This requirement applies to first-party dataframe, SQL, and Spark execution
plugins. It does not apply to plugins that do not execute transformations,
including orchestrator compilers, schedulers, secret providers, storage or
resource providers, observability providers, and model/migration bridges.
Third-party runtime plugins may remain native-only, but must document that
choice and must not advertise or register unsupported portable compilation.

### Gate A — Platform and truthful discoverability (hard)

#### Deliver

- maintain an authoritative capability matrix for Polars, Pandas, SQL,
  PySpark, and future first-party transformation runtimes, listing exact DTCS
  profiles, actions, functions, operators, types, modes, and limits
- extend `etlantic plugin list` with transform-compiler inventory and exact
  portable capability summaries so installed runtime/compiler pairs are
  inspectable without planning a pipeline
- expand public portable conformance selection beyond kernel and
  `portable-relational/1` so graduated-family claims are enforceable from
  advertised capability records
- pair every applicable first-party execution plugin with a discoverable
  `etlantic.transform_compilers` implementation in the same distribution or a
  clearly documented companion distribution (already true for the four
  shipped runtimes; keep as a release gate for new first-party runtimes)
- update [Building an ETLantic Plugin](docs/07_PLUGIN_SDK/BUILDING_A_PLUGIN.md)
  and the category protocol pages whenever entry points, capability metadata,
  conformance requirements, or the first-party portable baseline changes
- add guide-drift checks so reference plugin packaging, public factories,
  capability declarations, conformance tests, and documentation remain aligned
  with the canonical plugin guide
- frame matrix and docs as 0.17 graduated versus continuation (not the
  historical 0.15 continuation backlog label)

#### Non-goals

- graduating rich profile families (Gates B and C)
- requiring portable compilers from orchestrator, scheduler, secret, storage,
  resource, observability, SQLModel, or SparkForge integration packages
- moving engine dependencies or compiler implementations into ETLantic core
- allowing plugin identity alone to imply portable capability coverage

#### Acceptance scenarios

- installing any first-party dataframe, SQL, or Spark execution plugin exposes
  both its runtime entry point and its portable compiler entry point
- `etlantic plugin list`, plan JSON, and plan explanation identify the runtime,
  compiler, protocol versions, exact portable requirements, and selection or
  fallback reason without importing a different backend
- guide-drift checks fail closed when entry points, factories, capability
  claims, conformance coverage, or the plugin guide disagree
- plans, compiler diagnostics, golden fixtures, reports, and guide examples
  contain no source rows, live backend objects, or resolved secret values

#### Exit gate

Installed first-party transformation runtimes expose runtime and compiler;
CLI and plan explain surface exact claims; the capability matrix and plugin
guide match shipped entry points and conformance evidence; drift checks pass.

### Gate B — Wave 1 family graduation (hard)

Graduate these families (authoring and fixtures already exist under
`tests/fixtures/portable/`):

| Family | Role in Wave 1 |
|---|---|
| `portable-window/1` | First analytics family; `/2` stays in continuation |
| `portable-string-advanced/1` | Scalar-function family |
| `portable-conversion/1` | Scalar-function family |
| `portable-statistics/1` | Aggregate / analytics family |

#### Deliver (per family)

- publish normative DTCS semantics and capability identifiers
- select shared conformance fixtures from advertised capability records
- land at least **two independent** first-party compilers that pass those
  fixtures
- run cross-engine differential tests over each advertised capability
  intersection
- keep native implementations for backend-specific behavior and families that
  have not graduated
- keep `portable_transform_policy=require|prefer|native` consistent with no
  silent fallback; unsupported requirements fail during analyze/planning
  before resource acquisition or mutation
- verify portable lowering preserves contracts, null/missing/invalid
  semantics, output roles, write and materialization boundaries, lineage,
  diagnostics, and normalized report evidence
- publish a native-to-portable migration note and one multi-engine portable
  pipeline example per graduated family
- claim only where truthful: do not require all four engines when SQL or
  Pandas cannot honor semantics; publish exact per-engine limits in the
  matrix

#### Non-goals

- claiming `portable-window/2` or Wave 2 / continuation families
- claiming the full portable authoring surface on every engine regardless of
  backend semantics
- emulating unsupported semantics with Python, Pandas, Spark UDFs, raw SQL, or
  eager collection without an explicit, policy-permitted, diagnosed boundary

#### Acceptance scenarios

- each Wave 1 family has ≥2 conformant first-party compilers and differential
  coverage for the advertised intersection
- a profile requiring an unsupported Wave 1 claim fails deterministically
  during planning and performs no reads, writes, credential resolution, or
  cluster / database acquisition
- the capability matrix lists exact Wave 1 claims, modes, and limits per
  engine
- migration notes and multi-engine examples cover every graduated Wave 1
  family without secrets or source rows

#### Exit gate

All four Wave 1 families meet the two-compiler graduation bar with matrix,
conformance, differentials, examples, and guide alignment.

### Gate C — Wave 2 family graduation (hard, after B)

Sequence after Gate B so platform and conformance machinery already enforce
rich claims. Graduate:

| Family | Role in Wave 2 |
|---|---|
| `portable-complex-types/1` | Nested type surface; pairs with values |
| `portable-complex-values/1` | Constructors, accessors, and lambdas |
| `portable-reshape/1` | Explode / reshape actions |

#### Deliver / non-goals / acceptance

Same per-family bar, policy, and fail-closed rules as Gate B, applied to the
Wave 2 families only.

#### Exit gate

All three Wave 2 families meet the two-compiler graduation bar with matrix,
conformance, differentials, examples, and guide alignment.

### 0.17 Coverage Graduation Work Package

**Status: planned — after the 0.17 exit gate.** Not required to close 0.17.

These families remain authorable but stay unclaimed / native-only until they
meet the two-compiler bar:

- `portable-relational-extended/1`
- `portable-temporal-iana/1`
- `portable-nondeterministic/1` (policy-gated)
- `portable-window/2`
- any Gate B or Gate C family that cannot meet the two-compiler bar before
  cut (demote here rather than weaken claims)

**Not 0.17** (post-0.16 / later runtime work):

- fusion-driven `physical_units` scheduling
- Prefect deployment/serve or durable scheduling
- the full scheduler conformance corpus
- SQL `MERGE`, managed Spark providers, Dagster, and other
  [Known Issues](docs/10_REFERENCE/KNOWN_ISSUES.md) items not listed above

### Non-goals (release-wide)

- requiring every third-party execution plugin to implement portable lowering
- requiring portable compilers from non-transformation integration packages
- moving compilers into ETLantic core
- promising that every authored rich family graduates in 0.17

### Acceptance scenarios (release-wide)

- Gates A, B, and C exit gates all pass
- the same portable pipeline produces contract-equivalent results on every
  first-party engine in the advertised capability intersection for graduated
  families
- native-only third-party plugins remain valid when they omit the transform
  compiler entry point and clearly document the limitation
- a new first-party transformation runtime cannot pass its release gate until
  its plugin-guide checklist, portable conformance suite, differential tests,
  capability matrix, and native-to-portable documentation are complete for the
  release baseline
- continuation families remain expressible without implying compiler claims

### Exit gate

0.17 ships when Gate A is complete; Gates B and C families are graduated under
the two-compiler rule with matrix, conformance, differentials, examples, and
guide alignment; continuation families remain authorable but unclaimed where
not graduated; native fallback is explicit and policy-governed; and plans,
fixtures, reports, and examples contain no secrets or source rows.

## 0.18 — Versioned Tabular Interchange (Gate A)

**Status: shipped in 0.18.0.** **0.18.0 ships Gate A only**: a public, versioned,
capability-driven tabular interchange contract. DataFusion is a **non-blocking
Gate B / 0.19+ experiment** and does not gate 0.18.0.

Authority for contracts, milestones, fidelity, and graduation policy:
[0.18 Versioned Tabular Interchange Plan](docs/11_DEVELOPMENT/INTEROPERABILITY_FOUNDATION_PLAN.md).

### Architectural boundary

ETLantic retains Pydantic / ContractModel and ODCS / DTCS / DPCS as its
semantic foundation. ETLantic continues to own typed pipeline meaning,
validation, deterministic planning, trust, reliability, lineage, and
normalized evidence.

- Arrow mechanisms are preferred **physical tabular interchange** at compatible
  cross-plugin boundaries (recorded as `etlantic.interchange/1`).
- Parquet is a **durable artifact** strategy, not an in-process transport.
- `etlantic-datafusion` (Gate B) is a candidate first-party **local analytical
  engine and portable compiler**, never the scheduler or pipeline planner.

Heavy dependencies remain outside the core wheel. Installing `etlantic` alone
must not install or import PyArrow or DataFusion.

**0.17 continuation** portable families may proceed in parallel; they are
**not** required to close 0.18.0.

### Non-goals for 0.18.0

- DataFusion scaffolding, recommendation, or graduation
- PySpark or SQL Arrow physical boundaries (follow-ups after Polars↔Pandas)
- Multi-tenant streaming fabric / Arrow Flight services
- Replacing logical contracts with Arrow schemas
- Advertising today’s best-effort Arrow helper as the formal interchange API

### Gate A — Versioned tabular interchange (hard; = 0.18.0)

#### Deliver

- **A0:** generalize dataframe engine dispatch/ownership off hard-coded
  engine-name sets for new interchange boundaries (capability/registry driven)
- **A1:** replace best-effort, invisible conversion with `etlantic.interchange/1`
  decisions in plans and run evidence; 0.17 plans regenerate rather than
  silently upgrade
- **A2:** select mechanism from producer/consumer capabilities via the
  published truth table (C Data/Stream, IPC stream/file, Parquet artifact,
  records/native fallback)
- **A3:** fidelity matrix + quantitative stream/artifact bounds; observed
  conversion/copy evidence; no silent exception swallowing
- **A4:** Polars ↔ Pandas conformance; documented non-Arrow fallback; core
  tests pass without PyArrow

#### Acceptance scenarios

- compatible Polars ↔ Pandas boundaries use the planned mechanism without
  hidden eager collection beyond what the descriptor records
- unavailable, unsupported, or lossy conversion produces an explicit
  plan/report decision and fails before mutation when the contract cannot be
  preserved
- “zero copy” is reported only as planned eligibility plus observed evidence,
  never inferred from plugin identity
- stream and artifact payloads are bounded; plans, diagnostics, and reports
  contain no source rows, live Arrow objects, or resolved secret values
- core tests and imports pass without PyArrow installed

#### Exit gate (0.18.0)

Milestones A0–A4 are complete. Arrow interchange is a public, versioned,
capability-driven contract with fidelity, ownership, streaming, fallback, and
evidence conformance for the Polars↔Pandas pair. CAPABILITIES / COMPATIBILITY /
What’s New / Migration describe the formal boundary (not best-effort
conversion). Existing plugins pass Gate A before a new analytical engine is
added.

### Gate B — Experimental `etlantic-datafusion` (non-blocking)

Begins only after Gate A / 0.18.0. DataFusion is initially an experimental
first-party plugin and does not replace Polars as the reference dataframe
backend or `LocalScheduler` as the execution coordinator. **Gate B does not
block 0.18.0.**

#### Deliver

- add independently installable `etlantic-datafusion` with dataframe runtime
  and `etlantic.transform_compilers` entry points
- expose installation as `pip install "etlantic[datafusion]"`
- consume and produce Arrow through Gate A boundaries
- compile the smallest truthful DTCS kernel claim set first: projection,
  filtering, with-fields, rename/drop, scalar expressions, and supported casts
- preserve lazy execution until a declared validation, conversion,
  materialization, or publication boundary
- normalize schema, diagnostics, metrics, logical-to-physical attribution, and
  outputs through existing ETLantic protocols
- publish correctness, import/install cost, memory, conversion, and performance
  comparisons against local records and Polars using reproducible fixtures
- expand to joins, unions, grouping, aggregation, sorting, and relational `/1`
  only after kernel conformance and differential gates pass

#### Non-goals

- replacing ETLantic planning, scheduling, contracts, or reports with
  DataFusion objects
- adding DataFusion to core dependencies or exposing its classes in core
  protocols and serialized plans
- claiming writes, UDFs, streaming state, or the full DTCS surface in the
  initial slice
- making DataFusion the default merely because the integration works
- treating an installed-but-ungraduated plugin as production-recommended

#### Graduation gate

`etlantic-datafusion` graduates from experimental only if it passes dataframe
and portable conformance, cross-engine differentials, Arrow boundary tests,
failure/redaction tests, and demonstrates a distinct measured advantage in at
least one of local analytical performance, streaming/laziness, conversion
cost, or external interoperability. Otherwise it remains experimental or is
stopped without changing the core default and without creating a
stable-foundation
compatibility obligation.

### Program success measures

- fewer copied or silently materialized cross-engine boundaries
- deterministic interchange decisions with stable fingerprints
- no increase in mandatory core dependencies
- equal or stronger fail-before-mutation, plugin-trust, and redaction behavior
- DataFusion earns graduation through measured value rather than duplication
- plugin authoring and runtime behavior remain simpler and more inspectable
- SDK, CLI, notebook, scheduler, and compiler use remain independent

### Exit rule

Gate A is required for the **0.18.0** interchange baseline. Gate B may continue
across later minors and cannot weaken Gate A or the semantic foundation.
DataFusion ships as recommended only after its graduation gate; a failed
experiment is removed or remains explicitly experimental without becoming a
core compatibility obligation.

## 0.19 — Contract and Configuration Freeze

**Status: Shipped in ETLantic 0.19.0.**

**Objective:** turn the shipped logical model and plan boundary into a precise,
deeply immutable, versioned contract before adding further stable surface area.
The experimental DataFusion Gate B may proceed in parallel, but it cannot
change or weaken these gates and does not become a stable-foundation obligation
unless it
graduates independently.

### Deliver

- make `PipelinePlan` and all plan-owned nested values deeply immutable rather
  than only freezing the top-level dataclass
- define canonical serialization and the exact fingerprint participation rules
  for logical graphs, profiles, implementations, bindings, artifacts,
  capabilities, interchange decisions, and extension metadata
- verify plan fingerprints after deserialization and immediately before
  execution or compilation across a trust boundary
- fully specify nested JSON Schemas for plans, run reports, profiles,
  diagnostics, events, artifacts, capability decisions, and interchange
  evidence; replace unconstrained objects and arrays with versioned shapes
- reject missing and unknown wire-schema versions; add explicit, tested schema
  upgrade functions instead of silently applying current defaults
- define extension namespaces and size budgets so plugin metadata remains
  evolvable without making every core schema open-ended
- make profile resolution strict: unknown named profiles fail unless an
  explicit ad hoc-profile option is selected
- add an explicit profile security mode rather than relying only on profile
  names or security-domain spelling to identify production-like behavior
- finish the public `assets` vocabulary migration; preserve legacy `bindings`
  reads only through a diagnosed compatibility or migration path
- inventory the top-level SDK, submodule SDKs, CLI, schemas, diagnostic codes,
  and plugin protocols as stable, provisional, experimental, or private
- decide every pre-foundation deprecation and publish the final
  removal/migration
  schedule

### Acceptance scenarios

- attempts to mutate any plan-owned mapping, sequence, descriptor, or nested
  metadata fail without changing the plan or its fingerprint
- equivalent inputs serialize byte-for-byte identically across supported
  Python versions and operating systems
- altered, corrupt, or incorrectly fingerprinted plans fail before plugin
  loading, resource acquisition, compilation, or execution
- every supported historical wire fixture either loads exactly as documented
  or produces a stable unsupported-version/migration diagnostic
- a misspelled production profile cannot resolve to a permissive default
- public profile output contains `assets`; legacy `bindings` input is explicit,
  diagnosed, and never re-emitted as current authoring guidance

### Exit gate

The authoring model, profile vocabulary, canonical plan representation, and
public wire schemas are precise enough to enter compatibility testing. No new
stable backend or control-plane surface may bypass these contracts.

## 0.20 — Trust, Isolation, and Safe I/O

**Status:** Implemented in ETLantic 0.20.0 (see
[EXIT_GATE_0_20](docs/11_DEVELOPMENT/EXIT_GATE_0_20.md)).

**Objective:** authorize plugins and external effects before executable code or
mutable resources cross the analysis boundary.

### Deliver

- split plugin handling into deterministic `discover → evaluate → authorize →
  load` phases
- define a static plugin manifest that can be inspected from distribution
  metadata without importing the plugin entry point
- evaluate package name, distribution version, protocol range, capabilities,
  allowlist, provenance, and conflicts before executable plugin loading
- record selected distribution identity, digest, provenance, protocol, and
  authorization decision in plans, reports, and security events
- diagnose duplicate names, conflicting entry points, invalid manifests, and
  package/manifest identity mismatches deterministically
- provide an optional isolated capability probe with strict time, output, and
  resource budgets; document that process isolation is containment, not a
  complete sandbox
- route contract, profile, report, schema-history, reliability, generated
  artifact, cache, checkpoint, and visualization filesystem access through one
  safe I/O policy
- enforce approved roots, normalized paths, explicit symlink behavior, special
  file rejection, bounded reads, atomic writes, overwrite policy, locking,
  integrity digests, retention, and cleanup
- isolate artifact and cache identities by run, environment, tenant, security
  domain, logical authorization, compiler fingerprint, and contract version
- implement outbound network, redirect, webhook, and remote-reference policy
  with scheme/host/address controls, timeouts, response bounds, and no ambient
  credential forwarding
- enforce unsafe-serialization prohibitions across all loaders and plugin
  boundaries
- emit versioned security and audit events without secret values or source rows
- generate release SBOMs and provenance attestations; sign release artifacts
  and use short-lived trusted publishing where supported

### Acceptance scenarios

- a disallowed installed plugin is rejected without importing its executable
  entry point
- plugin manifest tampering, version mismatch, duplicate identity, and
  provenance failure stop planning or execution with stable diagnostics
- traversal, symlink escape, special files, partial writes, oversized inputs,
  and concurrent history/report writers fail safely
- artifacts and caches from another tenant, run, environment, or security
  domain cannot be selected through identity collision or fallback
- loopback, link-local, metadata-service, private, redirected, oversized, and
  unapproved outbound targets are rejected by default
- plans, reports, diagnostics, audit events, build artifacts, and failure logs
  contain no resolved secrets or source rows

### Exit gate

Every mandatory trust and I/O control has an implementation owner, automated
verification, a stable diagnostic or event, and documented residual risk.

## 0.21 — Cohesive CLI and Authoring Experience

**Status:** Shipped in ETLantic 0.21.0.

**Objective:** make the supported workflow usable end to end without hidden
process-local setup or Python-only registration steps.

### Deliver

- define one documented journey: `init → doctor → inspect → validate → plan →
  run → report`
- add `etlantic init` for a minimal import-safe pipeline, explicit profile, and
  executable test without introducing a framework-specific project layout
- add `etlantic doctor` for read-only environment, dependency, plugin, profile,
  approved-root, and optional backend connectivity checks
- add first-class `profile validate`, `profile show`, `profile diff`, and
  `profile migrate` commands
- support declarative asset/provider configuration so durable CLI runs do not
  require application-side runtime registration
- make a durable workspace and file report store the normal CLI path; retain
  process-local operation only as an explicit ephemeral mode
- make reports written by one CLI invocation discoverable by later `report`
  commands
- standardize global output, color, verbosity, quiet, and non-interactive
  options across command groups
- assign documented exit codes for usage, invalid model, trust failure,
  planning failure, execution failure, partial run, and breaking change
- show mutation scope, resolved profile source, security mode, selected
  plugins, and write intent before mutating commands
- provide consistent dry-run/no-write behavior and explicit confirmation
  policy for destructive or externally mutating operations
- improve human diagnostics with source span, phase, explanation, remediation,
  and safe machine-readable action
- add compact `plan diff` and “why this engine, boundary, materialization, or
  fallback?” views
- make command help expose default target forms and all applicable options;
  test shell completion and help output as public UX
- publish a small recommended top-level authoring API and route advanced APIs
  through clearly owned public submodules

### Acceptance scenarios

- a new user can initialize, validate, plan, run, and inspect a durable report
  in separate shell invocations using only generated guidance
- the quickstart's primary CLI path succeeds without process-local memory
  seeding or undocumented Python registration
- every mutating command declares its target and supports a truthful preview
  where the underlying operation permits one
- human, JSON, and SARIF output agree on diagnostic identity, severity, phase,
  and result status
- help snapshots, completion tests, Windows path tests, and non-interactive CI
  examples remain stable across patch releases

### Exit gate

The CLI and Python quickstarts describe one coherent product, and durable
local workflows no longer depend on state retained inside a single process.

## 0.22 — Plugin SDK Release Candidate

**Status:** Shipped in ETLantic 0.22.0.

**Objective:** prove that the extension model is capability-driven and usable
outside the monorepo before freezing protocol `/1` surfaces.

### Deliver

- remove first-party engine-name classification and hard-coded engine sets from
  planning, execution, interchange, reporting, and visualization decisions
- derive execution family and behavior entirely from authorized protocol
  descriptors, semantic capabilities, and registered providers
- version capability vocabulary independently and publish compatibility,
  implication, conflict, and deprecation rules
- replace unconstrained public `Any` and metadata contracts with typed value
  models where interoperability or stability depends on their contents
- require each first-party plugin to pass the same public conformance package
  available to third-party authors
- expand conformance with adversarial, malformed-response, cancellation,
  cleanup, redaction, ownership, and capability-truthfulness cases
- publish a plugin compatibility report command covering core, SDK, plan
  schema, protocol, DTCS, capability, and Python-version ranges
- maintain at least one reference third-party plugin outside the monorepo to
  expose packaging, documentation, and compatibility assumptions
- document protocol evolution, optional-method negotiation, support windows,
  and the difference between protocol compatibility and production trust
- make `import etlantic as etl` the recommended application and tutorial
  import style through a deliberately curated, typed root facade
- keep common authoring and operational primitives directly available as
  `etl.Data`, `etl.Transformation`, `etl.Pipeline`, `etl.Extract`, `etl.Load`,
  `etl.Input`, `etl.Output`, `etl.Parameter`, `etl.Profile`, and
  `etl.PipelineRuntime`; do not flatten every specialized symbol into the root
- guarantee stable, discoverable namespaces such as `etl.transform`,
  `etl.dataframe`, `etl.sql`, `etl.spark`, `etl.orchestration`, `etl.viz`,
  `etl.secrets`, and `etl.testing`, using lazy loading where needed to preserve
  minimal-install behavior and prevent optional plugin imports
- retain explicit `from etlantic import ...` and public submodule imports as
  supported alternatives; migrate misplaced specialist root exports only
  through documented pre-foundation compatibility aliases
- publish and test the root-versus-namespace ownership rule in the public
  surface inventory, generated API reference, type-consumer fixtures, and
  import-time budget
- freeze protocol `/1` only after external implementation feedback and a
  release-candidate compatibility period

### Acceptance scenarios

- an unknown third-party engine name validates, plans, executes or compiles,
  reports, and visualizes solely through its descriptors and capabilities
- a plugin cannot gain behavior through a reserved name or hidden core alias
- overstated or internally inconsistent capabilities fail conformance with an
  actionable finding
- independently installed plugins can test compatibility without importing
  private underscore modules
- older compatible plugins work across the documented core range, while
  incompatible protocol or schema ranges fail before execution
- `import etlantic as etl` succeeds in a minimal installation without loading
  optional plugins, backend engines, credentials, or external resources
- the documented root primitives and subsystem namespaces are available to
  static type checkers, IDE completion, runtime introspection, and generated
  reference documentation
- alias-style, explicit root, and public submodule imports resolve to the same
  supported objects without duplicate registration or import-order changes

### Exit gate

The Plugin SDK has external proof, a compatibility policy, a conformance
contract, and no architectural dependency on the identities of first-party
plugins. The curated `etl.*` facade is typed, documented, import-safe, and
covered by the public surface and compatibility policy.

## 0.23 — Runtime Resilience and Performance Budgets

**Status:** Shipped in ETLantic 0.23.0.

**Objective:** quantify supported scale and prove correct behavior under
partial failure, concurrency, cancellation, and resource pressure.

### Deliver

- establish reproducible time and memory benchmarks for graph construction,
  validation, planning, fingerprinting, serialization, plugin discovery,
  portable compilation, reporting, and representative backend paths
- publish supported workload envelopes and enforce regression budgets in CI
- measure cross-engine interchange copies, collections, peak memory,
  conversion cost, and artifact size against declared plan evidence
- add deterministic failure injection at extract, conversion, transform,
  validation, materialization, load, report persistence, cleanup, callback,
  and outbound-event boundaries
- test cancellation and timeout behavior during reads, compilation, execution,
  writes, retries, cleanup, and report persistence
- make report, schema-history, state, and artifact persistence atomic,
  concurrency-safe, idempotent, and recoverable after process termination
- verify retry safety, duplicate-publication prevention, reconciliation, and
  partial-success semantics for every supported write mode
- test disk-full, permission, corrupt artifact, lost connection, plugin hang,
  malformed plugin output, and cleanup failure scenarios
- run real PySpark integration tests in addition to Sparkless and parse/import
  generated Airflow artifacts against every supported Airflow line
- publish measured limits rather than implying unrestricted production scale

### Acceptance scenarios

- cancellation produces bounded cleanup and one terminal report without
  duplicate committed writes
- interruption between data publication and report persistence is detected and
  recoverable without reporting a false success
- concurrent writers cannot corrupt report or schema-history stores
- benchmark regressions above the published budget fail CI or require an
  explicit reviewed budget change
- planned and observed interchange evidence agree within the documented
  measurement limits

### Exit gate

All stable reference paths have measured budgets, failure-injection coverage,
documented scale limits, and deterministic terminal-state semantics.

## 0.24 — Programmatic Authoring and Lossless JSON

**Status: shipped — 0.24.0.**

**Objective:** make every ETLantic modeling workflow available without class
declarations, and make every public semantic artifact safely, canonically, and
losslessly round-trip through JSON. An independent application must be able to
provide a complete visual pipeline builder using only public ETLantic APIs and
schemas; generating Python classes must not be required.

Class-based authoring remains a first-class convenience API. The functional
API and class API are two views over the same canonical object model; neither
may have capabilities, validation rules, identities, or runtime semantics that
the other cannot express.

### Prerequisites already shipped (0.23)

- Class authoring (`Pipeline`, `Transformation`, ports, `Extract`/`Load`) and
  lifecycle entry points that take `type[Pipeline]`
- Resolved execution IR: `etlantic.plan/1` with codecs, fingerprint, upgrade,
  and JSON Schema (`pipeline-plan.schema.json`)
- Run reports: `etlantic.run_report/1` codecs and schema
- Profile JSON load/write, ODCS / DTCS / DPCS interchange, and portable
  transform-plan IR (`dtcs.transform-plan/2`)
- Production fail-closed plugin trust, Safe I/O, and secret-free plans/reports

### Hard distinctions (do not overload)

| Artifact | Role in 0.24 |
|---|---|
| `etlantic.pipeline/1` | **New** unresolved, data-only pipeline definition (authoring complete) |
| `etlantic.plan/1` | Resolved execution IR — lossy for authoring (no parameter values, no Python `contract_type`, limited nesting) — **not** the round-trip substrate |
| ODCS / DTCS / DPCS | External interchange; may feed or emit definitions, but DPCS that regenerates Python classes is not `pipeline/1` |
| Portable transform plan | Transformation IR only; not a full pipeline definition |

### Work packages (sequenced)

#### WP1 — Canonical `PipelineDefinition` model

**In scope**

- public `PipelineDefinition` protocol and immutable data model for topology,
  ports, parameters (including values), extracts, loads, steps, nested
  subpipelines, profile refs, policies, reliability declarations, provenance,
  extensions, and stable identities
- normalize class-authored pipelines into that model without requiring the
  originating class for subsequent lifecycle calls
- declaration-independent identities (prefer published ids over
  `module:qualname` for wire documents)

**Out of scope**

- CLI JSON targets, full builder UX, schema migrations tooling

#### WP2 — `etlantic.pipeline/1` codecs and JSON Schema

**In scope**

- uniform `to_dict` / `from_dict` / `to_json` / `from_json` (+ bounded file
  helpers) for pipeline definitions
- packaged JSON Schema with explicit `schema: "etlantic.pipeline/1"`
- canonical JSON, deterministic fingerprint, golden fixtures, and
  property-based round-trip tests across supported Python versions
- unknown-field / unknown-version diagnostics; never silently discard input

**Out of scope**

- redesigning ODCS/DTCS/DPCS; executing deserialized defs beyond stub wiring
  needed for codec tests

#### WP3 — Functional authoring surface

**In scope**

- public constructors and immutable builders for data contracts,
  transformations, inputs, outputs, parameters, extracts, loads, steps,
  subpipelines, profiles, and complete pipelines
- incremental graph assembly, composition, cloning, and updates without
  metaclasses, decorators, or dynamically generated user classes
- parity tests: every documented class primitive has a functional equivalent
  with the same diagnostics and logical fingerprint

**Out of scope**

- replacing or deprecating the class API; AI-assisted authoring; LSP

#### WP4 — Lifecycle on definitions + separate resolve phase

**In scope**

- validate, inspect, plan, run, compile, generate, visualize, and diff accept
  `PipelineDefinition` (or a thin adapter) without the originating class
- reconstruct a data-only definition from JSON that enters the normal lifecycle
  after referenced implementations, providers, and plugins are resolved
- structured diagnostics for missing references, incompatible registry
  entries, and untrusted plugins

**Out of scope**

- new execution engines; weakening production `plugin_allowlist` fail-closed
  behavior

#### WP5 — Artifact codec consistency

**In scope**

- align Profile, reliability, policy, and extension codecs with the same
  unknown-field / schema-id / secret-free rules used by `pipeline/1`
- document which public semantic artifacts are wire-stable in 0.24 versus
  remaining internal

**Out of scope**

- rewriting ContractModel / ODCS / DTCS / DPCS toolkits

#### WP6 — CLI envelope and documentation

**In scope**

- export a Python-authored pipeline to `etlantic.pipeline/1` JSON
- accept a definition JSON document as a CLI TARGET (alongside `module:Class`)
- SDK and CLI round trips produce the same canonical document and diagnostics
- document the functional API as a complete authoring path (not internal graph
  helpers)
- What's New / Migration / Exit Gate 0.24

**Out of scope**

- pickle/executable payloads; embedding resolved secrets; remote federation

#### WP7 — Application and visual-builder integration contract

**In scope**

- publish a machine-readable authoring catalog for available data contracts,
  transformations, ports, parameters, portable operations, providers,
  schedulers, plugins, capabilities, profiles, policies, and reliability
  declarations
- include UI-safe metadata needed to build forms and palettes: stable
  identifiers, display names, descriptions, types, required/default state,
  constraints, enumerated choices, sensitivity markers, deprecation state,
  capability requirements, and compatible connection endpoints
- expose public, immutable edit operations for adding, removing, connecting,
  disconnecting, moving, cloning, and updating definition elements without
  rebuilding a Python class
- define stable node, port, field, and document paths for edits and diagnostics;
  validation errors include machine-readable paths and related endpoints so a
  GUI can highlight the exact control, node, or edge
- support safe incremental validation and planning previews over an in-memory
  `PipelineDefinition`, with no execution, writes, secret resolution, or plugin
  imports required for structural editing
- provide schema/capability negotiation so an application can detect which
  document versions, components, operations, and lifecycle actions the
  installed ETLantic environment supports
- provide deterministic import/export APIs suitable for undo/redo, autosave,
  source control, and collaborative application storage
- ship an independent reference visual-builder fixture or example that
  discovers the catalog, builds and edits a pipeline, renders diagnostics,
  exports canonical JSON, reloads it, and submits it to the public lifecycle
- document the application integration contract separately from any particular
  web, desktop, or notebook framework

**Out of scope**

- shipping a production GUI, hosted control plane, collaborative server, user
  authentication, or application database in ETLantic core
- allowing UI metadata or edit operations to bypass contract validation,
  plugin trust, Safe I/O, outbound, or secret-handling policy

#### WP8 — API service boundary and FastAPI reference integration

**In scope**

- ensure pipeline definitions, catalogs, edit commands, diagnostics, plans,
  run requests, run status, and public result envelopes expose
  OpenAPI-compatible JSON Schemas without application-specific encoders
- define transport-neutral request/response models for catalog discovery,
  definition CRUD payloads, edit application, validation, planning,
  compilation, generation, visualization, run submission, cancellation, and
  run/report retrieval
- provide a public application-service facade that maps those request models to
  ETLantic lifecycle operations without requiring callers to invoke class
  methods or private modules
- define stable machine-readable error envelopes, diagnostic paths, schema and
  capability negotiation headers/fields, idempotency keys, optimistic
  concurrency/version tokens, and canonical definition fingerprints
- separate quick authoring operations from potentially long-running execution:
  validate and plan may return directly within documented budgets, while run
  submission, cancellation, progress, terminal status, and report retrieval
  have explicit asynchronous job contracts
- expose policy-context hooks through which the host application supplies the
  authenticated principal's allowed tenant, environment, profile, assets,
  plugins, and lifecycle actions; client payloads cannot grant themselves
  authority
- provide a thin FastAPI reference adapter or optional integration package that
  publishes the public schemas in OpenAPI and demonstrates catalog,
  pipeline-definition, validate, plan, run, cancellation, and report endpoints
- generate and test an OpenAPI document plus a frontend client fixture against
  the FastAPI reference adapter, proving that the GUI can use generated types
  without importing Python or ETLantic internals
- document deployment boundaries for authentication, authorization, CORS,
  CSRF, rate limiting, request-size limits, persistence, queues/workers,
  WebSocket or event-stream progress, and process isolation

**Out of scope**

- making FastAPI, an ASGI server, a database, a queue, or a frontend framework
  a required dependency of ETLantic core
- providing production authentication, authorization, user management,
  collaborative editing, durable job scheduling, or hosted execution
- accepting Python source, arbitrary import paths, resolved secrets, or
  executable objects through API payloads
- replacing the production FastAPI Control API planned for 0.39–0.43; WP8
  proves the 0.24 authoring/service contract that the later control API will
  consume

### Non-goals

- replacing `etlantic.plan/1` or requiring a plan-schema reset
- treating DPCS YAML as the lossless authoring codec
- serializing Python callables, closures, import-time expressions, dataframe
  objects, sessions, connections, scheduler handles, or backend-native plans
- first-class multi-tenant control plane (0.39–0.42 incubation; 0.43
  graduation), LSP, or unrestricted enterprise production claims
- a framework-specific UI toolkit or requirement that consumers use a
  particular frontend, transport, or application architecture
- coupling the canonical application-service contract to HTTP even though
  FastAPI is the 0.24 reference adapter
- protocol `/1` freeze (remains a 0.22 RC follow-up under burn-in)

### Serialization and security boundary

- JSON contains data and stable references only
- deserialization performs no arbitrary imports, plugin loading, secret
  resolution, network access, storage access, or user-code execution
- registry and plugin resolution is a separate, policy-governed phase and
  continues to fail closed under production allowlists
- parsers enforce document-size, nesting, collection, string, and reference
  resolution limits (extend Safe I/O / interchange budgets)
- canonical JSON is deterministic and secret-free; source formatting and Python
  class syntax are not part of the round-trip guarantee
- hostile documents, executable payloads, unresolved references, and plaintext
  secrets fail closed without partial pipeline construction

### Acceptance scenarios

- a user can author and run a representative multi-source, multi-output,
  parameterized pipeline using functions and immutable builders without
  declaring an ETLantic class
- every documented class-based authoring primitive has a documented functional
  equivalent with the same diagnostics and resulting logical fingerprint
- equivalent class-authored and functionally authored pipelines normalize to
  semantically equivalent logical graphs and byte-identical canonical JSON
- `pipeline → JSON → PipelineDefinition → JSON` is byte-stable and preserves
  the logical fingerprint across supported Python versions
- a deserialized pipeline validates and plans without the original Python
  pipeline class
- a deserialized pipeline runs when all referenced implementations, providers,
  and plugins are present and trusted, and fails with structured diagnostics
  when they are not
- ODCS, DTCS, and DPCS bundles generated before and after a JSON round trip are
  semantically equivalent
- unknown future schema versions, hostile documents, executable payloads,
  unresolved references, and secret values fail closed without partial
  construction
- CLI and SDK round trips produce the same canonical document and diagnostics
- an independently implemented visual builder can discover an authoring
  catalog, render suitable controls, assemble and edit a complete pipeline,
  connect only compatible ports, and show validation diagnostics on the
  responsible fields, nodes, and edges using public APIs
- the visual builder can autosave canonical JSON, reload it without semantic
  loss, continue editing, and submit the definition to validation, planning,
  compilation, generation, visualization, and execution without generating or
  importing a pipeline class
- catalog and definition version negotiation lets the visual builder reject or
  degrade unsupported features explicitly rather than silently losing them
- a FastAPI application can expose the complete GUI-facing workflow using the
  public service facade and publish an OpenAPI document from ETLantic's schemas
  without handwritten duplicate request models or custom serialization
- a generated frontend client can discover components, create and edit a
  pipeline, validate and plan it, submit and cancel a run, observe terminal
  status, and retrieve its report using only documented API envelopes
- malformed, oversized, stale, unauthorized, untrusted, and
  version-incompatible API requests fail with stable error/diagnostic envelopes
  and cannot trigger partial mutation, secret resolution, plugin import, or
  execution before policy authorization

### Exit gate

ETLantic has one canonical, data-only pipeline definition equally authorable
through classes, functions, and JSON. All in-scope public semantic state has a
versioned JSON representation and supported reverse conversion.
`PipelineDefinition` enters validate → plan → compile/generate/viz/run without
access to its originating class, while executable code and secrets remain
outside serialization. WP1–WP8 acceptance scenarios and docs gates pass. The
independent visual-builder fixture proves the WP7 integration contract, and
the FastAPI/OpenAPI reference proves WP8, without privileged access to ETLantic
internals.

## 0.25 — Compatibility Burn-In (First Slice)

**Status: shipped in 0.25.0.**

**Objective:** prove that the contracts shipped through 0.24 — especially
`etlantic.pipeline/1`, plan/report codecs, and Plugin SDK `/1` protocols —
can survive a real minor upgrade without a wire-schema reset. 0.25 is the
first named slice of the broader compatibility burn-in band; **0.26** is the
second slice; **0.27** is the third; **0.28** is the fourth (quadruple-minor
window plus Plugin `/1` freeze and Medallantic M0 closeout); **0.29–0.35**
preserve co-evolution discipline while ETLantic and Medallantic advance feature
parity, followed by joint burn-in in **0.37** toward the 0.37 stable foundation.

This is **not** a control-plane, GUI, or new-engine milestone. Data
connectivity (0.38), FastAPI (0.39), registry/workspaces (0.40), and
TransformationModel incubation (0.52) remain post-foundation phases.

### Prerequisites already shipped (0.24)

- Canonical `PipelineDefinition` and lossless `etlantic.pipeline/1`
- Definition lifecycle (validate / plan / run / …) without originating classes
- Authoring catalog, `EditCommand`s, service facade, `etlantic-fastapi` reference
- Plugin SDK `/1` freeze-eligible (0.22 RC; freeze decision is a 0.25 deliverable)
- Frozen-style plan/report/capabilities/interchange schemas from earlier minors

### Work packages

#### WP1 — `etlantic.pipeline/1` upgrade fixtures

**In scope**

- golden old-reader/new-writer and new-reader/old-writer fixtures for
  `etlantic.pipeline/1`
- intentional break → documented migration helper (no silent field drops)
- CI gate that fails on unversioned incompatible changes to the definition codec

**Out of scope**

- redesigning the authoring model; new edit UX beyond fixture needs

#### WP2 — Cross-artifact codec matrix

**In scope**

- the same reader/writer fixture discipline for `etlantic.plan/1`,
  `etlantic.run_report/1`, profile JSON, and (where already versioned)
  `etlantic.capabilities/1` / `etlantic.interchange/1`
- document supported schema ranges and unsupported downgrade behavior

**Out of scope**

- replacing `etlantic.plan/1`; expanding interchange Gate B

#### WP3 — Plugin SDK `/1` freeze evidence

**In scope**

- close the 0.22 freeze-eligible checklist: external plugin conformance
  (`etlantic-plugin-echo` + documented third-party path), packaging/manifest
  gates, and “no provisional core protocol” on the stable-foundation path
- record an explicit freeze **or** publish remaining blockers

**Out of scope**

- new plugin protocols (Storage / Resource / Observability catalogs stay future)

#### WP4 — Stable-foundation removal inventory

**In scope**

- catalog ambiguous aliases and pre-foundation compatibility shims
- each candidate gets a removal ticket and migration note (no new indefinite
  aliases)

**Out of scope**

- performing the stable-foundation removals in 0.25 (inventory and discipline
  only)

#### WP5 — Bounded authoring polish (fixture-driven only)

**In scope**

- functional parity edge cases and nested-subpipeline edit gaps called out in
  [Exit gate 0.24](docs/11_DEVELOPMENT/EXIT_GATE_0_24.md), **only** where they
  block upgrade/parity evidence

**Out of scope**

- new product UX, production GUI hosts, AI-assisted authoring

### Non-goals

- first-class multi-tenant control plane (0.39–0.42 incubation; 0.43 graduation)
- tenant/workspace registry and durable submission/state (0.40–0.41)
- shipping a GUI, LSP, or AI authoring surface
- new engines/orchestrators, expanded streaming, DataFusion graduation
- replacing `etlantic.plan/1` or requiring a wire-schema reset

### Acceptance scenarios

- CI exercises a documented **0.24 → 0.25** upgrade path for
  `etlantic.pipeline/1` with old↔new reader/writer fixtures green
- at least one additional versioned artifact (plan or run report) has the same
  fixture discipline in CI
- Plugin SDK `/1` freeze decision is recorded (freeze or explicit blockers)
- a published “stable-foundation removal candidates” list exists; no new
  silent keep-forever
  aliases land in 0.25
- What's New / Migration 0.24→0.25 / Exit Gate 0.25 pass docs gates

### Exit gate

0.25.0 ships with upgrade fixtures for `pipeline/1` (and at least one sibling
artifact), a Plugin SDK `/1` freeze decision on record, a stable-foundation
removal
inventory, and migration/docs gates. No wire-schema reset. Control plane and
GUI remain out of scope.

## 0.26 — Compatibility Burn-In (Second Slice)

**Status: shipped in 0.27.0.**

**Objective:** prove **two consecutive** minor upgrade paths without a
wire-schema reset (**0.24 → 0.25** and **0.25 → 0.26**), close remaining
freeze/fixture gaps from 0.25, and execute the first wave of stable-foundation
removal
candidates with migrations — not a control-plane or GUI milestone.

### Prerequisites from 0.25

- Documented `0.24 → 0.25` upgrade path with `pipeline/1` (and sibling)
  reader/writer fixtures in CI
- Plugin SDK `/1` freeze decision recorded (freeze **or** published blockers)
- Published stable-foundation removal inventory (tickets + migration notes; no
  removals yet)

### Work packages

#### WP1 — Second consecutive upgrade path

**In scope**

- golden old↔new fixtures for **0.25 → 0.26** across every schema/protocol
  range covered in 0.25
- CI gate that treats an undocumented incompatible change as a release blocker
- document unsupported downgrade behavior for the dual-minor window

**Out of scope**

- schema resets; inventing new wire formats

#### WP2 — Complete public wire fixture matrix

**In scope**

- finish old-reader/new-writer coverage for any public versioned artifact still
  missing after 0.25 (plan, run report, profile, capabilities, interchange,
  authoring catalog envelopes as applicable)
- single inventory table of supported schema ranges in docs/reference

**Out of scope**

- Gate B / DataFusion graduation; new interchange physical boundaries

#### WP3 — Freeze closure

**In scope**

- if 0.25 froze Plugin SDK `/1`: lock conformance suite versions and reject
  provisional core protocol drifts
- if 0.25 left blockers: clear them or re-scope with an explicit 0.27+ plan
  (no silent “freeze-eligible forever”)

**Out of scope**

- new Storage / Resource / Observability protocol catalogs

#### WP4 — First-wave stable-foundation removal execution

**In scope**

- remove or hard-deprecate the highest-priority inventory items with
  migrations, diagnostics, and What's New / Migration 0.25→0.26 notes
- keep the inventory current; no new indefinite aliases

**Out of scope**

- completing the entire stable-foundation removal list (later burn-in / 0.37)

#### WP5 — Authoring parity completion (bounded)

**In scope**

- close remaining class ↔ functional parity edge cases and nested-subpipeline
  edit gaps that were deferred in 0.25 as non-blocking
- keep parity fingerprints in CI

**Out of scope**

- production GUI, LSP, AI authoring, or the 0.39–0.43 control plane

### Non-goals

- first-class multi-tenant control plane (0.39–0.42 incubation; 0.43 graduation)
- tenant/workspace registry and durable submission/state (0.40–0.41)
- shipping a GUI, LSP, or AI authoring surface
- new engines/orchestrators, expanded streaming, DataFusion graduation
- replacing `etlantic.plan/1` or requiring a wire-schema reset

### Acceptance scenarios

- CI proves **0.24 → 0.25** and **0.25 → 0.26** without a wire-schema reset
- public wire schemas in the 0.26 inventory have old↔new fixtures (or an
  explicit “N/A / not versioned” rationale)
- Plugin SDK `/1` is frozen, or remaining blockers are cleared/rescheduled
  with owners
- at least one inventory removal/hard-deprecation ships with a migration path
- What's New / Migration 0.25→0.26 / Exit Gate 0.26 pass docs gates

### Exit gate

0.26.0 ships the second consecutive upgrade proof, a completed public wire
fixture matrix (or documented exceptions), freeze closure, first-wave
deprecation execution, and migration/docs gates. Control plane and GUI remain
out of scope.

## 0.27 — Compatibility Burn-In (Third Slice)

**Status: shipped in 0.27.0.**

**Objective:** prove a **triple-minor** upgrade window without a wire-schema
reset (**0.25 → 0.26 → 0.27**), close the Plugin SDK `/1` freeze external
feedback blocker (or re-scope again with owners), and execute the second wave
of stable-foundation removal candidates — not a control-plane or GUI
milestone.

### Prerequisites from 0.26

- Dual-minor burn-in fixtures (`v0_24/` + `v0_25/`) green in CI
- Plugin SDK `/1` freeze re-scoped to 0.27 with published external feedback
  blocker ([PROTOCOL_EVOLUTION.md](docs/07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md))
- First-wave root alias removals shipped; remaining inventory current
  ([REMOVAL_CANDIDATES_0_37.md](docs/11_DEVELOPMENT/REMOVAL_CANDIDATES_0_37.md))

### Work packages

#### WP1 — Triple-minor upgrade path

**In scope**

- golden fixtures under `tests/fixtures/burn_in/**/v0_26/` proving
  **0.26 → 0.27** across every schema/protocol range covered in the dual-minor
  window
- keep `v0_25/` (and documented prior trees as required by wire ranges) loadable
  so CI proves **0.25 → 0.26 → 0.27** without a wire-schema reset
- update [WIRE_SCHEMA_RANGES.md](docs/10_REFERENCE/WIRE_SCHEMA_RANGES.md) and
  burn-in check scripts for the triple-minor window
- document unsupported downgrade behavior for the expanded window

**Out of scope**

- schema resets; inventing new wire formats

#### WP2 — Protocol `/1` freeze closure

**In scope**

- clear the ≥1 non-first-party plugin-author external feedback blocker
  (echo CI alone remains insufficient per Exit Gate 0.22 / 0.26 notes), **or**
  re-scope freeze again with dated owners and rationale — no silent
  “freeze-eligible forever”
- if frozen: lock conformance suite versions and reject provisional core
  protocol drifts

**Out of scope**

- new Storage / Resource / Observability protocol catalogs

#### WP3 — Second-wave stable-foundation removal execution

**In scope**

- execute `REM-RELIABILITY-ROOT` (~12 reliability declaration types) with
  migrations, diagnostics, and What's New / Migration 0.26→0.27 notes
- remove a bounded next wave of remaining `REM-ROOT-DEMOTED` symbols
  (prefer high-traffic owning modules still demoted after 0.26 — e.g.
  schema_drift, registry, sql, profile — exact list in PR + inventory update)
- keep the inventory Target column current; no new indefinite aliases

**Out of scope**

- completing the entire stable-foundation removal list (later burn-in / 0.37)
- curated root facade and lazy namespaces

#### WP4 — Wire matrix maintenance

**In scope**

- keep old-reader/new-writer and new-reader/old-writer coverage green for every
  public versioned artifact in the 0.27 inventory (or explicit N/A rationale)
- refresh codec burn-in matrix digests for `v0_26/` alongside existing trees

**Out of scope**

- Gate B / DataFusion graduation; new interchange physical boundaries

#### WP5 — Trust / docs residuals (bounded)

**In scope**

- fold any residual trust, allowlist, or diagnostics hygiene follow-ons from
  the 0.26 harden pass that are release-blocking for 0.27
- What's New / Migration 0.26→0.27 / Exit Gate 0.27 pass docs gates

**Out of scope**

- first-class multi-tenant control plane / GUI / LSP / AI authoring

### Non-goals

- first-class multi-tenant control plane (0.39–0.42 incubation; 0.43 graduation)
- tenant/workspace registry and durable submission/state (0.40–0.41)
- shipping a GUI, LSP, or AI authoring surface
- new engines/orchestrators, expanded streaming, DataFusion graduation
- replacing `etlantic.plan/1` or requiring a wire-schema reset

### Acceptance scenarios

- CI proves **0.25 → 0.26 → 0.27** without a wire-schema reset
- Plugin SDK `/1` is frozen, or remaining blockers are cleared/rescheduled
  with owners and a dated rationale
- `REM-RELIABILITY-ROOT` (and the chosen demoted-alias wave) ship with
  migration paths
- public wire schemas in the 0.27 inventory have old↔new fixtures (or
  documented N/A)
- What's New / Migration 0.26→0.27 / Exit Gate 0.27 pass docs gates

### Exit gate

0.27.0 ships the triple-minor upgrade proof, freeze closure (or explicit
re-scope), second-wave deprecation execution, wire matrix maintenance, and
migration/docs gates. Control plane and GUI remain out of scope.

Tracking: [EXIT_GATE_0_27.md](docs/11_DEVELOPMENT/EXIT_GATE_0_27.md).

## 0.28 — Burn-In (Fourth Slice), Plugin Freeze, and Medallantic M0 Closeout

**Medallantic phase:** M0 closeout (rename and release hygiene largely shipped in
**0.27.0**).

**Status:** Shipped in ETLantic **0.28.0**.

**Objective:** prove a **quadruple-minor** upgrade window without a wire-schema
reset (**0.26 → 0.27 → 0.28**), **close** the Plugin SDK `/1`
freeze (carried from 0.22–0.27), finish Medallantic **M0** exit criteria, and
execute the **third wave** of `REM-ROOT-DEMOTED` removals — while keeping
native medallion authoring (**M1**) and facade conformance for **0.29**.

This is **not** native `MedallionPipeline` authoring, quality-rule parity, or a
control-plane / GUI milestone.

### Prerequisites from 0.27 (satisfied)

- Triple-minor burn-in fixtures (`v0_26/`) green in CI
- `medallantic` distribution published; workspace, docs, CI, release, and
  `etlantic[medallantic]` extra aligned
- Final `etlantic-sparkforge` compatibility redirect wheel published (depends
  on `medallantic`); SparkForge conversion helpers retained on `medallantic`
  migration surfaces
- Plugin SDK `/1` freeze **closed in 0.28.0**
  ([PROTOCOL_EVOLUTION.md](docs/07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md);
  [EXTERNAL_PLUGIN_FEEDBACK.md](docs/11_DEVELOPMENT/EXTERNAL_PLUGIN_FEEDBACK.md))
- Second-wave root removals shipped (reliability, schema_drift, registry);
  ~36 demoted root aliases remain after the 0.28 third wave
  ([REMOVAL_CANDIDATES_0_37.md](docs/11_DEVELOPMENT/REMOVAL_CANDIDATES_0_37.md))

### Work packages

#### WP1 — Quadruple-minor upgrade path

**In scope**

- golden fixtures under `tests/fixtures/burn_in/**/v0_27/` proving
  **0.27 → 0.28** across every schema/protocol range in the triple-minor window
- keep `v0_26/` (and documented prior trees per wire ranges) loadable so CI
  proves **0.26 → 0.27 → 0.28** without a wire-schema reset
- update [WIRE_SCHEMA_RANGES.md](docs/10_REFERENCE/WIRE_SCHEMA_RANGES.md) and
  burn-in check scripts for the quadruple-minor window
- document unsupported downgrade behavior for the expanded window

**Out of scope**

- schema resets; inventing new wire formats

#### WP2 — Protocol `/1` freeze closure (owned by 0.28)

**In scope**

- satisfy the ≥1 documented external feedback cycle from a non-first-party
  plugin author (echo CI alone remains insufficient), **or** re-scope freeze
  again with dated owners and rationale — no silent “freeze-eligible forever”
- if frozen: lock conformance suite versions, publish freeze record, and reject
  provisional core protocol drift in CI
- align [BUILDING_A_PLUGIN.md](docs/07_PLUGIN_SDK/BUILDING_A_PLUGIN.md),
  [PROTOCOL_EVOLUTION.md](docs/07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md), and
  surface inventory with the decision

**Out of scope**

- new Storage / Resource / Observability protocol catalogs (post-freeze or
  later 0.x)

#### WP3 — Third-wave `REM-ROOT-DEMOTED` execution

**In scope**

- remove a bounded third wave of high-traffic demoted root aliases (priority:
  `etlantic.sql`, `etlantic.profile`, `etlantic.lifecycle`, then remaining
  clusters per inventory snapshot)
- migration notes, What's New / Migration 0.27→0.28, and diagnostics for each
  removed symbol group
- keep the inventory Target column current; no new indefinite root aliases

**Out of scope**

- completing the entire stable-foundation removal list
  (`REM-DATACONTRACTMODEL`, experimental
  graduation, Prefect MVP expansion)
- curated root facade and lazy namespaces

#### WP4 — Medallantic M0 closeout

**In scope**

- decide and document whether a final **`etlantic-sparkforge` compatibility
  redirect** wheel ships (depends on `medallantic`, emits deprecation warning)
  or migration docs-only
- reserve PyPI project names / trusted publishing hygiene for `medallantic`
  (first publish landed in 0.27; 0.28 confirms ongoing release evidence)
- publish facade-package guidance: medallion vocabulary stays in Medallantic;
  core wire schemas gain no bronze/silver/gold identifiers
- green Medallantic adapter parity suite on every release matrix job

**Out of scope**

- `MedallionPipeline` / native builder surfaces (**0.29 / M1**)
- live SparkForge `PipelineBuilder` bridge (**0.32 / M4**)

#### WP5 — First-party facade boundary (ETLantic)

**In scope**

- codify **facade package** as a release category distinct from execution,
  compiler, scheduler, storage, and model-bridge plugins
- extend release gates (SBOM, provenance, wheel smoke, compatibility pins) for
  facade packages alongside execution plugins
- document which public authoring/plan APIs facades may call; block private
  adapter shortcuts in conformance guidance
- optional: stub **facade conformance kit** requirements that M1 enforced (shipped in 0.29.0)
  (definition round-trip, graph equivalence hooks)

**Out of scope**

- promoting medallion types into `etlantic.pipeline/1` or plan wire metadata

### Non-goals

- native medallion authoring (**0.29**), portable quality rules (**0.30**),
  execution/materialization parity (**0.31**)
- first-class multi-tenant control plane (0.39–0.42 incubation; **0.43**
  graduation)
- tenant/workspace registry and durable submission/state (**0.40–0.41**)
- GUI, LSP, or AI authoring surfaces
- new engines/orchestrators, DataFusion graduation, expanded streaming
- replacing `etlantic.plan/1` or requiring a wire-schema reset

### Acceptance scenarios

- CI proves **0.26 → 0.27 → 0.28** without a wire-schema reset
- Plugin SDK `/1` is **frozen** or explicitly re-scoped with owners and rationale
- third-wave root removals ship with migration paths
- `medallantic` installs, imports, and passes adapter parity without PySpark or
  SparkForge; core installs without Medallantic
- public wire schemas in the 0.28 inventory have old↔new fixtures (or documented
  N/A)
- What's New / Migration 0.27→0.28 / Exit Gate 0.28 pass docs gates

### Exit gate

0.28.0 ships the quadruple-minor upgrade proof, Plugin SDK `/1` freeze closure
(or dated re-scope), third-wave deprecation execution, Medallantic M0 closeout,
and facade-package release discipline. Native medallion authoring shipped in
**0.29**.

Tracking: [EXIT_GATE_0_28.md](docs/11_DEVELOPMENT/EXIT_GATE_0_28.md).

## 0.29 — Native Medallion Authoring

> **Status: Shipped in ETLantic 0.29.0.**

**Medallantic phase:** M1 — Native medallion authoring.

**Objective:** prove that an opinionated domain facade can construct complete,
portable ETLantic definitions without a parallel execution model.

### Medallantic deliverables

- native `MedallionPipeline`, builder, and bronze/silver/gold authoring
  surfaces
- fluent and declarative/serialized definitions
- partial pipelines, branches, typed prior-result references, cross-schema
  assets, descriptions, tags, deterministic names, and stable diagnostics
- SparkForge IR isolated under a migration namespace

### ETLantic evolution

- harden `PipelineDefinition` as the supported lowering target for external
  facades, including deterministic extension metadata and source attribution
- add a facade conformance kit for definition construction, round-trip
  serialization, graph equivalence, diagnostics, and plan determinism
- generalize typed multi-input/multi-output and partial-graph authoring where
  Medallantic reveals domain-neutral gaps
- add namespaced extension points for facade annotations that survive
  validation, planning, reports, and lineage without changing core meaning
- ensure public builder/edit APIs can express the complete Medallantic graph
  without private imports

### Joint exit gate

Representative SparkForge pipelines can be authored natively in Medallantic,
round-trip through ETLantic's public definition schema, and produce
deterministic, semantically equivalent graphs and plans without SparkForge or
an execution backend installed.

Tracking: [EXIT_GATE_0_29.md](docs/11_DEVELOPMENT/EXIT_GATE_0_29.md).

## 0.30 — Portable Quality and Rule Semantics

**Medallantic phase:** M2 — Quality and rules parity.

**Status:** Shipped in ETLantic **0.31.0**.

**Objective:** turn the common portion of legacy Spark and SQL validation rules
into portable, contract-backed semantics while preserving explicit native
escape hatches and failing closed at plan time when a required rule is
unsupported.

This is **not** execution/materialization parity (**0.31**), native PySpark
Column / Moltres-only expressions (**0.32 / 0.33**), or quality-trend analytics
(**0.34**).

### Protocol and engine decisions

- **Protocol home:** ETLantic ships a provisional versioned quality-expression
  envelope (`etlantic.quality/1`). ContractModel remains the **semantic
  authority** for field and constraint meaning; every portable rule must map
  to ContractModel-compatible constraints or an explicit custom-contract
  check. Joint ownership is documented; ContractModel may later absorb or
  align the expression schema. **0.30 does not block** on ContractModel
  shipping a full bounded-validation protocol first.
- **Engine exit bar:** live lowering and shared conformance on **Polars and
  Pandas** (plus the existing local ContractModel row-validation path) for
  the portable core rule set. **SQL and PySpark** must advertise rule
  capabilities and **fail closed at plan/analysis** when a required rule is
  unsupported; live SQL/PySpark compilers for the portable core are in scope
  when cheap, but incomplete live coverage is allowed when classified in
  Medallantic docs and gated in CI. Native PySpark Column / Moltres expression
  rules remain **0.32 / 0.33**.

### Prerequisites from 0.29 (satisfied)

- Native `MedallionPipeline` / builder / Bronze·Silver·Gold authoring shipped
- Facade conformance kit (`etlantic.testing.facade`) green
- Medallantic `rules=` retained as opaque bags with `MDL110` / `MDL111`
  (unenforced passthrough; portable rules deferred to this milestone)
- Layer accept-rate thresholds mapped into `ValidationPolicy.metadata` only
- Typed `Output.as_invalid()` ports, `invalid_row_separation`, and
  `ValidationResult` hooks exist without a portable rule DSL

### Work packages

#### WP1 — Provisional `etlantic.quality/1` (ETLantic)

**In scope**

- versioned quality-expression AST and JSON Schema for the portable core:
  `not_null`, comparisons, membership, range, regex, length, uniqueness, and
  `custom_contract`
- deterministic serialization and identity/fingerprint rules for expressions
- map every portable node onto ContractModel-compatible constraints or an
  explicit custom-contract check; forbid a parallel schema/rule vocabulary
- document joint ownership with ContractModel and the provisional status of
  `etlantic.quality/1`

**Out of scope**

- waiting for ContractModel 0.3 bounded-validation protocol
- engine-native Column / Moltres expression ASTs as portable nodes
- medallion layer names or thresholds inside the quality schema

#### WP2 — Quality-gate planning (ETLantic)

**In scope**

- strengthen plans for typed accepted / rejected / observed outputs (building
  on existing port roles and `invalid_row_separation`)
- declare rule capability requirements, validation cost, and fallback evidence
  on the plan
- fail unsupported **required** rules during analysis/planning, before data
  access or target mutation, with stable diagnostics
- preserve reserved plan hooks such as `validation_boundary` where they aid
  collection and explain

**Out of scope**

- validation-only run intents and write/materialization lifecycle (**0.31**)
- changing `etlantic.plan/1` major version or resetting the wire schema

#### WP3 — Conformance fixtures and engine lowering (ETLantic + plugins)

**In scope**

- engine-independent quality conformance fixtures and normalized result
  assertions (decisions, accepted/rejected counts, reasons, diagnostics)
- live Polars and Pandas compilers for the portable core, plus the local
  ContractModel row-validation path
- SQL and PySpark: capability vocabulary participation and plan-time
  fail-closed fixtures; live portable-core subset when present and classified
- every engine that **advertises** a rule must pass the shared fixtures for
  that rule

**Out of scope**

- full live parity of every portable rule on SQL and PySpark as a hard exit
  requirement
- native PySpark Column / Moltres-only rules as portable (**0.32 / 0.33**)

#### WP4 — Medallantic rule DSL and layer policy (Medallantic)

**In scope**

- engine-neutral shorthand DSL → `etlantic.quality/1` AST for common rules
- named per-layer quality defaults and per-step overrides
- replace `MDL110` unenforced passthrough with real quality-gate lowering onto
  public ETLantic definitions
- compare layer accept-rate thresholds against validation outcomes where the
  named medallion policy requires it
- keep bronze/silver/gold vocabulary and threshold ownership in Medallantic

**Out of scope**

- promoting medallion types into `etlantic.pipeline/1` or plan wire metadata
- execution of legacy transform callables (**0.31**)
- live SparkForge `PipelineBuilder` bridge (**0.32**)

#### WP5 — Docs and release gates

**In scope**

- What's New in 0.30, Migration 0.29→0.30, and
  [Exit gate 0.30](docs/11_DEVELOPMENT/EXIT_GATE_0_30.md)
- Medallantic compatibility matrix classifying portable vs native-only vs
  deferred (SQL/PySpark live coverage called out explicitly)
- surface inventory / wire-range notes for `etlantic.quality/1` without a
  plan-schema reset

**Out of scope**

- first-class multi-tenant control plane / GUI / LSP / AI authoring
- quality-trend / anomaly analytics providers (**0.34**)

### Non-goals

- execution, state, and materialization parity (**0.31**)
- native PySpark Column / Moltres-only expressions as portable
  (**0.32 / 0.33**)
- trend, quality, and anomaly analytics consumers (**0.34**)
- first-class multi-tenant control plane (0.39–0.42 incubation; **0.43**
  graduation)
- tenant/workspace registry and durable submission/state (**0.40–0.41**)
- GUI, LSP, or AI authoring surfaces
- replacing `etlantic.plan/1` or requiring a wire-schema reset
- a second schema/rule system outside ContractModel authority
- blocking 0.30 on ContractModel releasing a full validation protocol first

### Acceptance scenarios

- shared fixtures produce contract-equivalent decisions, accepted/rejected
  artifacts, counts, reasons, and diagnostics on every engine that advertises
  a given portable rule
- unsupported required rules fail at plan/analysis with stable diagnostics and
  never silently pass
- Polars and Pandas (plus local ContractModel validation) are green for the
  portable core rule set
- SQL and PySpark either lower the portable core live or advertise + fail
  closed, with coverage classified in Medallantic docs and gated in CI
- Medallantic shorthand lowers to `etlantic.quality/1`; layer thresholds remain
  Medallantic policy; native-only expressions are capability-gated
- What's New / Migration 0.29→0.30 / Exit Gate 0.30 pass docs gates

### Exit gate

0.30.0 ships provisional `etlantic.quality/1`, quality-gate planning with
plan-time fail-closed capability negotiation, engine-independent conformance
fixtures with Polars/Pandas live coverage for the portable core, Medallantic
rule DSL and layer-policy enforcement (replacing `MDL110` passthrough), and
docs/compatibility classification for SQL/PySpark and native escape hatches.
Medallion vocabulary stays out of core wire schemas. ContractModel remains
semantic authority; no second rule system.

Tracking: [EXIT_GATE_0_30.md](docs/11_DEVELOPMENT/EXIT_GATE_0_30.md).

## 0.31 — Execution, State, and Materialization Semantics

**Medallantic phase:** M3 — Execution and materialization parity.

**Status:** Shipped in ETLantic **0.31.0**.

**Objective:** exercise ETLantic's runtime with real medallion lifecycle
semantics and promote any reusable reliability primitives exposed by that use.

### Medallantic deliverables

- callable transforms through ETLantic implementation references
- standard, initialize, incremental, refresh, and validation-only runs
- watermark/cursor state mapping
- append, replace, keyed merge, skip-if-exists, and partition-replace intents
- explicit bronze preservation, silver refresh, and gold publication defaults
- normalized run, layer, step, validation, artifact, write, and state results

### ETLantic evolution

- complete atomic state-transition and checkpoint contracts, including
  commit-after-materialization and failed/no-write non-advancement guarantees
- refine portable write and materialization intents for keyed merge,
  partition replacement, atomic publication, and skip-if-exists
- make idempotency, retry safety, transaction scope, mutation order, and
  unknown commit outcomes explicit in plans and reports
- generalize layer-independent lifecycle policy composition so a facade can
  supply defaults without core knowing bronze/silver/gold
- expand cross-engine runtime conformance around state, failure, cancellation,
  retry, and partial-result behavior

### Joint exit gate

The same Medallantic definition passes normalized lifecycle fixtures on local,
Polars, Pandas, SQL, and PySpark where capabilities are advertised; unsupported
write/state semantics fail before mutation; ETLantic core contains only
domain-neutral policies.

## 0.32 — PySpark and Delta Differential Parity

**Medallantic phase:** M4 — PySpark/SparkForge parity.

**Status:** Shipped in ETLantic **0.32.0**.

**Objective:** use the legacy Spark builder as a differential corpus to harden
distributed execution and storage capability boundaries.

### Medallantic deliverables

- live `PipelineBuilder` migration bridge
- PySpark Column rules and callable transforms
- explicit real-PySpark and Sparkless test modes
- run-one, run-until, no-write, overrides, rerun, and downstream invalidation
- Delta merge, optimize, vacuum, history, schema evolution, and time travel
  through declared plugins
- fixture-by-fixture compatibility classifications

### ETLantic evolution

- strengthen Spark implementation-reference, session/resource, metrics,
  cancellation, cache, and artifact-lifetime protocols
- add a storage-capability vocabulary for Delta operations without making
  Delta a core dependency or treating maintenance commands as generic writes
- generalize catalog/schema mutation authorization, JDBC/asset bindings, and
  cross-schema planning where the behavior is portable
- extend debug/invalidation provenance so fused or distributed artifacts
  retain logical-step identity
- publish differential-test hooks that compare normalized semantics rather
  than backend dataframe objects

### Joint exit gate

Every supported SparkForge `pipeline_builder` fixture is classified as
equivalent, explicitly plugin-dependent, or intentionally rejected; live
PySpark and Delta suites pass their advertised semantics; no Spark or Delta
dependency enters ETLantic core.

Tracking: [EXIT_GATE_0_32.md](docs/11_DEVELOPMENT/EXIT_GATE_0_32.md).

## 0.33 — SQLAlchemy and Relational Differential Parity

**Status: shipped in 0.33.0.**

**Medallantic phase:** M5 — SQL pipeline-builder parity.

**Objective:** use the legacy SQL builder to harden ETLantic's relational,
transaction, catalog, and async execution contracts without creating a SQL
pipeline type.

### Medallantic deliverables

- live `SqlPipelineBuilder` migration bridge
- migration support for Moltres, SQLAlchemy ORM, `Select`, and compound selects
- lazy relational step reuse without mandatory table round-trips
- model-driven table creation and primary-key validation
- sync/async execution, rollback behavior, and dialect support tiers
- differential suites for SQLite and PostgreSQL

### ETLantic evolution

- refine relation/artifact references so adjacent SQL steps can reuse a CTE,
  subquery, temporary relation, or durable artifact according to the plan
- promote reusable model-to-contract/catalog mapping through the SQLModel and
  SQL plugin boundaries
- complete async transaction, rollback, connection-loss, and unknown-outcome
  conformance
- strengthen dialect capability declarations for DDL, merge, isolation,
  returning, compound selects, duplicate columns, and identifier handling
- add planner evidence for fusion barriers, table recreation, schema
  mutation, and transaction scopes

### Joint exit gate

The SQL parity matrix passes on SQLite and PostgreSQL, additional dialect
claims are accurately gated, failures preserve transaction guarantees, and
one Medallantic authoring model serves SQL and non-SQL engines.

Tracking: [EXIT_GATE_0_33.md](docs/11_DEVELOPMENT/EXIT_GATE_0_33.md).

## 0.34 — Operations, Evidence, and Production Readiness

**Status:** Shipped in ETLantic 0.34.0.

**Medallantic phase:** M6 — Operations, observability, and production
readiness.

**Objective:** prove that a first-party facade can meet ETLantic's production
envelope with complete evidence and no storage-specific observability in core.

### Medallantic deliverables

- medallion-oriented plan/run explanation
- layer-aware lifecycle views over normalized ETLantic events
- durable run-history provider conformance
- optional trend, quality, performance, and anomaly consumers
- development, testing, and production profile templates
- published compatibility, security, performance, and support tiers

### ETLantic evolution

- stabilize observability-provider and event-consumer protocols required for
  durable run history and derived analytics
- complete correlation across logical steps, physical regions, attempts,
  remote jobs, writes, state transitions, and facade annotations
- extend profile composition so facades can provide inspectable defaults while
  production trust, allowlists, mutation, and redaction policies remain
  authoritative
- add production conformance for concurrency, cancellation, timeout,
  recovery, redaction, schema mutation, and bounded metrics
- expose evidence queries and report extensions without coupling core to a
  log-table schema

### Joint exit gate

Medallantic satisfies ETLantic's documented production profile and security
requirements; all fallback and mutation behavior is planned and reported; run
history and analytics remain optional providers/consumers.

## 0.35 — Migration Completion and Joint Freeze

**Status:** Shipped (exit gate closed in-tree; tag when release CI is green).

**Medallantic phase:** M7 — Migration completion.

**Objective:** complete both legacy builder migrations and freeze the
ETLantic/Medallantic boundary before the final compatibility-burn-in window.

### Medallantic deliverables

- automated SparkForge project inventory and migration report
- safe generation of native Medallantic definitions
- stable diagnostics for manual migration points
- golden before/after plans and normalized reports
- versioned deprecation timeline for legacy imports and serialized IR
- no transitional adapter removal before a documented major release

### ETLantic evolution

- provide public, bounded definition-inspection and rewrite APIs needed by
  migration tooling
- add public application-pipeline testing helpers in `etlantic.testing` for
  static logical inputs, expected normalized outputs, fake providers,
  deterministic clocks/identities, plan/report snapshots, and bounded fault
  scenarios without contacting production systems
- stabilize facade protocol/version compatibility and generated-definition
  provenance
- include Medallantic definitions, diagnostics, and extension metadata in
  old-reader/new-writer and new-reader/old-writer burn-in matrices
- close remaining public API, Plugin SDK, plan/report schema, and diagnostic
  stability blockers exposed by the full parity corpus
- forbid migration tooling from resolving secrets, importing untrusted code,
  reading source rows, or mutating targets during analysis

### Joint exit gate

Both legacy builders have tested migration paths; all claimed parity is backed
by differential/conformance evidence; the facade/core boundary and required
wire schemas are freeze-ready; no unresolved P0 parity gap remains.

The testing preview must also prove that an independently maintained pipeline
can exercise validate → plan → run → report through public installed-wheel
imports with explicit fixtures and no resolved secrets or retained source
rows.

## 0.36 — Joint Compatibility Burn-In

**Status:** Gate-ready for tag/publish.

**Objective:** accumulate adoption and upgrade evidence for ETLantic and
Medallantic together after the 0.25–0.27 core slices and the 0.28–0.35
co-evolution phases, then close burn-in as one bounded release.

The execution sequence, workstream ownership, quantified scorecard, and
required evidence are defined in the
[0.36 implementation plan](docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_36.md).

### Deliver

- exercise consecutive minor upgrades for ETLantic core, first-party plugins,
  Medallantic definitions, migration IR, plans, reports, and diagnostics
  without an unplanned wire-schema reset
- maintain old-reader/new-writer and new-reader/old-writer fixtures for every
  supported schema and protocol range
- require migrations for intentional breaking changes and keep both projects'
  stable-foundation removal inventories current
- run the Medallantic semantic conformance and legacy differential corpora as
  first-party release gates
- burn in application-pipeline tests across supported local engines, SQL, and
  PySpark for their advertised capability intersection, including deterministic
  snapshot migration and normalized failure evidence
- graduate experimental engines or portable families only through existing
  conformance, differential, security, performance, and documentation gates
- keep server, registry, LSP, remote federation, expanded streaming,
  additional orchestrators, and AI-assisted authoring out of stable core
  unless needed to prove an already-promised stable-foundation abstraction

### Quantified acceptance

- the `0.34 → 0.35` and `0.35 → 0.36` joint upgrade paths pass for ETLantic,
  every first-party plugin, and Medallantic
- old-reader/new-writer and new-reader/old-writer fixtures pass for 100% of
  supported public wire schemas and protocol ranges
- 100% of first-party plugins pass the frozen public conformance suite from
  isolated wheels
- representative user pipeline cases pass from isolated wheels across every
  supported engine intersection, and all deliberate failures produce stable
  diagnostics and normalized reports
- the Medallantic semantic corpus and legacy differential corpus pass with zero
  unexplained semantic differences
- there are zero unresolved P0 compatibility, security, parity, or migration
  findings and zero unversioned wire-schema changes
- every remaining P1 finding has an owner, target phase, and documented reason
  it does not block the stable foundation

### Exit gate

No unresolved naming migration, P0 Medallantic parity gap, silent capability
fallback, schema reset, provisional facade/core protocol, or provisional core
plugin protocol remains on the stable-foundation path.


## 0.37 — Stable Foundation

**Status:** Gate-ready for tag/publish rehearsal.

### Public stability

- Stable authoring API
- Stable Plugin SDK protocols
- Stable application-pipeline testing helpers for public pipeline projects
- Stable `PipelinePlan`, result, event, and `PipelineRunReport` schemas
- Deeply immutable plans with canonical serialization and verified fingerprints
- Strict schema-version handling and explicit compatibility migrations
- Published public API and diagnostic-code stability tiers
- Supported ODCS, DTCS, DPCS, ContractModel, and Python version policy
- Deprecation, compatibility, and schema-migration policies

### Production readiness

- Implemented threat model and security verification matrix
- Safe and bounded contract, profile, and configuration loading
- Pre-import plugin authorization, allowlists, pins, and provenance reporting
- Central secret wrapper and redaction boundary
- Artifact and cache isolation by run, environment, tenant, and security domain
- Network destination, webhook, and remote-reference policies
- Security-event and audit model
- Unified safe I/O with atomic persistence and explicit root/overwrite policy
- Repository security policy and private reporting process
- SBOMs, signed provenance, and reproducible release artifacts
- Performance budgets for modeling, validation, planning, reporting, and
  representative backends
- Failure injection and cancellation testing
- Durable, cross-process CLI reports and declarative provider configuration
- Complete tutorials, references, migration guides, and executable examples

### Stable-foundation acceptance suite

The stable-foundation release must demonstrate:

1. A code-first pipeline that generates ODCS, DTCS, and DPCS.
2. A contract-first pipeline that normalizes to the same logical model.
3. Direct consumption of a prior step's named result.
4. Selective local execution with dependency closure and a complete run report.
5. Equivalent Polars and Pandas transformations.
6. A SQL-native pipeline with safe pushdown.
7. A PySpark batch pipeline with lazy-region preservation.
8. An Airflow compilation of the same logical plan.
9. Lifecycle, middleware, resource, callback, outbound-event, logging, and
   redaction behavior.
10. Plugin conformance and production trust-policy enforcement.
11. Security-boundary preservation through planning and optimization.
12. A representative SparkForge pipeline using ETLantic underneath.
13. One portable definition with conformant Polars, PySpark, Pandas, and SQL
    realizations for their advertised capability intersection.
14. A planned cross-plugin Arrow boundary with contract-equivalent results,
    explicit ownership/collection/copy evidence, and a diagnosed fallback.
15. Any graduated DataFusion integration passing its Gate B conformance,
    differential, dependency-isolation, and semantic-preservation gates;
    experiments that did not graduate create no stable-foundation compatibility
    obligation.
16. Rejection of mutated, corrupt, incorrectly fingerprinted, unknown-version,
    or cross-security-domain plans before plugin loading or external mutation.
17. Authorization of an allowed plugin and rejection of a disallowed installed
    plugin without importing the disallowed executable entry point.
18. A durable CLI workflow whose run report is inspected in a later process,
    with consistent human, JSON, and SARIF diagnostic identity.
19. Failure injection across read, transform, interchange, write, persistence,
    cancellation, and cleanup boundaries without duplicate committed effects.
20. An independently maintained third-party plugin passing public conformance
    and compatibility checks without private core imports or reserved names.
21. An independently maintained application pipeline tested with static
    inputs, expected normalized outputs, explicit snapshot review, and injected
    write/cancellation failures using only public `etlantic.testing` imports.

### Exit gate

ETLantic's stable foundation ships only when:

- Typed authoring, contract interoperability, validation, planning, execution,
  reporting, and plugin coordination work together end to end.
- Every mandatory control in the
  [Security Model](docs/02_FOUNDATIONS/SECURITY.md) has an implementation owner,
  automated verification, and documented residual risk.
- Public APIs, protocols, diagnostics, plans, reports, profiles, events, and
  artifacts have frozen schemas or explicit documented stability status.
- Compatibility, upgrade, rollback, isolated-wheel, and release-provenance
  rehearsals pass against the exact release artifacts.
- Stable reference paths meet published performance, memory, cancellation,
  cleanup, persistence, and scale budgets.
- The public examples describe tested behavior rather than aspirations.
- Application-pipeline fixtures, fake providers, and snapshot helpers are
  deterministic, bounded, redacted, and usable without production access.
- SparkForge migration has proved the core abstractions without moving
  medallion semantics into ETLantic.

## Defined Post-Foundation Sequence

All planned ETLantic releases remain in the 0.x series. This roadmap has no
1.0 or 1.x phase: 0.37 is the stable foundation, and later capabilities use
sequential 0.x minors. Versions belonging to external standards, dependencies,
or user-authored artifacts do not change this release-numbering policy.

Phases 0.38 through 0.52 expand ETLantic around the stable-foundation model
without turning the core into a storage system, server, catalog, scheduler,
IDE, cloud control plane, or AI platform. Each initiative has one assigned
phase or a named gate in an integrated multi-phase program; none is an
open-ended placeholder.

Each minor release should:

- add one coherent integration or capability family;
- preserve stable-foundation plan, report, and Plugin SDK compatibility unless
  an explicitly versioned schema extension is required;
- ship independently installable integrations for heavyweight concerns;
- use adoption evidence to adjust ordering without collapsing boundaries.

## 0.38 — Data Connectivity and Connector SDK

**Status:** planned first-class connectivity program; begins after ETLantic
0.37 ships.

**Objective:** graduate logical source, sink, and storage bindings from Future
design studies into a versioned, capability-driven connector family with
supported reference implementations.

ETLantic remains the owner of logical assets, deterministic planning,
capability negotiation, and normalized evidence. Vendor clients, credentials,
physical endpoints, and backend-specific behavior remain in optional provider
packages.

#### Deliver

- versioned source, sink, and storage provider protocols with static manifests
  and pre-import production trust checks;
- typed, secret-free binding configuration and deterministic plan snapshots;
- capability vocabulary for batch snapshot, partitioned access, incremental
  cursor, predicate/projection pushdown, schema discovery, append, merge,
  replace, atomic publication, transactions, idempotency, reconciliation, and
  cleanup;
- a connector development kit with reusable configuration validation,
  checkpoint, retry, pagination, rate-limit, observability, packaging, and
  documentation helpers;
- capability-selected fake and live conformance suites;
- measurable experimental, preview, supported, and deprecated maturity levels;
- bounded schema/statistics inspection that never retains arbitrary source
  rows;
- a compatibility matrix for ETLantic, connector, external service or format,
  and Python versions;
- at least one independently maintained third-party connector;
- a **local file landing-zone reference connector** so authors choose, at
  binding/profile design time, how a periodically populated directory is
  consumed without rewriting the logical pipeline:
  - **batch snapshot** — each run lists and reads matching files (e.g. `*.csv`)
    under a Safe I/O root in deterministic order;
  - **incremental** — only new/unprocessed files since the last successfully
    committed cursor; cursor must not advance after an uncommitted write;
  - idempotent consume/cleanup (rename, archive, or ledger) so retries do not
    double-commit;
  - continuous **file-drop watching** remains a trigger/submitter concern
    (compose in 0.39+); the extract stays snapshot or incremental.

Exact authoring and phase split:
[Landing-Zone File Connector Plan](docs/11_DEVELOPMENT/LANDING_ZONE_CONNECTOR_PLAN.md).

#### Reference set

The exit candidate must prove:

- one local reference connector suitable for deterministic CI (**including
  directory/glob CSV landing-zone batch snapshot and incremental modes**);
- one S3-compatible object-storage path with Parquet;
- one open table-format path using Iceberg or Delta;
- one cloud warehouse path using Snowflake or BigQuery;
- one relational path exercising transaction, rollback, and unknown-outcome
  semantics.

Reference selection does not make vendor libraries core dependencies. Each
integration remains independently installable and production profiles must
allowlist it explicitly.

#### Acceptance

- one logical pipeline runs against a local reference, object storage, and a
  warehouse without changing the authoring model;
- unsupported write, transaction, schema, or pushdown semantics fail during
  planning rather than degrading silently;
- incremental resume cannot advance a cursor after an uncommitted write;
- partial object-store publication cannot appear as a committed dataset;
- connector configuration, diagnostics, plans, and reports contain no resolved
  secrets;
- live-system conformance publishes isolation, cost, rate-limit, and cleanup
  controls;
- an independent connector passes public conformance without private imports;
- landing-zone batch and incremental modes are selectable via binding/profile
  without changing `Extract` topology; missing mode capability fails at plan.

See the
[Adoption, Connectivity, and Operations Plan](docs/11_DEVELOPMENT/ADOPTION_ECOSYSTEM_PLAN.md),
the [Landing-Zone File Connector Plan](docs/11_DEVELOPMENT/LANDING_ZONE_CONNECTOR_PLAN.md),
and the [Storage Plugin design](docs/07_PLUGIN_SDK/STORAGE_PLUGIN.md).

### First-class control-plane program

The 0.39–0.42 sequence is one first-class multi-tenant control-plane program:
API and identity, tenant persistence, durable execution coordination, then
policy/audit hardening. These are incubation gates for a 0.43 graduation, not
four unrelated optional experiments. ETLantic core remains a library, and no
phase claims in-process isolation for mutually untrusted Python.

**Landing-zone composition in 0.39+:** continuous directory watches and
file-drop sensors submit durable control-plane runs against the same logical
pipeline and 0.38 landing-zone bindings; tenant/workspace-scoped Safe I/O
roots and authorized checkpoint stores are control-plane concerns. See
[Landing-Zone File Connector Plan](docs/11_DEVELOPMENT/LANDING_ZONE_CONNECTOR_PLAN.md).

The authoritative integrated gates are in the
[Multi-Tenant Control Plane Plan](docs/11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md).

## 0.39 — Multi-Tenant Control Plane: API and Identity Foundation

**Status:** Planned CP1 incubation; not shipped in 0.37.

**Objective:** establish typed, tenant-aware control-plane contracts and a
deny-by-default HTTP/SDK boundary without treating the API process as a worker
or security sandbox.

Deliver:

- separate `etlantic-fastapi` distribution;
- versioned principal, tenant, workspace, environment, security-domain, and
  immutable request-context models;
- embeddable router and standalone application factory;
- typed discovery, validation, planning, run submission, status, cancellation,
  report, artifact-metadata, and lineage endpoints;
- typed schema observation, history, diff, impact, proposal, and
  acknowledgement endpoints with authorization distinct from ordinary pipeline
  reads;
- typed freshness, partition, repair, backfill, reconciliation, parity, plan
  drift, environment drift, quality-trend, and statistical-drift endpoints;
- FastAPI lifespan integration for registry, store, broker, and submitter
  clients;
- dependency adapters for identity, tenant, policy, idempotency, and request
  context;
- authorization before lookup/pagination, non-enumerating errors, bounded
  tenant-scoped cursors, and separate cross-tenant administration;
- HTTP middleware guidance distinct from ETLantic runtime middleware;
- OpenAPI 3.1 schema with stable operation IDs and client-generation fixtures;
- SSE run-event streaming and optional experimental WebSockets;
- OpenAPI callbacks and webhooks generated from outbound event declarations;
- OAuth2/OIDC and application-defined authorization dependencies;
- durable submission contract returning `202 Accepted`;
- optional SQLModel-backed reference stores for registry, runs, reports,
  events, schema observations, reliability evidence, and approvals;
- separate request, persistence, and response models where fields or security
  boundaries differ;
- **landing-zone continuous trigger hook:** file-drop / directory-watch
  sensors may call the durable submission API so the same 0.38
  snapshot/incremental landing-zone binding runs under tenant-scoped
  authorization (no in-process watch loop in core).

Acceptance:

- the router embeds in an existing FastAPI application without owning its
  lifespan or dependency policy;
- OpenAPI-generated clients can submit and observe a run;
- multiple API workers share durable run state and resumable events;
- heavy pipeline work never depends on FastAPI `BackgroundTasks`;
- unauthorized profile, artifact, override, and cancellation access fails
  closed;
- live schema inspection and drift acknowledgement require explicit subject,
  profile, workspace, and policy authority;
- SQLModel sessions remain request-scoped integration details and never become
  pipeline runtime resources;
- every action/resource pair passes two-tenant and two-workspace authorization
  tests, including list, search, cursor, and event-stream non-enumeration;
- no production multi-tenant claim is made at CP1.

See [FastAPI Integration Plan](docs/11_DEVELOPMENT/FASTAPI_INTEGRATION_PLAN.md).

## 0.40 — Tenant Registry, Workspaces, and Persistence Isolation

**Status:** Planned CP2 incubation.

**Objective:** make tenant/workspace scope part of every registry and
persistence key, with supported isolation profiles and migration evidence.

Deliver:

- registry-provider protocol for contracts, pipelines, plans, plugins, and
  generated documentation;
- immutable revisions, aliases, promotion channels, signatures, and provenance;
- workspace and tenant model with namespaced identities;
- compound tenant/workspace keys, mandatory scoped repository APIs, and
  database-enforced isolation for supported shared-service profiles;
- isolated-deployment, dedicated-database/schema, and shared-service
  conformance profiles with explicit residual risks;
- dependency and impact queries across pipeline revisions;
- immutable schema observations, operational baselines, acknowledgements, and
  remediation references;
- immutable plan, environment, reconciliation, quality, freshness,
  completeness, and statistical observation histories;
- field-aware impact queries from observed changes through contracts,
  transformations, outputs, sinks, and downstream pipelines;
- searchable metadata indexes without storing arbitrary dataset contents;
- registry events and cache-invalidation protocol;
- stable metadata identity mapping for pipeline, step, run, attempt, input,
  output, contract, plan, schema observation, and artifact revisions;
- optional `etlantic-openlineage` provider for tenant-aware design-time and
  runtime metadata export, with documented namespace, ordering, retry, and
  reconciliation semantics;
- FastAPI registry routes and CLI parity;
- optional SQLModel-backed registry, revision, and history reference provider.

Acceptance:

- a pipeline revision can be promoted from development to production without
  changing its identity or embedding environment secrets;
- impact analysis explains which pipelines and outputs depend on a changed
  contract;
- tenant and workspace boundaries are preserved in registry, cache, API, and
  artifact identities;
- accepting an operational baseline never mutates or aliases the authoritative
  contract revision;
- two-tenant/two-workspace matrices pass every repository method and pagination
  path;
- backup, restore, mixed-version migration, and rollback preserve tenant scope;
- shared-service profiles prove a second independent isolation control.
- design-time and runtime OpenLineage events join on stable identities across
  local, compiled, and remote execution without exposing secrets or source
  rows;
- outbound catalog export cannot mutate authoritative contracts, plans,
  baselines, or promotion state.

## 0.41 — Durable Submission, State, and Reproducibility

**Status:** Planned CP3 incubation.

**Objective:** coordinate accepted work across API replicas and isolated
execution hosts using durable transactions, outbox dispatch, leases, fencing,
and normalized recovery evidence.

Deliver:

- state-provider protocol;
- transactional submission/outbox, broker/submitter, execution-host, lease,
  fencing-token, heartbeat, and attempt-history protocols;
- caller/tenant/workspace-scoped idempotency and per-tenant admission control;
- versioned, secret-free execution-attempt context that lets hosts correlate
  retries, replay, resume, cancellation, deadlines, checkpoints, and reports
  without making ETLantic a queue or worker supervisor;
- versioned cursors, watermarks, checkpoints, partitions, and snapshot
  identities;
- compare-and-swap and atomic checkpoint advancement;
- replay, resume, repair, and backfill planning;
- partition-aware invalidation, reusable-artifact selection, and minimum-safe
  repair closure;
- dataset and code provenance sufficient to reproduce or explain a run;
- schema-baseline revisions linked to checkpoints, snapshots, runs, and replay
  evidence;
- compare-and-swap baseline acknowledgement and concurrent-observation
  handling;
- state migration and corruption diagnostics;
- dry-run state transition explanation.
- commit- and pull-request-qualified preview workspaces with bounded lifecycle,
  time-to-live, cleanup, quotas, and immutable base/candidate revision links;
- base-versus-candidate contract, graph, plan, schema, policy, cost, and
  environment diffs plus impacted-subgraph selection;
- explicitly authorized shadow execution whose effects can never be promoted
  as authoritative production outputs;
- optional SQLModel-backed state, checkpoint, and idempotency reference
  provider with transactional concurrency controls.
- normalized external-effect outcome (`none`, known committed/not committed,
  or unknown), durable-publication, compensation, and reconciliation evidence
  for host recovery decisions.

Acceptance:

- a failed run cannot advance a checkpoint incorrectly;
- concurrent runs detect and resolve state conflicts explicitly;
- replay identifies the exact contracts, plan, implementation, input snapshot,
  secret versions where safe, and state transition used by the original run.
- replay identifies the schema observations and baseline decisions used by the
  original run.
- an unknown external commit outcome fails closed against automatic retry
  unless a provider supplies valid transaction, deduplication, reconciliation,
  or idempotency evidence;
- API or worker loss cannot lose an accepted request or permit a stale attempt
  to publish terminal state, checkpoints, or artifacts;
- duplicate submissions and broker retries do not duplicate work;
- preview cleanup is idempotent, fully scoped, and unable to delete shared or
  production resources;
- preview evidence becomes stale when its code, plan, dependency, policy, or
  target-environment identity changes;
- multi-worker chaos, disconnect/resume, and recovery tests pass.

## 0.42 — Tenant Policy, Quotas, Audit, and Supply-Chain Assurance

**Status:** Planned CP4 release-candidate gate.

**Objective:** add the governance, noisy-neighbor controls, integrity evidence,
and operational proof required before the integrated 0.43 graduation decision.

Deliver:

- policy-provider protocol with pre-plan, post-plan, pre-submit, and
  post-execution decisions;
- adapters for external policy engines such as OPA where justified;
- signed plans, plugin provenance, SBOM attachment, and artifact attestations;
- approval gates and separation-of-duty workflows;
- tenant/workspace quotas, fairness, suspension, emergency containment, and
  fail-closed admission policy;
- residency, classification, masking, retention, and egress constraints;
- policy decision evidence in reports and APIs;
- append-only, integrity-protected tenant audit evidence without source rows or
  resolved secrets;
- signed or integrity-protected production schema observations, approval gates,
  retention rules, and acknowledgement evidence;
- policy gates for stale or incomplete inputs, unsafe retries, destructive
  writes, backfills, reconciliation failures, plan drift, environment drift,
  quality trends, and privacy-sensitive statistical profiling;
- source-revision provenance, untrusted-fork restrictions, preview budgets,
  separation of duties, promotion approvals, supersession, and rollback policy;
- compatibility rules for policy revisions.

Acceptance:

- optimization and backend selection cannot cross a policy boundary;
- a submitted plan can be verified against its authoring revision, approved
  plugins, and policy bundle;
- approval and denial are durable, auditable, and free of secret values.
- forged, cross-tenant, or cross-environment schema observations cannot satisfy
  a deployment or execution gate;
- identity, policy, quota, broker, and persistence outages fail closed according
  to documented degraded modes;
- noisy-neighbor, backup/restore, migration, redaction, and external security
  review gates pass.
- preview workspaces receive no implicit secret or production authority, and
  promotion revalidates the exact approved revision against current policy and
  environment state.

## 0.43 — First-Class Multi-Tenant Control-Plane Graduation

The production multi-tenant control-plane claim is a first-class 0.43 feature
only after CP1–CP4 pass as an integrated system. Graduation requires a frozen
supported-isolation-profile matrix, public compatibility/migration policy,
cross-tenant conformance for every public operation, measured capacity
envelopes, multi-replica failure injection, operator runbooks, backup/restore
evidence, a supported preview-to-production GitOps workflow, stable outbound
metadata identity/export, and no unresolved critical/high isolation finding.

Failure of a mandatory gate keeps the program in release-candidate status. The
project does not weaken “multi-tenant” to meet a release date.

## 0.44 — Developer Intelligence: LSP, IDE, and Static Analysis

Deliver:

- an editor-neutral language server for Python-authored and contract-first
  pipelines;
- a first-party VS Code extension and a documented integration contract for
  PyCharm, Neovim, Zed, and other LSP-capable editors;
- workspace discovery for monorepositories, multiple project files, and
  selectable profiles;
- completion for bindings, ports, parameters, profiles, plugin capabilities,
  secret references, `Data`, `Transformation`, `Pipeline`, implementations,
  run intents, selectors, and contract fields;
- hover cards with contract summaries, producers, consumers, selected
  implementations, compatibility status, and documentation links;
- go-to-definition, find references, call hierarchy, document symbols, and
  workspace symbols across Python, ODCS, DTCS, DPCS, plans, profiles, and
  generated artifacts;
- inline diagnostics with related locations, stable codes, suppression
  guidance, and direct links to relevant documentation;
- safe quick fixes for missing bindings, incompatible ports, stale generated
  artifacts, unknown profiles, deprecated APIs, and deterministic migrations;
- semantic rename with a reviewable workspace edit across Python, contracts,
  profiles, generated artifacts, and known registry references;
- in-editor previews for pipeline graphs, lineage, execution regions, resolved
  plans, and plan diffs;
- CodeLens actions for validate, plan, explain, run, run to step, run from step,
  generate artifacts, and open the latest report;
- a run and debug panel showing live step state, logs, diagnostics, artifacts,
  metrics, cancellation controls, and backend links;
- an optional Jupyter and IPython integration with rich displays for `Data`,
  `Transformation`, `Pipeline`, `PipelinePlan`, diagnostics, lineage, and
  `PipelineRunReport`;
- notebook controls for validate, plan, explain, run selected steps, cancel,
  compare runs, and open generated artifacts without inventing notebook-only
  execution semantics;
- optional progress widgets driven by the same structured lifecycle events used
  by the CLI, IDE, and report system;
- safe artifact previews with configurable row, byte, column, and rendering
  limits, explicit sampling, and automatic redaction of protected values;
- deterministic notebook export helpers that capture code, resolved
  non-secret configuration, plan hashes, contract versions, implementation
  identities, and report references for reproducible analysis;
- notebook-to-project extraction actions that turn exploratory transformations
  and pipelines into ordinary Python modules and tests;
- clear stale-state detection when notebook cells redefine a model after a plan
  or run was created;
- logical lifecycle breakpoints at validation, pre-step, post-step, failure, and
  publication boundaries without pretending that every remote backend can
  pause arbitrary user code;
- a profile and configuration inspector showing effective values, provenance,
  overrides, unused settings, and redacted secret references;
- compatibility and downstream-impact previews before a contract or port
  change is accepted;
- source and port drift indicators, declared-versus-observed hover summaries,
  schema-history timelines, field-level impact navigation, and reviewable
  adapter or contract-update proposals;
- SQLModel generation, contract-to-table navigation, table comparison,
  API-field exposure warnings, and migration-impact actions;
- freshness and incomplete-partition indicators, repair and backfill previews,
  unsafe-retry and destructive-write diagnostics, reconciliation results,
  implementation comparisons, plan and environment diffs, and bounded quality
  or statistical-drift charts;
- test discovery and one-click conformance runs across multiple transformation
  implementations;
- code actions to extract a transformation, add an adapter, create a missing
  binding, and scaffold an implementation;
- pyright-oriented type diagnostics and generated typing metadata where it
  improves editor inference;
- an incremental analysis cache with cancellation, bounded memory, precise
  invalidation, and source provenance;
- restricted static analysis that avoids importing project modules by default,
  with explicit trusted-workspace opt-in for deeper introspection;
- notebook-friendly inspection without hidden runtime state.

Acceptance:

- changing an output contract updates downstream diagnostics before execution;
- an editor can navigate from a step input to its producing output and contract;
- rename produces a reviewable workspace edit and identifies external
  references that cannot be changed automatically;
- graph previews preserve stable layout as nearby files change;
- an editor-triggered run produces the same plan hash and report model as the
  equivalent CLI command;
- remote-run observation can reconnect after an editor restart when the backend
  provides a durable event and report store;
- configuration inspection never reveals secret values;
- editors and notebooks never query live production schemas automatically;
- notebook execution produces the same plan hash and report model as the
  equivalent Python API or CLI request;
- rich display methods remain side-effect free and never resolve secrets,
  import execution plugins, read artifacts, or contact remote systems unless
  the user invokes an explicit operation;
- large artifact previews remain bounded and visibly identify sampling or
  truncation;
- stale notebook definitions are detected before execution instead of silently
  reusing an obsolete plan;
- representative large workspaces meet documented interactive latency and
  memory budgets;
- quick fixes never import untrusted modules or resolve remote references
  implicitly.

## 0.45 — Planner and Optimization SDK

Deliver:

- stable optimization-pass protocol;
- rule-based and statistics-aware cost model;
- explainable implementation selection and materialization decisions;
- cost- and evidence-aware repair closure, backfill batching, artifact reuse,
  and implementation selection;
- cardinality, partitioning, ordering, locality, and reuse metadata;
- safe cross-backend region optimization;
- shadow planning and plan comparison;
- optimizer conformance suite proving semantic and security preservation.

Acceptance:

- every optimization identifies its evidence, estimated benefit, and semantic
  proof obligations;
- users can compare baseline and optimized plans before execution;
- an optimization that cannot prove boundary preservation is rejected.

## 0.46 — Streaming and Event-Driven Pipelines

Deliver:

- stable streaming semantics beyond the 0.37 foundation;
- event-time, watermark, trigger, state, late-data, and replay contracts;
- versioned change-event envelopes with insert, update, delete/tombstone,
  transaction, source-position, ordering, and schema-revision evidence;
- bounded snapshot-to-change-stream handoff with explicit gap and overlap
  handling;
- source offset, cursor, checkpoint, deduplication, and idempotent sink
  semantics shared with the 0.38 connector protocol;
- Kafka and additional streaming provider integrations;
- continuous `PipelineRunReport` snapshots and terminal/nonterminal status;
- event-driven run triggers with deduplication and backpressure;
- streaming contract compatibility and deployment migration rules.

Acceptance:

- batch and streaming implementations of the same eligible transformation have
  documented semantic equivalence;
- restart and replay do not silently duplicate externally visible effects;
- backpressure and late-data behavior are visible in plans and reports.
- snapshot/stream handoff proves no silent loss, duplication, or position
  advance across restart and concurrent schema change;
- unsupported delete, ordering, transaction, or schema-evolution semantics fail
  capability negotiation rather than degrading to append-only behavior.

## 0.47 — Remote Execution Federation

Deliver:

- remote submitter and execution-control protocols;
- capability, version, identity, and trust negotiation between client and
  runtime;
- signed plan envelopes and content-addressed artifact exchange;
- resumable event, log, and report synchronization;
- cancellation, retries, leases, heartbeats, and disconnected-client behavior;
- fenced attempt ownership and normalized attempt history while leaving the
  durable queue/lease implementation to the conforming remote runtime;
- recovery negotiation for whole-run retry, checkpoint resume, replay, repair,
  reconciliation, or manual review;
- placement across multiple approved execution environments;
- a Kubernetes Job reference provider with workload identity, resource limits,
  cancellation, log/event correlation, terminal-state reconciliation, and
  bounded provider-owned cleanup;
- versioned OCI execution-image contracts and at least one maintained managed
  Spark reference path using Databricks, EMR, or Spark Connect;
- FastAPI gateway support without requiring FastAPI in workers.

Acceptance:

- the same signed plan can be submitted to two conforming runtimes and produce
  comparable normalized reports;
- clients can disconnect and later resume observation without losing durable
  state;
- a remote runtime cannot request undeclared secrets, plugins, or network
  authority.
- loss of a worker after an external commit cannot be reported as safely
  retryable when the commit outcome is unknown.
- the Kubernetes and managed Spark references pass public conformance from
  isolated deployments, prefer workload identity, and leave no unscoped
  resources after cancellation or failure.

## 0.48 — AI-Assisted, Human-Governed Engineering

Deliver:

- read-only machine-consumable inspection APIs for models, contracts, lineage,
  diagnostics, plans, capabilities, and run history;
- a versioned, vendor-neutral ETLantic AI workflow catalog;
- maintained skill packs for Codex and Claude Code plus scoped Cursor rules and
  commands for explaining pipelines, scaffolding models, diagnosing wiring,
  generating contracts, creating conformance tests, reviewing security, and
  performing migrations;
- project-local generators for `AGENTS.md`, `CLAUDE.md`, Codex skills, and
  `.cursor/rules` or `.cursor/commands` that preserve user-owned instructions;
- composable repository, directory, and task-specific instruction layers;
- bounded machine-readable context bundles containing selected contracts,
  graph slices, diagnostics, plan explanations, and report summaries with
  explicit provenance;
- an optional read-only MCP server for inspection, validation, planning,
  documentation, and report-query tools;
- structured proposal format for generated pipelines, migrations, policies, and
  optimization suggestions;
- human-governed proposals for schema adapters, source corrections, contract
  revisions, migrations, and conformance tests using bounded redacted drift
  evidence;
- human-governed proposals for repair plans, backfill tests, reconciliation
  rules, parity fixes, write-policy migrations, and quality remediation;
- provenance and evidence attached to every generated proposal;
- deterministic validation sandbox for proposals before review;
- proposal previews showing file diffs, graph changes, compatibility, plan
  changes, downstream impact, and required approvals;
- cross-agent evaluation fixtures that score correctness, safety, determinism,
  and unnecessary context use;
- prompt-injection-resistant boundaries around documents, logs, and metadata;
- explicit human approval before mutation, submission, secret access, or
  external communication;
- optional agent/tool adapters in separate packages, with no Claude, OpenAI, or
  Cursor SDK dependency in ETLantic core.

Acceptance:

- an assistant can propose a contract-compatible transformation and receive
  precise validation feedback without execution authority;
- Codex, Claude Code, and Cursor can perform the same canonical scaffold,
  validation, migration, and review workflows through their native project
  instruction formats;
- regeneration is deterministic, preserves marked user-owned regions, and
  reports conflicts rather than silently overwriting them;
- context bundles are bounded, redacted, explicitly selected, and identify
  every included source;
- read-only MCP tools cannot submit runs, install plugins, resolve secrets,
  mutate files, or contact undeclared external systems;
- generated changes are ordinary reviewable files and plans, not hidden runtime
  mutations;
- every proposed mutation includes validation results and a semantic-impact
  preview before human approval;
- an assistant cannot acknowledge drift, replace an operational baseline, or
  revise an authoritative contract without explicit human approval;
- untrusted contract text or logs cannot grant tools, reveal secrets, install
  plugins, or initiate runs.

See [Schema Drift and Evolution Plan](docs/11_DEVELOPMENT/SCHEMA_DRIFT_PLAN.md).
See [ETL Reliability and Recovery Plan](docs/11_DEVELOPMENT/ETL_RELIABILITY_PLAN.md).

## 0.49 — Brownfield Adoption Bridges

**Objective:** let teams introduce ETLantic alongside existing dbt and
orchestrator projects through bounded metadata import, explicit fidelity
reports, and incremental migration rather than a flag-day rewrite.

Deliver:

- a versioned dbt `manifest.json` reader covering models, tests, sources,
  exposures, metrics, groups, selectors, and dependency maps;
- an intermediate migration model that classifies exact, lossy, unsupported,
  and externally owned semantics;
- deterministic contract and pipeline skeleton generation with provenance,
  reviewable diffs, and no implicit overwrite;
- semantic diff between source artifacts and generated ETLantic definitions;
- optional Dagster Definitions compiler;
- expanded Prefect compile/deployment integration distinct from the shipped
  local `ExecutionScheduler` MVP;
- an Argo Workflow compiler consuming only valid plans;
- side-by-side validation, plan, lineage, and normalized report comparison;
- compatibility fixtures for every supported upstream artifact version.

Acceptance:

- metadata import does not execute arbitrary project Python, Jinja, macros, or
  hooks;
- unsupported dynamic graphs, macros, sensors, or platform semantics are
  diagnosed rather than guessed;
- dbt-owned transformations may remain external while ETLantic imports their
  contracts and lineage;
- each compiler fails when required plan semantics cannot be preserved;
- generated files never overwrite user work without an explicit target and
  review;
- at least one real project adopts ETLantic incrementally without a flag-day
  rewrite.

## 0.50 — Operator Console

**Objective:** provide a separately deployable, read-only-first operations UI
over the graduated multi-tenant control plane.

Deliver:

- a version-pinned client generated from the control-plane OpenAPI schema;
- scoped views for definitions, revisions, plans, diffs, runs, attempts,
  lineage, partitions, checkpoints, quality, schema drift, repair, backfill,
  quotas, policy, approvals, audit evidence, providers, and deployment health;
- resumable live events with durable-history fallback;
- explicit privileged actions for cancellation, retry, replay, repair,
  acknowledgement, approval, promotion, suspension, and containment;
- bounded, sampled, visibly truncated, and redacted artifact previews;
- accessibility, localization readiness, interactive latency budgets, and
  large-workspace pagination/virtualization;
- maintained operator workflows and visual fixtures.

Acceptance:

- the console is never an independent source of truth or authorization path;
- every mutation uses the same typed API, policy, idempotency, and audit path as
  other clients;
- unauthorized resources do not leak through counts, search, links, errors,
  caches, browser history, or event streams;
- reconnect or refresh cannot duplicate a privileged action;
- hostile schemas, logs, and artifacts remain bounded and redacted;
- ETLantic core and the control API remain usable without frontend
  dependencies.

## 0.51 — Managed Runtime and Enterprise Provider Packs

**Objective:** graduate common cloud integrations into maintained,
independently installable production profiles without coupling ETLantic core to
vendor SDKs.

Deliver:

- reference OCI images and Helm deployment profiles for the control plane and
  execution hosts;
- production hardening of the 0.47 Kubernetes Job execution provider;
- managed Spark providers for Databricks, EMR, and Spark Connect with truthful
  capability profiles;
- optional secret-provider packages for AWS Secrets Manager, Azure Key Vault,
  Google Cloud Secret Manager, and HashiCorp Vault;
- cloud storage and warehouse providers promoted from the 0.38 connector
  program through live conformance;
- short-lived workload identity and credential flows where supported;
- provider-specific compatibility, support, cost, quota, region, deprecation,
  upgrade, and rollback matrices;
- maintained infrastructure recipes only where automated tests prove them.

Acceptance:

- every provider is independently versioned, installable, removable, and
  allowlistable;
- secret providers resolve only at authorized runtime boundaries and prove
  redaction, rotation, missing-secret, and outage behavior;
- plans, reports, deployment manifests, examples, and support evidence contain
  no static or resolved credential values;
- managed execution loss produces a normalized known or unknown external-effect
  outcome before retry;
- Kubernetes cleanup is bounded to provider-owned, fully scoped resources;
- live conformance uses isolated accounts or projects and proves cleanup;
- no provider-specific type or SDK becomes a mandatory core dependency.

## 0.52 — TransformationModel Incubation

**Status:** deferred from the 0.20+ and former 0.38 tracks; begins only after
the higher-adoption connectivity, control-plane, interoperability, operations,
and provider programs have assigned ownership.

**Objective:** incubate a reusable, Python-native transformation modeling
package at `packages/transformationmodel` while ETLantic remains the
integration, planning, and execution system.

TransformationModel is the [DTCS](docs/04_TRANSFORMATIONS/DTCS.md) counterpart
to ContractModel: `dtcs` remains the authority for
[DTCS](docs/04_TRANSFORMATIONS/DTCS.md) document parsing, canonical
representation, validation, diagnostics, portable plans, and compatibility
semantics; TransformationModel provides ergonomic typed authoring,
translation, and fidelity APIs over that standard. The package must not import
ETLantic or acquire backend execution, orchestration, plugin-loading,
secret-resolution, or mutable-resource concerns.

#### Incubation deliverables

- create `packages/transformationmodel` as an independently buildable, typed
  package with its own public API, tests, documentation, changelog, and release
  policy;
- define `TransformationModel`, typed input/output references, expressions,
  capability requirements, and extension protocols without ETLantic imports;
- depend on public `dtcs` APIs for normative
  [DTCS](docs/04_TRANSFORMATIONS/DTCS.md) semantics instead of copying
  specification rules or portable-plan behavior;
- provide deterministic [DTCS](docs/04_TRANSFORMATIONS/DTCS.md) import, export,
  canonical serialization, fingerprinting, structured diagnostics, semantic
  diff, and explicit loss/fidelity reports;
- extract reusable transformation authoring and lowering behavior from
  ETLantic incrementally, preserving compatibility shims at the ETLantic
  public surface;
- keep Pandas, Polars, PySpark, SQL, orchestration, and other backend
  realization in ETLantic plugins or provider packages rather than
  TransformationModel core;
- publish a [DTCS](docs/04_TRANSFORMATIONS/DTCS.md) and Python compatibility
  matrix and exercise upstream conformance fixtures across every supported
  version;
- retain `dtcs` as a direct ETLantic dependency while low-level APIs are used;
  dependency ownership may become transitive only after the boundary is
  proven.

#### Graduation gates

- at least one consumer independent of ETLantic can author, validate, inspect,
  round-trip, and diff a transformation;
- equivalent definitions serialize and fingerprint identically across
  supported Python versions and operating systems;
- every conversion reports unsupported or lossy semantics explicitly and
  fails closed where fidelity is required;
- ETLantic's transformation conformance suite passes through the package
  without weakening [DTCS](docs/04_TRANSFORMATIONS/DTCS.md) validation,
  portability, or diagnostic guarantees;
- the package has a stable public protocol, semantic-versioning policy,
  deprecation policy, `py.typed` marker, and no dependency on ETLantic
  internals;
- installation keeps backend engines optional and introduces no runtime plugin
  imports or external effects during model inspection and validation.

#### ETLantic adoption

During 0.52, ETLantic may consume TransformationModel from the workspace behind
provisional boundaries. It becomes a required ETLantic dependency only after
the graduation gates pass and a separately released version has proven the
package boundary. No later 0.x compatibility promise may depend exclusively on
the incubating API until graduation.

See the
[TransformationModel Incubation Plan](docs/11_DEVELOPMENT/TRANSFORMATIONMODEL_PLAN.md).

## Unscheduled Candidate Themes

These remain candidates rather than promised release numbers:

- a near-term profile-policy bundle with one typed, versioned configuration
  surface for:
  - contract validation, including `unexpected_fields=forbid|ignore`,
    bounded coercion modes, and `forbid` as the backward-compatible default;
  - schema-drift actions for additive, breaking, and safe type-widening
    changes, with observation enabled independently from acceptance;
  - deterministic validation budgets for row, error, time, and sampling
    limits, with full validation required whenever contract or production
    policy does not explicitly permit sampling;
  - write-safety constraints that may reject unsafe overwrite, schema
    mutation, or non-transactional publication intents but never silently
    rewrite pipeline intent;
  the resolved bundle must be secret-free, included in plan snapshots and
  fingerprints, emit bounded schema-drift evidence without source rows,
  behave consistently across local, SQL, Pandas, Polars, and PySpark
  execution, and fail closed when a backend cannot enforce a required rule;
- run-history trends, regression detection, and anomaly analysis;
- schema-drift frequency, recurring-change, and source-stability trends;
- freshness, completeness, reconciliation, quality, statistical-drift, plan,
  and environment stability trends;
- additional orchestrators, dataframe engines, SQL dialects, connectors, and
  stores beyond the assigned reference and support matrices;
- declarative data previews with bounded privacy budgets;
- Wasm or isolated remote transformations where ecosystem maturity permits;
- cross-organization contract federation.

## SparkForge Replacement Gate

ETLantic is ready to replace SparkForge's duplicated underlying engines
only when it preserves these behaviors in domain-neutral form:

- selective and interactive execution
- direct prior-step result consumption without mandatory table materialization
- initial, incremental, refresh, validation, backfill, and replay intents
- backend-independent incremental state
- quality gates with valid and invalid artifacts
- deterministic dependency and execution-group explanation
- normalized reports, run history, lifecycle events, and contextual logging
- portable materialization, write, retry, and failure policies
- SQL, PySpark, Delta, and orchestration capabilities supplied through plugins
- semantic parity tests for representative SparkForge pipelines

This gate does not require ETLantic to understand medallion layers.

## Explicit Non-Goals

ETLantic does not plan to become:

- A proprietary distributed scheduler
- A dataframe or SQL engine
- A storage or catalog system
- A cluster provisioner
- A secret manager
- An in-process sandbox for untrusted Python
- A medallion architecture framework
- A replacement for Airflow, Spark, Pandas, Polars, SQL engines, or
  ContractModel

## Prioritization Rule

A proposed feature belongs in ETLantic when it strengthens portable
modeling, static analysis, deterministic planning, lifecycle coordination,
result normalization, or plugin interoperability.

Use this ownership test:

| Concern | Owner |
|---|---|
| Meaning of data, transformation, or pipeline contracts | ODCS, DTCS, or DPCS |
| Operationalizing data contracts | ContractModel |
| Portable pipeline model, planner, and coordination protocols | ETLantic |
| Backend execution mechanics | Execution plugins and providers |
| Medallion conventions and migration experience | SparkForge |

When ownership is unclear, prefer a small public protocol and keep concrete
runtime behavior outside the core.
