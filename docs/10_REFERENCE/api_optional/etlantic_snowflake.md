---
status: available
since: "0.43.0"
current_minor: "0.44"
audience: developer
---

# etlantic-snowflake API

> **Status: Experimental in ETLantic 0.43.0.** Snowflake source, sink, and
> storage connectors with fake/CI conformance evidence. Install narrative:
> package README. Hub: [Optional packages API](../API_OPTIONAL_PACKAGES.md).

## Setup

```bash
pip install 'etlantic-snowflake==0.44.0'
```

```python
import etlantic_snowflake
print(etlantic_snowflake.__version__)
```

## Failure modes

| Topic | Behavior |
|---|---|
| Experimental | No production guarantees; unsupported capabilities fail closed |
| Vendor SDK | Optional; fake connection remains available for conformance tests |

## Public API

::: etlantic_snowflake
    options:
      show_source: false
      show_submodules: true
      members_order: source
      filters:
        - "!^_"
