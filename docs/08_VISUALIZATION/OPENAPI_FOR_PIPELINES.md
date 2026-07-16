# OpenAPI for Pipelines

!!! warning "Future design—not a Pipelantic 0.6 API guide"
    Graphviz, HTML, lineage exporters, and generated pipeline docs beyond
    Mermaid are not shipped in 0.5. For diagrams today, use
    `Pipeline.to_mermaid()`.


Pipelantic can generate an **OpenAPI-inspired interface description for data
pipelines**.

Just as OpenAPI provides a machine-readable description of HTTP APIs, this
proposed Pipelantic artifact describes *what a pipeline accepts, what it
produces, and how it behaves* without exposing implementation details.

It is not OpenAPI and is not a fourth contract standard. ODCS, DTCS, and DPCS
remain the authoritative contract family. This document explores a derived,
non-normative view generated from those contracts and a validated pipeline
model.

The generated specification is intended for documentation, discovery,
governance, validation, IDE tooling, registries, and interoperability.

## Purpose

An OpenAPI-inspired pipeline description enables:

- Pipeline discovery
- Automatic documentation
- Client generation
- Contract validation
- Dependency analysis
- Registry publication
- Governance
- Impact analysis

## Philosophy

Treat pipelines as products with well-defined interfaces.

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
Pipeline Plan (IR)
    │
    ▼
Pipeline Interface Generator
    │
    ▼
Pipeline Interface Description
```

The specification is generated from the validated model and is never the source
of truth.

## Why an OpenAPI Analogy?

OpenAPI answers questions such as:

- What endpoints exist?
- What parameters are accepted?
- What schemas are exchanged?

Pipelantic answers analogous questions:

- What sources exist?
- What parameters are accepted?
- What contracts are consumed?
- What contracts are produced?
- What quality gates exist?
- What execution requirements exist?

## Specification Structure

Conceptually:

```yaml
pipeline:
  id: customer-curation
  version: 1.2.0

inputs:
  - RawCustomer

outputs:
  - Customer

transformations:
  - NormalizeCustomers
  - ValidateCustomers

contracts:
  odcs:
    - customer
  dtcs:
    - normalize-customers
  dpcs:
    - customer-curation
```

The actual schema is defined by Pipelantic and evolves independently.

## Public Interface

A generated specification may include:

- Pipeline identity
- Version
- Description
- Owners
- Tags
- Inputs
- Outputs
- Parameters
- Source bindings
- Sink bindings
- Referenced contracts
- Quality gates
- Failure policies
- Capability requirements
- Compatibility metadata

## Relationship to Standards

The specification references, rather than replaces:

- ODCS (data contracts)
- DTCS (transformation contracts)
- DPCS (pipeline contracts)

It acts as an integration document across those standards.

## Tooling

The specification may power:

- Documentation sites
- Interactive explorers
- IDE support
- Search indexes
- Pipeline registries
- Dependency visualizers
- Governance dashboards

## Generation

Conceptually:

```python
spec = pipeline.to_openapi()
```

or

```python
plan.write_openapi("customer-pipeline.yaml")
```

Generation should consume the validated Pipeline Plan.

## Versioning

Every generated specification should declare:

- Pipelantic version
- Specification version
- Pipeline version
- Referenced contract versions
- Compatibility metadata

## Determinism

Equivalent Pipeline Plans should generate semantically equivalent specifications.

Stable ordering should be used for:

- Objects
- Parameters
- Contracts
- References
- Tags

## Security

Generated specifications should never include:

- Secrets
- Credentials
- Runtime tokens
- Physical infrastructure details

Logical bindings may be included when appropriate.

## Best Practices

- Generate specifications automatically.
- Treat them as derived artifacts.
- Reference canonical contracts.
- Publish explicit versions.
- Keep them deterministic.
- Validate in CI.

## Anti-Patterns

Avoid:

- Editing generated specifications manually.
- Treating specifications as executable pipelines.
- Embedding runtime secrets.
- Duplicating contract definitions instead of referencing them.

## Comparison

| HTTP APIs | Pipelantic |
|-----------|---------------|
| OpenAPI | Pipeline interface description |
| Endpoint | Pipeline |
| Request schema | Input contract |
| Response schema | Output contract |
| Operation | Transformation |
| Tags | Domains / Labels |
| Components | Shared contracts |

## Future Directions

Future versions may support:

- Registry discovery
- JSON Schema generation
- Client SDK generation
- Governance integrations
- Catalog synchronization
- Interactive documentation

## Key Principle

> An OpenAPI-inspired pipeline description provides a portable,
> machine-readable
> description of a pipeline's public interface. Like OpenAPI, it documents the
> contract—not the implementation—and is generated directly from
> Pipelantic's canonical models.

## Next Step

Continue with the [Examples](../09_EXAMPLES/README.md) section to see generated
pipeline descriptions used alongside executable documentation.
