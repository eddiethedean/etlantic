---
status: available
since: "0.39.0"
current_minor: "0.39"
audience: developer
---

# etlantic-polars API

> **Status: Available in ETLantic 0.39.0.** Polars dataframe plugin + portable compiler.
> Install narrative: package README. Hub: [Optional packages API](../API_OPTIONAL_PACKAGES.md).

## Setup

```bash
pip install 'etlantic-polars==0.39.0'
```

```python
import etlantic_polars
print(etlantic_polars.__version__)
```

## Failure modes

| Topic | Behavior |
|---|---|
| Missing Polars / entry point | PMPLUG* discovery; importorskip |

## Public API

::: etlantic_polars
    options:
      show_source: false
      show_submodules: true
      members_order: source
      filters:
        - "!^_"
