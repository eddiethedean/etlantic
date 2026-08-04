# Observability Today

> **Status: Available in ETLantic 0.43.0.** What ships now vs future provider
> protocols.

## Shipped (0.34+)

| Surface | Notes |
|---|---|
| Observability provider protocol | `etlantic.observability/1`; entry-point group |
| Run history providers | File + in-memory reference implementations |
| Event consumers | Reference trend consumer |
| Structured run reports | `PipelineRunReport`; CLI `etlantic report` |
| Lifecycle correlation | `etlantic.lifecycle_event/1` |
| Optional OpenTelemetry | `pip install 'etlantic[otel]'` |
| Mermaid / Graphviz / HTML lineage | `etlantic.viz` / `etlantic viz` |

## Not shipped

- Compliance-grade audit system of record (operational evidence only)
- Guaranteed cross-run correlation without a configured history provider

## Operator howto (durable_audit + report query)

See the consolidated hub: [Reports and history](REPORTS_AND_HISTORY.md).

```bash
python -m etlantic report query --since 2026-01-01T00:00:00+00:00 --format json
```

Profile keys: `run_history_provider`, `observability_providers`,
`event_consumers`, `observability_delivery` (`best_effort` | `durable_audit`).

## Related

- [Reports and history](REPORTS_AND_HISTORY.md)
- [Run Reports](RUN_REPORTS.md)
- [Ops Pilot](OPS_PILOT.md)
- [Observability Provider](../07_PLUGIN_SDK/OBSERVABILITY_PROVIDER.md)
- Failures: [Troubleshooting → M6 ops cookbook](../01_GETTING_STARTED/TROUBLESHOOTING.md#m6-ops-failure-cookbook-observability-history-reports)
