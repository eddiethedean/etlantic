---
status: available
since: "0.37.0"
current_minor: "0.37"
audience: developer
---

# etlantic-sqlmodel API

> **Status: Available in ETLantic 0.37.0.** SQLModel bridge helpers.
> Install narrative: package README. Hub: [Optional packages API](../API_OPTIONAL_PACKAGES.md).

## Setup

```bash
pip install 'etlantic-sqlmodel==0.37.0'
```

```python
import etlantic_sqlmodel
print(etlantic_sqlmodel.__version__)
```

## Failure modes

| Topic | Behavior |
|---|---|
| Model mismatch | Type/bridge errors |

## Public API

::: etlantic_sqlmodel
    options:
      show_source: false
      show_submodules: true
      members_order: source
      filters:
        - "!^_"
