---
title: ETLantic 0.44 Implementation Plan
description: Implementation-grade plan for language-server, editor, notebook, and developer-intelligence surfaces.
plan_status: current
plan_last_reviewed: 0.37.0
---

# ETLantic 0.44 Implementation Plan

Phase 0.44 makes ETLantic's contracts, diagnostics, plans, graphs, runs, schema
observations, and reliability evidence available through editor-neutral protocols
and safe notebook displays. The [UI/UX plan](UI_UX_PLAN.md) governs shared
interaction language and artifact semantics.

## Outcome

Developers can understand and change a pipeline before execution: navigate
symbols, preview downstream effects, inspect plans and configuration provenance,
inspect delivery objectives and erasure impact, apply reviewable fixes, launch
the same plan used by the CLI, reconnect to runs, and inspect bounded artifacts
without importing user code or exposing secrets.

## Prerequisites And Non-Goals

- 0.43 public API, identity, event, and authorization contracts are the only
  control-plane integration surface.
- Workspace analysis is static and side-effect-free by default. Importing user
  modules requires an explicit trusted-workspace opt-in and a constrained host.
- The VS Code client is a reference integration; the language-server protocol,
  diagnostics, and plan artifacts remain editor-neutral.
- Notebook widgets do not become an independent execution or authorization path.

## Workstreams

| ID | Workstream | Deliverables | Completion evidence |
|---|---|---|---|
| 044-L | Language server | Workspace discovery, completion, hover, definition, references, symbols, rename, diagnostics, code actions | Protocol tests across single-file, package, and monorepo fixtures |
| 044-A | Static analysis | Incremental parser/index, pipeline graph, field lineage, plan preview, configuration provenance, capability checks | Cold/warm latency, cache invalidation, and memory benchmarks |
| 044-X | Safe execution boundary | No-import default; trusted-workspace policy; constrained analysis/execution host; cancellation/timeouts | Malicious import, infinite analysis, secret access, and workspace escape tests |
| 044-V | VS Code integration | Graph/lineage/plan views, CodeLens actions, run/debug panel, reconnect, drift/impact/reliability views including objective/deadline and erasure-plan previews | End-to-end extension tests against local and remote APIs |
| 044-N | Notebook integration | Rich displays, bounded previews, run controls, export/extraction, stale-state markers, logical breakpoints | Jupyter/IPython parity and kernel restart/reconnect tests |
| 044-Q | Change safety | Reviewable rename/quick fixes, semantic diff, downstream impact, stale-plan detection | Golden edits with no unrelated rewrites and required revalidation |
| 044-O | Packaging and docs | Standalone server, extension package, compatibility matrix, troubleshooting, accessibility | Clean install, version-skew, accessibility, and release smoke tests |

## Delivery Sequence

1. Freeze editor-neutral diagnostics, locations, symbols, graph, plan, and action
   payloads.
2. Implement static workspace discovery and incremental indexing with no imports.
3. Add navigation, diagnostics, quick fixes, rename, graph, and plan previews.
4. Build the VS Code reference client against the neutral protocol.
5. Add notebook displays and control-plane run/event integration.
6. Qualify trusted execution, performance, accessibility, and version skew.

## Exit Gates

- A downstream contract incompatibility is diagnosed before execution with a
  stable code, precise location, and actionable impact explanation.
- Definition/reference navigation and rename work across supported workspace
  layouts; edits are reviewable and do not rewrite unrelated code.
- IDE, notebook, and CLI launch the same immutable plan and retrieve the same
  report identity through the public API.
- Run panels reconnect through resumable events without duplicating attempts or
  bypassing authorization.
- Default analysis imports no user code and reads no secret or live production
  schema; trusted mode is explicit, constrained, cancellable, and audited.
- Notebook displays are side-effect-free, bounded, redact hostile content, and
  visibly mark stale kernel/workspace/plan state.
- Objective views expose timezone/calendar/reference provenance without routing
  notifications, and erasure previews expose lineage and policy decisions
  without data-subject values or execution authority.
- Published latency and memory budgets pass for representative small, medium,
  and monorepo fixtures.

## Required Release Evidence

- LSP protocol/conformance and golden-diagnostic report.
- Static-analysis performance and invalidation benchmark.
- Trusted-workspace threat and escape-test report.
- IDE/CLI/notebook plan-and-report identity trace.
- Accessibility, version-skew, and reconnect results.
