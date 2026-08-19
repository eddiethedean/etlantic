---
status: available
since: "0.48.0"
current_minor: "0.48"
audience: developer
---

# etlantic-schemaregistry API

> **Status: Experimental in ETLantic 0.48.0.** Confluent-compatible schema-registry
> adapter over the core identity protocol. Live HTTP is opt-in. Hub:
> [Optional packages API](../API_OPTIONAL_PACKAGES.md).

## Setup

```bash
pip install 'etlantic-schemaregistry==0.48.0'
```

```python
import etlantic_schemaregistry
print(etlantic_schemaregistry.__version__)
```

## Failure modes

| Topic | Behavior |
|---|---|
| Experimental | No production guarantees; production requires `schema_registry_allowlist` |
| Vendor SDK | Not required; FakeConfluentRegistry is the default test adapter |
| Live registry | Skipped unless `ETLANTIC_SCHEMA_REGISTRY_URL` is set |

## Public API

::: etlantic_schemaregistry
    options:
      show_source: false
      show_submodules: true
      members_order: source
      filters:
        - "!^_"
