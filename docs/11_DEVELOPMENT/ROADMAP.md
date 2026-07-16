# Roadmap

This roadmap sequences Pipelantic from a typed modeling library into a
stable, secure orchestration model and plugin platform.

It is a direction and dependency plan, not a release-date commitment. Version
numbers describe capability milestones. A milestone is complete only when its
acceptance scenarios, documentation, tests, and security requirements pass.

## Product Outcome

Pipelantic will provide one portable model for:

- ContractModel-compatible, ODCS-aligned data contracts
- Type-driven, DTCS-aligned transformations
- Typed, DPCS-aligned pipeline composition
- Deterministic validation and planning
- References to prior step outputs without mandatory table materialization
- External execution through interchangeable plugins
- Structured logging, lifecycle extension points, and normalized run reports
- Contract, lineage, documentation, and visualization generation

Pipelantic owns the logical model and coordination contracts. It does not
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
  [Security Model](../02_FOUNDATIONS/SECURITY.md).
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
  [Dependency Strategy](DEPENDENCY_STRATEGY.md).

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
with explicit provenance and no domain semantics duplicated in Pipelantic.

## 0.3 — Validation and Pipeline Plan IR

**Status: shipped in 0.3.0**

### Deliver

- Unified top-level authoring primitives:
  `Data`, `Transformation`, and `Pipeline`
- `Data` as Pipelantic's thin public facade over ContractModel, without
  duplicating data-contract semantics or implementation
- Compatibility acceptance for existing ContractModel subclasses wherever a
  `Data` type is accepted
- Deprecation path for the uneven Pipelantic-facing `DataContractModel` name
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
  from pipelantic import Data, Pipeline, Transformation
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

The local runtime is a complete reference implementation of Pipelantic
runtime semantics, not a simplified test-only path.

## 0.5 — Dataframe Execution

### Deliver

- Stable dataframe-plugin protocol
- Polars reference plugin
- Pandas compatibility plugin
- Typed native-object and Arrow interchange
- Contract validation before and after transformations
- Valid and invalid artifact production
- Row-count, schema, timing, and validation metrics
- Shared implementation-parity fixtures and normalized reconciliation evidence
- Initial quality-history observations for null, invalid, duplicate, rejection,
  cardinality, and volume metrics
- Polars, Pandas, Arrow, and native-object schema inspectors with equivalent
  normalization and explicit inference limitations
- Safe ownership, mutation, and copy semantics
- Cross-backend conformance fixtures

### Acceptance scenarios

- Equivalent transformations produce semantically equivalent results across
  Polars and Pandas.
- Equivalent logical schemas observed through Polars, Pandas, and Arrow produce
  compatible normalized observations.
- Prior-step outputs can flow directly without forced persistence.
- Backend-native lazy behavior is retained when supported.
- Mutation or ownership rules cannot corrupt sibling branches.

### Exit gate

The dataframe SDK proves that one transformation contract can support multiple
implementations without changing pipeline semantics.

## 0.6 — SQL-Native Execution

### Deliver

- SQL implementation and relation protocols
- SQL plugin, compiler, provider, and dialect capability model
- SQL-to-SQL execution without Python materialization
- Parameter binding and identifier validation
- Transaction, retry, and materialization boundaries
- Portable append, replace, merge, create-table-as, and insert-select intents
- Replace-partition, insert-only, snapshot, delete-propagation, and slowly
  changing dimension write intents
- SQL-native reconciliation and write-result evidence
- Predicate, projection, join, and aggregation pushdown
- Safe adjacent-step query fusion
- SQL lineage and query-plan explanation
- SQL catalog, relation, and result-schema inspection with dialect-specific
  metadata preserved separately from the logical schema
- Dialect conformance suite

### Acceptance scenarios

- An eligible SQL-to-SQL pipeline executes entirely in the database.
- Values are bound rather than interpolated into SQL strings.
- Fusion preserves logical step identities, diagnostics, validation gates,
  lineage, and security boundaries.
- Unsupported merge or transaction semantics fail before execution or use an
  explicitly documented fallback.
- Catalog-supported inspection does not execute arbitrary queries or read
  source rows merely to discover schema metadata.

### Exit gate

SQL is a first-class execution backend rather than a special pipeline type.

## 0.7 — Distributed Spark Execution

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
  validating, planning, testing, documenting, and safely modifying Pipelantic
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
  importing Pipelantic internals or executing a pipeline during analysis.
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

See [Schema Drift and Evolution Plan](SCHEMA_DRIFT_PLAN.md) for the cross-phase
observation, history, policy, impact, and remediation design.
See [ETL Reliability and Recovery Plan](ETL_RELIABILITY_PLAN.md) for freshness,
repair, retries, writes, reconciliation, backfills, parity, drift, and quality
tracking.

## 0.10 — SparkForge Migration Preview

This milestone begins only after Local Python, SQL, PySpark, reporting, and the
Plugin SDK have stable integration surfaces.

### Deliver

- SparkForge-to-Pipelantic adapter
- Mapping of medallion steps to ordinary Pipelantic nodes and profiles
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
- Pipelantic receives no bronze, silver, or gold concepts.
- SparkForge can progressively replace its SQL and Spark engines without an
  all-at-once user migration.

### Exit gate

SparkForge can depend on Pipelantic as its underlying model, planner, and
coordination engine while remaining the medallion-focused facade.

See [SparkForge Feature Adoption](SPARKFORGE_ADOPTION.md) for the detailed
feature assessment and adapter sequence.

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
12. A representative SparkForge pipeline using Pipelantic underneath.

### Exit gate

Pipelantic 1.0 ships only when:

- Typed authoring, contract interoperability, validation, planning, execution,
  reporting, and plugin coordination work together end to end.
- Every mandatory control in the
  [Security Model](../02_FOUNDATIONS/SECURITY.md) has an implementation owner,
  automated verification, and documented residual risk.
- The public examples describe tested behavior rather than aspirations.
- SparkForge migration has proved the core abstractions without moving
  medallion semantics into Pipelantic.

## 1.x Strategy

The 1.x series expands Pipelantic around the stable 1.0 model without turning
the core into a server, catalog, scheduler, IDE, or AI platform.

Each minor release should:

- add one coherent integration or capability family;
- preserve 1.0 plan, report, and Plugin SDK compatibility unless an explicitly
  versioned schema extension is required;
- ship independently installable integrations for heavyweight concerns;
- use adoption evidence to adjust ordering without collapsing boundaries.

### 1.1 — FastAPI Control API

Deliver:

- separate `pipelantic-fastapi` distribution;
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
- HTTP middleware guidance distinct from Pipelantic runtime middleware;
- OpenAPI 3.1 schema with stable operation IDs and client-generation fixtures;
- SSE run-event streaming and optional experimental WebSockets;
- OpenAPI callbacks and webhooks generated from outbound event declarations;
- OAuth2/OIDC and application-defined authorization dependencies;
- durable submission contract returning `202 Accepted`.

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

See [FastAPI Integration Plan](FASTAPI_INTEGRATION_PLAN.md).

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
- a versioned, vendor-neutral Pipelantic AI workflow catalog;
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
  Cursor SDK dependency in Pipelantic core.

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

See [Schema Drift and Evolution Plan](SCHEMA_DRIFT_PLAN.md).
See [ETL Reliability and Recovery Plan](ETL_RELIABILITY_PLAN.md).

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

Pipelantic is ready to replace SparkForge's duplicated underlying engines
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

This gate does not require Pipelantic to understand medallion layers.

## Explicit Non-Goals

Pipelantic does not plan to become:

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

A proposed feature belongs in Pipelantic when it strengthens portable
modeling, static analysis, deterministic planning, lifecycle coordination,
result normalization, or plugin interoperability.

Use this ownership test:

| Concern | Owner |
|---|---|
| Meaning of data, transformation, or pipeline contracts | ODCS, DTCS, or DPCS |
| Operationalizing data contracts | ContractModel |
| Portable pipeline model, planner, and coordination protocols | Pipelantic |
| Backend execution mechanics | Execution plugins and providers |
| Medallion conventions and migration experience | SparkForge |

When ownership is unclear, prefer a small public protocol and keep concrete
runtime behavior outside the core.
