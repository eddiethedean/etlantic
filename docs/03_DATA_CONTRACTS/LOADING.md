# Loading

Loading is the inverse of generation.

Where generation produces portable artifacts from Python models, loading reconstructs typed models and metadata from existing contract artifacts so they can participate in ETLantic.

## Goals

Loading should:

- Support contract-first and hybrid workflows.
- Reconstruct typed Python models from published artifacts.
- Preserve contract identity and metadata.
- Validate loaded artifacts before use.
- Hide serialization details behind stable APIs.

## Responsibility Boundaries

| Component | Responsibility |
|-----------|----------------|
| ContractModel | Load and validate [ODCS](ODCS.md) data contracts |
| ETLantic | Register loaded contracts and connect them to transformations and pipelines |
| [DTCS](../04_TRANSFORMATIONS/DTCS.md)/[DPCS](../05_PIPELINES/DPCS.md) | Define portable transformation and pipeline artifacts |
| Plugins | Load optional runtime-specific metadata |

## Loading Workflows

### Code-first

Python classes are authored directly and artifacts are generated.

### Contract-first

Existing artifacts are loaded into Python.

```python
from etlantic import Data
from etlantic.contracts import load_data_contract

Customer = load_data_contract(
    "contracts/data/customer.odcs.yaml",
)
```

The resulting class should behave like any authored `Data`.

### Hybrid

Projects may combine authored contracts with externally supplied contracts.

```text
Python Models ─┐
               ├──► ETLantic
ODCS Artifacts ┘
```

## Loading Pipeline

```text
Artifact
   │
   ▼
Parse
   │
   ▼
Validate
   │
   ▼
Normalize
   │
   ▼
Register
   │
   ▼
ETLantic
```

Invalid artifacts should fail during loading rather than later during execution.

## Identity Preservation

Loading should preserve:

- Contract identifier
- Version
- Metadata
- Field definitions
- Constraints
- Documentation
- Extension metadata where supported

Identity should not change simply because a contract was loaded instead of authored.

## Registration

Loaded contracts become first-class pipeline types.

```python
class NormalizeCustomers(Transformation):
    customers: Input[Customer]
    result: Output[Customer]
```

ETLantic should not distinguish between authored and loaded contracts once registration is complete.

## Validation During Loading

Artifacts should be validated for:

- Specification version
- Required metadata
- Structural correctness
- Schema consistency
- Unsupported features
- Duplicate identities

Errors should include clear diagnostics and remediation guidance.

## Loading Bundles

Future APIs may support loading complete contract bundles.

```python
registry = ContractRegistry.load(
    "contracts/",
)
```

A bundle may contain:

- ODCS data contracts
- DTCS transformation contracts
- DPCS pipeline contracts

ETLantic can then resolve references automatically.

## Unknown Extensions

Unknown extension metadata should be preserved whenever practical instead of discarded.

This allows organizations to use custom extensions without breaking portability.

## Caching

Implementations may cache loaded contracts to reduce repeated parsing and validation.

Caching must not change contract semantics.

## Recommended Practices

- Validate artifacts during loading.
- Preserve contract identity.
- Prefer public loading APIs over manual parsing.
- Keep generated artifacts under version control.
- Treat loaded and authored contracts equivalently.

## Anti-Patterns

Avoid:

- Modifying loaded metadata in place.
- Bypassing validation.
- Depending on private serialization details.
- Reimplementing ODCS parsing outside ContractModel.

## Key Principle

> Loading reconstructs portable contracts into typed Python models. After loading, authored and imported contracts should behave the same inside ETLantic.

## Next Step

Continue with the **Transformations** section to learn how data contracts become typed transformation interfaces.
