---
status: available
since: "0.46.0"
current_minor: "0.46"
audience: developer
---

# etlantic-kafka API

> **Status: Experimental in ETLantic 0.46.0.** Kafka source and sink connectors
> with fake/CI conformance evidence. Live brokers are opt-in. Hub:
> [Optional packages API](../API_OPTIONAL_PACKAGES.md).

## Setup

```bash
pip install 'etlantic-kafka==0.46.0'
```

```python
import etlantic_kafka
print(etlantic_kafka.__version__)
```

## Failure modes

| Topic | Behavior |
|---|---|
| Experimental | No production guarantees; unsupported capabilities fail closed |
| Vendor SDK | Not required; FakeKafka remains available for conformance tests |
| Live broker | Skipped unless `ETLANTIC_KAFKA_BOOTSTRAP` is set |

## Public API

::: etlantic_kafka
    options:
      show_source: false
      show_submodules: true
      members_order: source
      filters:
        - "!^_"
