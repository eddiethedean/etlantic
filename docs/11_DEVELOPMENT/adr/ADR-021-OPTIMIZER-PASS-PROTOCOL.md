# ADR-021: Optimizer Pass Protocol and Advisory Selection

Date: 2026-08-05  
Status: Accepted (ships with ETLantic **0.46.0**)

## Context

ETLantic already produces an immutable, fingerprinted `PipelinePlan`
(`etlantic.plan/1`) with implementation selection, execution regions, and
materialization boundaries. Phase 0.45 must open a stable optimization-pass
SDK so built-in and third-party passes can propose deterministic physical
plan changes without gaining runtime authority or silently changing
policy-visible behavior.

Authoritative sequencing:
[IMPLEMENTATION_PLAN_0_45](../IMPLEMENTATION_PLAN_0_45.md) and ROADMAP § 0.45.
See [DPCS](../../05_PIPELINES/DPCS.md) §7 Optimization.

## Decision

### Wire schema and package ownership

Core owns versioned artifacts under `etlantic.optimization`
(`etlantic.optimization/1`):

- pass metadata, prerequisites, candidates, proof obligations
- evidence / statistics records (cardinality, partitioning, ordering,
  locality, reuse, freshness, confidence, provenance, expiry)
- cost scores from pluggable providers (no universal cost currency)
- `OptimizationExplanation` and `OptimizationResult`
- shadow comparison records

Language: `import etlantic as etl` exposes the lazy namespace
`etl.optimization`. Specialist symbols are not promoted to the curated root.

### Advisory until accept

Optimization is **advisory**. Default `plan` / `run` / `compile` emit the
**baseline** plan. An optimized candidate is applied only when:

1. every selected rewrite records evidence, expected benefit, and semantic
   proof obligations;
2. policy and capability gates accept the candidate;
3. the host opts in via `Profile.optimization_policy` /
   `--apply-optimizations`.

`optimization_policy` values: `off` | `shadow` | `apply_accepted`.

### Non-authority for passes

An optimization pass MUST NOT:

- execute data access or resolve secrets
- mutate registry, durable state, schema history, or reliability baselines
- widen authz, tenant, residency, masking, or security-domain boundaries

Passes read an `EvidenceStore` and baseline `PipelinePlan` only. Bounded
trial runs (if any) are host/runtime authority under profile policy.

### Trust and allowlisting

Production profiles fail closed on undeclared passes via
`Profile.optimization_pass_allowlist` (name → optional version pin),
mirroring `plugin_allowlist`. Discovery uses the entry-point group
`etlantic.optimization_passes`.

### Determinism

Re-running the same ordered pass set on the same plan fingerprint and
evidence fingerprint MUST produce the same optimization result fingerprint.
Missing, stale, or conflicting evidence degrades to a safe choice and a
stable `PMOPT*` diagnostic—never an unjustified rewrite.

### Cost providers

Rule-based and statistical `CostProvider`s are Supported. Scores are
comparable within a provider identity, not across providers. Multi-objective
selection and budgets are host-configured.

### Relation to the planner

The existing planner remains the logical→physical construction authority.
Optimization proposes candidates; accepted rewrites prefer re-plan-with-hints
or metadata annotations on a derived plan rather than mutating a frozen
baseline graph in place. `diff_plans` compares baseline and optimized plans.

## Consequences

- CLI gains `etlantic plan optimize` and optimization-aware explain/diff.
- IDE plan previews reuse the same explanation schema (no new execution path).
- Third-party passes qualify through
  `etlantic.testing.run_optimizer_conformance_suite`.
- Engine-local Spark Catalyst guidance remains separate; it may later wrap as
  a conforming pass but is not required for 0.45.

## See also

- [IMPLEMENTATION_PLAN_0_45](../IMPLEMENTATION_PLAN_0_45.md)
- [EXIT_GATE_0_45](../EXIT_GATE_0_45.md)
- [OPTIMIZATION_PASSES](../../07_PLUGIN_SDK/OPTIMIZATION_PASSES.md)
