# Exit Gate 0.45 — Planner and Optimization SDK

> **Status: Released — ETLantic 0.45.0.** Advisory optimization-pass protocol,
> evidence/cost selection, reference rewrites, explanation and shadow compare,
> and optimizer conformance.

| Deliverable | Status |
|---|---|
| Planning: this exit gate / findings / What's New / migration / ADR-021 | **Complete** |
| Pass protocol (045-P) | **Complete** |
| Statistics / evidence (045-S) | **Complete** |
| Cost and selection (045-C) | **Complete** |
| Reference rewrites (045-R) | **Complete** |
| Explanation surfaces (045-E) | **Complete** |
| Shadow validation (045-H) | **Complete** |
| SDK lifecycle / conformance (045-O) | **Complete** |
| Lockstep version 0.45.0 | **Complete** |

## Supported claim (frozen)

| Surface | GA status | Notes |
|---|---|---|
| `etlantic.optimization/1` pass protocol | **Supported** | Advisory until accept |
| EvidenceStore + cost providers | **Supported** | No universal cost currency |
| Reference rewrite passes | **Supported** | Reject without proof |
| CLI/API/IDE explanation parity | **Supported** | Same immutable artifacts |
| Shadow plan comparison | **Supported** | Plan-only default |
| Bounded trial runs | **Experimental** | Host authority only |
| Third-party pass entry points | **Supported** | Allowlisted in production |

## Quantified exit scorecard

From [IMPLEMENTATION_PLAN_0_45](IMPLEMENTATION_PLAN_0_45.md):

| # | Measure | Required | Current |
|---|---|---:|---|
| 1 | Candidate records inputs, evidence, benefit, proof, policy, capability, reason | Pass | **Met** — protocol + engine |
| 2 | Deterministic re-run on same plan + evidence | Pass | **Met** — `test_optimize_deterministic_and_off_policy` |
| 3 | Missing/stale/conflicting stats → safe choice + diagnostic | Pass | **Met** — evidence + selection tests |
| 4 | No boundary cross without proof | Pass | **Met** — proof/capability rejection + cross-domain reject |
| 5 | Reference + third-party conformance | Pass | **Met** — [optimizer_conformance_0_45.json](optimizer_conformance_0_45.json) |
| 6 | CLI/API/IDE share explanation schema | Pass | **Met** — `explain_optimization` + CLI/IDE |
| 7 | No unresolved critical/high finding in phase scope | 0 | **Met** — [FINDINGS_0_45](FINDINGS_0_45.md) P0=0 |
| 8 | Release record: supported vs experimental | Pass | **Met** — this document |

## Evidence map

| Gate item | Evidence |
|---|---|
| Implementation plan | [IMPLEMENTATION_PLAN_0_45](IMPLEMENTATION_PLAN_0_45.md) |
| ADR | [ADR-021](adr/ADR-021-OPTIMIZER-PASS-PROTOCOL.md) |
| Conformance | [optimizer_conformance_0_45.json](optimizer_conformance_0_45.json) |
| Findings | [FINDINGS_0_45](FINDINGS_0_45.md) |
| Migration | [MIGRATION_0_44_TO_0_45](MIGRATION_0_44_TO_0_45.md) |
| What's New | [WHATS_NEW_0_45](../01_GETTING_STARTED/WHATS_NEW_0_45.md) |
| Author guide | [OPTIMIZATION_PASSES](../07_PLUGIN_SDK/OPTIMIZATION_PASSES.md) |
| External example | `examples/optimization_pass_echo/` |

## Go / no-go

**Released** as `0.45.0`. All scorecard rows are **Met** under the evidence
language above.

## Explicit non-claims

- No universal cost model or cross-provider cost currency
- Passes cannot access data, secrets, or mutate registries/baselines
- Optimization is not applied by default on `plan` / `run`
- Streaming / dynamic control remains 0.46
- AI-proposed optimizations remain 0.48
