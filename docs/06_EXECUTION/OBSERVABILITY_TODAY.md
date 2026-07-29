# Observability Today

> **Status: Available in ETLantic 0.34.0.** What ships now vs future provider
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

## Related

- [Run Reports](RUN_REPORTS.md)
- [Ops Pilot](OPS_PILOT.md)
- [Observability Provider (future)](../07_PLUGIN_SDK/OBSERVABILITY_PROVIDER.md)
