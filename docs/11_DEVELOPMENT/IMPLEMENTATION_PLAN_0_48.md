---
title: ETLantic 0.48 Implementation Plan
description: Implementation-grade plan for human-governed AI and agent workflows.
plan_status: current
plan_last_reviewed: 0.48.0
---

# ETLantic 0.48 Implementation Plan

> **Status: Gate-ready (in-tree 0.48.0; no tag).** See
> [ADR-024](adr/ADR-024-HUMAN-GOVERNED-AI.md) (Accepted) and
> [EXIT_GATE_0_48](EXIT_GATE_0_48.md). Context bundles, proposal sandbox,
> MCP extras, and generator-region semantics are Available in 0.48.0.

Phase 0.48 exposes bounded, read-only ETLantic intelligence to AI-assisted
workflows and turns proposed changes into deterministic, reviewable artifacts.
No model or agent receives implicit authority to mutate contracts, baselines,
state, runs, secrets, providers, schedules, or external systems.

It reuses `etlantic.agents.generate_agent_guidance`,
`scripts/check_agent_guidance.py`, `etlantic validate|plan|diff|inspect`,
0.44 impact/diff artifacts, 0.45 advisory optimizer candidates, and 0.42
`ApprovalStore` / `/v1/approvals*` instead of inventing a second mutation
path or a second GitOps promotion API.

## Outcome

Codex, Claude Code, Cursor, and other adapters can inspect redacted context,
propose pipeline/schema/reliability changes, validate them in a deterministic
sandbox, show semantic and downstream impact, and hand a human an explicit
approval step before any privileged action.

## Prerequisites And Non-Goals

- 0.44 diagnostics/change previews and 0.42 policy/approval/audit contracts
  are the required foundations ([EXIT_GATE_0_44](EXIT_GATE_0_44.md),
  [EXIT_GATE_0_42](EXIT_GATE_0_42.md),
  [ADR-019](adr/ADR-019-POLICY-QUOTAS-AND-AUDIT.md),
  [ADR-020](adr/ADR-020-DEVELOPER-INTELLIGENCE.md)).
- 0.47 scheduler/federation is closed ([EXIT_GATE_0_47](EXIT_GATE_0_47.md),
  [ADR-023](adr/ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md)). Those surfaces
  are **explain-only** in 0.48.
- [SECURITY.md — AI Coding Assistants](../02_FOUNDATIONS/SECURITY.md) is the
  security policy. 0.48 implements it; it does not invent a parallel policy.
- AI SDKs live in adapter packages and never become core dependencies.
- Read-only MCP or similar interfaces cannot mutate, submit, install, resolve
  secrets, contact external parties, or expand their own tool authority.
- Generated output is untrusted input until deterministic validation and
  human review complete.
- GitOps preview workspaces, promotion, and rollback remain 0.41–0.43. 0.48
  proposals may *request* those existing flows; they do not replace them.
- Brownfield dbt/orchestrator import is 0.49. Operator console is 0.50. Live
  cloud providers are 0.51.
- Write MCP tools, autonomous run submission, and applying optimizations
  without approval are out of 0.48.
- Live paid-model evaluation is not a release blocker (skip `048-E-01`).

## Optional packages (named before implementation)

Per [FORWARD_IMPLEMENTATION_PLANS](FORWARD_IMPLEMENTATION_PLANS.md) Shared
Entry Criteria §3, extras are named now. This package does not exist yet.

| Extra / PyPI name | Role | Target maturity |
|---|---|---|
| `etlantic-mcp` | Read-only MCP server for inspection, validation, planning, documentation, and report-query tools | **Experimental** |

Core extends existing `etlantic.agents` generators, context/proposal schemas,
and the validation sandbox. FastAPI inspection may add a read-only
bundle/proposal-preview resource under existing authz; privileged apply stays
on `/v1/approvals*`.

Core gains no MCP, Claude, OpenAI, Anthropic, or Cursor SDK. Production
discovery of `etlantic-mcp` fails closed on `Profile.plugin_allowlist`.

Live MCP-client interop is skip `048-M-01` if in-process method-authority
fixtures suffice.

## Supported vs Experimental target freeze

Claims only. Nothing below is Available until [EXIT_GATE_0_48](EXIT_GATE_0_48.md)
records Met evidence.

| Surface | Target | Notes |
|---|---|---|
| Vendor-neutral task / proposal / evidence schemas | **Supported** (core) | `etlantic.ai_task/1`, `etlantic.proposal/1` |
| Bounded redacted context bundles | **Supported** (core) | `etlantic.context_bundle/1` |
| Deterministic no-network/no-secret sandbox | **Supported** (core) | Wraps validate/plan/diff |
| Generators + user-region preservation | **Supported** (core) | Extends `generate_agent_guidance` |
| Codex / Claude / Cursor adapters from one catalog | **Supported** (core generators) | Capability diffs documented |
| Approval handoff to 0.42 `ApprovalStore` | **Supported** (reuse CP4) | No new mutation API |
| Prompt-injection / false-authority tests | **Supported** (core tests) | Untrusted contracts/logs/metadata |
| `etlantic-mcp` read-only extra | **Experimental** | Live client skip `048-M-01` |
| Live paid-model eval | **Out of 0.48** | Skip `048-E-01`; fixtures only |
| Write MCP / autonomous submit / silent optimize | **Out of 0.48** | Forbidden |
| GitOps promotion / 0.49–0.51 programs | **Out of 0.48** | Existing or later phases |

## Authority topology

```text
Agent / IDE ── read-only context bundle ──> existing inspect/plan/diff/impact
       │
       └── structured proposal ──> validation sandbox (no network, no secrets)
                                      │
                                      └── preview + required approvals
                                             │
                                             └── 0.42 ApprovalStore / /v1/approvals*
                                                    │
                                                    └── existing mutation paths only
```

Instruction files (`AGENTS.md`, `CLAUDE.md`, Codex skills, Cursor rules) are
guidance, not a security boundary. MCP, if present, is a projection of the
same read-only catalog.

## Frozen public names

Exact names freeze here. Do not implement them in this freeze.

### CLI

- `etlantic context bundle`
- `etlantic proposal validate`
- `etlantic generate --kind agents` (wraps existing `generate_agent_guidance`)

### HTTP

No new mutation routes. Workspace-scoped; same authz, idempotency, and
non-enumeration as CP1.

- Read-only bundle or proposal-preview resource under existing `/v1/*`
  (inspection only)
- Privileged apply remains `/v1/approvals`, `/v1/approvals/{approval_id}`,
  `/v1/approvals/{approval_id}/decide`, `/v1/approvals/{approval_id}/revoke`

### Wire ids (provisional `/1`)

- `etlantic.ai_task/1` — vendor-neutral task catalog entry
- `etlantic.context_bundle/1` — selected inputs, provenance, freshness,
  redaction, byte/graph/diagnostic budgets
- `etlantic.proposal/1` — generated files/plans, validation results, impact
  preview, required approval fingerprints

Reuse `etlantic.plan/1`, 0.44 impact/diff artifacts, and CP4 approval
records. Bundles and proposals store fingerprints and redacted excerpts —
never resolved secrets, source rows, event payloads, or data-subject values.

### Diagnostics (preview families until ship)

Do not overload `PMSVC*`, `PMFIRE*`, `PMFED*`, or `PMRES*`.

- `PMCTX*` — context budget, provenance, freshness, redaction, staleness
- `PMPROP*` — proposal schema, sandbox, validation, impact preview
- `PMGUIDE*` — generator determinism, user-region conflict
- `PMMCP*` — MCP method authority / tool-expansion deny

## Reuse invariants

- Extend `generate_agent_guidance`; do not add a second generator family.
  Today it overwrites (`overwrite=True`). 0.48 adds preserve-user-region
  markers and reports conflicts.
- Context and sandbox wrap `etlantic validate|plan|diff|inspect` and 0.44
  impact artifacts. Do not reimplement planning or diff.
- Approval handoff calls existing 0.42 `ApprovalStore` / policy gates. Do
  not add a parallel execute/submit/ack API for agents.
- 0.45 optimizer candidates are one proposal *kind* and stay advisory
  ([ADR-021](adr/ADR-021-OPTIMIZER-PASS-PROTOCOL.md)) until human approval.
- 0.46/0.47 surfaces are explain-only. Agents cannot route notifications,
  redrive dead letters, reveal payloads or subject values, approve or
  execute erasure, create/pause/trigger schedules, or submit runs.

## Fail-closed authority

- Instruction files never prove that an action is authorized.
- Untrusted contract text, comments, logs, diagnostics, artifacts, and
  reports cannot grant tools, reveal secrets, install plugins, or initiate
  runs.
- Context assembly fails closed on budget overflow, missing provenance, stale
  evidence, or redaction-policy violation.
- The sandbox has no network, no secret resolver, and no pipeline execution.
- A stale, expired, revoked, or fingerprint-mismatched approval cannot apply.
- Generated guidance cannot weaken sandbox, network, plugin, resolver, or
  secret-provider policies.

## Workstreams

| ID | Workstream | Deliverables | Completion evidence |
|---|---|---|---|
| 048-C | Context bundles | Bounded/redacted definitions, plans, diagnostics, lineage, impact, schema/reliability evidence with provenance and freshness | Budget, leakage, staleness, and hostile-content tests |
| 048-I | Instruction adapters | Vendor-neutral task catalog plus Codex/Claude/Cursor skills/rules and project instruction layers | Equivalent task/evidence matrix across supported adapters |
| 048-G | Safe generation | Project-local generators, preserve-user-region markers, idempotent patches, structured proposal schema | Re-run determinism and user-region preservation corpus |
| 048-V | Validation sandbox | No-network/no-secret deterministic validation, compile/plan/diff, capability and policy checks | Escape, timeout, resource-limit, and reproducibility tests |
| 048-H | Human governance | Explicit approval records for mutation, submission, secret access, installation, and external communication via existing 0.42 APIs | Deny/expire/stale/change-after-approval tests |
| 048-M | Read-only machine surface | Optional `etlantic-mcp` with scoped queries and bounded output | Method-by-method authority and non-enumeration suite; live skip `048-M-01` |
| 048-E | Evaluation/security | Fixture cross-agent task corpus, semantic correctness, prompt-injection defense, evidence quality, false-authority tests | Repeatable evaluation report and security review; live model eval skip `048-E-01` |

## Quantified scorecard

All **Current** cells are **Met** in-tree. Live skips remain `048-M-01` /
`048-E-01`.

| # | Measure | Required | Current |
|---|---|---:|---|
| 1 | 048-C bounded/redacted context bundles + provenance/freshness | Pass | **Met** |
| 2 | 048-I vendor-neutral catalog + Codex/Claude/Cursor adapters | Pass | **Met** |
| 3 | 048-G generators preserve user regions; no silent overwrite | Pass | **Met** |
| 4 | 048-V no-network/no-secret sandbox; deterministic re-run | Pass | **Met** |
| 5 | 048-H approval handoff to existing `/v1/approvals*` only | Pass | **Met** |
| 6 | 048-M `etlantic-mcp` method-authority deny (Experimental) | Pass | **Met** |
| 7 | 048-E fixture eval + injection/authority campaign | Pass | **Met** |
| 8 | Propose contract-compatible transform without execution/secrets | Pass | **Met** |
| 9 | Same structured evidence/approval boundary across adapters | Pass | **Met** |
| 10 | 0.46/0.47 explain-only; no schedule/DLQ/erasure/run mutation | Pass | **Met** |
| 11 | No vendor AI/MCP SDK in core | Pass | **Met** |
| 12 | Existing `ApprovalStore`, generate/validate/plan/diff unchanged as public contracts | Pass | **Met** |
| 13 | No unresolved P0 in [FINDINGS_0_48](FINDINGS_0_48.md) | 0 | **Met** |
| 14 | Claim freeze recorded on [EXIT_GATE_0_48](EXIT_GATE_0_48.md) | Pass | **Met** |

Live MCP-client interop (`048-M-01`) and live paid-model eval (`048-E-01`)
are **deferred Experimental skips**, not blockers.

## Delivery sequence

Implementation (later — not this freeze):

1. Freeze the vendor-neutral task, context, proposal, evidence, and approval
   schemas (this document + ADR-024).
2. Implement bounded context assembly and the deterministic validation
   sandbox on existing CLI artifacts.
3. Add project-local generators and preserve-user-region semantics.
4. Add vendor-specific instruction adapters from one catalog; optional
   Experimental MCP extra.
5. Add approval handoff to existing policy/API paths; do not duplicate
   mutation endpoints.
6. Run fixture evaluations and prompt-injection/authority campaigns. Live
   model eval remains skip `048-E-01`.

## Exit Gates

- A supported agent can propose a contract-compatible transform without
  running user code, accessing secrets, or executing the pipeline.
- Supported adapters produce the same structured evidence and approval
  boundary for equivalent tasks, with documented capability differences.
- Context bundles are bounded, redacted, provenance-linked, freshness-
  labeled, and resistant to instructions embedded in untrusted
  project/source text.
- Re-running a generator is deterministic and preserves user-owned regions;
  all changes are ordinary reviewable files with semantic and impact
  previews.
- Read-only machine interfaces cannot mutate, submit, install, resolve
  secrets, communicate externally, or grant additional tools.
- No schema baseline, contract, reliability threshold, run, schedule,
  provider, or external effect changes without a current explicit human
  approval enforced by the existing API and policy layer.
- Agents may explain delivery-objective breaches, dynamic-control evidence,
  dead-letter/schema-registry outcomes, erasure plans, and schedules, but
  cannot route a notification, redrive a dead letter, reveal a payload or
  subject value, approve/execute erasure, create/pause/trigger a schedule,
  or submit a run.
- Security review has no unresolved critical/high prompt-injection, data
  leakage, sandbox escape, or authority-escalation finding.

## Required Release Evidence

Planning freeze (now):

- This implementation plan
- [ADR-024](adr/ADR-024-HUMAN-GOVERNED-AI.md)
- [EXIT_GATE_0_48](EXIT_GATE_0_48.md)
- [FINDINGS_0_48](FINDINGS_0_48.md)

At ship (not written in this freeze):

- Cross-agent task/evidence evaluation (fixtures; live skip `048-E-01`)
- Context budget, provenance, freshness, and redaction report
- Generator determinism/user-region preservation corpus
- Sandbox and prompt-injection adversarial report
- Method/action authority matrix and human-approval audit trace
- Optional `etlantic-mcp` method-authority suite; live skip `048-M-01`
- Future `WHATS_NEW_0_48` / `MIGRATION_0_47_TO_0_48` (do not publish as
  Available until the exit gate is Met)

## 0.49 / 0.50 / 0.51 boundary

[IMPLEMENTATION_PLAN_0_49](IMPLEMENTATION_PLAN_0_49.md) owns brownfield
metadata import and orchestration compilers.
[IMPLEMENTATION_PLAN_0_50](IMPLEMENTATION_PLAN_0_50.md) owns the operator
console. [IMPLEMENTATION_PLAN_0_51](IMPLEMENTATION_PLAN_0_51.md) owns live
cloud provider packs. 0.48 ships governed proposals over existing
inspection and approval APIs. Do not pull those programs into this gate.
