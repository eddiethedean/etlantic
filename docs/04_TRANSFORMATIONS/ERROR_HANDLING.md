# Error Handling

!!! success "Available in ETLantic 0.18"
    Structured diagnostics, validation failures, runtime
    `NodeExecutionError` paths, callback `FailureAction` results, and
    `Profile.retry_max_attempts` retry intent are shipped. Retry execution is
    gated by the runtime or orchestrator's safety checks.

Error handling in ETLantic is designed to make failures predictable,
typed, and portable across execution backends.

ETLantic distinguishes between **modeling errors**, **planning errors**,
and **runtime errors**. The core framework coordinates how errors are reported,
while execution plugins provide backend-specific details.

## Goals

Error handling should:

- Produce clear, actionable diagnostics.
- Fail early whenever possible.
- Preserve typed context.
- Remain execution-engine independent.
- Support synchronous and asynchronous execution.
- Integrate with callbacks and retry policies.

## Error Categories

### Model Errors

Detected while defining contracts, transformations, or pipelines.

Examples:

- Invalid type annotations
- Duplicate transformation outputs
- Missing required inputs
- Invalid contract metadata

These should be reported before planning.

### Planning Errors

Detected while building an execution plan.

Examples:

- Incompatible contracts
- Missing implementation
- Unsupported plugin capability
- Circular pipeline dependencies
- Missing runtime resources

Planning errors prevent execution.

### Runtime Errors

Occur while executing a valid plan.

Examples:

- Transformation exceptions
- Database failures
- Network timeouts
- Filesystem errors
- Unexpected plugin failures

Runtime errors may trigger retries or callbacks.

## Typed Error Context

Errors should be exposed through structured context objects instead of raw
exceptions.

Typical context includes:

- Pipeline ID
- Transformation ID
- Contract identity
- Execution profile
- Run ID
- Original exception
- Diagnostics
- Timestamp

## Error Flow

```text
Failure
   │
   ▼
Categorize
   │
   ▼
Create Typed Context
   │
   ▼
Invoke Callbacks
   │
   ▼
Determine Action
   │
   ▼
Plugin Executes Action
```

## Retry

Retry decisions should be declarative.

Shipped callbacks return `FailureAction`, while profiles declare the retry
limit:

```python
from etlantic import FailureAction, Profile


def on_step_failed(context):
    return FailureAction.RETRY


profile = Profile(name="local", retry_max_attempts=3)
```

The execution backend performs the retry according to the active profile and
its retry-safety checks. `FailureAction.FAIL`, `.SKIP`, and `.CONTINUE` are
also available for step-failure callbacks.

!!! warning "Future design—not a shipped API"
    `RetryAction` is not part of ETLantic 0.14. The following conceptual
    snippet must not be copied into current code:

    ```python
    from etlantic import RetryAction

    return RetryAction.retry(max_attempts=3)
    ```

## Diagnostics

Errors should provide:

- Stable error code
- Human-readable message
- Severity
- Suggested remediation
- Related contract or transformation
- Stack trace (when appropriate)

## Logging

ETLantic should emit structured logs.

Sensitive values should be redacted according to contract metadata and profile
settings.

## Best Practices

- Prefer typed exceptions and diagnostics.
- Fail during planning instead of execution when possible.
- Keep retry logic declarative.
- Use callbacks for operational responses.
- Preserve original exceptions for debugging.

## Anti-Patterns

Avoid:

- Raising untyped exceptions from public APIs.
- Hiding planning failures until runtime.
- Logging sensitive data by default.
- Embedding backend-specific exceptions in transformation contracts.

## Key Principle

> Errors are part of the execution model, not the transformation contract.
> ETLantic standardizes how failures are represented while plugins
> determine how backend-specific failures are handled.

## Next Step

Continue with [Async](ASYNC.md) to learn how ETLantic preserves equivalent
failure semantics for synchronous and asynchronous implementations.
