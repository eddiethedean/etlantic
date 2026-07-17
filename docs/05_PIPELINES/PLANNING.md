# Planning

Planning converts a validated logical pipeline and selected profile into an
immutable, resolved `PipelinePlan`.

The plan is the execution-facing intermediate representation shared by direct
execution, backend compilation, visualization, documentation, and static
analysis.

## Planning Contract

```text
Validated logical pipeline
          +
Selected profile
          +
Plugin registry and capabilities
          ↓
Resolved PipelinePlan
```

Planning never executes transformation code, acquires live credentials, or
materializes user data.

## Inputs

The planner consumes:

- Pipeline identity and logical graph
- ODCS data-contract references
- DTCS transformation definitions
- DPCS pipeline semantics
- Transformation implementations
- Portable transformation definitions and fingerprints
- Profile configuration
- Source and sink bindings
- Resource-provider references
- Installed plugin descriptors and capabilities

## Planning Phases

### 1. Freeze the Logical Model

Normalize code-first or contract-first input into a stable graph of:

- Sources
- Steps
- Sinks
- Subpipeline interfaces
- Typed ports
- Parameters
- Edges

No environment-specific behavior is introduced yet.

### 2. Resolve Contracts and References

Resolve contract identity and version requirements:

- ODCS data contracts
- DTCS transformations
- DPCS subpipelines
- Internal port references
- External registry references, when configured

The planner must preserve the authority of each domain model rather than
flattening all contracts into one generic object.

### 3. Apply the Profile

Apply environment-specific choices:

- Orchestrator
- Default transformation engine
- Node-specific implementation overrides
- Source and sink bindings
- Resource providers
- Concurrency and timeout settings
- Backend compiler options
- Portable/native selection policy

Profile application may select how the graph is realized. It may not change its
portable semantics.

### 4. Select Portable or Native Realization

Select a realization for every executable transformation. From 0.11 onward,
eligible steps may compile a `dtcs.transform-plan/1` produced by the
`etlantic.transform/1` authoring profile, or use a registered native
implementation.

Recommended precedence:

```text
Explicit step policy or override
        ↓
Portable definition supported by selected compiler
        ↓
Registered native implementation
        ↓
Unambiguous installed fallback allowed by policy
```

Ambiguity is a planning error.

### 5. Evaluate Capabilities

Compare required semantics with plugin capabilities.

Examples:

- Transactions
- Async execution
- Streaming
- Checkpoints
- Event-time watermarks
- Retry and cancellation behavior
- Dynamic mapping
- SQL functions and data types
- Spark stateful operations
- Portable relational operations, scalar functions, types, and semantic modes

ETLantic must not silently approximate mandatory behavior.

### 6. Form Execution Regions

Group compatible logical nodes where one backend can realize them together:

```text
SQL-capable steps       → SQL region
Polars lazy steps       → Polars lazy region
Spark-native steps      → Spark region
Python callables        → Local Python region
```

Region formation considers:

- Backend compatibility
- Shared environment
- Fan-out and reuse
- Validation gates
- Retry boundaries
- Failure attribution
- Required materialization
- Transaction scope

### 7. Insert Physical Boundaries

Add boundaries required for:

- Cross-backend artifact transfer
- Validation
- Persistence
- Checkpoints
- Reused outputs
- External orchestrator tasks
- Transaction boundaries

Logical edges remain preserved even when the physical graph differs.

### 8. Resolve Output References

Every downstream input references a logical output port, not an assumed table.

```python
scored = ScoreCustomers.step(
    customers=normalized.result,
)
```

The planner resolves `normalized.result` to an edge strategy:

```text
Logical OutputRef
       │
       ├── native in-memory value
       ├── lazy dataframe or logical plan
       ├── SQL relation or CTE
       ├── cached backend artifact
       └── durable ArtifactRef
```

The selected strategy depends on:

- whether producer and consumer share an execution region
- process and orchestrator boundaries
- fan-out and reuse
- memory and persistence policies
- validation and checkpoint requirements
- backend interoperability
- retry and failure boundaries

The default should preserve the upstream result directly when safe. Reading a
published table is appropriate only when the pipeline explicitly references a
source binding or when planning requires durable materialization.

### 9. Resolve Resource References

Resolve logical resource names to provider descriptors and scopes.

The plan records how a resource will be obtained but never includes resolved
credentials or live resource objects.

### 10. Produce the PipelinePlan

The final plan contains:

- Pipeline and plan identity
- Contract and plugin versions
- Logical graph
- Physical execution units
- Logical-to-physical mappings
- Resolved implementations
- Portable IR fingerprints, compiler identities, and implementation kind
- Bindings
- Resource references
- Execution regions
- Materialization boundaries
- Logical output references and resolved artifact strategies
- Retry, timeout, and failure requirements
- Capability decisions
- Generation and compilation metadata

## Determinism

Equivalent inputs should produce semantically equivalent plans.

A canonical plan hash may include:

- Pipeline definition
- Contract identities and versions
- Selected profile
- Plugin descriptors and versions
- Portable definition and compiler fingerprints
- Planner version

It must exclude secret values and incidental process state.

## Logical Versus Physical Plans

The logical graph explains the pipeline to users.

The physical graph explains how a selected backend will realize it.

```text
Logical:
filter → join → aggregate

Physical SQL:
one INSERT ... SELECT statement
```

The plan retains mappings to every logical node for lineage, diagnostics,
documentation, and failure attribution.

## Multiple Profiles, Multiple Plans

```text
CustomerPipeline
      ├── Local + Polars plan
      ├── Local + Pandas plan
      ├── Airflow + SQL plan
      └── Airflow + PySpark plan
```

The plans may differ physically while preserving one logical pipeline contract.

## Planning Diagnostics

Planning should report:

- Missing or ambiguous implementation
- Unresolved binding
- Missing resource provider
- Unsupported backend capability
- Unsafe artifact boundary
- Invalid transaction region
- Unsupported SQL dialect feature
- Unsupported Spark streaming behavior
- Plugin-version incompatibility

Diagnostics should explain the required capability, selected backend, and
available alternatives when known.

## API

Conceptually:

```python
plan = CustomerPipeline.plan(profile="production")
```

The plan may then be:

```python
result = await plan.arun()
artifact = plan.compile(target="airflow")
diagram = CustomerPipeline.to_mermaid()
```

Exact convenience methods remain a proposed 1.0 API; the architectural rule is
that each operation consumes the same resolved plan.

## Caching

Plans may be cached when the cache key includes every semantic input.

Cached plans are invalidated by relevant changes to:

- Pipeline definitions
- Contracts
- Profiles
- Plugin capabilities or versions
- Planner version

## Non-Goals

Planning does not:

- Execute transformations
- Read production data
- Acquire credentials
- Repair invalid pipelines
- Provision infrastructure
- Pretend unsupported runtime behavior is safe

## Key Principle

> Planning is the point where portable meaning meets a concrete environment.
> The result is resolved enough to execute, but still independent of any one
> runtime's private object model.

## Next Step

Continue with [Profiles](PROFILES.md) to learn how environment-specific choices
feed the planner without changing the logical pipeline.
