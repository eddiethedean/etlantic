---
title: ETLantic 0.49 Implementation Plan
description: Implementation-grade plan for deterministic adaptive heterogeneous execution planning and executable physical DAGs.
plan_status: current
plan_last_reviewed: 0.48.0
---

# ETLantic 0.49 Implementation Plan

Phase 0.49 turns the existing multi-engine planning, capability, optimization,
interchange, and hybrid-runtime foundations into an opt-in adaptive execution
strategy for static batch graphs. It converts one ETLantic logical plan into a
deterministic, inspectable, and executable physical DAG spanning multiple
trusted, profile-bound placement targets.

The governing backlog is
[epic #30](https://github.com/eddiethedean/etlantic/issues/30). Its ten stories
and implementation tasks are the delivery ledger for this phase.

## Outcome

Pipeline authors can retain explicit engine selection or opt into adaptive
placement through a profile. For adaptive plans, ETLantic enumerates only
eligible and trusted placement targets, proves per-node support, selects
placements using stable capability/locality rules, forms connected execution
regions, lowers cross-region handoffs into validated physical units, executes
the physical DAG, and explains every important selection and rejection.

Installing an engine does not grant it authority. A candidate participates only
when the profile, all applicable production allowlists, compiler and connector
capabilities, contracts, security boundaries, resource policy, and directional
interchange evidence admit its complete placement target.

## Frozen Phase Boundaries

- Adaptive plans use a new authoritative `etlantic.plan/2` wire schema. Existing
  explicit profiles continue producing the existing canonical `etlantic.plan/1`
  document and fingerprint unless the user opts into adaptive planning. New
  readers support `/1` and `/2`; old or unsupported consumers must reject `/2`
  before external I/O. Adaptive fields are not serialized into explicit `/1`
  plans merely because their defaults exist in a newer Profile implementation.
- A placement target is not only an engine name. Its stable identity includes
  engine family, implementation or compiler, profile-bound execution target or
  resource reference, location/security domain, and relevant version evidence.
  Region formation and transition counts operate on compatible placement-target
  identity.
- The 0.49 MVP assigns individual logical nodes. Portable multi-node fragment
  selection and overlapping fragment-cover optimization are deferred. Proven
  same-target fusion happens only after node placement.
- Adaptive 0.49 execution is limited to static batch graphs on the local runtime.
  Runtime-expanded maps, streaming graphs, speculative execution, external
  orchestrator compilation, and consumers without `/2` physical-DAG support
  fail closed with stable diagnostics. A durable or federated worker may execute
  `/2` only when it advertises and uses the same qualified physical-DAG runtime.
- The canonical physical-unit kinds are compute, transfer, collection,
  validation, materialization, reuse, and publication. Every unit records typed
  dependencies, placement target, logical provenance, security/policy envelope,
  artifact ownership/lifecycle, and effective retry/attempt semantics.
- One whole-DAG preflight verifies integrity, schema support, plugins, compilers,
  connectors, resource providers, schema-registry adapters when applicable,
  versions, capabilities, authorization, contracts, and every handoff before any
  read, resource acquisition, staging, or mutation.
- The gated 0.49 target is **Available** adaptive planning and local batch
  execution for an explicitly published combination matrix. Each participating
  engine/provider retains its own maturity, and a mixed combination inherits the
  weakest participating maturity. Nothing graduates by association.

## Prerequisites And Non-Goals

- The immutable `PipelinePlan`, execution regions, physical units, capability
  vocabulary, portable compiler analysis, connector negotiation, tabular
  interchange, and hybrid runtime from prior phases remain the foundation.
- The 0.45 optimization protocol remains advisory and proof-gated; phase 0.49
  may consume or extend its evidence and explanation contracts but cannot let an
  optimization pass acquire runtime, data, secret, registry, or mutation
  authority.
- The 0.47 scheduler/runtime and 0.48 human-governed proposal boundaries remain
  intact. Adaptive planning does not create an autonomous execution or approval
  path.
- Explicit planning remains the default. Explicit implementation overrides and
  required engines are hard constraints.
- The first release is deterministic and capability/locality-driven. Universal
  cost currency, statistics-dependent join ordering, speculative execution,
  live trial runs, telemetry feedback, and runtime adaptive replanning are out
  of scope.
- Adaptive placement cannot cross or weaken authorization, tenant, workspace,
  environment, residency, masking, classification, security-domain, contract,
  quality, retry-safety, or publication boundaries.
- Plans, evidence, explanations, diagnostics, reports, and fixtures never store
  resolved secrets or source rows.
- Fusion cannot cross external-effect, retry-safety, checkpoint/state,
  partial-selection, validation, or publication boundaries. A fused unit uses a
  deterministic conservative policy derived from every logical member; when no
  safe aggregate exists, the region is split.

## Workstreams

| ID | Workstream | Governing story | Deliverables | Completion evidence |
|---|---|---|---|---|
| 049-A | Policy and contracts | [#31](https://github.com/eddiethedean/etlantic/issues/31) | ADR; `/1` versus `/2` compatibility; Profile precedence; placement-target identity; unit taxonomy; bounded-search, fallback, partial-run, fusion, and consumer-support rules | Accepted ADR plus profile/plan reader-writer matrix, production-trust, and unsupported-consumer evidence |
| 049-C | Capability inventory | [#32](https://github.com/eddiethedean/etlantic/issues/32) | Unified target/compiler/connector/locality/directional-interchange inventory; canonical pushdown vocabulary; deterministic evidence fingerprint | Truthful inventory fixtures, directional pairwise matrix, authorize-before-import tests, and secret scan |
| 049-N | Candidate enumeration | [#33](https://github.com/eddiethedean/etlantic/issues/33) | Source, sink, native, and portable per-node candidates with exact support analysis and stable rejection reasons | Complete candidate matrix across native/portable/I/O/ambiguous/no-solution fixtures |
| 049-P | Placement selection | [#34](https://github.com/eddiethedean/etlantic/issues/34) | One graph-level constraint evaluator; versioned integer/enum objective vector; bounded deterministic search; explicit fallback records | Exhaustive small-graph oracle, seeded properties, resource budgets, and registration-randomized fingerprints |
| 049-R | Connected regions | [#35](https://github.com/eddiethedean/etlantic/issues/35) | Maximal connected compatible regions, stable identities, topological dependencies, protected semantic boundaries | Branch/join/fan-out/disconnected/security fixtures and explicit-plan compatibility goldens |
| 049-L | Physical lowering | [#36](https://github.com/eddiethedean/etlantic/issues/36) | Seven canonical unit kinds with validated dependencies, execution contract, policy/security envelopes, and directional handoffs | Physical-DAG round trips, tamper tests, interchange proofs, and secret/source-row scan |
| 049-X | Runtime authority | [#37](https://github.com/eddiethedean/etlantic/issues/37) | Whole-DAG admission; physical-unit scheduling/dispatch; explicit handoffs; fused attribution/reliability; unsupported-consumer rejection | Adaptive-versus-explicit local batch differential suite plus compile/control-plane/remote rejection or capability tests |
| 049-E | Explain and diff | [#38](https://github.com/eddiethedean/etlantic/issues/38) | Candidate, selection, rejection, region, topology, interchange, estimate, and fallback explanations across public surfaces | Python/CLI/IDE/notebook parity, deterministic output, redaction, and size/depth-budget tests |
| 049-Q | Conformance and graduation | [#39](https://github.com/eddiethedean/etlantic/issues/39) | Public claim conformance; graph corpus; solver oracle/budgets; heterogeneous end-to-end fixture; differential semantics; final evidence gate | Truthfulness, determinism, resource-bound, fail-closed, production-trust, docs, and stable-foundation reports |
| 049-D | Documentation | [#40](https://github.com/eddiethedean/etlantic/issues/40) | Concepts/quickstart, operations/security/rollback, plugin participation, migration, wire/API/CLI references, release notes | Executed examples, docs build/link checks, maturity review, and safety scan |

## Task Ledger

The GitHub sub-issue hierarchy and native `blocked by` relationships are the
operational source of truth. These task groups provide stable phase-plan
traceability without duplicating task acceptance criteria here.

| Story | Tasks |
|---|---|
| [#31](https://github.com/eddiethedean/etlantic/issues/31) | [#41](https://github.com/eddiethedean/etlantic/issues/41), [#42](https://github.com/eddiethedean/etlantic/issues/42), [#43](https://github.com/eddiethedean/etlantic/issues/43), [#44](https://github.com/eddiethedean/etlantic/issues/44) |
| [#32](https://github.com/eddiethedean/etlantic/issues/32) | [#45](https://github.com/eddiethedean/etlantic/issues/45), [#46](https://github.com/eddiethedean/etlantic/issues/46), [#47](https://github.com/eddiethedean/etlantic/issues/47), [#48](https://github.com/eddiethedean/etlantic/issues/48), [#49](https://github.com/eddiethedean/etlantic/issues/49) |
| [#33](https://github.com/eddiethedean/etlantic/issues/33) | [#50](https://github.com/eddiethedean/etlantic/issues/50), [#51](https://github.com/eddiethedean/etlantic/issues/51), [#52](https://github.com/eddiethedean/etlantic/issues/52), [#53](https://github.com/eddiethedean/etlantic/issues/53), [#54](https://github.com/eddiethedean/etlantic/issues/54) |
| [#34](https://github.com/eddiethedean/etlantic/issues/34) | [#55](https://github.com/eddiethedean/etlantic/issues/55), [#56](https://github.com/eddiethedean/etlantic/issues/56), [#57](https://github.com/eddiethedean/etlantic/issues/57), [#58](https://github.com/eddiethedean/etlantic/issues/58), [#59](https://github.com/eddiethedean/etlantic/issues/59) |
| [#35](https://github.com/eddiethedean/etlantic/issues/35) | [#60](https://github.com/eddiethedean/etlantic/issues/60), [#61](https://github.com/eddiethedean/etlantic/issues/61), [#62](https://github.com/eddiethedean/etlantic/issues/62), [#63](https://github.com/eddiethedean/etlantic/issues/63) |
| [#36](https://github.com/eddiethedean/etlantic/issues/36) | [#64](https://github.com/eddiethedean/etlantic/issues/64), [#65](https://github.com/eddiethedean/etlantic/issues/65), [#66](https://github.com/eddiethedean/etlantic/issues/66), [#67](https://github.com/eddiethedean/etlantic/issues/67), [#68](https://github.com/eddiethedean/etlantic/issues/68) |
| [#37](https://github.com/eddiethedean/etlantic/issues/37) | [#69](https://github.com/eddiethedean/etlantic/issues/69), [#70](https://github.com/eddiethedean/etlantic/issues/70), [#71](https://github.com/eddiethedean/etlantic/issues/71), [#72](https://github.com/eddiethedean/etlantic/issues/72), [#73](https://github.com/eddiethedean/etlantic/issues/73), [#88](https://github.com/eddiethedean/etlantic/issues/88), [#89](https://github.com/eddiethedean/etlantic/issues/89), [#90](https://github.com/eddiethedean/etlantic/issues/90) |
| [#38](https://github.com/eddiethedean/etlantic/issues/38) | [#74](https://github.com/eddiethedean/etlantic/issues/74), [#75](https://github.com/eddiethedean/etlantic/issues/75), [#76](https://github.com/eddiethedean/etlantic/issues/76), [#77](https://github.com/eddiethedean/etlantic/issues/77) |
| [#39](https://github.com/eddiethedean/etlantic/issues/39) | [#78](https://github.com/eddiethedean/etlantic/issues/78), [#79](https://github.com/eddiethedean/etlantic/issues/79), [#80](https://github.com/eddiethedean/etlantic/issues/80), [#81](https://github.com/eddiethedean/etlantic/issues/81), [#82](https://github.com/eddiethedean/etlantic/issues/82), [#91](https://github.com/eddiethedean/etlantic/issues/91), [#92](https://github.com/eddiethedean/etlantic/issues/92), [#93](https://github.com/eddiethedean/etlantic/issues/93), [#95](https://github.com/eddiethedean/etlantic/issues/95) |
| [#40](https://github.com/eddiethedean/etlantic/issues/40) | [#83](https://github.com/eddiethedean/etlantic/issues/83), [#84](https://github.com/eddiethedean/etlantic/issues/84), [#85](https://github.com/eddiethedean/etlantic/issues/85), [#86](https://github.com/eddiethedean/etlantic/issues/86), [#87](https://github.com/eddiethedean/etlantic/issues/87), [#94](https://github.com/eddiethedean/etlantic/issues/94) |

## Deterministic Placement Contract

For each logical node, the adaptive planner:

1. enumerates only profile-eligible and trust-approved placement targets;
2. rejects candidates that cannot prove the required operations, functions,
   types, semantic modes, contracts, connector behavior, or interchange;
3. applies explicit overrides, required engines, source/sink constraints, and
   security policy as hard constraints;
4. compares complete viable assignments with a versioned integer/enum vector:
   maximize proven source/sink-local nodes, maximize proven pushdown actions,
   minimize cross-target edges, minimize collections, minimize durable
   materializations, maximize safely fusible edges, then compare configured
   target-priority and stable target-identity vectors;
5. forms maximal connected same-target regions without crossing protected
   boundaries;
6. lowers every region and cross-region edge into a validated physical DAG;
7. fingerprints the candidate inventory, decisions, topology, and relevant
   evidence; and
8. emits selected and rejected alternatives with stable reason codes.

Unknown required capability is ineligible. Unknown optional locality or benefit
is ranked below proven evidence and never becomes a favorable zero. Search uses
ADR-frozen candidate, graph, and work-unit bounds; exhaustion produces a stable
diagnostic or the explicitly permitted baseline fallback, never a wall-clock-
dependent partial answer. Fallback must independently satisfy every trust,
security, contract, capability, and interchange constraint.

## Delivery Sequence

1. Accept the policy/schema ADR and freeze profile, placement, physical-unit,
   reason-code, fingerprint, and compatibility contracts (`049-A`).
2. Build the safe unified capability inventory and repair connector-pushdown
   evidence wiring (`049-C`).
3. Enumerate exact candidates, apply hard constraints, and prove deterministic
   graph placement (`049-N`, `049-P`).
4. Form connected regions and lower all canonical physical-unit kinds into
   a validated physical DAG (`049-R`, `049-L`).
5. Add whole-DAG admission and make the physical DAG authoritative for adaptive
   local batch execution while preserving logical lifecycle and reliability
   semantics (`049-X`).
6. Expose shared explain/diff artifacts and draft user/operator/plugin guidance
   from the frozen contracts (`049-E`, `049-D`).
7. Pass conformance, heterogeneous end-to-end, differential, compatibility,
   resource-bound, production-trust, redaction, unsupported-consumer, and
   determinism campaigns (`049-Q`).
8. Verify the completed documentation, assemble the evidence manifest, and make
   the final **Available**-scope release decision (`049-D`, `049-Q`).

## Exit Gates

- Profiles without adaptive policy retain the documented explicit plan and
  runtime behavior and canonical `/1` plan bytes/fingerprints.
- Adaptive profiles emit `/2`; `/1`-only readers, compilers, schedulers, and
  execution hosts reject it before external I/O rather than following the
  logical graph.
- Explicit per-step overrides always win or fail with a stable diagnostic; no
  automatic choice silently replaces them.
- Identical logical-plan, profile, eligible-target inventory, and evidence
  fingerprints produce identical physical plans and explanations, independent
  of registry insertion order.
- Disconnected same-target branches are separate regions, while adjacent
  compatible nodes fuse only when their execution, effect, retry, checkpoint,
  selection, security, and publication policies have a safe aggregate.
- Every cross-region edge has a validated producer/consumer contract and an
  executable interchange, collection, or materialization unit.
- Whole-DAG admission succeeds before any external I/O, and the local runtime
  schedules the adaptive physical DAG rather than treating
  physical units as advisory metadata.
- Adaptive and explicit executions produce equivalent observable outputs,
  validations, lifecycle semantics, retry behavior, and publication outcomes
  on the differential corpus.
- Missing capability, trust, contract, or interchange evidence produces a
  deterministic safe fallback only when policy permits it; otherwise planning
  fails before mutation.
- Explain output identifies the selected placement, rejected alternatives,
  reason codes, region/fusion decision, handoff mechanism, and unavailable
  estimates without leaking secrets or source rows.
- Production planning neither imports nor selects a non-allowlisted plugin,
  optimization pass, resource provider, connector, or applicable
  schema-registry adapter.
- Static batch and local-runtime bounds are enforced. Runtime-expanded or
  streaming graphs and unsupported compile/control-plane/federated consumers
  fail closed with stable diagnostics.
- All affected planner, optimizer, interchange, runtime, conformance,
  stable-foundation, compatibility, and documentation suites pass.

## Required Release Evidence

- Accepted adaptive policy and physical-plan ADR.
- Profile/plan `/1`–`/2` reader-writer, verify-mode, unsupported-consumer, and
  deterministic-fingerprint report.
- Capability inventory and candidate truthfulness matrix.
- Placement exhaustive-oracle, seeded-property, resource-budget, and
  connected-region randomized-order campaign.
- Physical-DAG validation, tamper, interchange, and redaction report.
- Whole-DAG admission, adaptive-versus-explicit runtime differential,
  batch/static rejection, and unsupported-consumer report.
- Public explain/diff parity report.
- Production trust/security campaign covering all applicable allowlists and the
  adaptive graduation exit gate with supported combination matrix.
- Executed quickstart plus documentation build and link report.

## Follow-On Boundary

Statistics-aware costing, provider-specific economic models, telemetry feedback,
bounded runtime replanning, and additional experimental engines require later,
separately gated phases. Phase 0.49 establishes no performance or maturity claim
for an engine that has not independently passed its existing conformance and
graduation requirements.
