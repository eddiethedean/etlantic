# Contract Generation

The proposed 0.11 DTCS generation path may include canonical
`dtcs.transform-plan/2` content and its fingerprint (v1 readable). Generated
artifacts remain data-only, deterministic, bounded, and free of native compiled
objects, runtime parameter values, source rows, and secrets.

Contract generation is one of ETLantic's defining capabilities.

Rather than requiring developers to manually author multiple contract files,
ETLantic derives portable contract artifacts directly from strongly typed
Python definitions.

The Python code is the primary authoring surface. Generated contracts are
deterministic artifacts suitable for review, version control, publishing, and
interoperability.

## Goals

Contract generation should:

- Eliminate duplicated definitions.
- Keep Python as the source of truth.
- Produce deterministic artifacts.
- Support CI/CD workflows.
- Generate standards-compliant contracts.
- Preserve semantic meaning.

## Philosophy

Developers write Python.

ETLantic generates contracts.

```text
Python Models
      │
      ▼
Introspection
      │
      ▼
Validation
      │
      ▼
Contract Generation
      │
      ├── ODCS
      ├── DTCS
      └── DPCS
```

Generated contracts should never require manual synchronization.

## Generated Contract Types

ETLantic may generate:

### ODCS

Generated from `Data` classes.

Contains:

- Schema
- Metadata
- Constraints
- Field definitions
- Compatibility information

### DTCS

Generated from `Transformation` classes.

Contains:

- Inputs
- Outputs
- Parameters
- Metadata
- Transformation identity

### DPCS

Generated from `Pipeline` classes.

Contains:

- Pipeline interface
- Sources
- Steps
- Sinks
- Graph
- Contract references
- Lineage
- Execution requirements

## Generation Workflow

Typical workflow:

```text
Python Code
      │
      ▼
Validation
      │
      ▼
Generate Contracts
      │
      ▼
Review
      │
      ▼
Publish
```

Validation should occur before generation.

## Determinism

Generation must be deterministic.

Equivalent Python definitions should produce semantically equivalent contracts.

Ordering differences or formatting changes must not alter contract meaning.

## Identity Preservation

Generated artifacts preserve:

- Contract identifiers
- Versions
- Metadata
- References
- Relationships

Identity must remain stable across repeated generation.

## Incremental Generation

ETLantic may regenerate only changed artifacts.

Examples:

- One modified data contract
- One transformation
- One pipeline

Unchanged contracts should not be rewritten unnecessarily.

## Output Formats

Portable contracts may be generated as:

- YAML
- JSON
- TOML (future)
- Other supported serializations

Serialization does not change contract semantics.

## Directory Layout

Example:

```text
contracts/
├── data/
│   ├── customer.odcs.yaml
│   └── order.odcs.yaml
├── transformations/
│   ├── normalize.dtcs.yaml
│   └── aggregate.dtcs.yaml
└── pipelines/
    └── customer_pipeline.dpcs.yaml
```

## Registry Publishing

Generated contracts may be published to:

- Local directories
- Git repositories
- Package resources
- Contract registries
- Organization repositories

Publishing should occur only after successful validation.

## Relationship to Planning

Planning consumes generated contracts or their in-memory equivalents.

Generation is not required for execution, but generated artifacts enable:

- Interoperability
- Documentation
- Review
- Versioning
- Distribution

## CI/CD

Recommended workflow:

- Validate
- Generate contracts
- Check deterministic output
- Run compatibility checks
- Publish artifacts
- Deploy

Generation should be automated whenever possible.

## Documentation

Generated contracts may also produce:

- Markdown documentation
- HTML documentation
- Mermaid diagrams
- Graphviz diagrams
- Lineage graphs
- API documentation

Documentation should derive from the same source model as the contracts.

## Best Practices

- Treat Python as the source of truth.
- Never manually edit generated contracts.
- Commit generated artifacts when appropriate.
- Validate before generation.
- Publish only validated contracts.

## Anti-Patterns

Avoid:

- Maintaining Python and YAML manually in parallel.
- Editing generated contracts by hand.
- Publishing unvalidated artifacts.
- Generating non-deterministic output.
- Embedding environment-specific configuration into portable contracts.

## Key Principle

> Python definitions are authored by developers. ETLantic generates
portable ODCS, DTCS, and DPCS artifacts that preserve those definitions without
requiring duplicate maintenance.

## Next Step

Continue with [Contract Loading](CONTRACT_LOADING.md) to learn how portable
ODCS, DTCS, and DPCS artifacts return to ETLantic's logical model.
