# ADR-020: Developer Intelligence Protocol and Safe Analysis Boundary

Date: 2026-08-04  
Status: Accepted (shipped with ETLantic **0.44.0**)

## Context

ETLantic 0.43 froze production multi-tenant control-plane contracts. Phase 0.44
(published Developer Intelligence) must expose contracts, diagnostics, plans,
graphs, and runs through editor-neutral protocols and notebooks without
inventing a second execution or authorization path, and without importing
untrusted project code by default.

Authoritative sequencing:
[IMPLEMENTATION_PLAN_0_44](../IMPLEMENTATION_PLAN_0_44.md),
[UI/UX Plan](../UI_UX_PLAN.md) Phase 4, and ROADMAP § 0.44.

## Decision

### Editor-neutral payloads

Core owns versioned JSON-serializable payloads under `etlantic.ide`:

- diagnostics with physical `SourceLocation` (file/line/column) when known
- symbols and location links across Python,
  [ODCS](../../03_DATA_CONTRACTS/ODCS.md)/[DTCS](../../04_TRANSFORMATIONS/DTCS.md)/[DPCS](../../05_PIPELINES/DPCS.md),
  plans, profiles
- graph, lineage, plan, explain, impact, and semantic-diff previews
- IDE commands/results that map 1:1 onto public SDK validate/plan/run/report

Language servers and editors are thin hosts. They must not redefine plan,
report, diagnostic, or trust semantics.

### No-import default and trusted opt-in

Default workspace analysis is static and side-effect-free:

- Python AST + JSON `PipelineDefinition` (`etlantic.pipeline/1`) only
- no `importlib` of user modules
- no secret resolution
- no live production schema queries

Trusted-workspace mode is an explicit policy (`TrustedWorkspacePolicy`) with
allowlisted roots, timeouts, cancellation, and an audit record. Only then may
hosts call `load_target` / import user modules. Trusted mode never grants more
authority than the equivalent CLI/SDK call under the same profile.

### Same plan identity

IDE, notebook, and CLI launches of equivalent inputs must produce the same
immutable plan fingerprint and retrieve the same report identity through the
public API. Notebook widgets and VS Code CodeLens are not independent
execution authorities.

### Packaging boundary

- Core: protocol, analysis, trust policy, command executor (no LSP transport)
- `etlantic-lsp`: pygls language server host
- `editors/vscode`: reference VS Code client (VSIX; not a Python wheel)
- `etlantic[notebook]`: optional IPython/ipywidgets displays and controls

## Consequences

- SARIF and GitHub annotation renderers prefer physical `SourceLocation` when
  present, falling back to logical diagnostic paths.
- A React interactive HTML product workspace remains deferred (UI/UX Phase 2);
  editor webviews reuse `etlantic.viz` IR / Mermaid.
- Deferred CP-GA multi-process residuals stay out of 0.44 scope.

## See also

- [IMPLEMENTATION_PLAN_0_44](../IMPLEMENTATION_PLAN_0_44.md)
- [EXIT_GATE_0_44](../EXIT_GATE_0_44.md)
