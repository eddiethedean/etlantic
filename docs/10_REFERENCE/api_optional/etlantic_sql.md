---
status: available
since: "0.40.0"
current_minor: "0.40"
audience: developer
---

# etlantic-sql API

> **Status: Available in ETLantic 0.40.0.** SQL plugin (SQLite + PostgreSQL).
> Install narrative: package README. Hub: [Optional packages API](../API_OPTIONAL_PACKAGES.md).

## Setup

```bash
pip install 'etlantic-sql==0.40.0'
```

```python
import etlantic_sql
print(etlantic_sql.__version__)
```

## Failure modes

| Topic | Behavior |
|---|---|
| Engine URL / dialect | PMEXEC433 empty engine; MERGE PostgreSQL-only |

## Public API

::: etlantic_sql
    options:
      show_source: false
      show_submodules: true
      members_order: source
      filters:
        - "!^_"
