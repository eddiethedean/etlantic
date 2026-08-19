# What's New in ETLantic 0.48

> **Status: Available in ETLantic 0.48.0 (shipped Beta).** Human-governed AI:
> redacted context bundles, `etlantic.proposal/1` sandbox, user-region
> generators, and approval handoff to existing 0.42 `/v1/approvals*`.
> Experimental `etlantic-mcp` is fake-first. Live MCP-client and paid-model
> eval remain skipped.

## Highlights

- **Context bundles** — `etlantic.context_bundle/1` from inspect/validate/plan;
  budget, provenance, freshness, and redaction fail closed (`PMCTX*`)
- **Proposal sandbox** — `etlantic.proposal/1` validates files without network,
  secrets, or execution (`PMPROP*`). `applied` is always false
- **Generators** — `etlantic generate --kind agents` preserves
  `<!-- etlantic:user-region:start id=... -->` markers (`PMGUIDE*`)
- **Task catalog** — vendor-neutral `etlantic.ai_task/1` shared by Codex,
  Claude, and Cursor adapters
- **Approval handoff** — proposal fingerprints call existing `ApprovalStore`
  / `/v1/approvals*`. Deny, expire, and stale fingerprints stay 0.42 behavior
- **CLI / FastAPI** — `etlantic context bundle`, `etlantic proposal validate`,
  `POST /v1/definitions/{id}/context`, `POST /v1/proposals/validate`.
  Tutorial: [Human-governed AI](HUMAN_GOVERNED_AI.md).
- **Experimental extra** — `etlantic-mcp` `FakeMcpServer` (live client skipped)

## Adopter actions

| Who | Action |
|---|---|
| Everyone on **0.47.x** | Upgrade to `etlantic==0.48.0` with matching plugins; see [Migration 0.47 → 0.48](../11_DEVELOPMENT/MIGRATION_0_47_TO_0_48.md) |
| Agent / IDE authors | Treat proposals as untrusted; require a current 0.42 approval before apply |
| Production operators | Pin `plugin_allowlist` for `etlantic-mcp` when that extra is selected |

## Not in 0.48

- Write MCP tools, vendor AI SDKs in core, autonomous run submit
- Live MCP-client interop
- Live paid-model eval
- GitOps promotion (0.40–0.43 APIs), brownfield import (0.49), operator console (0.50)
