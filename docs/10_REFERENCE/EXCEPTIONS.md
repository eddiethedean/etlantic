# Exceptions Reference

> **Status: Available in ETLantic 0.28.0.** This page documents exceptions
> exported by the installed package. Broader 1.0 exception trees on older
> design pages are not authoritative.

ETLantic uses structured diagnostics for expected contract and pipeline
problems. Exceptions represent failures in model definition, validation
escalation, or runtime execution.

## Hierarchy (shipped)

```text
ETLanticError
├── ModelDefinitionError
├── PipelineValidationError
├── InternalETLanticError
├── PipelineExecutionError
│   ├── NodeExecutionError
│   ├── DataValidationError
│   ├── PipelineTimeoutError
│   └── PipelineCancelledError
├── OrchestrationCompilationError   (etlantic.orchestration.compile)
└── UnsafeSerializationError        (etlantic.serialization_policy)

ValueError
└── InterchangeError                (etlantic.interchange.tabular)
    ├── InterchangeSelectionError
    └── InterchangeDescriptorError
```

```python
from etlantic.exceptions import (
    DataValidationError,
    ModelDefinitionError,
    NodeExecutionError,
    PipelineCancelledError,
    PipelineExecutionError,
    PipelineTimeoutError,
    PipelineValidationError,
    ETLanticError,
)
from etlantic.orchestration.compile import OrchestrationCompilationError
from etlantic.interchange.tabular import (
    InterchangeError,
    InterchangeDescriptorError,
    InterchangeSelectionError,
)
from etlantic.serialization_policy import UnsafeSerializationError
```

In **0.26**, root exception aliases were **removed**. Prefer owning modules
(`etlantic.exceptions`, orchestration, interchange, serialization_policy).
See [Migration 0.25 → 0.26](../11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md).

`InterchangeError` subclasses `ValueError` (not `ETLanticError`); catch it
explicitly at interchange boundaries.

## Base Exception

```python
class ETLanticError(Exception):
    """Base class for public ETLantic exceptions."""
```

Applications may catch this base class at integration boundaries, but should
usually catch a more specific exception.

## Model and validation

| Exception | When |
|---|---|
| `ModelDefinitionError` | A class definition cannot form a usable model |
| `PipelineValidationError` | Validation failed and the caller requested an exception (`raise_for_errors`) |

`PipelineValidationError` carries a `report` (`ValidationReport`).

## Execution

| Exception | When |
|---|---|
| `PipelineExecutionError` | Pipeline execution failed |
| `NodeExecutionError` | A single node failed (`node_name`, optional `stage`, `cause`) |
| `DataValidationError` | Runtime data failed a contract boundary |
| `PipelineTimeoutError` | A run or step exceeded its timeout |
| `PipelineCancelledError` | A run was cancelled |

Execution exceptions may include `run_id`, `report`, and `code` when available.
`NodeExecutionError` also exposes `node_name`, optional `stage`, and `cause`.
`DataValidationError` may include `node_name` and `boundary`. Messages are
redacted before entering reports and logs.

## Orchestration, interchange, and security

| Exception | When |
|---|---|
| `OrchestrationCompilationError` | Orchestrator compile failed (missing plugin, capability, or invalid artifact) |
| `InterchangeError` | Base error for tabular interchange contract violations |
| `InterchangeSelectionError` | No contract-safe interchange mechanism could be selected |
| `InterchangeDescriptorError` | Interchange descriptor failed closed validation |
| `UnsafeSerializationError` | Serialization policy blocked an unsafe object graph |

```python
from etlantic.orchestration.compile import OrchestrationCompilationError
from etlantic.interchange.tabular import (
    InterchangeError,
    InterchangeDescriptorError,
    InterchangeSelectionError,
)
from etlantic.serialization_policy import UnsafeSerializationError
```

Import exceptions from owning modules (root exception aliases were removed in
0.26). Prefer the modules above; see
[Migration 0.25 → 0.26](../11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md).

## Internal

`InternalETLanticError` signals a violated internal invariant. Treat it as a
bug report candidate, not a normal control-flow signal.

## Diagnostics vs exceptions

Most wiring and contract problems surface as diagnostics on a
`ValidationReport` without raising. Call `report.raise_for_errors()` when you
want failures as exceptions.

## See also

- [Diagnostics](DIAGNOSTICS.md)
- [API Reference](API_REFERENCE.md)
- [CLI](CLI.md)
