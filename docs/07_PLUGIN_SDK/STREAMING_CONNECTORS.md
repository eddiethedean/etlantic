# Streaming connectors

> **Status: Supported in ETLantic 0.46.0** for core stream semantics and
> in-memory fixtures. **Kafka I/O is Experimental** (`etlantic-kafka`) and is
> never Available in core.

Core owns capability tokens (`source.stream`, `source.watermark`,
`sink.stream`, `sink.exactly_once`), record-error **policy**, and envelope
**metadata**. Providers own offsets, DLQ storage, and network I/O.

## Protocol

Implement the existing `SourceConnector` / `SinkConnector` protocols. Advertise
frozen stream tokens only. Compilers that cannot preserve map/branch/stream
nodes must **reject** the plan (no silent flatten-to-DAG).

```python
from etlantic.testing import run_streaming_conformance_suite

run_streaming_conformance_suite()
```

## Kafka extra

Install `etlantic-kafka==0.48.0`. Default tests use in-process `FakeKafka`.
Live brokers require `ETLANTIC_KAFKA_BOOTSTRAP` and are skipped in CI.

Production profiles must pin the package on `Profile.plugin_allowlist`.

## Payloads

Plans, reports, and diagnostics must not contain event payloads. See
[ADR-022](../11_DEVELOPMENT/adr/ADR-022-DYNAMIC-CONTROL-AND-STREAMING.md).
