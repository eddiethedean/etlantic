---
status: available
since: "0.43.0"
current_minor: "0.51"
audience: developer
---

# medallantic API

> **Status: ETLantic 0.51.0 release candidate; publication pending.** Medallion facade + SparkForge migrate.
> Install narrative: package README. Hub: [Optional packages API](../API_OPTIONAL_PACKAGES.md).

## Setup

```bash
pip install 'medallantic==0.51.0'
```

```python
import medallantic
print(medallantic.__version__)
```

## Failure modes

| Topic | Behavior |
|---|---|
| IR convertibility | MDL210 manual; MDL220 unsupported |

## Public API

::: medallantic
    options:
      show_source: false
      show_submodules: true
      members_order: source
      filters:
        - "!^_"
