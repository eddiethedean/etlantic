# End-to-End Pipeline Example

!!! warning "Future design—not a ETLantic 0.10 API guide"
    This page is a design study. It may describe packages, commands, or
    interfaces beyond the shipped API surface. Prefer Current Capabilities,
    the runnable examples under `examples/`, the API reference, and the CLI
    reference for installable behavior.


This example demonstrates the complete ETLantic lifecycle from initial
authoring through execution, validation, documentation, publication, and
governance.

## Overview

```text
Author Pipeline
      │
      ▼
Validate
      │
      ▼
Generate Pipeline Plan
      │
      ├── Execute
      ├── Generate ODCS
      ├── Generate DTCS
      ├── Generate DPCS
      ├── Generate Documentation
      ├── Generate Mermaid
      ├── Generate OpenAPI Pipeline Description
      ├── Publish Contracts
      └── Produce Lineage
```

## End-to-End Workflow

1. Define data contracts.
2. Define transformation contracts.
3. Define the pipeline graph.
4. Bind implementations (Polars, SQL, PySpark, etc.).
5. Configure an execution profile.
6. Validate contracts, graph, plugins, and profile.
7. Produce a deterministic Pipeline Plan.
8. Execute the pipeline.
9. Validate outputs.
10. Publish sinks.
11. Generate documentation and diagrams.
12. Export ODCS, DTCS, and DPCS artifacts.
13. Publish contracts to a registry.
14. Archive execution metadata and lineage.

## Example Project

```text
customer_pipeline/
├── src/
├── contracts/
├── docs/
├── tests/
└── output/
```

## Typical Code

```python
report = CustomerPipeline.validate()
report.raise_for_errors()

plan = CustomerPipeline.plan(profile=production)

result = CustomerPipeline.run(profile=production)

CustomerPipeline.write_contracts("contracts/")
plan.write_html("docs/pipeline.html")
plan.write_mermaid("docs/pipeline.mmd")
```

## Outputs

A successful run produces:

- Curated datasets
- Execution report
- Validation report
- Lineage graph
- HTML documentation
- Mermaid diagrams
- OpenAPI-style pipeline description
- ODCS data contracts
- DTCS transformation contracts
- DPCS pipeline contract

## CI/CD Pipeline

```text
Lint
  │
Type Check
  │
Unit Tests
  │
Pipeline Validation
  │
Implementation Conformance
  │
Contract Generation
  │
Round-trip Verification
  │
Documentation Generation
  │
Package Build
  │
Registry Publication
```

## Production Principles

- Contracts are validated before execution.
- Execution always originates from a Pipeline Plan.
- Environment-specific configuration lives in profiles.
- Portable contracts remain implementation independent.
- Every execution is observable, reproducible, and versioned.
- Lineage is generated automatically from the validated graph.

## Best Practices

- Keep contracts and implementations separate.
- Validate early and often.
- Generate documentation from the same Pipeline Plan used for execution.
- Publish only validated contracts.
- Test every execution backend for behavioral equivalence.
- Treat the Pipeline Plan as the single executable representation.

## Final Architecture

```text
Python or Contract Definitions
             │
             ▼
      Normalized Model
             │
             ▼
        Pipeline Plan
             │
 ┌───────────┼────────────┐
 ▼           ▼            ▼
Execution Documentation Contracts
             │
             ▼
          Registry
             │
             ▼
 Governance & Lineage
```

## Key Principle

> Every ETLantic workflow—whether code-first or contract-first—should
> converge on one validated, deterministic Pipeline Plan that becomes the
> source for execution, documentation, governance, lineage, and portable
> contract generation.
