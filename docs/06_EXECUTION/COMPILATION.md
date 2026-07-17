**Status: shipped in 0.8.0** via `etlantic-airflow`.

# Compilation

Compilation is the process of transforming a validated **Pipeline Plan** into an
optimized, executable representation for a specific execution backend.

Unlike traditional programming language compilers, ETLantic compilation
does not change the meaning of a pipeline. Instead, it translates a portable
`PipelinePlan` into a backend-specific artifact while preserving the semantics
defined by ODCS, DTCS, and DPCS.

Compilation occurs after planning and before execution.

The future portable transformation compiler performs a nested, narrower form
of compilation: it lowers DTCS Transformation Plan expressions to native
Polars, Pandas, SQL, or Spark expressions. The DTCS plan remains the semantic source
of truth and its fingerprint remains in the plan.

## Goals

Compilation should:

- Preserve pipeline semantics.
- Produce deterministic output.
- Optimize execution where permitted.
- Target multiple execution backends.
- Validate backend compatibility.
- Remain independent of pipeline authoring.

## Execution Lifecycle

```text
Pipeline
    │
    ▼
Validation
    │
    ▼
Planning
    │
    ▼
Pipeline Plan
    │
    ▼
Compilation
    │
    ▼
Executable Artifact
    │
    ▼
Execution
```

Compilation never changes the logical meaning of the Pipeline Plan.

## Why Compilation?

The Pipeline Plan is an implementation-independent intermediate
representation (IR).

Execution backends require backend-specific artifacts such as:

- Airflow DAGs
- Dagster Definitions
- Prefect Flows
- Local execution graphs
- Deployment manifests

Compilation performs this translation.

## Intermediate Representation

The Pipeline Plan acts as ETLantic's canonical IR.

It contains:

- Graph topology
- Step identities
- Contract references
- Parameters
- Resource bindings
- Execution requirements
- Failure semantics
- Quality gates
- Lineage

Every compiler consumes the same IR.

## Compilation Targets

ETLantic may compile to:

- Local Python
- Airflow
- Dagster
- Prefect
- Argo Workflows
- Future orchestration systems

Additional plugins may define new compilation targets.

## Optimization

Compilers may perform optimizations that preserve observable behavior.

Examples include:

- Parallel scheduling
- Step fusion
- Resource reuse
- Lazy evaluation
- Execution batching

Optimizations must never change:

- Data contracts
- Transformation semantics
- Pipeline semantics
- Failure behavior

## Capability Verification

Compilation verifies that the target backend supports all required semantics.

Examples include:

- Retry support
- Scheduling
- Streaming
- Checkpoints
- Compensation
- Dynamic branching

Compilation fails if mandatory capabilities cannot be preserved.

## Determinism

Compilation should be deterministic.

Equivalent Pipeline Plans should produce semantically equivalent backend
artifacts.

## Diagnostics

Compilation failures should produce structured diagnostics.

Typical causes include:

- Unsupported backend feature
- Missing plugin
- Capability mismatch
- Invalid binding
- Version incompatibility

## Relationship to Plugins

Compilation is performed by execution plugins.

ETLantic defines the compilation interface.

Plugins implement backend-specific compilation strategies.

## Caching

Compiled artifacts may be cached when:

- Pipeline Plan is unchanged.
- Plugin version is unchanged.
- Profile is unchanged.
- Runtime capabilities are unchanged.

## Best Practices

- Compile only validated Pipeline Plans.
- Preserve observable semantics.
- Keep optimizations backend-specific.
- Produce deterministic artifacts.
- Report structured diagnostics.

## Anti-Patterns

Avoid:

- Compiling directly from Python pipeline classes.
- Changing pipeline meaning during optimization.
- Embedding backend-specific logic into pipeline definitions.
- Skipping capability verification.

## Key Principle

> Compilation transforms a portable Pipeline Plan into a backend-specific
execution artifact while preserving every semantic defined by the pipeline
contracts. The Pipeline Plan is the canonical intermediate representation;
compiled artifacts are backend-specific implementations of that plan.

## Next Step

Continue with [SQL](SQL.md) to see how compilation and backend capability
analysis enable database-native execution.
