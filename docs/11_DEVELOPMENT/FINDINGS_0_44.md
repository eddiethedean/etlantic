# Findings Ledger 0.44 — Developer Intelligence

> **Status: Released** — ETLantic **0.44.0** developer-intelligence exit.
> Open **P0 count is 0**.

## Severity policy

From [IMPLEMENTATION_PLAN_0_44](IMPLEMENTATION_PLAN_0_44.md) and
[ADR-020](adr/ADR-020-DEVELOPER-INTELLIGENCE.md):

| Severity | Meaning | Release treatment |
|---|---|---|
| **P0** | Default analysis imports user code / resolves secrets / queries live prod schema; IDE bypasses authz or duplicates durable attempts; secret leakage in diagnostics/previews | Must close before 0.44 |
| **P1** | Material navigation, rename, reconnect, or performance risk | Close or defer with owner, mitigation, target |
| **P2** | Localized usability / maintainability | May defer with owner and target |
| **P3** | Cosmetic | Backlog |

## Locked dispositions

| Decision | Outcome | Notes |
|---|---|---|
| Protocol ownership | Core `etlantic.ide` | ADR-020 |
| LSP transport | `etlantic-lsp` (pygls) | Not a core hard dependency |
| VS Code client | Reference / Experimental | Other editors via LSP |
| Default analysis | No-import | Trusted opt-in only |
| Plan identity | IDE = CLI = notebook | Public SDK only |

## Open findings

Open **P0 count is 0**.

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| — | — | — | — | No open P0 | — |

## Soft-continue from prior phases

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| `043-R-01` | P1 | Control-plane | Deferred | True multi-process dual-API drill | Out of 0.44 scope |
| `043-M-01` | P1 | Control-plane | Deferred | OpenLineage reconciliation product drill | Out of 0.44 scope |

## Closure rules

A finding closes only with a test, evidence artifact, or explicit deferral row.
