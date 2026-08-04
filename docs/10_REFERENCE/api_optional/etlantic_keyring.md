---
status: available
since: "0.43.0"
current_minor: "0.43"
audience: developer
---

# etlantic-keyring API

> **Status: Available in ETLantic 0.43.0.** OS keyring secret provider.
> Install narrative: package README. Hub: [Optional packages API](../API_OPTIONAL_PACKAGES.md).

## Setup

```bash
pip install 'etlantic-keyring==0.43.0'
```

```python
import etlantic_keyring
print(etlantic_keyring.__version__)
```

## Failure modes

| Topic | Behavior |
|---|---|
| Backend unavailable | Secret resolve failures; never log secrets |

## Public API

::: etlantic_keyring
    options:
      show_source: false
      show_submodules: true
      members_order: source
      filters:
        - "!^_"
