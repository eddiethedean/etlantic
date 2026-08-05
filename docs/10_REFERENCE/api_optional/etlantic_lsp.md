---
status: available
since: "0.45.0"
current_minor: "0.45"
audience: developer
---

# etlantic-lsp API

> **Status: Available in ETLantic 0.45.0.** Editor-neutral language server
> wrapping `etlantic.ide` analysis. Install via `etlantic[lsp]` or
> `etlantic-lsp==0.45.0`. VS Code reference client remains **Experimental**.

## Setup

```bash
pip install 'etlantic[lsp]==0.45.0'
etlantic-lsp
# or: python -m etlantic_lsp
```

```python
import etlantic_lsp
from etlantic_lsp import create_server

print(etlantic_lsp.__version__)
server = create_server()
```

## Trust

Default analysis is **no-import**. Pass initialization option
`trustedImports: true` (VS Code setting `etlantic.trustedImports`) so workspace
folders become `TrustedWorkspacePolicy.allow_roots`. Secret resolution and live
schema queries stay denied by the analysis host.

## Surfaces

| Surface | Role |
|---|---|
| Diagnostics / symbols / rename | From `WorkspaceIndex` (AST + JSON) |
| Custom requests | `etlantic/graphPreview`, `planPreview`, `impactPreview`, `executeCommand` |
| IdeCommand | Public validate/plan/explain/report paths; `generate` returns unsupported |

See [ADR-020](../../11_DEVELOPMENT/adr/ADR-020-DEVELOPER-INTELLIGENCE.md) and
the [package README](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-lsp/README.md).

## Module

::: etlantic_lsp
    options:
      show_source: false
      members_order: source
      filters:
        - "!^_"
