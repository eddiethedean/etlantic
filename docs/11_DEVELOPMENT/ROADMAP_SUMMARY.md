# Roadmap Summary

ETLantic 0.17.0 is production/stable for documented single-tenant reference
deployments. Milestones describe capability order, not release-date
commitments, and do not expand that bounded support envelope.

## Shipped: 0.15, 0.16, and 0.17

ETLantic **0.15.0** closed Safe SQL Lowering and the LocalScheduler companion.

ETLantic **0.16.0** shipped Gate A (authoring vocabulary cleanup) and Gate B
(optional `etlantic-prefect` `ExecutionScheduler`).

ETLantic **0.17.0** shipped portable coverage expansion:

- Gate A — transform-compiler CLI inventory, exact capability matrix, drift
  checks, allowlist-safe discovery
- Gate B — Wave 1 on Polars + PySpark (`portable-window/1`,
  `portable-string-advanced/1`, `portable-conversion/1`,
  `portable-statistics/1`)
- Gate C — Wave 2 on Polars + PySpark (`portable-complex-types/1`,
  `portable-complex-values/1`, `portable-reshape/1`)

Pandas and SQL remain kernel + `portable-relational/1` in 0.17. See
[What's New in 0.17](../01_GETTING_STARTED/WHATS_NEW_0_17.md) and
[Migration 0.16 → 0.17](MIGRATION_0_16_TO_0_17.md).

**0.17 continuation** (not required to close 0.17):
`portable-relational-extended/1`, `portable-temporal-iana/1`,
`portable-nondeterministic/1`, `portable-window/2`.

## Planned: 0.18+ standards-based interoperability

0.18+ formalizes Arrow as the preferred, versioned physical interchange at
compatible cross-plugin boundaries while retaining ETLantic contracts and
plans as the semantic authority.

- Gate A: capability-driven Arrow stream/artifact decisions, fidelity,
  ownership, fallback, and evidence conformance
- Gate B: experimental `etlantic-datafusion` runtime + portable kernel
  compiler, graduating only with conformance and a measured advantage

PyArrow and DataFusion stay out of the core dependency set. See the
[Arrow and DataFusion Integration Plan](INTEROPERABILITY_FOUNDATION_PLAN.md).

## Prior: 0.14

ETLantic 0.14.0 completed the first three-engine portable relational baseline
and published the public portable conformance SDK. See
[What's New in 0.14](../01_GETTING_STARTED/WHATS_NEW_0_14.md).

## Toward 1.0

The 1.0 goal is a stable foundation with:

- stable authoring, Plugin SDK, plan, event, result, and run-report contracts;
- documented compatibility, deprecation, and schema-migration policies;
- completed security gates for plugin provenance, secret handling, artifact and
  cache isolation, network constraints, audit evidence, and bounded work;
- conformance and acceptance coverage across reference engines and
  orchestrators;
- complete executable tutorials, references, and migration guides.

> **Production use is supported only within the documented 0.17 reference
> envelope.** Multi-tenant isolation, deployment topology, compliance/SBOM/
> signing, and advanced supply-chain controls remain adopter-owned. Available
> allowlists and version pins do not make arbitrary topologies safe. See the
> [Evaluator Brief](../01_GETTING_STARTED/EVALUATOR.md).

Read the
[full roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md)
for milestone details, acceptance scenarios, and release gates.
