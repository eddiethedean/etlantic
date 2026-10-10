---
status: available
since: "0.43.0"
current_minor: "0.57"
audience: developer
---

# etlantic-sqlmodel API

> **Status: ETLantic 0.57.0 Beta release.** SQLModel bridge helpers.
> Install narrative: package README. Hub: [Optional packages API](../API_OPTIONAL_PACKAGES.md).

## Setup

```bash
pip install 'etlantic-sqlmodel==0.57.1'
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
