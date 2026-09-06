---
title: ETLantic 0.50 Implementation Plan
description: Implementation-grade plan for deterministic adaptive heterogeneous execution planning and executable physical DAGs.
plan_status: current
plan_last_reviewed: 0.48.0
---

# ETLantic 0.50 Implementation Plan

Phase 0.50 turns the existing multi-engine planning, capability, optimization,
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
- The 0.50 MVP assigns individual logical nodes. Portable multi-node fragment
  selection and overlapping fragment-cover optimization are deferred. Proven
  same-target fusion happens only after node placement.
- Adaptive 0.50 execution is limited to static batch graphs on the local runtime.
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
- Partial selection is resolved into a dependency-closed logical graph before
  candidate enumeration. The resulting `/2` plan and fingerprint cover that
  exact selection. A runtime request cannot apply a different selection to a
  stored `/2` plan; it must re-plan first. Fusion therefore never executes an
  unselected logical effect.
- Adaptive fallback defaults to `error`. An explicit-baseline fallback is used
  only when the profile opts in, the ordinary explicit planner independently
  passes every constraint, and the result is emitted as `/1` with a stable
  fallback decision. A partial or approximate `/2` plan is never executable.
- The gated 0.50 target is **Available** adaptive planning and local batch
  execution for an explicitly published combination matrix. Each participating
  engine/provider retains its own maturity, and a mixed combination inherits the
  weakest participating maturity. Nothing graduates by association.

## Prerequisites And Non-Goals

- The immutable `PipelinePlan`, execution regions, physical units, capability
  vocabulary, portable compiler analysis, connector negotiation, tabular
  interchange, and hybrid runtime from prior phases remain the foundation.
- The 0.45 optimization protocol remains advisory and proof-gated; phase 0.50
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

## MVP Public Contract

The ADR in #41 records these phase locks and rejected alternatives; it does not
leave them open for downstream tasks. It may tighten a bound or validation rule,
but a public rename or scope expansion requires an explicit update to this plan,
the epic, and affected task acceptance criteria first.

| Surface | Phase 0.50 lock |
|---|---|
| Profile strategy | `execution_strategy: Literal["explicit", "adaptive"] = "explicit"` |
| Placement definitions | `placement_targets` is a secret-free mapping from stable target id to engine family, implementation/compiler, optional `resources` reference, location, security domain, and version/capability evidence requirements |
| Eligible order | `eligible_targets` is an ordered, duplicate-free tuple of keys in `placement_targets`; adaptive mode requires at least one target and never discovers extra candidates from installed packages |
| Fallback | `adaptive_fallback: Literal["error", "explicit"] = "error"`; `explicit` regenerates through the existing explicit planner and returns `/1` only after independent admission |
| Existing engine fields | `dataframe_engine`, `sql_engine`, and `spark_engine` define the explicit baseline and do not silently enter the adaptive candidate set |
| Override precedence | `RunRequest.implementation_overrides` → `Profile.implementation_overrides` → binding/provider and required-capability constraints → portable-transform policy → adaptive ranking; an override outside the eligible/trusted set fails instead of widening it |
| Plan schemas | Keep `PLAN_SCHEMA == "etlantic.plan/1"` for compatibility and add `ADAPTIVE_PLAN_SCHEMA == "etlantic.plan/2"`; the public `PipelinePlan` reader façade dispatches to schema-specific codecs |
| `/2` downgrade | No stored `/2` → `/1` downgrade. Regenerate with explicit policy; unsupported `/2` consumers reject before acceptance or external I/O |
| Unit protocol | `etlantic.physical_unit/1` is the versioned admission/execution/result protocol for all seven unit kinds; executors advertise supported plan, unit, and capability versions |
| Fusion | A backend may fuse only with an advertised fused-region capability. Otherwise the planner deterministically emits ordered single-node compute units without changing region identity or semantics |
| Selection | Selection closure is computed before placement and fingerprinted. A different runtime selection requires a new plan |
| Diagnostics | Reserve `PMADP1xx` policy/schema, `PMADP2xx` inventory/candidate, `PMADP3xx` solver/bounds, `PMADP4xx` physical validation, and `PMADP5xx` admission/runtime families |

Planning remains side-effect free. Static manifests and already-authorized
capability analyzers may contribute bounded evidence, but planning does not list
sources, resolve secrets, acquire resources, execute user transformations, or
probe a live data plane. Whole-DAG runtime preflight re-evaluates mutable
authorization and resource policy rather than trusting a planning snapshot as
live authority.

## Deterministic Resource Envelope

These are the initial required defaults. Profiles may tighten them but cannot
raise them in 0.50. The limit-set version and effective values participate in
the `/2` fingerprint.

| Limit | Default | Deterministic behavior at the limit |
|---|---:|---|
| Selected logical nodes | 256 | `PMADP300`; use permitted explicit fallback or fail |
| Eligible placement targets | 8 | `PMADP301`; reject profile before discovery |
| Candidates per node | 8 | `PMADP302`; reject excess rather than truncate viable candidates |
| Candidate/rejection records | 2,048 | `PMADP303`; canonical summary is explain-only, never solver input |
| Solver state expansions | 1,000,000 | `PMADP304`; no approximate assignment is returned |
| Explain alternatives per node/target | 8 | Canonical truncation marker plus omitted count |
| Serialized adaptive explain artifact | 4 MiB | `PMADP305`; emit bounded summary and retain the plan |
| Peak planner-owned transient memory | 256 MiB | `PMADP306`; measured in the release resource campaign |

A solver work unit is one visited partial or complete assignment after hard
constraint propagation. Nodes are visited in stable topological/name order and
candidates in objective/target-identity order. Exact branch-and-bound may prune
only with a deterministic proof that the subtree cannot beat the incumbent.
Wall-clock duration is measured for evidence but never changes the selected
assignment. The independent exhaustive oracle covers graphs of at most eight
nodes, four targets, and 65,536 complete assignments.

## Initial Qualification Matrix

The phase must qualify at least the rows below. #95 may remove a row whose
evidence does not pass; it cannot add a row without the same evidence. Connector,
resource-provider, and engine maturity remain independent axes, so a qualified
engine pair does not graduate an unrelated provider.

| Placement combination | Physical boundary | Runtime | Target claim |
|---|---|---|---|
| Local Python only | None | Local | Available after single-target physical-DAG differential evidence |
| Polars only | None | Local | Available after single-target physical-DAG differential evidence |
| Pandas only | None | Local | Available after single-target physical-DAG differential evidence |
| Polars → Pandas | `etlantic.interchange/1` Arrow Gate A | Local | Available after directional handoff, cleanup, and publication evidence |
| Pandas → Polars | `etlantic.interchange/1` Arrow Gate A | Local | Available after independent reverse-direction evidence |

SQL, PySpark, DataFusion, remote warehouses, external orchestrator compilation,
durable/federated execution, streaming, and runtime-expanded graphs receive no
0.50 adaptive availability claim. They fail closed unless a later gate adds a
qualified `/2` physical-DAG consumer and combination row.

## Workstreams

| ID | Workstream | Governing story | Deliverables | Completion evidence |
|---|---|---|---|---|
| 050-A | Policy and contracts | [#31](https://github.com/eddiethedean/etlantic/issues/31) | ADR; `/1` versus `/2` compatibility; Profile precedence; placement-target identity; unit taxonomy; bounded-search, fallback, partial-run, fusion, and consumer-support rules | Accepted ADR plus profile/plan reader-writer matrix, production-trust, and unsupported-consumer evidence |
| 050-C | Capability inventory | [#32](https://github.com/eddiethedean/etlantic/issues/32) | Unified target/compiler/connector/locality/directional-interchange inventory; canonical pushdown vocabulary; deterministic evidence fingerprint | Truthful inventory fixtures, directional pairwise matrix, authorize-before-import tests, and secret scan |
| 050-N | Candidate enumeration | [#33](https://github.com/eddiethedean/etlantic/issues/33) | Source, sink, native, and portable per-node candidates with exact support analysis and stable rejection reasons | Complete candidate matrix across native/portable/I/O/ambiguous/no-solution fixtures |
| 050-P | Placement selection | [#34](https://github.com/eddiethedean/etlantic/issues/34) | One graph-level constraint evaluator; versioned integer/enum objective vector; bounded deterministic search; explicit fallback records | Exhaustive small-graph oracle, seeded properties, resource budgets, and registration-randomized fingerprints |
| 050-R | Connected regions | [#35](https://github.com/eddiethedean/etlantic/issues/35) | Maximal connected compatible regions, stable identities, topological dependencies, protected semantic boundaries | Branch/join/fan-out/disconnected/security fixtures and explicit-plan compatibility goldens |
| 050-L | Physical lowering | [#36](https://github.com/eddiethedean/etlantic/issues/36) | Seven canonical unit kinds with validated dependencies, execution contract, policy/security envelopes, and directional handoffs | Physical-DAG round trips, tamper tests, interchange proofs, and secret/source-row scan |
| 050-X | Runtime authority | [#37](https://github.com/eddiethedean/etlantic/issues/37) | Whole-DAG admission; physical-unit scheduling/dispatch; explicit handoffs; fused attribution/reliability; unsupported-consumer rejection | Adaptive-versus-explicit local batch differential suite plus compile/control-plane/remote rejection or capability tests |
| 050-E | Explain and diff | [#38](https://github.com/eddiethedean/etlantic/issues/38) | Candidate, selection, rejection, region, topology, interchange, estimate, and fallback explanations across public surfaces | Python/CLI/IDE/notebook parity, deterministic output, redaction, and size/depth-budget tests |
| 050-Q | Conformance and graduation | [#39](https://github.com/eddiethedean/etlantic/issues/39) | Public claim conformance; graph corpus; solver oracle/budgets; heterogeneous end-to-end fixture; differential semantics; final evidence gate | Truthfulness, determinism, resource-bound, fail-closed, production-trust, docs, and stable-foundation reports |
| 050-D | Documentation | [#40](https://github.com/eddiethedean/etlantic/issues/40) | Concepts/quickstart, operations/security/rollback, plugin participation, migration, wire/API/CLI references, release notes | Executed examples, docs build/link checks, maturity review, and safety scan |

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

The exact minimized comparison tuple is:

```text
(-proven_local_io_nodes,
 -proven_pushdown_actions,
 cross_target_logical_edges,
 collection_units,
 durable_materialization_units,
 -safely_fusible_logical_edges,
 target_priority_vector,
 target_identity_vector)
```

An I/O node counts as local only with positive provider/target locality evidence.
A pushdown action is a distinct canonical predicate or projection action proved
executable at that I/O target; a generic `pushdown` claim contributes nothing.
Collection and materialization counts come from the candidate physical lowering,
not from estimates. Fusible edges must already pass the single #62 boundary
predicate. Both final vectors list one value per selected node in stable
topological/name order, so multi-source and multi-sink ties are total and
transitive.

Unknown required capability is ineligible. Unknown optional locality or benefit
is ranked below proven evidence and never becomes a favorable zero. Search uses
ADR-frozen candidate, graph, and work-unit bounds; exhaustion produces a stable
diagnostic or the explicitly permitted baseline fallback, never a wall-clock-
dependent partial answer. Fallback must independently satisfy every trust,
security, contract, capability, and interchange constraint.

## Delivery Increments

Each increment is independently mergeable and leaves every public execution
path safe. An incomplete increment cannot advertise the claim of a later one.

| Increment | Task spine | Merge condition | Public state after merge |
|---|---|---|---|
| **I0 — contract freeze** | #41–#44, #82 | ADR accepted; Profile and `/2` schemas fixed; `/1` golden bytes pass; exit-gate skeleton names every required artifact | Explicit `/1` unchanged; adaptive remains unavailable |
| **I1 — plan and explain** | #45–#68, #74–#77, #91, #93 | Inventory, node candidates, exact bounded solver, connected regions, seven-kind lowering, explain/diff, oracle, and tamper evidence pass | Adaptive `/2` may be generated and inspected behind opt-in; every execution consumer rejects it before I/O |
| **I2 — local execution** | #88–#90, #69–#73, #92 | Versioned unit protocol, whole-DAG admission, physical scheduling, lifecycle/retry/publication semantics, and unsupported-consumer matrix pass | Qualified local static-batch fixtures may execute; no availability claim yet |
| **I3 — qualification** | #78–#81, #83–#87, #94–#95 | Public conformance, fixed launch topology, directional pair matrix, differential semantics, documentation, security scan, and final evidence decision pass | Only the published matrix becomes Available |

The task-level critical path is:

```text
#41 → #42/#43 → #44/#45 → #46–#54 → #55–#59
    → #62 → #60–#68 → #88/#90 → #69–#73
    → #74–#81/#91–#94 → #87 → #95
```

Documentation drafting starts once its source contract is frozen; it does not
wait for I3. #82 creates and maintains the
[0.50 exit gate](EXIT_GATE_0_50.md), while #95 alone records the final release
decision.

## Exit Gates

- Profiles without adaptive policy retain the documented explicit plan and
  runtime behavior and canonical `/1` plan bytes/fingerprints.
- Adaptive profiles emit `/2`; `/1`-only readers, compilers, schedulers, and
  execution hosts reject it before external I/O rather than following the
  logical graph.
- An opted-in explicit fallback returns an independently validated `/1` plan
  with a stable fallback decision; the runtime never executes a partial,
  approximate, or exhausted-search `/2` plan.
- Explicit per-step overrides always win or fail with a stable diagnostic; no
  automatic choice silently replaces them.
- Partial-run selection is dependency-closed before placement and is part of
  the `/2` fingerprint; runtime selection drift requires re-planning.
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
- The deterministic resource envelope is enforced with stable `PMADP3xx`
  diagnostics and no wall-clock-dependent selection.
- Only rows that pass the initial qualification matrix may be described as
  Available; every other adaptive engine/provider/consumer path remains
  Experimental or unavailable according to its independently published gate.
- All affected planner, optimizer, interchange, runtime, conformance,
  stable-foundation, compatibility, and documentation suites pass.

## Required Release Evidence

- Accepted adaptive policy and physical-plan ADR.
- Completed [0.50 exit gate](EXIT_GATE_0_50.md) with a dated #95 go/no-go
  decision and no unresolved critical/high phase finding.
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

## Evidence Ownership

| Evidence artifact | Owning tasks |
|---|---|
| ADR, public-field inventory, diagnostic ranges | #41–#43 |
| `/1`–`/2` compatibility matrix | #44, #94 |
| Capability/candidate truthfulness | #45–#54, #78 |
| Solver oracle and resource envelope | #55–#59, #91, #93 |
| Physical-DAG validation and interchange | #60–#68, #79 |
| Admission, execution, lifecycle, and unsupported consumers | #69–#73, #88–#92 |
| Explain/diff parity and redaction | #74–#77 |
| Fixed heterogeneous differential | #80–#81 |
| Operator/plugin/migration documentation | #83–#87, #94 |
| Evidence manifest and final maturity decision | #82, #95 |

## Follow-On Boundary

Statistics-aware costing, provider-specific economic models, telemetry feedback,
bounded runtime replanning, and additional experimental engines require later,
separately gated phases. Phase 0.50 establishes no performance or maturity claim
for an engine that has not independently passed its existing conformance and
graduation requirements.
