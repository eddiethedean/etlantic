# Reports and history

> **Status: Available in ETLantic 0.45.0.** Operator hub for run reports,
> durable history, and `durable_audit`. Protocol detail lives under Plugin SDK.

## What to use when

| Need | Use | CLI |
|---|---|---|
| Latest run outcomes in the workspace | File report store (`.etlantic/reports/`) | `etlantic report list` / `show` |
| Cross-run history + events | Run history provider (`.etlantic/history/` via workspace) | `etlantic report query` |
| Fail closed when history cannot persist | `observability_delivery: durable_audit` on the Profile | configure profile JSON |
| Fan-out to OTel / console providers | Observability providers | profile `observability_providers` |

## Minimal operator path

1. Run a pipeline (CLI creates workspace reports by default):

```bash
python -m etlantic run pipeline.py:SamplePipeline --profile development
python -m etlantic report list
```

2. Query durable history (workspace `.etlantic/history/`):

```bash
python -m etlantic report query --format json --limit 20
python -m etlantic report query --since 2026-01-01T00:00:00+00:00 --status succeeded
```

3. For production pilots that require audit-style persistence, set in profile JSON:

```json
{
  "name": "production",
  "security_mode": "production",
  "plugin_allowlist": {"etlantic-polars": "==0.45.0"},
  "run_history_provider": "file",
  "observability_delivery": "durable_audit"
}
```

`durable_audit` fails closed when required history persistence or provider flush
fails. `best_effort` logs and continues.

## Detail pages

- [Run Reports](RUN_REPORTS.md) — report model and fields
- [Durable Reports](DURABLE_REPORTS.md) — `.etlantic/reports/` store
- [Observability today](OBSERVABILITY_TODAY.md) — M6 surface summary
- Protocols: [Observability](../07_PLUGIN_SDK/OBSERVABILITY_PROVIDER.md),
  [Run history](../07_PLUGIN_SDK/RUN_HISTORY_PROVIDER.md),
  [Event consumer](../07_PLUGIN_SDK/EVENT_CONSUMER.md)
- Failures: [Troubleshooting → M6 ops cookbook](../01_GETTING_STARTED/TROUBLESHOOTING.md#m6-ops-failure-cookbook-observability-history-reports)

## SDK sketch

```python
import etlantic as etl
from etlantic.observability import FileRunHistoryProvider
from etlantic.runtime.observability_bridge import ObservabilityBridge

profile = etl.Profile(
    name="production",
    security_mode="production",
    plugin_allowlist={"etlantic-polars": "==0.45.0"},
    run_history_provider="file",
    observability_delivery="durable_audit",
)
# Register providers on PipelineRuntime / bridge as documented in
# Observability Provider + Run History Provider guides.
```

Prefer `import etlantic.observability` (or the guides above) — there is no
`etl.observability` lazy namespace on the curated root.
