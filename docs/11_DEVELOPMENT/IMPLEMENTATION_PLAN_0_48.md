---
title: ETLantic 0.48 Implementation Plan
description: Implementation-grade plan for human-governed AI and agent workflows.
plan_status: current
plan_last_reviewed: 0.37.0
---

# ETLantic 0.48 Implementation Plan

Phase 0.48 exposes bounded, read-only ETLantic intelligence to AI-assisted
workflows and turns proposed changes into deterministic, reviewable artifacts.
No model or agent receives implicit authority to mutate contracts, baselines,
state, runs, secrets, providers, or external systems.

## Outcome

Codex, Claude, Cursor, and other adapters can inspect redacted context, propose
pipeline/schema/reliability changes, validate them in a deterministic sandbox,
show semantic and downstream impact, and hand a human an explicit approval step
before any privileged action.

## Prerequisites And Non-Goals

- 0.44 diagnostics/change previews and 0.42 policy/approval/audit contracts are
  the required foundations.
- AI SDKs live in adapter packages and never become core dependencies.
- Read-only MCP or similar interfaces cannot mutate, submit, install, resolve
  secrets, contact external parties, or expand their own tool authority.
- Generated output is untrusted input until deterministic validation and human
  review complete.

## Workstreams

| ID | Workstream | Deliverables | Completion evidence |
|---|---|---|---|
| 048-C | Context bundles | Bounded/redacted definitions, plans, diagnostics, lineage, impact, schema/reliability evidence with provenance and freshness | Budget, leakage, staleness, and hostile-content tests |
| 048-I | Instruction adapters | Vendor-neutral task catalog plus Codex/Claude/Cursor skills/rules and project instruction layers | Equivalent task/evidence matrix across supported adapters |
| 048-G | Safe generation | Project-local generators, preserve-user-region markers, idempotent patches, structured proposal schema | Re-run determinism and user-region preservation corpus |
| 048-V | Validation sandbox | No-network/no-secret deterministic validation, compile/plan/diff, capability and policy checks | Escape, timeout, resource-limit, and reproducibility tests |
| 048-H | Human governance | Explicit approval records for mutation, submission, secret access, installation, and external communication | Deny/expire/stale/change-after-approval tests |
| 048-M | Read-only machine surface | Optional read-only MCP/resource adapters with scoped queries and bounded output | Method-by-method authority and non-enumeration suite |
| 048-E | Evaluation/security | Cross-agent task corpus, semantic correctness, prompt-injection defense, evidence quality, false-authority tests | Repeatable evaluation report and security review |

## Delivery Sequence

1. Freeze the vendor-neutral task, context, proposal, evidence, and approval
   schemas.
2. Implement bounded context assembly and the deterministic validation sandbox.
3. Add project-local generators and preserve-user-region semantics.
4. Add read-only machine interfaces and vendor-specific instruction adapters.
5. Add approval handoff to existing policy/API paths; do not duplicate mutation
   endpoints.
6. Run cross-agent evaluations and prompt-injection/authority campaigns.

## Exit Gates

- A supported agent can propose a contract-compatible transform without running
  user code, accessing secrets, or executing the pipeline.
- Supported adapters produce the same structured evidence and approval boundary
  for equivalent tasks, with documented capability differences.
- Context bundles are bounded, redacted, provenance-linked, freshness-labeled,
  and resistant to instructions embedded in untrusted project/source text.
- Re-running a generator is deterministic and preserves user-owned regions; all
  changes are ordinary reviewable files with semantic and impact previews.
- Read-only machine interfaces cannot mutate, submit, install, resolve secrets,
  communicate externally, or grant additional tools.
- No schema baseline, contract, reliability threshold, run, provider, or external
  effect changes without a current explicit human approval enforced by the
  existing API and policy layer.
- Agents may explain delivery-objective breaches, dynamic-control evidence,
  dead-letter/schema-registry outcomes, and erasure plans, but cannot route a
  notification, redrive a dead letter, reveal a payload or subject value,
  approve/execute erasure, or weaken a hold/retention rule.
- Security review has no unresolved critical/high prompt-injection, data leakage,
  sandbox escape, or authority-escalation finding.

## Required Release Evidence

- Cross-agent task/evidence evaluation.
- Context budget, provenance, freshness, and redaction report.
- Generator determinism/user-region preservation corpus.
- Sandbox and prompt-injection adversarial report.
- Method/action authority matrix and human-approval audit trace.
