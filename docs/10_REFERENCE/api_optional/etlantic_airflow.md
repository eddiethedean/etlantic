---
status: available
since: "0.42.0"
current_minor: "0.42"
audience: developer
---

# etlantic-airflow API

> **Status: Available in ETLantic 0.42.0.** Airflow DAG compiler.
> Install narrative: package README. Hub: [Optional packages API](../API_OPTIONAL_PACKAGES.md).

## Setup

```bash
pip install 'etlantic-airflow==0.42.0'
```

```python
import etlantic_airflow
print(etlantic_airflow.__version__)
```

## Failure modes

| Topic | Behavior |
|---|---|
| Missing Airflow at import | Compile succeeds without Airflow; import needs apache-airflow |

## Public API

::: etlantic_airflow
    options:
      show_source: false
      show_submodules: true
      members_order: source
      filters:
        - "!^_"
