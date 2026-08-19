# Findings Ledger 0.48 — Human-Governed AI Workflows

> **Status: Closed for 0.48.0 (in-tree; no tag).** Open **P0 count is 0**.
> Live MCP-client interop (`048-M-01`) and live paid-model eval (`048-E-01`)
> remain deferred Experimental skips.

## Severity policy

From [IMPLEMENTATION_PLAN_0_48](IMPLEMENTATION_PLAN_0_48.md) and
[ADR-024](adr/ADR-024-HUMAN-GOVERNED-AI.md):

| Severity | Meaning | Release treatment |
|---|---|---|
| **P0** | Implicit agent authority; secret/row/payload/subject leakage in a bundle, proposal, guidance file, or fixture; sandbox escape (network, secrets, execution); duplicate mutation path beside `/v1/approvals*`; untrusted text grants tools | Must close before 0.48 |
| **P1** | Material generator-region, MCP method-authority, or adapter-skew risk | Close or defer with owner |
| **P2** | Localized usability / maintainability | May defer with owner |
| **P3** | Cosmetic | Backlog |

## Locked dispositions

| Decision | Outcome | Notes |
|---|---|---|
| Authority | Proposals untrusted until sandbox + current 0.42 approval | ADR-024; instruction files are not a security boundary |
| Mutation path | Reuse `ApprovalStore` / `/v1/approvals*` | No agent-only execute/submit/ack API |
| Promotion | Out of 0.48 | 0.40–0.43 GitOps promotion remains those APIs |
| Generators | Extend `generate_agent_guidance` | Preserve user regions; no silent overwrite |
| Optimizer | Advisory proposal kind | ADR-021 until human approval |
| 0.46/0.47 | Explain-only | No schedule, DLQ, erasure, or run mutation |
| MCP | Optional Experimental `etlantic-mcp` | Read-only; live client skip `048-M-01` |
| Vendor SDKs | Not in core | Codex/Claude/Cursor are generated files |
| Live model eval | Skip `048-E-01` | Fixture corpus is the gate |
| Payloads / secrets | Fingerprints and redacted excerpts only | FORWARD invariant |

## Open findings

Open **P0 count is 0**.

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| — | — | — | closed | No open P0 | Fixture corpus + method-authority tests |

## Deferred Experimental skips

| ID | Summary |
|---|---|
| `048-M-01` | Live MCP-client interop |
| `048-E-01` | Live paid-model evaluation |
