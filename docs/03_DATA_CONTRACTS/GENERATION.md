# Generation

Generation is the process of producing portable artifacts from typed Python models.

ETLantic follows a **code-first** philosophy. Developers author data contracts, transformation contracts, and pipelines in Python. The framework generates standards-compliant artifacts, documentation, visualizations, and execution plans from those definitions.

## Goals

Generation should:

- Eliminate duplicated definitions
- Produce deterministic artifacts
- Preserve open standards
- Support reproducible builds
- Enable code review through generated outputs
- Remain independent of execution engines

## Responsibility Boundaries

| Component | Responsibility |
|-----------|----------------|
| ContractModel | Generate and load [ODCS](ODCS.md) data contracts |
| ETLantic | Discover models and orchestrate artifact generation |
| [DTCS](../04_TRANSFORMATIONS/DTCS.md) | Portable transformation contract format |
| [DPCS](../05_PIPELINES/DPCS.md) | Portable pipeline contract format |
| Plugins | Optional generators for runtime-specific outputs |

## The Generation Pipeline

```text
Python Models
      │
      ▼
Type Introspection
      │
      ▼
Validation
      │
      ▼
Artifact Generation
      │
      ├── ODCS
      ├── DTCS
      ├── DPCS
      ├── Documentation
      ├── Mermaid
      ├── Graphviz
      └── Execution Plans
```

Validation should always precede generation so invalid models do not produce misleading artifacts.

## Code-First Workflow

Developers define Python classes:

```python
class Customer(Data):
    customer_id: int
    email: str
```

```python
class NormalizeCustomers(Transformation):
    customers: Input[Customer]
    result: Output[Customer]
```

```python
class CustomerPipeline(Pipeline):
    ...
```

ETLantic discovers these definitions and generates portable artifacts.

## Generated Artifacts

Typical output:

```text
contracts/
├── data/
│   └── customer.odcs.yaml
├── transformations/
│   └── normalize-customers.dtcs.yaml
└── pipelines/
    └── customer-pipeline.dpcs.yaml
```

Additional outputs may include:

- HTML documentation
- Markdown documentation
- Mermaid diagrams
- Graphviz diagrams
- Lineage graphs
- Execution plans

## Deterministic Output

Generation should be deterministic.

The same source models should always produce identical artifacts unless the source changes.

This enables:

- Meaningful Git diffs
- CI verification
- Reproducible builds
- Reliable code review

## Discovery

ETLantic should automatically discover referenced contracts.

Conceptually:

```python
CustomerPipeline.write_contracts("contracts/")
```

The framework walks the pipeline graph, finds every referenced data contract and transformation, removes duplicates, and generates a complete bundle.

## Incremental Generation

Future versions may support generating only artifacts affected by changed models.

Incremental generation should preserve the same output format as a full generation run.

## Validation Reports

Generation should emit structured diagnostics rather than silently skipping unsupported features.

Warnings may include:

- Unsupported metadata
- Missing descriptions
- Unknown extensions
- Deprecated fields
- Version mismatches

Errors should prevent generation when portability or correctness would be compromised.

## Extension Points

Plugins may generate additional artifacts, including:

- SQL DDL
- API schemas
- Warehouse documentation
- IDE metadata
- Organization-specific formats

These extensions should not modify the core ODCS, DTCS, or DPCS artifacts.

## Recommended Practices

- Generate artifacts in CI.
- Commit generated contract artifacts when they are part of governance.
- Keep generated output separate from authored source code.
- Treat generated files as reproducible build artifacts.
- Validate before generation.

## Anti-Patterns

Avoid:

- Editing generated artifacts by hand.
- Maintaining parallel handwritten contract files.
- Generating artifacts from invalid models.
- Allowing plugins to change standard artifacts.

## Key Principle

> In code-first projects, Python models are the authoring source of truth.
> Generated artifacts are portable representations derived from those models.

## Next Step

Continue with **LOADING.md** to learn how ETLantic consumes existing contract artifacts and reconstructs typed models from them.
