# Callbacks

> **Status: Available in ETLantic 0.21.0** for the shipped lifecycle callback
> surface. Broader invalid-data quarantine APIs remain future design.

Callbacks let applications respond to pipeline lifecycle outcomes without
embedding operational logic inside transformation implementations.

Callbacks are distinct from runtime lifespan, execution middleware, and
resource injection. See
[Lifecycle Extension Mechanisms](../06_EXECUTION/LIFECYCLE_EXTENSIONS.md).

## Shipped surface

```python
from etlantic import FailureAction, PipelineRuntime, StepFailureContext
from etlantic.lifecycle import CallbackRegistry

runtime = PipelineRuntime()
callbacks = CallbackRegistry()


@callbacks.on_step_failed
def on_step_failed(context: StepFailureContext) -> FailureAction:
    # context.run_id, pipeline_id, step_name, attempt, error, stage
    return FailureAction.FAIL


@callbacks.on_failure
def on_run_failed(context: object) -> None:
    ...


@callbacks.on_complete
def on_run_completed(context: object) -> None:
    ...


runtime.callbacks = callbacks
```

`FailureAction` values:

| Action | Meaning |
|---|---|
| `CONTINUE` | Soft-fail the step and allow dependents to run |
| `RETRY` | Retry the step according to run/profile retry settings |
| `FAIL` | Fail the run |
| `SKIP` | Soft-fail the step and abandon its transitive dependents |

Register handlers on a `CallbackRegistry`, then attach it to
`PipelineRuntime` before `Pipeline.run(...)`.

## Retry policy

Prefer declarative retry settings on the profile or run request rather than
inventing callback-only retry APIs:

```python
from etlantic import Profile

profile = Profile(
    name="pilot",
    retry_max_attempts=3,
    plugin_allowlist={"local": None},
)
```

Orchestrator plugins (for example Airflow compile) map schedule/retry intents
from the plan; they do not require unshipped callback helpers.

## Future design — invalid-data quarantine

!!! warning "Future design—not an ETLantic 0.16 API guide"
    Dedicated `on_invalid_data` / quarantine action helpers are not shipped.
    Use contract validation boundaries, invalid-output ports, and sinks for
    quarantine-style flows today.

## Sync and Async

Handlers may be sync or async. The runtime awaits coroutine handlers.

## Related

- [Lifecycle Extensions](../06_EXECUTION/LIFECYCLE_EXTENSIONS.md)
- [Error Handling](ERROR_HANDLING.md)
- [API Reference](../10_REFERENCE/API_REFERENCE.md)
