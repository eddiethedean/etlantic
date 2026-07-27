# OpenAPI for Pipelines

!!! warning "Future design—not an ETLantic 0.23 API guide"
    OpenAPI-for-pipelines is future design. Mermaid, Graphviz, HTML, and lineage
    exporters are shipped via `Pipeline.to_mermaid()` and `etlantic.viz`.


ETLantic can generate an **OpenAPI-inspired interface description for data
pipelines**.

Just as OpenAPI provides a machine-readable description of HTTP APIs, this
proposed ETLantic artifact describes *what a pipeline accepts, what it
produces, and how it behaves* without exposing implementation details.

It is not a fourth contract standard. ODCS, DTCS, and DPCS remain the
authoritative contract family. This document explores a derived, non-normative
pipeline-interface view.

ETLantic 0.24 separately plans real OpenAPI schemas for the HTTP/service
request and response models used by a GUI-facing FastAPI adapter. Do not confuse
that service API with the pipeline-interface description on this page:

| Document | Meaning |
|---|---|
| `etlantic.pipeline/1` | Authoring-complete pipeline definition planned for 0.24 |
| Pipeline interface description | Derived discovery/documentation view described here |
| FastAPI OpenAPI document | HTTP operations and schemas for an application service |
| `etlantic.plan/1` | Resolved execution plan |

See [Programmatic Authoring in 0.24](../11_DEVELOPMENT/PROGRAMMATIC_AUTHORING_0_24.md).

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
of truth. In 0.24, `PipelineDefinition` is the authoring source of truth after
class, functional, JSON, or GUI input has normalized.

## Why an OpenAPI Analogy?

OpenAPI answers questions such as:

- What endpoints exist?
- What parameters are accepted?
- What schemas are exchanged?

ETLantic answers analogous questions:

- What sources exist?
- What parameters are accepted?
- What contracts are consumed?
- What contracts are produced?
- What quality gates exist?
- What execution requirements exist?

## Specification Structure

Conceptually (not a shipped 0.23 API):

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

The actual schema is defined by ETLantic and evolves independently.

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

- ETLantic version
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

| HTTP APIs | ETLantic |
|-----------|---------------|
| OpenAPI | Pipeline interface description |
| Endpoint | Pipeline |
| Request schema | Input contract |
| Response schema | Output contract |
| Operation | Transformation |
| Tags | Domains / Labels |
| Components | Shared contracts |

## Future Directions

The 0.24 programmatic-authoring phase plans:

- Registry discovery
- JSON Schema generation
- Client SDK generation
- Governance integrations
- Catalog synchronization
- Interactive documentation

The generated client belongs to the service/OpenAPI layer. It manipulates
canonical pipeline definitions and lifecycle requests; it does not execute
arbitrary Python supplied by a browser.

## Key Principle

> An OpenAPI-inspired pipeline description provides a portable,
> machine-readable
> description of a pipeline's public interface. Like OpenAPI, it documents the
> contract—not the implementation—and is generated directly from
> ETLantic's canonical models.

## Next Step

Continue with the [Examples](../09_EXAMPLES/README.md) section to see generated
pipeline descriptions used alongside executable documentation.
