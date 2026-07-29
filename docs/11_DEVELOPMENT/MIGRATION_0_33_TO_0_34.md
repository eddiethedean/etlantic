# Migration 0.33 → 0.34

> **Status: Available in ETLantic 0.34.0.** Operations / observability slice
> (M6); **no wire-schema reset** (`etlantic.plan/1` / `pipeline/1` unchanged).

## Summary

| Area | Change |
|---|---|
| Wire schemas | Still `pipeline/1`, `plan/1`, … |
| Package pin | `etlantic==0.34.0`; plugins / `medallantic==0.34.0` |
| Lifecycle events | Optional correlation fields + `etlantic.lifecycle_event/1` |
| Profile JSON | New optional keys for observability/history providers |
| CLI | `etlantic report query`; workspace run history under `.etlantic/history/` |
| Medallantic | `explain_medallion_plan`, lifecycle views, profile templates |

## Upgrade steps

1. Pin core and matching plugins:

   ```bash
   python -m pip install --upgrade 'etlantic==0.34.0'
   python -m pip install --upgrade 'medallantic==0.34.0'
   ```

2. Optionally configure profile observability keys (see the repository
   [development profile example](https://github.com/eddiethedean/etlantic/blob/main/profiles/dev.example.json)).

3. Register reference providers on `PipelineRuntime` when not using entry points:

   ```python
   from etlantic.observability import FileRunHistoryProvider, JsonConsoleObservabilityProvider

   runtime.register_observability_provider("console", JsonConsoleObservabilityProvider())
   runtime.register_run_history_provider("file", FileRunHistoryProvider(path))
   ```

4. For production audit delivery, set `observability_delivery="durable_audit"` and
   ensure run-history persistence succeeds (fail-closed on flush/persist errors).

## Breaking / behavior notes

- Existing lifecycle event consumers reading `to_dict()` see additive fields only.
- `ObservabilityProvider` is now async `/1`; sync `emit()` adapters remain as
  `JsonConsoleObservabilityProvider` implementing the full protocol.
- Production profiles still require non-empty `plugin_allowlist`.

## See also

- [What's New 0.34](../01_GETTING_STARTED/WHATS_NEW_0_34.md)
- [Exit gate 0.34](EXIT_GATE_0_34.md)
- [Observability provider](../07_PLUGIN_SDK/OBSERVABILITY_PROVIDER.md)
