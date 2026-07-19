# Subpipelines

> **Status split (0.14.0):** Nested pipeline composition as typed steps is
> **Available** where examples and tests cover it. Treat deep nesting, separate
> versioning productization, and advanced lineage claims as **pilot-bounded**
> unless CAPABILITIES.md lists them as shipped.


A **subpipeline** is a reusable pipeline embedded inside another pipeline.

Subpipelines allow complex workflows to be composed from smaller, independently
validated pipeline units. Each subpipeline preserves its own typed interface,
contract identity, and internal graph while exposing a clear boundary to its
parent pipeline.

## Purpose

A subpipeline answers one question:

> How can a complete pipeline be reused as one logical step inside another pipeline?

Subpipelines support:

- Modular pipeline design
- Reuse across projects
- Independent validation
- Clear ownership boundaries
- Nested DPCS composition
- Separate testing and versioning
- Simpler lineage and documentation

## Basic Example

```python
class CustomerCurationPipeline(Pipeline):
    raw = Extract[RawCustomer](
        binding="raw.customers",
    )

    normalized = NormalizeCustomers.step(
        customers=raw,
    )

    curated = Load[Customer](
        input=normalized.result,
        binding="curated.customers",
    )
```

The pipeline can then be reused inside a larger workflow:

```python
class AnalyticsPipeline(Pipeline):
    customers = CustomerCurationPipeline.subpipeline(
        raw=customer_source,
    )

    metrics = CalculateCustomerMetrics.step(
        customers=customers.curated,
    )
```

The exact API may evolve, but the architectural model should remain the same:
the parent pipeline interacts with the subpipeline through a typed public
interface rather than its internal nodes.

## Public Interface

A subpipeline should expose explicit inputs and outputs.

Conceptually:

```python
class CustomerCurationPipeline(Pipeline):
    source: PipelineInput[RawCustomer]
    curated: PipelineOutput[Customer]
```

The parent pipeline should not need to reference private internal steps.

```text
Parent Pipeline
      │
      ▼
Subpipeline Input
      │
      ▼
Internal Graph
      │
      ▼
Subpipeline Output
      │
      ▼
Parent Pipeline
```

## Encapsulation

A subpipeline is more than a visual grouping of steps.

It should preserve:

- Pipeline identity
- Version
- Inputs
- Outputs
- Internal graph
- Contract references
- Validation rules
- Lineage
- Metadata

Internal implementation details should remain hidden unless explicitly exposed
for inspection or debugging.

## Typed Inputs

Subpipeline inputs are governed by data contracts.

```python
class CustomerCurationPipeline(Pipeline):
    raw_customers: PipelineInput[RawCustomer]
```

The parent pipeline must provide a compatible output.

ETLantic validates the connection before planning.

## Typed Outputs

Subpipeline outputs are also governed by data contracts.

```python
class CustomerCurationPipeline(Pipeline):
    curated_customers: PipelineOutput[Customer]
```

The parent pipeline may connect that output to downstream steps or sinks.

## Relationship to DPCS

A subpipeline should reference another DPCS pipeline contract rather than
duplicate its entire semantic definition.

Conceptually:

```text
Parent DPCS Contract
        │
        └── references Child DPCS Contract
```

The child contract retains its own:

- Identifier
- Version
- Interface
- Compatibility rules
- Internal topology

The parent contract records how its graph binds to the child's public inputs and
outputs.

## Versioning

Subpipelines should be independently versioned.

```text
customer-curation@1.2.0
```

A parent pipeline may depend on:

- An exact subpipeline version
- A compatible version range
- A registry-resolved version

Compatibility should be evaluated through DPCS rules rather than version
numbers alone.

## Validation

ETLantic should validate subpipelines at two levels.

### Internal validation

The child pipeline must be valid on its own.

Checks include:

- Internal graph integrity
- Contract compatibility
- Required implementations
- Source and sink definitions
- Public interface completeness

### Parent-child validation

The parent must bind correctly to the child's public interface.

Checks include:

- Required child inputs are supplied
- Parent outputs are contract-compatible
- Child outputs are used correctly
- Version requirements are satisfied
- No private child nodes are referenced directly

## Planning

During planning, ETLantic may handle a subpipeline in one of two ways.

### Preserve the boundary

The subpipeline remains one logical planning unit.

This is useful when:

- The child is executed by a separate orchestrator
- The child has a distinct deployment lifecycle
- The child is remotely managed
- The child should remain operationally isolated

### Expand the graph

The planner may inline the internal nodes into the parent `PipelinePlan`.

This is useful when:

- The same runtime executes both pipelines
- Cross-boundary optimization is allowed
- The child explicitly permits expansion

Either strategy must preserve observable DPCS semantics.

## Execution Independence

A subpipeline may use a different execution profile from its parent when the
selected orchestrator supports that arrangement.

Example:

```text
Parent Pipeline
    Orchestrator: Airflow
        │
        ▼
Subpipeline
    Execution: Remote service
```

Runtime differences should be resolved through bindings and profiles, not by
changing the subpipeline contract.

## Reuse

Subpipelines are useful for reusable domains such as:

- Customer curation
- Order processing
- Feature engineering
- Data quality gates
- Reference data loading
- Regulatory reporting
- Shared publication workflows

A well-designed subpipeline should be understandable and testable without
reading every parent pipeline that consumes it.

## Lineage

Subpipeline boundaries should preserve lineage.

ETLantic should support:

- High-level lineage through the child pipeline
- Expanded lineage through internal steps
- Parent-to-child input mappings
- Child-to-parent output mappings

Documentation tools may allow users to collapse or expand subpipeline details.

## Failure Handling

Failure semantics should be explicit at the subpipeline boundary.

A parent pipeline may treat child failure as:

- Parent failure
- Retryable failure
- Optional branch failure
- Degraded output
- Compensatable failure

The parent must not silently redefine the child's internal failure semantics.

## Callbacks

Callbacks may exist at:

- Internal step level
- Child pipeline level
- Parent pipeline level

ETLantic should invoke them in a deterministic order.

A child pipeline's callbacks should remain associated with the child, while the
parent may add broader operational handling.

## Parameters

Subpipelines may expose public parameters.

```python
class CustomerCurationPipeline(Pipeline):
    minimum_age: PipelineParameter[int] = 18
```

Only explicitly declared parameters should be configurable by the parent.

Internal step parameters should remain encapsulated unless promoted to the
public interface.

## Testing

Subpipelines should be tested independently.

Recommended tests include:

- Public input compatibility
- Public output compatibility
- Internal graph validation
- Version compatibility
- Parent-child binding
- Lineage preservation
- Failure propagation
- Planning with preserved and expanded boundaries

## Best Practices

- Expose a small, explicit public interface.
- Keep internal nodes private.
- Version subpipelines independently.
- Reference child DPCS contracts rather than duplicating them.
- Validate children independently before parent planning.
- Preserve lineage across boundaries.
- Use subpipelines for meaningful reusable workflows, not arbitrary grouping.

## Anti-Patterns

Avoid:

- Referencing internal child steps from the parent.
- Using subpipelines only as visual folders.
- Duplicating the child graph inside the parent contract.
- Sharing mutable runtime state implicitly.
- Allowing the parent to override undeclared internal parameters.
- Flattening subpipelines when doing so would change semantics.

## Key Principle

> A subpipeline is a complete pipeline with a typed public interface. Parent
> pipelines compose with that interface, not with the child's internal graph.

## Next Step

Continue with **DPCS.md** to learn how pipeline classes, steps, sources, sinks,
and subpipelines map to the Data Pipeline Contract Standard.
