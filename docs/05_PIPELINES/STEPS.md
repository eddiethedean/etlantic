# Steps

A step may eventually be realized either by a native registered implementation
or by compiling its transformation's portable DTCS Transformation Plan. This
0.11+ choice does not change step identity, bindings, output
references, or graph topology.

A `Step` is a concrete instance of a `Transformation` inside a `Pipeline`.

A `Transformation` defines a reusable contract. A `Step` binds that contract to
specific inputs, parameter values, and downstream connections, making it part
of a pipeline graph.

## Purpose

Steps answer one question:

> Where and how is this transformation used in this pipeline?

A transformation may be reused multiple times, producing multiple independent
steps.

## Transformation vs. Step

```python
class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    minimum_age: Parameter[int] = 18
    result: Output[Customer]
```

Reusable transformation.

```python
normalized = NormalizeCustomers.step(
    customers=raw,
    minimum_age=21,
)
```

Concrete pipeline step.

## Why Steps Exist

Separating transformations from steps allows:

- Reusable transformation definitions
- Multiple instances of the same transformation
- Different parameter values
- Different pipeline graphs
- Stable DTCS contracts with many DPCS references

## Inputs

Steps bind upstream outputs to transformation inputs.

```python
NormalizeCustomers.step(
    customers=raw.result,
)
```

ETLantic validates compatibility before planning.

## Parameters

Each step may override parameter defaults.

```python
NormalizeCustomers.step(
    customers=raw.result,
    minimum_age=25,
)
```

The transformation contract is unchanged; only this step's configuration differs.

## Outputs

Outputs become typed references for downstream steps.

```python
validated = ValidateCustomers.step(
    customers=normalized.result,
)
```

`normalized.result` refers to the result produced by that specific step
instance. It does not mean "load the table associated with
`NormalizeCustomers`."

## Referencing Previous Step Results

Step outputs are first-class graph references.

```python
normalized = NormalizeCustomers.step(customers=raw.result)
scored = ScoreCustomers.step(customers=normalized.result)
published = PublishCustomers.step(customers=scored.result)
```

Conceptually, `normalized.result` is an `OutputRef[Customer]`. It records:

- the producing step
- the named output port
- the output contract
- the consuming input

It does not contain a Pandas, Polars, Spark, or SQL object during pipeline
definition.

At runtime, the selected backend may realize the same reference as:

- an in-memory dataframe
- a lazy dataframe
- a SQL relation or common table expression
- a Spark logical plan
- a temporary artifact
- a durable artifact reference across task boundaries

This allows downstream steps to use the exact result of previous computation
without forcing every intermediate result through persistent storage.

### Result references versus table bindings

These concepts must remain distinct:

```text
normalized.result
    Result produced within this pipeline run.

Extract(asset="warehouse.customers")
    Dataset loaded from an external binding.

Load(input=normalized.result, asset="warehouse.customers")
    Explicit publication of a result.
```

A step result becomes a published table or dataset only when connected to a
`Sink` or an explicit persistence policy.

### Named results

Multiple outputs can be referenced independently:

```python
validated = ValidateCustomers.step(customers=normalized.result)

published = PublishCustomers.step(customers=validated.valid)
quarantined = QuarantineCustomers.step(customers=validated.rejected)
```

ETLantic tracks each reference independently for dependency analysis,
contract validation, lineage, reuse, and invalidation.

## Identity

Every step should have a stable identity within its pipeline.

Conceptually:

- Step name
- Transformation identity
- Pipeline identity
- Parameter values
- Input bindings
- Output-port identities

This identity supports lineage, diagnostics, and execution planning.

## Planning

During planning, each step becomes a node in the execution graph.

The planner resolves:

- Dependencies
- Execution order
- Parallel opportunities
- Runtime implementation
- Validation policy
- Physical representation of every output reference
- Whether a result remains ephemeral, is cached, or is materialized

## Relationship to DPCS

Each step is represented in the generated DPCS artifact with:

- Transformation reference
- Input bindings
- Output bindings
- Parameter values
- Metadata

The transformation itself remains defined by DTCS.

## Best Practices

- Keep transformations reusable.
- Instantiate them with `.step()`.
- Use descriptive step names.
- Override only necessary parameters.
- Let outputs feed downstream inputs.
- Use a `Sink` only when the result must be published.

## Anti-Patterns

Avoid:

- Embedding business logic in pipeline definitions.
- Duplicating transformation definitions for different parameter values.
- Referencing runtime-specific objects in step declarations.
- Re-reading a persisted table when the desired value is an upstream step
  result from the same run.

## Key Principle

> A `Transformation` defines a reusable operation. A `Step` is one use of that
operation within a specific pipeline.

## Next Step

Continue with **SINKS.md** to learn how pipelines publish validated outputs.
