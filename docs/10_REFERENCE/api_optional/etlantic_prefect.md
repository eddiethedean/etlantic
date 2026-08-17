---
status: available
since: "0.43.0"
current_minor: "0.47"
audience: developer
---

# etlantic-prefect API

> **Status: Available in ETLantic 0.47.0.** Prefect local scheduler MVP.
> Install narrative: package README. Hub: [Optional packages API](../API_OPTIONAL_PACKAGES.md).

## Setup

```bash
pip install 'etlantic-prefect==0.47.0'
```

```python
import etlantic_prefect
print(etlantic_prefect.__version__)
```

## Failure modes

| Topic | Behavior |
|---|---|
| Missing Prefect | Scheduler discovery / trust |

## Public API

::: etlantic_prefect
    options:
      show_source: false
      show_submodules: true
      members_order: source
      filters:
        - "!^_"
