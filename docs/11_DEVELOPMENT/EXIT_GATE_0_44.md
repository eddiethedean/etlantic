# Exit Gate 0.44 — Developer Intelligence (LSP / IDE / Static Analysis)

> **Status: Released — ETLantic 0.44.0.** Editor-neutral language server,
> static analysis, VS Code reference client, notebook surfaces, and safe
> trusted-workspace boundary. Control-plane graduation remains 0.43.

| Deliverable | Status |
|---|---|
| Planning: this exit gate / findings / What's New / migration / ADR-020 | **Complete** |
| Editor-neutral protocol payloads (044-L precursor) | **Complete** |
| Static workspace analysis + watch (044-A) | **Complete** |
| Trusted-workspace boundary (044-X) | **Complete** |
| Language server package `etlantic-lsp` (044-L) | **Complete** |
| VS Code reference extension (044-V) | **Complete** (Experimental client) |
| Notebook integration (044-N) | **Complete** |
| Change safety / rename / impact (044-Q) | **Complete** |
| Packaging / docs / evidence (044-O) | **Complete** |
| Lockstep version 0.44.0 | **Complete** |

## Supported claim (frozen)

| Surface | GA status | Notes |
|---|---|---|
| No-import static analysis + diagnostics | **Supported** | AST + JSON PipelineDefinition |
| `etlantic-lsp` editor-neutral LSP | **Supported** | Requires matching `etlantic` minor |
| IDE/CLI/notebook plan fingerprint identity | **Supported** | Same public SDK paths |
| VS Code reference extension | **Experimental** | Reference client; other editors via LSP |
| Trusted-workspace import mode | **Supported** | Explicit opt-in; audited; timed out |
| Notebook widgets (`etlantic[notebook]`) | **Experimental** | Displays Supported without widgets |

## Quantified exit scorecard

From [IMPLEMENTATION_PLAN_0_44](IMPLEMENTATION_PLAN_0_44.md):

| # | Measure | Required | Current |
|---|---|---:|---|
| 1 | Downstream incompatibility diagnosed pre-exec with stable code, location, impact | Pass | **Met** — golden diagnostics + impact preview |
| 2 | Definition/refs/rename across layouts; reviewable edits | Pass | **Met** — LSP helpers + rename preview goldens |
| 3 | IDE/notebook/CLI same plan + report identity | Pass | **Met** — [ide_plan_identity_0_44.json](ide_plan_identity_0_44.json) |
| 4 | Run reconnect without duplicate attempts / authz bypass | Pass | **Met** — [ide_client_matrix_0_44.json](ide_client_matrix_0_44.json) |
| 5 | Default analysis: no import/secrets/live schema; trusted constrained | Pass | **Met** — [ide_trust_matrix_0_44.json](ide_trust_matrix_0_44.json) |
| 6 | Notebook displays safe, bounded, stale-marked | Pass | **Met** — `tests/ide/test_notebook_0_44.py` |
| 7 | Objective/erasure previews metadata-only | Pass | **Met** — preview panels metadata-only; redaction in ArtifactPreview |
| 8 | Latency/memory budgets for representative fixtures | Pass | **Met** — [ide_analysis_bench_0_44.json](ide_analysis_bench_0_44.json) |
| 9 | No unresolved critical/high finding in phase scope | 0 | **Met** — [FINDINGS_0_44](FINDINGS_0_44.md) P0=0 |
| 10 | Release record: supported vs experimental | Pass | **Met** — this document |

## Evidence map

| Gate item | Evidence |
|---|---|
| Implementation plan | [IMPLEMENTATION_PLAN_0_44](IMPLEMENTATION_PLAN_0_44.md) |
| ADR | [ADR-020](adr/ADR-020-DEVELOPER-INTELLIGENCE.md) |
| LSP conformance | [lsp_conformance_0_44.json](lsp_conformance_0_44.json) |
| Analysis bench | [ide_analysis_bench_0_44.json](ide_analysis_bench_0_44.json) |
| Trust matrix | [ide_trust_matrix_0_44.json](ide_trust_matrix_0_44.json) |
| Plan identity | [ide_plan_identity_0_44.json](ide_plan_identity_0_44.json) |
| Client matrix | [ide_client_matrix_0_44.json](ide_client_matrix_0_44.json) |
| Findings | [FINDINGS_0_44](FINDINGS_0_44.md) |
| Migration | [MIGRATION_0_43_TO_0_44](MIGRATION_0_43_TO_0_44.md) |
| What's New | [WHATS_NEW_0_44](../01_GETTING_STARTED/WHATS_NEW_0_44.md) |

## Go / no-go

**Released** as `0.44.0` (tag `v0.44.0` / PyPI / RTD). ROADMAP current row
remains **Gate-ready for tag/publish** vocabulary until the next minor. All
scorecard rows are **Met** under the evidence language above (in-process
analysis + LSP smoke + notebook unit tests).

## Explicit non-claims

- No React interactive HTML product workspace (deferred UI/UX Phase 2)
- No formal enterprise SLA for editor hosts
- No automatic import of untrusted project modules
- VS Code extension remains Experimental reference client
