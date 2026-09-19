---
status: available
since: "0.43.0"
current_minor: "0.54"
audience: developer
---

# etlantic-polars API

The 0.54 Experimental `create_parquet_storage()` factory provides a read-only,
bounded local Parquet source. Register it explicitly with `PipelineRuntime`;
ordinary reads remain separate from the exact scan/filter/project fusion
candidate. No general connector pushdown is claimed. See the
[bounded reference and registration guide](../../11_DEVELOPMENT/ADAPTIVE_0_54_USAGE.md).

> **Status: Available in ETLantic 0.54.0 (Beta release candidate).** Polars dataframe plugin + portable compiler.
> Install narrative: package README. Hub: [Optional packages API](../API_OPTIONAL_PACKAGES.md).

## Setup

```bash
pip install 'etlantic-polars==0.54.0'
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
