# What's New in ETLantic 0.44

> **Status: Available in ETLantic 0.44.0 (Beta).** Developer intelligence:
> editor-neutral LSP, static analysis, notebook displays, and safe
> trusted-workspace analysis. CP-GA claims remain those of 0.43.

## Highlights

- **Editor-neutral protocol** — versioned diagnostics, symbols, graph/plan/
  impact previews, and IDE commands under `etlantic.ide` ([ADR-020](../11_DEVELOPMENT/adr/ADR-020-DEVELOPER-INTELLIGENCE.md))
- **No-import static analysis** — workspace index over Python AST and JSON
  pipeline definitions; optional CLI watch mode
- **`etlantic-lsp`** — language server (completion, hover, navigation, rename,
  diagnostics, code actions, custom previews)
- **VS Code reference extension** — Experimental client in `editors/vscode`
- **Notebooks** — richer displays and `etlantic[notebook]` widgets; side-effect
  free by default; stale-state markers
- **Trusted workspace** — explicit opt-in for import-based analysis with
  timeouts and audit; never implicit
- **SARIF physical locations** — prefer `SourceLocation` file/line/column when
  present
- **Plan identity** — IDE, notebook, and CLI share public SDK paths and plan
  fingerprints

## Adopter actions

| Who | Action |
|---|---|
| Everyone on **0.43.x** | Upgrade to `etlantic==0.44.0` with matching plugins; see [migration](../11_DEVELOPMENT/MIGRATION_0_43_TO_0_44.md) |
| Editor users | Install `etlantic[lsp]` and configure `etlantic-lsp` |
| Notebook users | Install `etlantic[notebook]` for widgets; displays work without it |
| Multi-tenant operators | CP-GA claim unchanged; see 0.43 support matrix |

## Not in 0.44

- Operator Console (0.50)
- Planner / optimization SDK (0.45)
- Full React interactive HTML product workspace (UI/UX Phase 2)
- Closing deferred CP-GA multi-process / OpenLineage product drills

## See also

- [Migration 0.43 → 0.44](../11_DEVELOPMENT/MIGRATION_0_43_TO_0_44.md)
- [Exit gate 0.44](../11_DEVELOPMENT/EXIT_GATE_0_44.md)
- [Findings ledger 0.44](../11_DEVELOPMENT/FINDINGS_0_44.md)
- [Implementation plan 0.44](../11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_44.md)
- [ADR-020](../11_DEVELOPMENT/adr/ADR-020-DEVELOPER-INTELLIGENCE.md)
