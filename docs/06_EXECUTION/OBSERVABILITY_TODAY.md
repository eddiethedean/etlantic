# Observability Today (0.11)

> **Status: Available in ETLantic 0.11.0.** What ships now vs future provider
> protocols.

## Shipped

| Surface | Notes |
|---|---|
| Structured run reports | `PipelineRunReport`; CLI `etlantic report` |
| Process logging | Local runtime structured logs |
| Optional OpenTelemetry | `pip install 'etlantic[otel]'` |
| Mermaid / Graphviz / HTML lineage | `etlantic.viz` / `etlantic viz` |

Run reports are **operational evidence for a single process**, not an audit
system of record. Export or file-backed report stores when you need retention.

## Not shipped

- Durable multi-tenant observability provider protocol (Design Proposals)
- Guaranteed cross-run correlation without your own store
- Compliance-grade audit trails

## Related

- [Run Reports](RUN_REPORTS.md)
- [Ops Pilot](OPS_PILOT.md)
- [Observability Provider (future)](../07_PLUGIN_SDK/OBSERVABILITY_PROVIDER.md)
