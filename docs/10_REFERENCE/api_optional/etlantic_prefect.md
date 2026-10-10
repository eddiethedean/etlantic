---
status: available
since: "0.43.0"
current_minor: "0.57"
audience: developer
---

# etlantic-prefect API

> **Status: ETLantic 0.57.0 Beta release.** Prefect local scheduler MVP.
> Install narrative: package README. Hub: [Optional packages API](../API_OPTIONAL_PACKAGES.md).

## Setup

```bash
pip install 'etlantic-prefect==0.57.1'
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
