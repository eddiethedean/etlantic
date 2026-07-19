# Roadmap

This roadmap sequences ETLantic from a typed modeling library into a
stable, secure orchestration model and plugin platform.

It is a direction and dependency plan, not a release-date commitment. Version
numbers describe capability milestones. A milestone is complete only when its
acceptance scenarios, documentation, tests, and security requirements pass.

## Product Outcome

ETLantic will provide one portable model for:

- ContractModel-compatible, ODCS-aligned data contracts
- Type-driven, DTCS-aligned transformations
- Typed, DPCS-aligned pipeline composition
- Deterministic validation and planning
- References to prior step outputs without mandatory table materialization
- External execution through interchangeable plugins
- Structured logging, lifecycle extension points, and normalized run reports
- Contract, lineage, documentation, and visualization generation

ETLantic owns the logical model and coordination contracts. It does not
become a dataframe engine, distributed scheduler, storage system, secret
manager, or medallion framework.

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
  before 1.0
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
[0.15 continuation](#015-continuation-profile-graduation)).

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

- Production readiness, SLA, HA, or multi-tenant isolation (remain 1.0)
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

## 0.15 continuation (profile graduation)

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
(historically tracked as [0.15 continuation](#015-continuation-profile-graduation)),
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
  (post-0.16 / before 1.0 runtime work)
- the full scheduler conformance corpus from the scheduler plan (later)
- treating Prefect as an Airflow-style `compile_plan` / DAG artifact compiler
- passing large datasets through scheduler control payloads
- allowing Prefect retries or task boundaries to weaken ETLantic transaction,
  validation, security, or materialization semantics
- replacing Airflow compilation
- portable profile graduation ([0.17](#017--portable-coverage-expansion-platform--multi-family-graduation))
- production-default orchestrator selection or the full 1.0 security matrix

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
or C remain in [0.17 continuation](#017-continuation) and do not block the
0.17 exit gate.

**Prerequisites already shipped:** Polars, Pandas, SQL, and PySpark ship the
kernel and `portable-relational/1` baseline with public conformance and
cross-engine differentials. Rich-family authoring and fixtures exist; compiler
claims remain baseline-only until Gates B and C graduate them. Profile
graduation ownership moves here from
[0.15 continuation](#015-continuation-profile-graduation).

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

### 0.17 continuation

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

## 0.18+ — Standards-Based Interchange and Local Analytics

**Status: planned.** This is a sequenced 0.18-and-later program. Arrow
interchange is the hard foundation gate. DataFusion graduates only when its
independent value and semantic-preservation gates pass.

The detailed design and stop/go criteria live in the
[Arrow and DataFusion Integration Plan](docs/11_DEVELOPMENT/INTEROPERABILITY_FOUNDATION_PLAN.md).

### Architectural boundary

ETLantic retains Pydantic / ContractModel and ODCS / DTCS / DPCS as its
semantic foundation. ETLantic continues to own typed pipeline meaning,
validation, deterministic planning, trust, reliability, lineage, and
normalized evidence.

- Arrow is the preferred **physical tabular interchange** at compatible
  cross-plugin boundaries.
- `etlantic-datafusion` is a candidate first-party **local analytical engine
  and portable compiler**, never the scheduler or pipeline planner.

Heavy dependencies remain outside the core wheel. Installing `etlantic` alone
must not install or import PyArrow or DataFusion.

### Gate A — Versioned Arrow interchange (hard)

#### Deliver

- replace best-effort, invisible dataframe conversion with a versioned,
  deterministic interchange decision recorded in plans and run evidence
- distinguish Arrow C Data / Stream in-process exchange, Arrow IPC stream,
  Arrow IPC file, durable Parquet artifacts, and explicit records/file
  fallbacks
- select interchange from producer and consumer capability claims rather than
  hard-coded engine-name pairs
- record schema fingerprint, ownership, batching, collection, copy / zero-copy
  eligibility, fallback reason, and observed conversion evidence
- preserve ETLantic logical contracts separately from Arrow physical schemas;
  normalize and diagnose nullability, decimal, temporal/timezone, nested,
  dictionary, extension-type, and field-order mappings
- add bounded batch, backpressure, lifetime, branch-isolation, retry, and
  cleanup rules for Arrow streams and artifacts
- publish cross-plugin Arrow conformance fixtures and a documented non-Arrow
  fallback that never silently loses logical semantics

#### Acceptance scenarios

- compatible Polars ↔ Pandas and future plugin boundaries use the planned
  Arrow mechanism without hidden eager collection
- unavailable, unsupported, or lossy Arrow conversion produces an explicit
  plan/report decision and fails before mutation when the contract cannot be
  preserved
- “zero copy” is reported only as planned eligibility plus observed evidence,
  never inferred from plugin identity
- stream and artifact payloads are bounded; plans, diagnostics, and reports
  contain no source rows, live Arrow objects, or resolved secret values
- core tests and imports pass without PyArrow installed

#### Exit gate

Arrow interchange is a public, versioned, capability-driven contract with
fidelity, ownership, streaming, fallback, and evidence conformance. Existing
plugins pass it before a new analytical engine is added.

### Gate B — Experimental `etlantic-datafusion` vertical slice

Begins only after Gate A. DataFusion is initially an experimental first-party
plugin and does not replace Polars as the reference dataframe backend or
`LocalScheduler` as the execution coordinator.

#### Deliver

- remove fixed dataframe-engine-name assumptions from planning/runtime in
  favor of registered protocol and capability descriptors
- add independently installable `etlantic-datafusion` with dataframe runtime
  and `etlantic.transform_compilers` entry points
- expose the recommended installation as `pip install "etlantic[datafusion]"`
  so users do not need to select or assemble adapter/backend dependencies
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

#### Graduation gate

`etlantic-datafusion` graduates from experimental only if it passes dataframe
and portable conformance, cross-engine differentials, Arrow boundary tests,
failure/redaction tests, and demonstrates a distinct measured advantage in at
least one of local analytical performance, streaming/laziness, conversion
cost, or external interoperability. Otherwise it remains experimental or is
stopped without changing the core default.

### Program success measures

- fewer copied or silently materialized cross-engine boundaries
- deterministic Arrow interchange decisions with stable fingerprints
- no increase in mandatory core dependencies
- equal or stronger fail-before-mutation, plugin-trust, and redaction behavior
- DataFusion earns graduation through measured value rather than duplication
- plugin authoring and runtime behavior remain simpler and more inspectable
- SDK, CLI, notebook, scheduler, and compiler use remain independent

### Exit rule

Gate A is required for the 0.18 interchange baseline. Gate B may continue
across later minors and cannot weaken Gate A or the semantic foundation.
DataFusion ships as recommended only after its graduation gate; a failed
experiment is removed or remains explicitly experimental without becoming a
core compatibility obligation.

## 1.0 — Stable Foundation

### Public stability

- Stable authoring API
- Stable Plugin SDK protocols
- Stable `PipelinePlan`, result, event, and `PipelineRunReport` schemas
- Supported ODCS, DTCS, DPCS, ContractModel, and Python version policy
- Deprecation, compatibility, and schema-migration policies

### Production readiness

- Implemented threat model and security verification matrix
- Safe and bounded contract, profile, and configuration loading
- Plugin trust policy, allowlists, pins, and provenance reporting
- Central secret wrapper and redaction boundary
- Artifact and cache isolation by run, environment, tenant, and security domain
- Network destination, webhook, and remote-reference policies
- Security-event and audit model
- Repository security policy and private reporting process
- Performance budgets for modeling, validation, planning, reporting, and
  representative backends
- Failure injection and cancellation testing
- Complete tutorials, references, migration guides, and executable examples

### 1.0 acceptance suite

The release candidate must demonstrate:

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
15. Any graduated DataFusion integration passing its 0.18+ conformance,
    differential, dependency-isolation, and semantic-preservation gates;
    experiments that did not graduate create no 1.0 compatibility obligation.

### Exit gate

ETLantic 1.0 ships only when:

- Typed authoring, contract interoperability, validation, planning, execution,
  reporting, and plugin coordination work together end to end.
- Every mandatory control in the
  [Security Model](docs/02_FOUNDATIONS/SECURITY.md) has an implementation owner,
  automated verification, and documented residual risk.
- The public examples describe tested behavior rather than aspirations.
- SparkForge migration has proved the core abstractions without moving
  medallion semantics into ETLantic.

## 1.x Strategy

The 1.x series expands ETLantic around the stable 1.0 model without turning
the core into a server, catalog, scheduler, IDE, or AI platform.

Each minor release should:

- add one coherent integration or capability family;
- preserve 1.0 plan, report, and Plugin SDK compatibility unless an explicitly
  versioned schema extension is required;
- ship independently installable integrations for heavyweight concerns;
- use adoption evidence to adjust ordering without collapsing boundaries.

### 1.1 — FastAPI Control API

Deliver:

- separate `etlantic-fastapi` distribution;
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
- HTTP middleware guidance distinct from ETLantic runtime middleware;
- OpenAPI 3.1 schema with stable operation IDs and client-generation fixtures;
- SSE run-event streaming and optional experimental WebSockets;
- OpenAPI callbacks and webhooks generated from outbound event declarations;
- OAuth2/OIDC and application-defined authorization dependencies;
- durable submission contract returning `202 Accepted`.
- optional SQLModel-backed reference stores for registry, runs, reports,
  events, schema observations, reliability evidence, and approvals;
- separate request, persistence, and response models where fields or security
  boundaries differ.

Acceptance:

- the router embeds in an existing FastAPI application without owning its
  lifespan or dependency policy;
- OpenAPI-generated clients can submit and observe a run;
- multiple API workers share durable run state and resumable events;
- heavy pipeline work never depends on FastAPI `BackgroundTasks`;
- unauthorized profile, artifact, override, and cancellation access fails
  closed.
- live schema inspection and drift acknowledgement require explicit subject,
  profile, workspace, and policy authority.
- SQLModel sessions remain request-scoped integration details and never become
  pipeline runtime resources.

See [FastAPI Integration Plan](docs/11_DEVELOPMENT/FASTAPI_INTEGRATION_PLAN.md).

### 1.2 — Registry, Workspaces, and Discovery

Deliver:

- registry-provider protocol for contracts, pipelines, plans, plugins, and
  generated documentation;
- immutable revisions, aliases, promotion channels, signatures, and provenance;
- workspace and tenant model with namespaced identities;
- dependency and impact queries across pipeline revisions;
- immutable schema observations, operational baselines, acknowledgements, and
  remediation references;
- immutable plan, environment, reconciliation, quality, freshness,
  completeness, and statistical observation histories;
- field-aware impact queries from observed changes through contracts,
  transformations, outputs, sinks, and downstream pipelines;
- searchable metadata indexes without storing arbitrary dataset contents;
- registry events and cache-invalidation protocol;
- FastAPI registry routes and CLI parity.
- optional SQLModel-backed registry, revision, and history reference provider.

Acceptance:

- a pipeline revision can be promoted from development to production without
  changing its identity or embedding environment secrets;
- impact analysis explains which pipelines and outputs depend on a changed
  contract;
- tenant and workspace boundaries are preserved in registry, cache, API, and
  artifact identities.
- accepting an operational baseline never mutates or aliases the authoritative
  contract revision.

### 1.3 — Incremental State and Reproducibility

Deliver:

- state-provider protocol;
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
- optional SQLModel-backed state, checkpoint, and idempotency reference
  provider with transactional concurrency controls.

Acceptance:

- a failed run cannot advance a checkpoint incorrectly;
- concurrent runs detect and resolve state conflicts explicitly;
- replay identifies the exact contracts, plan, implementation, input snapshot,
  secret versions where safe, and state transition used by the original run.
- replay identifies the schema observations and baseline decisions used by the
  original run.

### 1.4 — Policy, Governance, and Supply-Chain Assurance

Deliver:

- policy-provider protocol with pre-plan, post-plan, pre-submit, and
  post-execution decisions;
- adapters for external policy engines such as OPA where justified;
- signed plans, plugin provenance, SBOM attachment, and artifact attestations;
- approval gates and separation-of-duty workflows;
- residency, classification, masking, retention, and egress constraints;
- policy decision evidence in reports and APIs;
- signed or integrity-protected production schema observations, approval gates,
  retention rules, and acknowledgement evidence;
- policy gates for stale or incomplete inputs, unsafe retries, destructive
  writes, backfills, reconciliation failures, plan drift, environment drift,
  quality trends, and privacy-sensitive statistical profiling;
- compatibility rules for policy revisions.

Acceptance:

- optimization and backend selection cannot cross a policy boundary;
- a submitted plan can be verified against its authoring revision, approved
  plugins, and policy bundle;
- approval and denial are durable, auditable, and free of secret values.
- forged, cross-tenant, or cross-environment schema observations cannot satisfy
  a deployment or execution gate.

### 1.5 — Developer Intelligence: LSP, IDE, and Static Analysis

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

### 1.6 — Planner and Optimization SDK

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

### 1.7 — Streaming and Event-Driven Pipelines

Deliver:

- stable streaming semantics beyond the 1.0 foundation;
- event-time, watermark, trigger, state, late-data, and replay contracts;
- Kafka and additional streaming provider integrations;
- continuous `PipelineRunReport` snapshots and terminal/nonterminal status;
- event-driven run triggers with deduplication and backpressure;
- streaming contract compatibility and deployment migration rules.

Acceptance:

- batch and streaming implementations of the same eligible transformation have
  documented semantic equivalence;
- restart and replay do not silently duplicate externally visible effects;
- backpressure and late-data behavior are visible in plans and reports.

### 1.8 — Remote Execution Federation

Deliver:

- remote submitter and execution-control protocols;
- capability, version, identity, and trust negotiation between client and
  runtime;
- signed plan envelopes and content-addressed artifact exchange;
- resumable event, log, and report synchronization;
- cancellation, retries, leases, heartbeats, and disconnected-client behavior;
- placement across multiple approved execution environments;
- FastAPI gateway support without requiring FastAPI in workers.

Acceptance:

- the same signed plan can be submitted to two conforming runtimes and produce
  comparable normalized reports;
- clients can disconnect and later resume observation without losing durable
  state;
- a remote runtime cannot request undeclared secrets, plugins, or network
  authority.

### 1.9 — AI-Assisted, Human-Governed Engineering

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

### 1.x Candidate Themes

These remain candidates rather than promised release numbers:

- run-history trends, regression detection, and anomaly analysis;
- schema-drift frequency, recurring-change, and source-stability trends;
- freshness, completeness, reconciliation, quality, statistical-drift, plan,
  and environment stability trends;
- additional orchestrators, dataframe engines, SQL dialects, and stores;
- declarative data previews with bounded privacy budgets;
- Wasm or isolated remote transformations where ecosystem maturity permits;
- portable testing environments and ephemeral integration stacks;
- contract-aware generated user interfaces;
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
