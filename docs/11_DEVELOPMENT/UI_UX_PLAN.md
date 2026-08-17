# User Interface and Experience Plan

> **Plan status: partially shipped, cross-cutting plan.**
>
> **Current 0.45 boundary:** The local CLI, generated read-only HTML/diagram
> artifacts, and Phase 4 developer intelligence (watch, `etlantic-lsp`, VS Code
> reference client, notebooks) are available in published **0.45.0**. Interactive
> HTML workspace (Phase 2), run dashboard (Phase 3), and hosted Operator Console
> (Phase 5 / 0.50) remain planned and must pass their own accessibility,
> security, and operational gates.
>
> **Authority:** Current CLI and visualization guides define shipped behavior.
> This plan sequences interface outcomes; it never makes a UI an independent
> source of truth. See [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md)
> and the [Planning Hub](PLAN_INDEX.md).
>
> **Review trigger:** Update when an interface phase ships or its control-plane
> dependency changes.

## Outcome

ETLantic should make the safe path the obvious path for developers, reviewers,
and operators. The same typed requests, diagnostics, plans, reports, lineage,
authorization, redaction, and audit evidence must power every interface.

The phases below describe dependency order rather than release dates. They map
onto existing roadmap milestones and may ship incrementally when their
acceptance gates pass.

Release-specific delivery and evidence are defined by the
[0.45 developer-intelligence plan](IMPLEMENTATION_PLAN_0_44.md) and the
[0.50 operator-console plan](IMPLEMENTATION_PLAN_0_50.md). This domain plan
continues to own shared interaction, accessibility, and artifact semantics.

## Product principles

- Human, JSON, SARIF, HTML, SDK, and future HTTP views project the same public
  models and diagnostic identities.
- Human output leads with status, impact, location, and the safest next action.
- Mutating operations expose target, profile, scope, trust decision, and write
  intent before execution.
- Generated visualizations and dashboards remain read-only projections unless
  an action is routed through the same typed, authorized, idempotent API as
  every other client.
- Plans, reports, diagnostics, visualizations, browser state, and telemetry
  never contain resolved secrets or source rows.
- Core remains usable without browser, frontend, or hosted-service
  dependencies.
- Accessibility, keyboard operation, reduced motion, color-independent status,
  and bounded rendering are release requirements rather than polish.

## Phase 1 — CLI clarity and guided recovery

**Roadmap alignment:** stable-foundation tooling follow-up and a prerequisite
for 0.45 developer intelligence.

### Deliver

- one shared human renderer for status summaries, tables, diagnostics, diffs,
  timings, and progress;
- consistent `human`, `json`, `sarif`, and applicable `html` format names
  across commands, with `NO_COLOR`, quiet, verbose, and non-interactive
  behavior;
- actionable diagnostics that show source, explanation, remediation, and safe
  edit previews without silently changing schemas or trust policy;
- pipeline target discovery, a configured default target, target listing, and
  shell completion so the common single-pipeline path does not require
  repeatedly typing `path.py:Class`;
- progressive `init` guidance and task-oriented entry points for check,
  preview, explain, and changes workflows;
- resilient `--help` and `doctor` behavior under missing optional or
  development dependencies.

### Gates

1. Human and structured output agree on result, diagnostic identity, severity,
   phase, and exit code.
2. Every error in the golden path provides a specific safe next action.
3. Help and doctor remain usable without importing optional execution engines.
4. Existing scripts retain stable structured output and documented exit codes.
5. Usability fixtures cover empty projects, ambiguous targets, missing
   plugins, unauthorized plugins, invalid profiles, and first successful run.

## Phase 2 — Interactive self-contained pipeline workspace

**Roadmap alignment:** visualization/tooling work that can begin before 0.45
and becomes an IDE preview substrate in 0.44.

### React architecture spike

Run a bounded implementation spike before selecting the Phase 2 frontend
architecture. React is the preferred candidate for the interactive workspace
and for reuse through Phases 3–5, but the spike must establish that choice
with measured evidence rather than make it a core dependency by assumption.

The spike must:

- build a representative pipeline workspace from a versioned, generated
  TypeScript model derived from ETLantic's public, secret-free graph,
  diagnostic, plan-summary, and run-summary schemas;
- compare a React implementation with the existing dependency-free static
  renderer, preserving the static renderer as a portable fallback;
- evaluate graph-library and custom SVG/canvas approaches for layout,
  interaction, accessibility, licensing, maintenance, and large-graph
  performance;
- prove searchable lineage, upstream/downstream tracing, node details,
  diagnostic navigation, and a representative plan or run comparison;
- test a self-contained offline artifact and a separately deployable build
  from the same application code;
- define content-security policy, script/style embedding, hostile-label
  handling, redaction, source-map publication, and dependency/supply-chain
  controls;
- measure deterministic build output, bundle size, initial render,
  interaction latency, memory, and graph-size limits;
- evaluate keyboard navigation, focus management, reduced motion,
  color-independent status, and screen-reader behavior;
- propose the component/theme boundary and the reuse contract for the 0.50
  Operator Console;
- prohibit arbitrary user-authored frontend code unless a later isolated
  extension design passes a separate security review.

The spike closes with a short architecture decision record selecting React,
another interactive approach, or static-only continuation. The decision must
record measured tradeoffs, dependency ownership, upgrade policy, build
reproducibility, browser support, and the boundary that keeps frontend
dependencies outside ETLantic core.

### Spike acceptance gates

1. The React candidate consumes only versioned generated data and cannot
   redefine pipeline, validation, planning, lineage, or report semantics.
2. A single build can produce an offline artifact without remote runtime
   dependencies and a deployable application without divergent UI logic.
3. The representative large graph stays within proposed bundle, render,
   interaction, and memory budgets.
4. Primary graph and diagnostic workflows pass keyboard and screen-reader
   acceptance scenarios.
5. Content-security, hostile-input, redaction, license, dependency-audit, and
   deterministic-build checks pass.
6. Removing frontend build tooling does not affect installation, import, CLI,
   SDK, or static-renderer use of ETLantic core.

### Deliver

- evolve `etlantic viz html` into a self-contained pipeline workspace with
  searchable, zoomable, keyboard-operable lineage;
- upstream/downstream tracing, subpipeline collapse, node filters, and a detail
  panel for contracts, assets, implementations, capabilities, and diagnostics;
- logical, planned-profile, validation, and recent-run views with explicit
  provenance and timestamps;
- static artifacts suitable for CI, release review, documentation hosting, and
  offline use without an application server;
- deterministic snapshots and large-graph rendering budgets.

### Gates

1. The workspace is derived only from validated public artifacts and never
   becomes a second authoring model.
2. Static output works without remote scripts, ambient credentials, or network
   access.
3. Redaction, safe-I/O, content-security, and hostile-label tests pass.
4. Keyboard-only and screen-reader acceptance scenarios cover the primary
   graph and diagnostic workflows.
5. Large graphs stay within published generation, file-size, and interaction
   budgets.

## Phase 3 — Run dashboard and visual comparison

**Roadmap alignment:** local read-only precursor to the 0.50 Operator Console.

### Deliver

- a generated local dashboard over durable run reports and history;
- outcome, duration, quality, schema-drift, and recurring-diagnostic trends;
- filters for pipeline, profile, status, time range, step, and diagnostic code;
- visual plan and report comparisons for topology, implementation, contract,
  write-scope, duration, and diagnostic changes;
- resumable live run progress where an event provider is available, with
  durable-history fallback;
- links from failures to stable source locations and remediation guidance.

### Gates

1. The first shipped dashboard is read-only and can be generated as a bounded,
   self-contained artifact.
2. Aggregates cannot leak unauthorized or redacted object existence.
3. Comparison results match public CLI/SDK diff semantics.
4. Missing, partial, orphaned, or corrupt history is clearly distinguished
   from zero activity.
5. Dashboard generation and filtering have published workspace-size budgets.

## Phase 4 — Fast authoring feedback and editor integration

**Roadmap alignment:** 0.44 Developer Intelligence (**Released** with
ETLantic 0.44.0 — see [EXIT_GATE_0_44](EXIT_GATE_0_44.md)). 0.45 adds
advisory planner/optimization explanation on the same IDE/CLI artifacts
([EXIT_GATE_0_45](EXIT_GATE_0_45.md)).

### Deliver

- a watch-mode development loop that revalidates affected definitions and
  refreshes the local pipeline workspace;
- LSP diagnostics, completion, navigation, source maps, and safe quick-fix
  previews backed by public diagnostic actions;
- effective-profile and profile-comparison views;
- plan-selection explanations and impact previews before execution;
- editor-neutral protocols and maintained reference integration.

### Gates

1. Incremental and clean validation produce equivalent diagnostics.
2. File watching is bounded, ignores generated/workspace churn, and never
   executes a pipeline implicitly.
3. Suggested edits require review and cannot weaken production trust,
   authorization, safe-I/O, or schema policy silently.
4. The editor and CLI produce the same plan fingerprint for equivalent input.
5. Core and headless CI workflows remain independent of editor dependencies.

## Phase 5 — Hosted, governed product experience

**Roadmap alignment:** 0.39–0.43 establish the control-plane substrate; 0.50
delivers the read-only-first Operator Console and governed actions.

### Deliver

- a separately deployable web application using the version-pinned typed
  control-plane client;
- visible tenant, workspace, environment, revision, and authorization context
  on every screen;
- read-only-first definitions, plans, diffs, runs, lineage, quality, drift,
  delivery objectives, deadline/escalation state, erasure requests and proof,
  dynamic expansions and branch decisions, dead-letter/redrive and schema
  compatibility, policy, quota, provider, and audit views;
- explicit privileged workflows for cancel, retry, replay, repair, approve,
  acknowledge, promote, authorize/retry erasure, suspend, and contain;
- idempotent action confirmation, durable event reconnection, accessibility,
  localization readiness, pagination, and virtualization.

### Gates

1. No hosted UI is claimed before the applicable 0.39–0.43 isolation,
   authorization, idempotency, policy, quota, audit, and recovery gates pass.
2. Every mutation follows the same typed API and produces the same audit
   evidence as SDK, CLI, and HTTP clients.
3. Search, counts, links, errors, caches, browser history, and event streams
   cannot reveal unauthorized objects.
4. Refresh, reconnect, or repeated submission cannot duplicate privileged
   actions.
5. Deployment and frontend dependencies remain outside ETLantic core.
6. Dead-letter and erasure screens expose bounded identifiers and policy
   evidence only; event payloads and data-subject values never enter browser
   state, URLs, logs, telemetry, or generated fixtures.

## Success measures

- median time from `init` to first valid plan and first successful local run;
- percentage of failed golden-path commands with an actionable next step;
- target-discovery and completion success without documentation lookup;
- diagnostic resolution rate and repeated-diagnostic frequency;
- time to locate the failing step and compare it with the previous good run;
- accessibility conformance and keyboard completion of primary workflows;
- dashboard performance at published workspace sizes;
- zero redaction, authorization, or cross-tenant disclosure regressions.
