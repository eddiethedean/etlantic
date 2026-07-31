---
status: available
since: "0.36.0"
current_minor: "0.36"
audience: developer
---

# etlantic-pandas API

> **Status: Available in ETLantic 0.36.0.** Pandas dataframe plugin + portable compiler.
> Install narrative: package README. Hub: [Optional packages API](../API_OPTIONAL_PACKAGES.md).

## Setup

```bash
pip install 'etlantic-pandas==0.36.0'
```

```python
import etlantic_pandas
print(etlantic_pandas.__version__)
```

## Failure modes

| Topic | Behavior |
|---|---|
| Missing Pandas | PMPLUG* discovery |

## Public API

::: etlantic_pandas
    options:
      show_source: false
      show_submodules: true
      members_order: source
      filters:
        - "!^_"
