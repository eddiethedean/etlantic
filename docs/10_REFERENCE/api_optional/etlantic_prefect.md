---
status: available
since: "0.43.0"
current_minor: "0.60"
audience: developer
---

# etlantic-prefect API

> **Status: ETLantic core 0.60.0 is a Beta candidate; 0.59.x remains the published support line.** Prefect local scheduler MVP.
> Install narrative: package README. Hub: [Optional packages API](../API_OPTIONAL_PACKAGES.md).

The managed Process-deployment adapter implemented under phase 0.58 is
experimental and is not production-qualified. See the package guide and
[phase 0.58 implementation plan](../../11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_58.md)
for its trusted backend, dispatcher, worker, and current qualification status.

## Setup

```bash
pip install 'etlantic-prefect==0.60.0'
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
