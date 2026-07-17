# Pipeline Validation

For portable steps in 0.11+, validation additionally resolves referenced
columns, infers expression types and nullability, verifies named outputs against
contracts, enforces IR budgets, and checks exact compiler capabilities before
execution.

Pipeline validation ensures that a pipeline is **correct before it executes**.

One of ETLantic's core design goals is to detect modeling mistakes during
authoring and planning rather than allowing them to fail unpredictably at
runtime. Validation is therefore a first-class feature, not an optional step.

## Goals

Pipeline validation should:

- Detect errors as early as possible.
- Produce deterministic, typed diagnostics.
- Remain independent of execution engines.
- Validate logical semantics instead of implementation details.
- Support both code-first and contract-first workflows.
- Enable CI/CD validation before deployment.

## Validation Philosophy

ETLantic validates a pipeline in layers.

```text
Python Pipeline
       │
       ▼
Definition Validation
       │
       ▼
Graph Validation
       │
       ▼
Contract Validation
       │
       ▼
Semantic Validation
       │
       ▼
Capability Validation
       │
       ▼
Pipeline Plan
```

Each stage builds on the previous one.

## Validation Phases

### 1. Definition Validation

Checks the Python model itself.

Examples:

- Duplicate names
- Invalid type annotations
- Missing required metadata
- Invalid source, sink, or step declarations
- Invalid subpipeline declarations

### 2. Graph Validation

Ensures the logical graph is well formed.

Checks include:

- No prohibited cycles
- Valid dependencies
- Reachable nodes
- Connected inputs
- Connected outputs
- No duplicate edges
- Valid source and sink placement

### 3. Contract Validation

Verifies referenced contracts.

Examples:

- ODCS data contracts exist
- DTCS transformation contracts exist
- DPCS subpipelines resolve
- Version requirements
- Compatibility rules

### 4. Semantic Validation

Validates pipeline meaning.

Examples:

- Scheduling intent
- Failure semantics
- Quality gates
- Public interfaces
- Execution requirements
- Extension integrity

### 5. Capability Validation

Compares pipeline requirements against the selected execution profile.

Examples:

- Retry support
- Parallel execution
- Streaming
- Checkpoints
- Compensation
- Approval workflows

Mandatory unsupported capabilities should prevent execution.

## Validation Scope

ETLantic validates:

- Pipeline metadata
- Sources
- Steps
- Sinks
- Subpipelines
- Inputs
- Outputs
- Parameters
- Data contracts
- Transformation contracts
- Pipeline contracts
- References
- Graph topology
- Lineage
- Extensions

## Incremental Validation

Editors and IDE integrations should validate incrementally as developers modify
their pipelines.

This enables immediate feedback without rebuilding the entire `PipelinePlan`.

## Diagnostics

Validation should return structured diagnostics instead of only raising
exceptions.

A diagnostic may include:

- Stable code
- Severity
- Validation phase
- Pipeline identity
- Step identity
- Source location
- Human-readable message
- Suggested remediation

Example:

```text
PMVAL104

Pipeline: CustomerPipeline
Step: publish_customers
Phase: Graph Validation

Required input "customers" is not connected.
```

## Validation API

Conceptually:

```python
result = CustomerPipeline.validate()

if result.valid:
    print("Pipeline is valid.")
else:
    for diagnostic in result.diagnostics:
        print(diagnostic)
```

Validation should never require execution.

## Planning Relationship

Validation precedes planning.

```text
Pipeline
   │
   ▼
Validation
   │
   ▼
Pipeline Plan
   │
   ▼
Execution
```

An invalid pipeline must not produce a Pipeline Plan.

## CI/CD

Recommended validation workflow:

- Validate every commit.
- Validate before artifact generation.
- Validate before publishing DPCS.
- Validate before deployment.
- Fail builds on validation errors.

## Best Practices

- Validate early and often.
- Treat warnings and errors differently.
- Keep diagnostics deterministic.
- Validate contracts before binding.
- Validate against execution capabilities before deployment.

## Anti-Patterns

Avoid:

- Delaying validation until runtime.
- Depending on orchestrator-specific validators.
- Ignoring compatibility warnings.
- Silently skipping unsupported requirements.
- Returning unstructured validation errors.

## Key Principle

> Validation proves that a pipeline is logically correct. Execution proves that
> the surrounding environment can successfully run it.

## Next Step

Continue with [Planning](PLANNING.md) to learn how a validated pipeline is
resolved into an execution-independent `PipelinePlan`.
