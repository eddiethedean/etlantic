# ADR-024: Human-Governed AI Workflows

Date: 2026-08-18
Status: Accepted (ETLantic **0.48.0**)

## Context

ETLantic 0.48.0 closed the scheduler/runner service and remote-federation
gate. ROADMAP § 0.48 and
[IMPLEMENTATION_PLAN_0_48](../IMPLEMENTATION_PLAN_0_48.md) require bounded,
read-only AI assistance whose proposals become ordinary reviewable artifacts
and take effect only through existing human-approval APIs.

Today, `etlantic.agents.generate_agent_guidance` writes `AGENTS.md`,
`CLAUDE.md`, Codex `SKILL.md`, and Cursor rules with overwrite-by-default
semantics. `etlantic validate|plan|diff|inspect` and 0.44 impact artifacts
already exist. CP4 `ApprovalStore` and `/v1/approvals*` already enforce
separation of duties. 0.45 optimization stays advisory
([ADR-021](ADR-021-OPTIMIZER-PASS-PROTOCOL.md)).
[SECURITY.md](../../02_FOUNDATIONS/SECURITY.md) already states that
instruction files are guidance, not a security boundary.

Without a freeze, implementations will put vendor AI SDKs in core, give MCP
tools mutate/submit/secret authority, silently overwrite user instruction
regions, duplicate GitOps promotion (0.40–0.43), or treat agent output as
authorized mutation.

Authoritative sequencing:
[IMPLEMENTATION_PLAN_0_48](../IMPLEMENTATION_PLAN_0_48.md), ROADMAP § 0.48,
[ADR-019](ADR-019-POLICY-QUOTAS-AND-AUDIT.md),
[ADR-020](ADR-020-DEVELOPER-INTELLIGENCE.md),
[ADR-021](ADR-021-OPTIMIZER-PASS-PROTOCOL.md), and
[SECURITY.md — AI Coding Assistants](../../02_FOUNDATIONS/SECURITY.md).
Brownfield import remains [0.49](../IMPLEMENTATION_PLAN_0_49.md). Operator
console remains [0.50](../IMPLEMENTATION_PLAN_0_50.md). Live providers remain
[0.51](../IMPLEMENTATION_PLAN_0_51.md).

## Decision

### Proposals are untrusted until validation and human approval

Agent, skill, rule, and MCP output is untrusted input. It becomes an
ordinary file or plan proposal, runs through the deterministic sandbox, and
applies only when a **current** 0.42 approval covers the proposal and policy
fingerprints. Instruction files never prove that an action is authorized.

### Read-only default

Agent-facing APIs and MCP tools default to inspection, validation, planning,
explanation, and report queries. They cannot mutate files, submit runs,
install plugins, resolve secrets, contact undeclared external systems, or
grant additional tools.

0.46/0.47 surfaces are **explain-only**. Agents may describe delivery
objectives, dead letters, erasure plans, schedules, and federation evidence.
They cannot route notifications, redrive dead letters, reveal payloads or
subject values, approve/execute erasure, create/pause/trigger schedules, or
submit runs.

### Reuse existing mutation and promotion paths

0.48 does not add a second execute/submit/ack API and does not reopen GitOps
preview, promotion, or rollback. Approval handoff calls existing
`ApprovalStore` / policy gates. 0.45 optimizer candidates are one proposal
kind and remain advisory until human approval.

Context assembly and the sandbox wrap `etlantic validate|plan|diff|inspect`
and 0.44 impact artifacts. Generators extend
`generate_agent_guidance` with preserve-user-region markers; they do not
become a second generator family.

### Core vs optional MCP vs vendor adapters

Core owns the vendor-neutral task catalog, context-bundle and proposal
schemas, validation sandbox, generator-region semantics, and diagnostics.

`etlantic-mcp` is an optional **Experimental** extra. Live MCP-client
interop is skip `048-M-01` if in-process method-authority fixtures suffice.

Codex, Claude Code, and Cursor adapters are generated project files from the
same catalog. Core installs no Claude, OpenAI, Anthropic, Cursor, or MCP
SDK. Live paid-model evaluation is skip `048-E-01`.

### Diagnostic families (preview until ship)

Do not overload `PMSVC*`, `PMFIRE*`, `PMFED*`, or `PMRES*`.

- `PMCTX*` — context budget, provenance, freshness, redaction, staleness
- `PMPROP*` — proposal schema, sandbox, validation, impact preview
- `PMGUIDE*` — generator determinism, user-region conflict
- `PMMCP*` — MCP method authority / tool-expansion deny

### Production trust

- Production `plugin_allowlist` covers `etlantic-mcp` when selected.
- Bundles, proposals, guidance, plans, reports, audit, and fixtures never
  contain resolved secrets, source rows, event payloads, or data-subject
  values (FORWARD invariant).
- A stale, expired, revoked, or fingerprint-mismatched approval cannot apply.
- Generated guidance cannot weaken sandbox, network, plugin, resolver, or
  secret-provider policies.

## Consequences

- Adopters can keep existing CLI, LSP, optimizer, scheduler, and approval
  surfaces without adopting MCP or any vendor agent.
- Agent-generated edits remain ordinary reviewable files.
- Experimental MCP can ship method-authority fixtures without a live-client
  CI requirement.
- Untrusted project text that attempts to jailbreak tools fails closed.

## Alternatives

| Alternative | Why rejected |
|---|---|
| Vendor AI SDK in core | Violates optional-package boundary; core stays engine- and vendor-free |
| Write/mutate MCP tools in 0.48 | Instruction files are not a security boundary; mutate stays on 0.42 APIs |
| New agent-only approval API | Duplicates CP4 `ApprovalStore` / `/v1/approvals*` |
| Reopen GitOps promotion in 0.48 | Promotion already shipped in 0.40–0.43 |
| Silent overwrite of `AGENTS.md` / rules | Loses user-owned regions; contradicts SECURITY.md |
| Make live paid-model eval a 0.48 blocker | Non-deterministic, credentialed, and not required for the gate |
| Apply 0.45 optimizations without approval | ADR-021 stays advisory |

## Compatibility

- Additive CLI commands and optional read-only HTTP inspection. Existing
  `/v1/approvals*` and `etlantic generate` stay `/1`.
- Official plugins remain on the 0.48 floor
  (`etlantic>=0.48.0,<0.49`).

## See also

- [IMPLEMENTATION_PLAN_0_48](../IMPLEMENTATION_PLAN_0_48.md)
- [EXIT_GATE_0_48](../EXIT_GATE_0_48.md)
- [FINDINGS_0_48](../FINDINGS_0_48.md)
- [ADR-019](ADR-019-POLICY-QUOTAS-AND-AUDIT.md)
- [ADR-020](ADR-020-DEVELOPER-INTELLIGENCE.md)
- [ADR-021](ADR-021-OPTIMIZER-PASS-PROTOCOL.md)
- [ADR-023](ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md)
