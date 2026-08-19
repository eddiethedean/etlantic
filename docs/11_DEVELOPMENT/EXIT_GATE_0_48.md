# Exit Gate 0.48 — AI-Assisted, Human-Governed Engineering

> **Status: Met — gate-ready for tag/publish (no tag in this commit).** ETLantic
> **0.48.0** closes the human-governed AI freeze with Supported
> context/proposal/sandbox/generators/approval handoff and Experimental
> `etlantic-mcp` fakes. Live MCP-client (`048-M-01`) and live paid-model eval
> (`048-E-01`) remain skipped. See
> [IMPLEMENTATION_PLAN_0_48](IMPLEMENTATION_PLAN_0_48.md) and
> [ADR-024](adr/ADR-024-HUMAN-GOVERNED-AI.md) (Accepted).

| Deliverable | Status |
|---|---|
| Planning: this exit gate / findings / ADR-024 | **Met** (Accepted ADR-024) |
| What's New / migration (ship artifacts) | **Met** |
| Context bundles (048-C) | **Met** |
| Instruction adapters (048-I) | **Met** |
| Safe generation (048-G) | **Met** |
| Validation sandbox (048-V) | **Met** |
| Human governance (048-H) | **Met** |
| Read-only MCP (048-M) | **Met** (Experimental; live skip `048-M-01`) |
| Evaluation/security (048-E) | **Met** (live skip `048-E-01`) |
| Lockstep version 0.48.0 | **Met** (in-tree; no git tag) |

## Supported claim (target freeze)

From [IMPLEMENTATION_PLAN_0_48](IMPLEMENTATION_PLAN_0_48.md).

| Surface | Target | Notes |
|---|---|---|
| Vendor-neutral task / proposal / evidence schemas | **Supported** (core) | `etlantic.ai_task/1`, `etlantic.proposal/1` |
| Bounded redacted context bundles | **Supported** (core) | Provenance + freshness |
| Deterministic no-network/no-secret sandbox | **Supported** (core) | Wraps validate/plan/diff |
| Generators + user-region preservation | **Supported** (core) | Extends `generate_agent_guidance` |
| Codex / Claude / Cursor adapters from one catalog | **Supported** (core generators) | Capability diffs documented |
| Approval handoff to 0.42 `ApprovalStore` | **Supported** (reuse CP4) | No new mutation API |
| Prompt-injection / false-authority tests | **Supported** (core tests) | Untrusted contracts/logs |
| `etlantic-mcp` read-only extra | **Experimental** | Live client skip `048-M-01` |
| Live paid-model eval | **Out of 0.48** | Skip `048-E-01` |
| Write MCP / autonomous submit / silent optimize | **Out of 0.48** | Forbidden |
| GitOps promotion / 0.49–0.51 programs | **Out of 0.48** | Existing or later phases |

## Quantified exit scorecard

From [IMPLEMENTATION_PLAN_0_48](IMPLEMENTATION_PLAN_0_48.md):

| # | Measure | Required | Current |
|---|---|---:|---|
| 1 | 048-C bounded/redacted context bundles + provenance/freshness | Pass | **Met** |
| 2 | 048-I vendor-neutral catalog + Codex/Claude/Cursor adapters | Pass | **Met** |
| 3 | 048-G generators preserve user regions; no silent overwrite | Pass | **Met** |
| 4 | 048-V no-network/no-secret sandbox; deterministic re-run | Pass | **Met** |
| 5 | 048-H approval handoff to existing `/v1/approvals*` only | Pass | **Met** |
| 6 | 048-M `etlantic-mcp` method-authority deny (Experimental) | Pass | **Met** (live skip) |
| 7 | 048-E fixture eval + injection/authority campaign | Pass | **Met** (live skip) |
| 8 | Propose contract-compatible transform without execution/secrets | Pass | **Met** |
| 9 | Same structured evidence/approval boundary across adapters | Pass | **Met** |
| 10 | 0.46/0.47 explain-only; no schedule/DLQ/erasure/run mutation | Pass | **Met** |
| 11 | No vendor AI/MCP SDK in core | Pass | **Met** |
| 12 | Existing `ApprovalStore`, generate/validate/plan/diff unchanged as public contracts | Pass | **Met** |
| 13 | No unresolved P0 in [FINDINGS_0_48](FINDINGS_0_48.md) | 0 | **Met** |
| 14 | Release record: supported vs experimental | Pass | **Met** |

Live MCP-client (`048-M-01`) and live paid-model eval (`048-E-01`) are
**deferred Experimental skips**, not blockers.

## Evidence map

| Gate item | Evidence |
|---|---|
| Implementation plan | [IMPLEMENTATION_PLAN_0_48](IMPLEMENTATION_PLAN_0_48.md) |
| ADR | [ADR-024](adr/ADR-024-HUMAN-GOVERNED-AI.md) (Accepted) |
| Findings | [FINDINGS_0_48](FINDINGS_0_48.md) |
| Conformance JSON | [context](context_conformance_0_48.json), [proposal](proposal_conformance_0_48.json), [mcp](mcp_conformance_0_48.json) |
| Migration | [MIGRATION_0_47_TO_0_48](MIGRATION_0_47_TO_0_48.md) |
| What's New | [WHATS_NEW_0_48](../01_GETTING_STARTED/WHATS_NEW_0_48.md) |
| Roadmap | [ROADMAP § 0.48](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md) |
