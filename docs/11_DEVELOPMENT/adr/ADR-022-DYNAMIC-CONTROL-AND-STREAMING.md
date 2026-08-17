# ADR-022: Dynamic Control and Streaming Ownership

Date: 2026-08-17
Status: Proposed (design freeze for ETLantic **0.46**; Accepted only at ship)

## Context

ETLantic 0.45.0 shipped an advisory optimization SDK. ROADMAP § 0.46 and
[IMPLEMENTATION_PLAN_0_46](../IMPLEMENTATION_PLAN_0_46.md) require bounded
runtime mapping/reduction, explicit branches, stream-time semantics, change
envelopes, record-error policy, and optional Kafka / schema-registry
providers—without a second control plane or payload-bearing artifacts.

Authoritative sequencing:
[IMPLEMENTATION_PLAN_0_46](../IMPLEMENTATION_PLAN_0_46.md), ROADMAP § 0.46, and
[ETL_RELIABILITY_PLAN](../ETL_RELIABILITY_PLAN.md) (dynamic control; streaming
DLQ / registries). Reuse 0.38 connector checkpoints and
[ADR-018](ADR-018-DURABLE-SUBMISSION-AND-STATE.md) namespaced state.
[DPCS](../../05_PIPELINES/DPCS.md) owns topology;
[DTCS](../../04_TRANSFORMATIONS/DTCS.md) owns transform meaning;
[ODCS](../../03_DATA_CONTRACTS/ODCS.md) remains the data-contract authority.

## Decision

### Core vs provider ownership

Core owns logical expansion, branch, stream-time, change-envelope **metadata**,
DLQ **policy**, and report fields as extensions of `etlantic.plan/1` and
`PipelineRunReport`—not a new top-level contract family (ODCS / DTCS / DPCS
remain the three public contract authorities).

Providers own Kafka I/O, schema-registry network lookup, DLQ **storage**, and
offsets in provider-owned stores. Optional packages named before
implementation: `etlantic-kafka` and `etlantic-schemaregistry` (Experimental).
Core installs neither.

### Explicit, bounded, deterministic graphs

Dynamic graphs are explicit, serializable, and bounded. For a declared input
identity, child identities, branch decisions, and report structure are
deterministic. Arbitrary Python control flow, recursion, or unbounded runtime
graph mutation is not a portable plan surface
([FORWARD_IMPLEMENTATION_PLANS](../FORWARD_IMPLEMENTATION_PLANS.md) invariant).

### Protocols, not emulation

Snapshot-to-stream handoff and compensation are core **protocols**. Engines
that cannot preserve required semantics fail capability-closed before work is
accepted. ETLantic does not flatten map/branch into an inequivalent static DAG
or degrade unsupported deletes/ordering/transactions to append-only.

### Payloads stay out of ETLantic artifacts

Plans, reports, diagnostics, audit evidence, and fixtures contain identifiers
and bounded metadata only. Event payloads, source rows, and resolved secrets
remain in authorized provider-owned storage.

### Production trust

`Profile.plugin_allowlist` covers streaming connectors. Registry adapters
require `Profile.schema_registry_allowlist` under
`security_mode="production"`. Empty allowlists fail closed.

### Relation to 0.45 optimization

[ADR-021](ADR-021-OPTIMIZER-PASS-PROTOCOL.md) remains the optimizer authority.
Until 0.46 ships expansion/stream proof kinds, a pass MUST NOT expand a graph
or rewrite stream-time / map / branch / compensation edges. Missing kinds fail
closed; default `optimization_policy` stays `off`.

## Consequences

- DPCS integration notes describe expansion/stream nodes as **Future / 0.46**,
  not Available.
- In-memory fixtures prove identity, bounds, and handoff before Kafka.
- Compilers that cannot preserve declared control flow reject the plan before
  emitting artifacts.
- 0.47 federation consumes these identities and error policies; it does not
  redefine them.

## Alternatives

| Alternative | Why rejected |
|---|---|
| Embed event payloads in plans, reports, or diagnostics | Violates fail-closed redaction; leaks subjects |
| A separate streaming control plane | Duplicates durability, identity, and policy already in 0.38–0.42 |
| Flatten map/branch into a static DAG | Loses replayable child identity and compensation semantics |
| Kafka or Confluent client in core | Violates optional-package boundary; core stays engine-free |
| Silent capability degrade to append-only | Hides unsupported deletes, order, and transactions |

## Compatibility

- Additive plan/report fields when implemented; wire family remains `/1` unless
  a schema bump is separately versioned.
- No public API or package version change in this planning freeze.
- Official plugins stay on the published 0.45 line until 0.46 implementation
  begins.

## See also

- [IMPLEMENTATION_PLAN_0_46](../IMPLEMENTATION_PLAN_0_46.md)
- [EXIT_GATE_0_46](../EXIT_GATE_0_46.md)
- [FINDINGS_0_46](../FINDINGS_0_46.md)
- [ADR-018](ADR-018-DURABLE-SUBMISSION-AND-STATE.md)
- [ADR-021](ADR-021-OPTIMIZER-PASS-PROTOCOL.md)
