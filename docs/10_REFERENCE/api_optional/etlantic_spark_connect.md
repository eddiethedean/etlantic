---
status: available
since: "0.47.0"
current_minor: "0.47"
audience: developer
---

# etlantic-spark-connect API

> **Status: Experimental in ETLantic 0.47.0.** Fake-first Spark Connect
> `SparkProvider`. Live Databricks/EMR/Connect endpoints are opt-in. Hub:
> [Optional packages API](../API_OPTIONAL_PACKAGES.md).

## Setup

```bash
pip install 'etlantic-spark-connect==0.47.0'
```

```python
import etlantic_spark_connect
print(etlantic_spark_connect.__version__)
```

## Failure modes

| Topic | Behavior |
|---|---|
| Experimental | No production guarantees; unsupported capabilities fail closed |
| Vendor SDK | Not required; the in-process fake remains available for tests |
| Live endpoint | Skipped unless `ETLANTIC_SPARK_CONNECT_URL` is set (`047-S-01`) |
| Not a connector | Implements `SparkProvider`, not `etlantic.source/1` / `sink/1` |

## Public API

::: etlantic_spark_connect
    options:
      show_source: false
      show_submodules: true
      members_order: source
      filters:
        - "!^_"
