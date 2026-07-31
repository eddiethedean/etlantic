# Run History Provider

> **Status: Available in ETLantic 0.40.0.** Reference file and in-memory
> providers ship in core; storage-specific backends stay in optional plugins.

Run history providers persist secret-free lifecycle events and terminal run
reports for cross-run queries.

## Protocol

```python
class RunHistoryProvider(Protocol):
    @property
    def descriptor(self) -> RunHistoryProviderDescriptor: ...

    def create_run(self, *, run_id, pipeline_id, plan_id=None, metadata=None) -> None: ...
    def append_event(self, event: LifecycleEvent | SecurityEvent) -> None: ...
    def append_report(self, report: PipelineRunReport) -> None: ...
    def read_run(self, run_id: str) -> dict[str, Any] | None: ...
    def list_runs(self, query: RunHistoryQuery | None = None) -> list[RunHistoryEntry]: ...
```

Entry-point group: `etlantic.run_history_providers`.

## Reference implementations

- `InMemoryRunHistoryProvider` — tests and conformance
- `FileRunHistoryProvider` — durable JSON under a SafeIoPolicy root (CLI workspace
  uses `.etlantic/history/`)

## Conformance

```python
from etlantic.testing import run_run_history_conformance_suite

run_run_history_conformance_suite(provider)
```

## See also

- [Observability Provider](OBSERVABILITY_PROVIDER.md)
- [Run Reports](../06_EXECUTION/RUN_REPORTS.md)
