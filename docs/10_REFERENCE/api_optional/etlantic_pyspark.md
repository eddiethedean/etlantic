---
status: available
since: "0.43.0"
current_minor: "0.46"
audience: developer
---

# etlantic-pyspark API

> **Status: Available in ETLantic 0.46.0.** PySpark plugin + portable compiler.
> Install narrative: package README. Hub: [Optional packages API](../API_OPTIONAL_PACKAGES.md).

## Setup

```bash
pip install 'etlantic-pyspark==0.46.0'
```

```python
import etlantic_pyspark
print(etlantic_pyspark.__version__)
```

## Failure modes

| Topic | Behavior |
|---|---|
| JVM / sparkless | SPARKLESS_TEST_MODE; JVM required for real Spark |

## Public API

::: etlantic_pyspark
    options:
      show_source: false
      show_submodules: true
      members_order: source
      filters:
        - "!^_"
