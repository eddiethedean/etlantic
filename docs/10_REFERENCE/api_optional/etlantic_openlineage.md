---
status: available
since: "0.42.0"
current_minor: "0.42"
audience: developer
---

# etlantic-openlineage API

> **Status: Experimental in ETLantic 0.42.0.** Outbound OpenLineage-compatible
> export for CP2. Install narrative: package README. Hub:
> [Optional packages API](../API_OPTIONAL_PACKAGES.md).
> **CP2 ≠ production multi-tenant** (**0.43**).

## Setup

```bash
pip install 'etlantic-openlineage==0.42.0'
```

```python
import etlantic_openlineage
print(etlantic_openlineage.__version__)
```

## Failure modes

| Topic | Behavior |
|---|---|
| Experimental | No production guarantees; unsupported capabilities fail closed |
| Transport failure | Raises; must never mutate registry authority |
| Vendor SDK | Optional; fake transport remains available for conformance tests |

## Public API

::: etlantic_openlineage
    options:
      show_source: false
      show_submodules: true
      members_order: source
      filters:
        - "!^_"
