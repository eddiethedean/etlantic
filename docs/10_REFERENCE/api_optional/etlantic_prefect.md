---
status: available
since: "0.43.0"
current_minor: "0.58"
audience: developer
---

# etlantic-prefect API

> **Status: ETLantic 0.58.0 Beta release.** Prefect direct and bounded managed execution.
> Install narrative: package README. Hub: [Optional packages API](../API_OPTIONAL_PACKAGES.md).

The managed Process-deployment adapter is qualified for static-batch
`etlantic.plan/1` work on a self-hosted Prefect API backed by PostgreSQL, using
the Process worker pool and the documented Ubuntu/Python matrix. Other pools,
hosting services, connectors, and plan families are outside this support
profile. See the package guide and [phase 0.58 implementation
plan](../../11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_58.md) for its trusted
backend, dispatcher, worker, and qualification evidence.

## Setup

```bash
pip install 'etlantic-prefect==0.58.0'
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
