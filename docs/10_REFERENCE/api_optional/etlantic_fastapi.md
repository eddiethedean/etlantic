---
status: available
since: "0.36.0"
current_minor: "0.36"
audience: developer
---

# etlantic-fastapi API

> **Status: Available in ETLantic 0.36.0.** FastAPI reference adapter.
> Install narrative: package README. Hub: [Optional packages API](../API_OPTIONAL_PACKAGES.md).

## Setup

```bash
pip install 'etlantic-fastapi==0.36.0'
```

```python
import etlantic_fastapi
print(etlantic_fastapi.__version__)
```

## Failure modes

| Topic | Behavior |
|---|---|
| App wiring | Reference only; not a control plane |

## Public API

::: etlantic_fastapi
    options:
      show_source: false
      show_submodules: true
      members_order: source
      filters:
        - "!^_"
