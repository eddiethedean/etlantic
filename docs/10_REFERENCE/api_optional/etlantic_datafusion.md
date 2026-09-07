---
status: available
since: "0.43.0"
current_minor: "0.49"
audience: developer
---

# etlantic-datafusion API

> **Status: Available in ETLantic 0.49.0.** DataFusion dataframe and portable compiler plugin.
> Install narrative: package README. Hub: [Optional packages API](../API_OPTIONAL_PACKAGES.md).

## Setup

```bash
pip install 'etlantic-datafusion==0.49.0'
```

```python
import etlantic_datafusion
print(etlantic_datafusion.__version__)
```

## Failure modes

| Topic | Behavior |
|---|---|
| Unsupported plan extension | Rejected during compiler analysis before execution |
| Native dependencies | Installed with `etlantic-datafusion`; core remains import-safe |

## Public API

::: etlantic_datafusion
    options:
      show_source: false
      show_submodules: true
      members_order: source
      filters:
        - "!^_"
