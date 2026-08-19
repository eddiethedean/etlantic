---
status: available
since: "0.48.0"
current_minor: "0.48"
audience: developer
---

# etlantic-mcp API

> **Status: Experimental in ETLantic 0.48.0.** Fake-first read-only MCP extra.
> Live MCP-client interop is opt-in. Hub:
> [Optional packages API](../API_OPTIONAL_PACKAGES.md).

## Setup

```bash
pip install 'etlantic-mcp==0.48.0'
```

```python
import etlantic_mcp
print(etlantic_mcp.__version__)
```

## Failure modes

| Topic | Behavior |
|---|---|
| Experimental | No production guarantees; unsupported capabilities fail closed |
| Vendor SDK | Not required; `FakeMcpServer` is the 0.48 gate |
| Live client | Skipped unless `ETLANTIC_MCP_LIVE` is set (`048-M-01`) |
| Production allowlist | Empty `plugin_allowlist` rejects with `PMMCP140` when selected |
| Authority | Mutate / submit / secrets / network / tool-expansion methods deny (`PMMCP*`) |

## Public API

::: etlantic_mcp
    options:
      show_source: false
      show_submodules: true
      members_order: source
      filters:
        - "!^_"
