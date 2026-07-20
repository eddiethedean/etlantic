# Exceptions Reference

> **Status: Available in ETLantic 0.21.0.** This page documents exceptions
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
└── PipelineExecutionError
    ├── NodeExecutionError
    ├── DataValidationError
    ├── PipelineTimeoutError
    └── PipelineCancelledError
```

```python
from etlantic import (
    DataValidationError,
    ModelDefinitionError,
    NodeExecutionError,
    PipelineCancelledError,
    PipelineExecutionError,
    PipelineTimeoutError,
    PipelineValidationError,
    ETLanticError,
)
```

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
Messages are redacted before entering reports and logs.

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
