# etlantic-mcp (Experimental / Preview)

Version **0.48.0** (lockstep with ETLantic core).
Fake-first read-only MCP server for [ETLantic](https://github.com/eddiethedean/etlantic).
Live MCP-client interop is opt-in via `ETLANTIC_MCP_LIVE` and is skipped in CI (`048-M-01`).

**Maturity:** Experimental (Alpha classifier). Pin with core.

## Install

```bash
pip install 'etlantic-mcp==0.48.0'
```

Core dependency: `etlantic>=0.48.0,<0.49`. No MCP SDK in the default extra.

## Entry points

| Group | Name | Factory |
|---|---|---|
| `etlantic.mcp_servers` | `mcp` | `etlantic_mcp:create_server` |
