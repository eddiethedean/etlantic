# API — Agents

> **Status: Available in ETLantic 0.48.0.** Human-governed context bundles,
> proposal sandbox, and instruction generators. Hub:
> [Python API Reference](API_REFERENCE.md). Tutorial:
> [Human-governed AI](../01_GETTING_STARTED/HUMAN_GOVERNED_AI.md).

```python
from etlantic.agents import ALLOWED_PROPOSAL_ACTIONS, FORBIDDEN_ACTIONS

assert "inspect" in ALLOWED_PROPOSAL_ACTIONS
assert "run.submit" in FORBIDDEN_ACTIONS
```

Proposals never apply files. `applied` is always false. Apply remains the
0.42 `ApprovalStore` / `/v1/approvals*` path. Failures use `PMCTX*`,
`PMPROP*`, `PMGUIDE*`, and `PMMCP*` — see
[Diagnostics](DIAGNOSTICS.md) and [Exceptions](EXCEPTIONS.md).

| Symbol | Behavior |
|---|---|
| `assemble_context_bundle` | Redacted inspect/validate/plan evidence; no network, no secrets |
| `validate_proposal` | Deterministic sandbox; allowlisted verbs only |
| `generate_agent_guidance` | Writes AGENTS.md / Claude / Codex / Cursor files; preserves user regions |
| `Proposal` / `ProposalValidation` | Wire `etlantic.proposal/1`; `applied` is always false |
| `ALLOWED_PROPOSAL_ACTIONS` | `inspect`, `validate`, `plan`, `diff`, `impact`, `context_bundle` |
| `FORBIDDEN_ACTIONS` | `run.submit`, schedule/erasure/secret/network/tool grants, … |

::: etlantic.agents
    options:
      show_root_heading: true
      members_order: source
      filters: ["!^_"]
