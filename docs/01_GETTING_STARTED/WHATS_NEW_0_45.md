# What's New in ETLantic 0.45

> **Status: Available in ETLantic 0.45.0 (published Beta).** Planner and
> optimization SDK: advisory passes, evidence/cost selection, explanation and
> shadow compare, and optimizer conformance.

## Highlights

- **Optimization-pass protocol** — versioned `etlantic.optimization/1` candidates,
  proofs, and diagnostics ([ADR-021](../11_DEVELOPMENT/adr/ADR-021-OPTIMIZER-PASS-PROTOCOL.md))
- **Evidence and cost** — plan-time `EvidenceStore`; rule-based and statistical
  `CostProvider`s (no universal cost currency)
- **Reference rewrites** — pushdown, pruning, fusion, materialization, reuse,
  repair/backfill selection, implementation selection, cross-backend handoffs
- **Advisory by default** — `plan` / `run` keep the baseline; apply via
  `optimization_policy=apply_accepted` or `etlantic plan optimize`
- **Explanation parity** — same explanation schema on CLI, API (`etl.optimization`),
  and IDE `optimize` command
- **Shadow comparison** — baseline vs candidate plan diff with regression
  thresholds
- **Conformance** — `etlantic.testing.run_optimizer_conformance_suite`
- **Production trust** — `Profile.optimization_pass_allowlist` fail-closed

## Adopter actions

| Who | Action |
|---|---|
| Everyone on **0.45.x** | Upgrade to `etlantic==0.45.0` with matching plugins; see [migration](../11_DEVELOPMENT/MIGRATION_0_44_TO_0_45.md) |
| Pass authors | Follow [Optimization Passes](../07_PLUGIN_SDK/OPTIMIZATION_PASSES.md) |
| Operators | Allowlist passes in production; keep `optimization_policy` at `off` or `shadow` until ready |

## Not in 0.45

- Streaming / dynamic control (0.46)
- Remote federation (0.47)
- AI-proposed optimizations (0.48)
- Universal cross-provider cost currency
- Default apply on every `plan` / `run`

## Related

- [Migration 0.44 → 0.45](../11_DEVELOPMENT/MIGRATION_0_44_TO_0_45.md)
- [Exit gate 0.45](../11_DEVELOPMENT/EXIT_GATE_0_45.md)
- [Capabilities](CAPABILITIES.md)
