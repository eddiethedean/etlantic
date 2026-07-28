# SparkForge Feature Adoption

This document records which ideas ETLantic should carry forward from
[SparkForge](https://github.com/eddiethedean/sparkforge), where those ideas
belong, and which implementation patterns should not be repeated.

SparkForge remains the user-facing medallion pipeline builder. ETLantic is
intended to become its typed, backend-independent modeling, planning, and
coordination engine.

## Architectural Boundary

The target relationship is:

```text
SparkForge
├── medallion vocabulary
├── bronze, silver, and gold conventions
├── opinionated defaults
├── migration compatibility
└── user-facing builder
          │
          ▼
ETLantic
├── typed pipeline graph
├── validation and diagnostics
├── run selection and planning
├── execution lifecycle
├── normalized results and events
└── plugin coordination
          │
          ▼
Execution plugins and providers
├── PySpark
├── SQL
├── Delta Lake
├── storage
├── orchestration
└── observability
```

ETLantic must not introduce bronze, silver, gold, or medallion semantics
into its core model. SparkForge maps those concepts onto ordinary
`Source`, `Step`, `Transformation`, `Sink`, profile, and policy objects.

## Executive Recommendation

SparkForge contains several valuable product behaviors, but they are spread
across Spark-specific, SQL-specific, base, writer, monitoring, and compatibility
packages. ETLantic should preserve the behavior while replacing the
fragmented implementation with stable logical models and capability-based
plugins.

The highest-value features to adopt are:

1. Interactive and selective pipeline execution.
2. Direct references to previous step results without requiring table
   materialization.
3. Explicit run intents such as initial, incremental, full refresh, and
   validation-only.
4. Quality gates that produce valid and invalid artifacts plus structured
   metrics.
5. Deterministic dependency analysis with explainable execution groups.
6. Rich, normalized run and step results.
7. Structured contextual logging across every backend.
8. Durable run-history interfaces for trends and anomaly detection.
9. Environment profiles with safe development, test, and production defaults.
10. Incremental state and watermark coordination.
11. Explicit write, materialization, and retry policies.
12. Backend parity and conformance testing.

## Adoption Matrix

| SparkForge capability | ETLantic disposition | Target owner | Priority |
|---|---|---|---|
| Automatic dependency ordering | Adopt and generalize | ETLantic planner | Required |
| Cycle detection | Adopt with diagnostics | ETLantic validation | Required |
| Automatic cycle breaking | Reject | — | Never |
| Run until a step | Adopt | Run selection and local orchestration | Required |
| Run one step | Adopt | Run selection and local orchestration | Required |
| Rerun with downstream invalidation | Adopt | Debug session and artifact state | Required |
| Reference an upstream step result | Adopt as typed output references | Logical graph and runtime artifact resolution | Required |
| Re-read every intermediate result from a table | Reject as the default | — | Never |
| Per-run parameter overrides | Adopt | Run request | Required |
| Skip writes while debugging | Adopt as materialization policy | Planner and plugins | Required |
| Initial, incremental, full-refresh, validation-only modes | Generalize as run intents | Execution model | Required |
| Incremental watermark column | Generalize as state strategy | ETLantic plus storage plugins | Required |
| Validation thresholds | Adopt as named quality policies | ContractModel integration and ETLantic gates | Required |
| Valid and invalid row outputs | Adopt as typed validation artifacts | ContractModel and execution plugins | Required |
| String validation-rule shorthand | Do not put in core | ContractModel adapters or compatibility layer | Optional |
| Development, test, and production presets | Adopt as profile templates | Profiles | Recommended |
| Run and step metrics | Adopt | Result and event model | Required |
| Contextual pipeline logging | Adopt and standardize | Logging context and observability providers | Required |
| Persisted execution logs | Adopt through a provider interface | Observability provider | Recommended |
| Quality trends and anomaly detection | Support through event consumers | Observability integrations | Later |
| Parallel candidates and execution groups | Adopt and expose through `explain` | Planner | Required |
| Dependency recommendations | Adopt as structured lint findings | Diagnostics and linting | Recommended |
| Retry configuration | Adopt as execution policy | Plan plus orchestrator plugins | Required |
| Spark, SQL, and mock engine variants | Replace with capabilities and conformance | Plugin SDK | Required |
| Delta merge, optimize, vacuum, and history | Keep backend-specific | Delta storage plugin | Plugin |
| Schema and catalog creation | Keep backend-specific | Storage plugins and profiles | Plugin |
| Medallion phases and defaults | Keep in SparkForge | SparkForge | Required boundary |

## 1. Interactive and Selective Execution

SparkForge's `PipelineDebugSession` provides unusually useful workflows:

- run the graph up to a named step
- execute one step using available dependencies
- rerun a step after changing parameters
- invalidate downstream results
- override a transformation or validation rules for one debug run
- suppress writes while inspecting intermediate output

These behaviors should become a backend-independent ETLantic feature rather
than a Spark notebook utility.

### Proposed model

```python
request = RunRequest(
    selection=RunSelection.until("normalize_customers"),
    materialization=MaterializationPolicy.none(),
    parameter_overrides={
        "normalize_customers": {"minimum_age": 21},
    },
)

result = pipeline.run(profile="local", request=request)
```

Additional selection forms should include:

```python
RunSelection.only("normalize_customers")
RunSelection.until("publish_customers")
RunSelection.from_("normalize_customers")
RunSelection.between("normalize_customers", "publish_customers")
RunSelection.upstream_of("publish_customers")
RunSelection.downstream_of("normalize_customers")
RunSelection.matching(tags={"daily"})
```

Selection is a graph operation. It must compute the necessary dependency
closure and explain why each node is included, skipped, reused, or invalidated.

### Debug session

A stateful local convenience API may sit above `RunRequest`:

```python
with pipeline.debug(profile="local") as session:
    first = session.run_until("normalize_customers")
    session.override(
        "normalize_customers",
        parameters={"minimum_age": 21},
    )
    second = session.rerun(
        "normalize_customers",
        invalidate="downstream",
    )
```

The session is developer tooling. The underlying selection, invalidation,
artifact, and result models must remain usable by every orchestrator.

## 2. Previous-Step Result References

One of SparkForge's most useful behaviors is that a transformation can consume
the result already produced by an earlier step. It does not have to identify
and reread the upstream step's entire persisted table.

ETLantic should make this a foundational graph concept:

```python
normalized = NormalizeCustomers.step(
    customers=raw.result,
)

scored = ScoreCustomers.step(
    customers=normalized.result,
)
```

`normalized.result` is a typed `OutputRef[Customer]`. It identifies a logical
result port, not a table name and not a dataframe object.

### Why this matters

Direct result references allow a backend to preserve its best native form:

- a Polars `LazyFrame`
- a Pandas dataframe in local memory
- a SQL relation or common table expression
- a Spark dataframe or unresolved logical plan
- a durable artifact reference across an orchestrator boundary

Forcing every intermediate through a table would:

- introduce unnecessary writes and reads
- lose lazy optimization opportunities
- make local debugging slower
- couple logical pipelines to storage layouts
- make SQL and Spark region fusion harder
- confuse an intermediate result with a published dataset

### Logical and physical references

ETLantic should distinguish:

```text
OutputRef
    Logical reference from one typed port to another.

ArtifactRef
    Physical runtime handle selected by planning or execution.

DatasetBinding
    External or published storage identity.
```

The logical pipeline contains `OutputRef` edges. Planning decides how each edge
is physically represented.

```text
normalize.result
       │
       ├── same process ─────► in-memory or lazy native object
       ├── same SQL region ──► SQL relation or CTE
       ├── same Spark job ───► Spark logical plan
       └── task boundary ────► durable ArtifactRef
```

### Persistence is a policy

Referencing a result must not imply that it is persisted. Materialization is a
separate planning decision.

```python
normalized.result.persist(
    policy=PersistencePolicy.when_reused(),
)
```

Possible decisions include:

- keep ephemeral
- cache within the backend
- checkpoint
- spill to an artifact store
- materialize as a temporary relation
- publish through a `Sink`

Only a `Sink` or explicit publication policy turns an intermediate result into
a published dataset.

### Multiple results

The mechanism must work with named outputs:

```python
validated = ValidateCustomers.step(customers=normalized.result)

publish = PublishCustomers.step(customers=validated.valid)
quarantine = QuarantineCustomers.step(customers=validated.rejected)
```

Each output has its own contract, consumers, validation state, and physical
realization.

### Runtime resolution

Execution resolves an `OutputRef` against the current run's artifact context:

```python
ArtifactKey(
    pipeline_id="customer_pipeline",
    run_id=run.id,
    step_id="normalize_customers",
    output_name="result",
)
```

The context should hold artifact handles and metadata, not a loose dictionary
of engine-specific dataframes. This gives ETLantic consistent behavior
across local, SQL, Spark, Airflow, and future backends.

### Reuse and invalidation

Previous-step references also make debug invalidation precise:

- rerunning a step replaces only its output artifacts
- downstream artifacts are marked stale through graph edges
- unrelated branches remain reusable
- a persisted artifact may be reused when its provenance and cache key match

This capability is therefore the bridge between typed wiring, selective
execution, caching, materialization, and lineage.

## 3. Run Intents

SparkForge exposes initial, incremental, full-refresh, and validation-only
execution. ETLantic should preserve the use cases without encoding
medallion-specific behavior.

```python
class RunIntent(str, Enum):
    STANDARD = "standard"
    INITIALIZE = "initialize"
    INCREMENTAL = "incremental"
    REFRESH = "refresh"
    VALIDATE = "validate"
    BACKFILL = "backfill"
    REPLAY = "replay"
```

A run intent expresses user intent. It does not directly dictate append,
overwrite, merge, or checkpoint mechanics. Planning resolves the intent against:

- source and sink capabilities
- transformation semantics
- profile policies
- available state
- selected execution backend

For example, `INCREMENTAL` may resolve to a watermark scan and merge for one
pipeline, change-data capture for another, and an unsupported-capability
diagnostic for a third.

## 4. Incremental State and Watermarks

SparkForge's `incremental_col` demonstrates a valuable capability but couples
incremental semantics to a column and engine implementation.

ETLantic should define a small state model:

```python
IncrementalStrategy.watermark(
    field="updated_at",
    ordering="ascending",
    overlap="5 minutes",
)

IncrementalStrategy.cursor(key="event_sequence")
IncrementalStrategy.change_feed(version_key="commit_version")
IncrementalStrategy.snapshot_diff(keys=["customer_id"])
```

The core owns:

- the declared strategy
- state identity and namespace
- checkpoint requirements
- planning rules
- diagnostics
- normalized state transitions

Providers own:

- reading and atomically committing state
- backend-specific filters
- change-feed access
- locking and concurrency control

State advancement must occur only after the required materializations succeed.
A failed or validation-only run must not silently advance production state.

## 5. Quality Gates and Invalid Artifacts

SparkForge applies validation rules, separates valid and invalid rows, calculates
validation rates, and compares them with configurable thresholds. This should be
preserved, but ContractModel remains the authority for operationalizing data
contracts.

ETLantic should coordinate a quality gate:

```python
QualityGate(
    contract=Customer,
    policy="production",
    on_failure=QualityAction.fail(),
    invalid_output="rejected_customers",
)
```

A normalized result should include:

```python
ValidationResult(
    evaluated_records=10_000,
    valid_records=9_970,
    invalid_records=30,
    pass_rate=0.997,
    passed=True,
    valid_artifact=...,
    invalid_artifact=...,
    diagnostics=(...),
)
```

Important design rules:

- thresholds are named policies, not medallion phase fields
- rules come from data contracts or explicit policy extensions
- plugins declare which rules they can evaluate natively
- unsupported rules produce capability diagnostics or an explicit fallback
- invalid data is a typed artifact, not an incidental dataframe
- counting and materialization costs are visible in the plan

## 6. Dependency Analysis and Explainability

SparkForge includes topological ordering, cycle detection, dependency
statistics, parallel candidates, cached analysis, and recommendations.
ETLantic already treats planning as compilation; it should make this
analysis visible and structured.

```python
explanation = pipeline.explain(profile="production")

explanation.execution_groups
explanation.critical_path
explanation.parallel_candidates
explanation.materialization_boundaries
explanation.capability_fallbacks
explanation.findings
```

Findings should use stable diagnostic codes rather than prose-only
recommendations.

```text
PMPLAN201: Node "publish_customers" introduces a cross-backend materialization.
PMPLAN214: Three downstream nodes reuse "normalized"; consider persistence.
PMGRAPH001: Circular dependency detected: a -> b -> a.
```

ETLantic must never automatically break a dependency cycle. A cycle changes
the declared meaning of the pipeline and therefore requires an error or a
domain-supported iterative construct.

## 7. Run Results, Events, and Durable History

SparkForge records run identity, mode, timestamps, step timing, row counts,
validation rates, table information, failures, warnings, and recommendations.
This is a strong foundation for ETLantic's normalized result model.

ETLantic should standardize:

```python
PipelineRunResult
StepRunResult
ArtifactResult
ValidationResult
StateTransitionResult
MaterializationResult
RunDiagnostic
```

Every result should carry stable logical and physical identities so fused SQL or
Spark regions can still report against the original logical steps.

Execution should also emit immutable lifecycle events:

```text
run.planned
run.started
step.started
validation.completed
artifact.materialized
state.committed
step.completed
step.failed
run.completed
run.failed
```

An observability provider may persist those events to SQL, Delta, OpenTelemetry,
OpenLineage, files, or another system. Analytics such as trends, regression
detection, and anomaly detection should consume the normalized history rather
than live inside a storage-specific log writer.

### Structured logging

SparkForge's pipeline logger and writer demonstrate the usefulness of consistent
run and step context. ETLantic should standardize structured log records
with:

- pipeline, plan, run, step, and attempt identifiers
- stable event and diagnostic codes
- selected plugin and physical backend
- redacted structured attributes
- links to remote jobs, queries, and task logs

The core owns context propagation and redaction. Observability providers own
routing and persistence. Logs complement lifecycle events and results; they do
not replace them.

## 8. Profile Templates

SparkForge's development, test, and production factories are useful because
they give users safe starting points. ETLantic should offer profile
templates without hiding their resolved values.

```python
Profile.development(...)
Profile.testing(...)
Profile.production(...)
```

Templates may set defaults for:

- diagnostics strictness
- validation policy
- concurrency
- retry policy
- caching and persistence
- observability
- local versus external artifact storage

The resolved profile must be inspectable and serializable with secrets removed.

## 9. Retry, Write, and Materialization Policies

SparkForge exposes append, overwrite, merge, ignore, retry counts, and retry
delays. ETLantic should model the portable intent and delegate mechanics.

```python
WriteIntent.append()
WriteIntent.replace()
WriteIntent.merge(keys=["customer_id"])
WriteIntent.skip_if_exists()

RetryPolicy(
    attempts=3,
    backoff="exponential",
    retry_on={"transient"},
)
```

The planner must verify that the selected storage and orchestration plugins can
preserve these semantics. It must not translate an unsupported merge into an
append or retry a non-idempotent operation without an explicit safe policy.

Materialization deserves its own policy because SparkForge's debug
`write_outputs=False`, validation materialization, Spark caching, SQL query
fusion, and durable writes are all forms of the same planning decision.

## 10. Backend Parity and Conformance

SparkForge's split into Spark and SQL builders is the main architecture to
avoid. ETLantic should retain one logical pipeline and test backend
implementations against the same semantic fixtures.

The Plugin SDK conformance suite should verify:

- equivalent logical inputs and outputs
- normalized failure categories
- validation behavior
- run-mode support
- write semantics
- lineage preservation
- logical step identity through fused execution
- deterministic plan and result serialization

A lightweight fake backend remains valuable for unit tests, but ETLantic
should not silently swap real and mock runtimes through import detection.
Backend choice must be explicit in the profile or test fixture.

## Capabilities That Stay in Plugins

The following SparkForge features are valuable but do not belong in
ETLantic core:

- Spark dataframe expressions and Catalyst behavior
- SQLAlchemy, Moltres, and dialect-specific query conversion
- JDBC reads and writes
- Delta Lake merge, optimization, vacuum, version history, and time travel
- schema and catalog creation
- engine-specific dataframe caching
- database transactions and isolation levels
- Spark cluster and session configuration

ETLantic may model the required capability and normalized result. The
plugin implements it.

## Capabilities That Stay in SparkForge

SparkForge should continue to own:

- bronze, silver, and gold terminology
- medallion-specific builder methods
- default medallion dependency conventions
- layer-oriented validation presets
- medallion naming and storage conventions
- compatibility with existing SparkForge projects
- migration helpers from the current API

Conceptually:

```python
sparkforge.add_bronze_step(...)
```

may internally construct:

```python
Source(...)
Step(...)
QualityGate(...)
Sink(...)
```

and then delegate validation and planning to ETLantic.

## Patterns Not to Carry Forward

ETLantic should explicitly avoid:

### Separate builders per execution engine

There must not be a `SparkPipeline`, `SqlPipeline`, and `PandasPipeline`
hierarchy with diverging behavior. Backends implement capabilities against one
logical model.

### Silent cycle resolution

Removing a graph edge to make an invalid graph executable changes its meaning.
Cycles require diagnostics or an explicit iterative semantic construct.

### Phase-coded core models

Fields such as bronze, silver, and gold validation thresholds are SparkForge
policy, not portable pipeline semantics.

### Implicit fallback

Unsupported operations must not silently move to another engine or degrade
semantics. Fallback must be planned, visible, and policy-controlled.

### Raw backend expressions as the portable model

PySpark columns, SQLAlchemy expressions, and string SQL can implement a
transformation, but they cannot define the shared pipeline graph.

### Storage-specific observability core

ETLantic standardizes events and results. Providers persist and analyze
them.

## Migration Strategy

### Phase 1 — Compatibility model

- Define a mapping from every SparkForge step to ETLantic logical nodes.
- Preserve current SparkForge user APIs.
- Generate and inspect ETLantic plans without changing execution.
- Compare dependency order, validation policies, and expected writes.

### Phase 2 — Shared results and diagnostics

- Convert SparkForge execution output into ETLantic result models.
- Emit ETLantic lifecycle events.
- Introduce stable diagnostic codes.
- Run both reporting paths during migration.

### Phase 3 — ETLantic planning

- Let ETLantic own graph validation and execution selection.
- Resolve SparkForge medallion conventions into explicit policies.
- Compare generated plans with current SparkForge execution behavior.

### Phase 4 — Plugin execution

- Move Spark execution to the PySpark plugin.
- Move SQL execution to SQL plugins and dialects.
- Move Delta behavior to a Delta storage plugin.
- Retire duplicated SparkForge execution engines.

### Phase 5 — SparkForge as a focused facade

- Keep the medallion builder and migration helpers.
- Delegate modeling, validation, planning, events, and results.
- Add deprecation paths for legacy engine-specific extension points.

## Required ETLantic Deliverables

The following deliverables should be tracked before SparkForge can depend on
ETLantic as its engine:

- [x] `RunIntent`
- [x] `RunSelection`
- [x] `RunRequest`
- [x] typed `OutputRef` and runtime `ArtifactRef`
- [x] run-scoped artifact context
- [x] direct upstream-result resolution without required persistence
- [x] graph slicing and dependency closure
- [x] debug session with downstream invalidation
- [x] parameter and implementation overrides scoped to a run
- [x] materialization policy
- [x] incremental strategy and state provider protocol
- [x] quality gate and invalid-artifact model
- [x] structured plan explanation
- [x] normalized run and step results
- [x] lifecycle event protocol
- [x] structured logging record and context propagation
- [x] redaction and sensitive-data conformance tests
- [x] observability provider protocol
- [x] write-intent capability checks
- [x] retry-safety validation
- [x] profile templates
- [x] cross-backend semantic conformance fixtures
- [x] SparkForge adapter and migration test suite (`medallantic`, 0.10)

## Source Notes

This assessment is based on the SparkForge repository's:

- [pipeline runner and run modes](https://github.com/eddiethedean/sparkforge/blob/main/src/pipeline_builder/pipeline/runner.py)
- [interactive debug session](https://github.com/eddiethedean/sparkforge/blob/main/src/pipeline_builder/pipeline/debug_session.py)
- [dependency analyzer](https://github.com/eddiethedean/sparkforge/blob/main/src/pipeline_builder_base/dependencies/analyzer.py)
- [dependency graph](https://github.com/eddiethedean/sparkforge/blob/main/src/pipeline_builder_base/dependencies/graph.py)
- [Spark validation implementation](https://github.com/eddiethedean/sparkforge/blob/main/src/pipeline_builder/validation/data_validation.py)
- [SQL validation implementation](https://github.com/eddiethedean/sparkforge/blob/main/src/sql_pipeline_builder/validation/sql_validation.py)
- [engine-neutral execution log model](https://github.com/eddiethedean/sparkforge/blob/main/src/pipeline_builder_base/writer/models.py)
- [writer analytics](https://github.com/eddiethedean/sparkforge/blob/main/src/pipeline_builder/writer/analytics.py)

The implementation contains compatibility layers and unfinished or conflicting
paths. The feature intent is useful; the current class hierarchy is not the
target architecture.
