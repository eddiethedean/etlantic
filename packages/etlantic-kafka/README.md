# etlantic-kafka (Experimental / Preview)

Version **0.48.0** (lockstep with ETLantic core).
Fake-first Kafka source/sink for [ETLantic](https://github.com/eddiethedean/etlantic).
Live brokers are opt-in via `ETLANTIC_KAFKA_BOOTSTRAP` and are not required for CI.

**Maturity:** Experimental (Alpha classifier). Pin with core.

## Install

```bash
pip install 'etlantic-kafka==0.48.0'
```

Core dependency: `etlantic>=0.48.0,<0.49`. No librdkafka / confluent-kafka in the default extra.

## Entry points

| Group | Name | Factory |
|---|---|---|
| `etlantic.source_connectors` | `kafka` | `etlantic_kafka:create_source` |
| `etlantic.sink_connectors` | `kafka` | `etlantic_kafka:create_sink` |
