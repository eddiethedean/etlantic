# Contract Loading

From 0.11, a DTCS artifact may carry a portable Transformation Plan profile.
Loading reconstructs bounded data-only IR and never imports the original Python
definition or executes a compiler. Unknown protocol majors and expression
nodes fail closed.

Contract loading allows ETLantic to construct in-memory models from
portable contract artifacts.

While ETLantic recommends a **code-first** workflow using strongly typed
Python classes, it also supports **contract-first** workflows by loading ODCS,
DTCS, and DPCS artifacts into the same typed logical pipeline model.

This enables interoperability with external tools, registries, and existing
contract repositories.

## Goals

Contract loading should:

- Support code-first and contract-first workflows.
- Produce the same internal models regardless of source.
- Validate contracts during loading.
- Resolve references automatically.
- Preserve identities and semantics.
- Remain independent of serialization formats.

## Philosophy

Whether authored in Python or YAML, a contract should become the same logical
model.

```text
Python Classes          YAML / JSON Contracts
       │                        │
       └────────────┬───────────┘
                    ▼
             Contract Loaders
                    ▼
      Typed Logical Pipeline Model
                    ▼
          Validation & Planning
```

The source format should not affect pipeline behavior.

## Supported Contract Types

ETLantic can load:

- ODCS Data Contracts
- DTCS Transformation Contracts
- DPCS Pipeline Contracts

Each contract is loaded into its domain model, then connected through the same
logical pipeline representation used by the code-first APIs. ETLantic does
not flatten data, transformation, and pipeline contracts into one universal
domain object.

## Loading APIs

Conceptually:

```python
from etlantic import Data, load_data_contract
from etlantic import Pipeline, Transformation

customer = load_data_contract("customer.odcs.yaml")

normalize = Transformation.from_dtcs(
    "normalize.dtcs.yaml",
)

pipeline = Pipeline.from_dpcs(
    "customer_pipeline.dpcs.yaml",
)
```

Future APIs may support loading from streams, registries, packages, or remote
URLs.

## Typed Logical Model

Loaded contracts retain their domain-specific representations while
ETLantic builds common references, ports, and graph relationships around
them.

The logical model preserves:

- Identity
- Metadata
- Interfaces
- References
- Graph topology
- Version information
- Compatibility metadata
- Extensions

Planning operates on the typed logical model rather than raw files.

## Reference Resolution

Contracts frequently reference one another.

Examples include:

- DPCS → DTCS
- DTCS → ODCS
- DPCS → nested DPCS

The loader resolves these references before planning.

Resolution sources may include:

- Local directories
- Python packages
- Git repositories
- Contract registries
- Organization-specific providers

## Validation During Loading

Loading performs structural validation before contracts become usable.

Checks may include:

- Required fields
- Schema correctness
- Version compatibility
- Identifier validity
- Reference integrity
- Extension validity

Invalid contracts should fail before planning begins.

## Serialization Independence

ETLantic separates semantics from serialization.

Equivalent contracts expressed as:

- YAML
- JSON
- TOML (future)

should produce semantically equivalent logical models.

## Caching

Implementations may cache loaded contracts to improve performance.

Cached contracts should be invalidated when:

- Source files change
- Contract versions change
- Registry revisions change
- Compatibility requirements change

## Registry Integration

Contract loading integrates naturally with contract registries.

Conceptually:

```python
pipeline = Pipeline.from_registry(
    "customer-pipeline",
    version="1.2.0",
)
```

Registry implementations remain pluggable.

## Relationship to Planning

Loading precedes planning.

```text
Contract Files
      │
      ▼
Loading
      │
      ▼
Typed Logical Model
      │
      ▼
Validation
      │
      ▼
Pipeline Plan
```

Planning never depends on the original file format.

## Relationship to Generation

Generation and loading are complementary.

```text
Python
   │
   ▼
Generate Contracts
   │
   ▼
Portable Artifacts
   │
   ▼
Load Contracts
   │
   ▼
Typed Logical Model
```

A generated contract should load into an equivalent internal model.

## Best Practices

- Treat generated contracts as portable artifacts.
- Validate during loading.
- Resolve references before planning.
- Prefer stable identifiers over file paths.
- Cache immutable contracts where appropriate.

## Anti-Patterns

Avoid:

- Depending on serialization-specific behavior.
- Skipping validation during loading.
- Using file paths as contract identities.
- Mutating loaded contracts in place.
- Loading contracts that cannot resolve required references.

## Key Principle

> Contract loading converts portable ODCS, DTCS, and DPCS artifacts into a
canonical ETLantic object model that is independent of serialization,
storage location, and authoring workflow.

## Next Step

Continue with the [Execution](../06_EXECUTION/README.md) section to learn how a
loaded, validated pipeline becomes a resolved plan for a selected runtime.
