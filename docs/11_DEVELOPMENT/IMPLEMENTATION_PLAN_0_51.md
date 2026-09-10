---
title: ETLantic 0.51 Implementation Plan
description: Implementation-grade plan for deterministic adaptive heterogeneous execution planning and executable physical DAGs.
plan_status: current
plan_last_reviewed: 0.50.1
---

# ETLantic 0.51 Implementation Plan

> **Status: Planned after published ETLantic 0.50.1.** The current repository
> implements explicit `etlantic.plan/1` planning and logical-node scheduling;
> adaptive Profile fields, authoritative `etlantic.plan/2`, and physical-unit
> scheduling are not implemented. This plan was audited against the 0.50.1
> release surface and evidence set before 0.51 implementation begins.

Phase 0.51 turns the existing multi-engine planning, capability, optimization,
interchange, and hybrid-runtime foundations into an opt-in adaptive execution
strategy for static batch graphs. It converts one ETLantic logical plan into a
deterministic, inspectable, and executable physical DAG spanning multiple
trusted, profile-bound placement targets.

The governing backlog is
[epic #30](https://github.com/eddiethedean/etlantic/issues/30). Its ten stories
and implementation tasks are the delivery ledger for this phase.

## Current 0.50.1 Baseline

Phase 0.51 starts from these shipped facts. They are inputs and compatibility
constraints, not evidence that adaptive execution already exists.

| 0.50.1 surface | Current repository state | 0.51 consequence |
|---|---|---|
| Portable transformation baseline | `etlantic.portable-baseline/1` is technically qualified across Local, Polars, Pandas, SQL, PySpark, DataFusion, and DuckDB, with requirement-level support, lowering, pushdown, target identity, and evidence fingerprints | Candidate inventory consumes exact requirement/support evidence; engine name, installation, or aggregate qualification never establishes eligibility |
| Adaptive handoff fixture | `portable_adaptive_handoff_0_50.json` proves bounded per-node evidence evaluation, required/unknown rejection, lowering provenance, graph constraints, and evidence-drift rejection | It is seed evidence only; `evaluate_adaptive_candidates` is not the public 0.51 planner, objective solver, `/2` codec, or runtime authority |
| Plan model | `etlantic.plan/1` contains deep-frozen planner-owned nests, regions, advisory `PhysicalUnit` records, logical-to-physical mappings, boundaries, and fingerprints | `/1` bytes and fingerprints remain unchanged; `/2` gets schema-specific records and validation rather than widening `/1` |
| Region/runtime behavior | Existing regions are selected from explicit engines and the Local scheduler schedules logical nodes; current physical units are advisory metadata | 0.51 must form connected placement-target regions and make validated `/2` physical dependencies authoritative before claiming execution |
| Interchange | `etlantic.interchange/1` Arrow Gate A is Available in both Polars→Pandas and Pandas→Polars directions | Each direction still requires 0.51 physical handoff, ownership, cleanup, retry, validation, and publication evidence |
| Native implementation bodies | `@Transformation.implementation(engine)` remains an explicit engine-specific escape hatch; 0.50 forbids silent fallback to it from rejected portable support | Native bodies are not adaptive candidates. They may run only through independently planned explicit `/1` behavior, including an opted-in explicit fallback |
| Run reports | `etlantic.run_report/1` writers currently use bare built-in step metadata keys (`dataframe`, `sql`, `spark`, `spark_schema`) | 0.51 performs the namespaced writer migration while preserving warning-free deterministic reads of 0.50 reports |

The authoritative 0.50 inputs are the baseline, requirement-support,
pushdown, adaptive-handoff, dependency/security, and evidence-index artifacts
under `docs/11_DEVELOPMENT/evidence/portable_0_50/`. Their digests and schema
versions must be recorded by the 0.51 inventory; copying selected fields into a
new unlinked artifact is insufficient provenance.

## Outcome

Pipeline authors can retain explicit engine selection or opt into adaptive
placement through a profile. For adaptive plans, ETLantic enumerates only
eligible and trusted I/O and portable-compiler placement targets, proves
per-node support, selects
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
- The 0.51 MVP assigns individual logical nodes. Portable multi-node fragment
  selection and overlapping fragment-cover optimization are deferred. Proven
  same-target fusion happens only after node placement.
- Adaptive compute candidates require `@Transformation.portable` definitions
  and exact compiler support evidence. Native
  `@Transformation.implementation(engine)` bodies are explicit-only `/1`
  escape hatches and are never `/2` candidates. An adaptive profile with a
  native-only node, `portable_transform_policy="native"`, or a native-body
  override has no adaptive solution; it fails or uses the independently planned
  explicit `/1` fallback when that fallback is enabled and valid. Existing
  explicit profiles retain the 0.50.1 `prefer` default; every new adaptive
  template and example sets `portable_transform_policy="require"`.
- Adaptive 0.51 execution is limited to static batch graphs on the local runtime.
  Runtime-expanded maps, streaming graphs, speculative execution, external
  orchestrator compilation, and consumers without `/2` physical-DAG support
  fail closed with stable diagnostics. Durable, federated, and remote workers
  reject `/2` throughout 0.51; qualifying one requires a later consumer gate.
- The canonical physical-unit kinds are compute, transfer, collection,
  validation, materialization, reuse, and publication. Every unit records typed
  dependencies, placement target, logical provenance, security/policy envelope,
  artifact ownership/lifecycle, and effective retry/attempt semantics.
- One whole-DAG preflight verifies integrity, schema support, plugins, compilers,
  connectors, resource providers, schema-registry adapters when applicable,
  versions, capabilities, authorization, contracts, and every handoff before any
  read, resource acquisition, staging, or mutation.
- Partial selection reuses the 0.50.1 `run_one`, `run_until`, and explicit-node
  slicing semantics. Before candidate enumeration, the planner stores the
  canonical non-empty `selected_nodes` tuple and the corresponding sliced
  `logical_graph`; it does not retain an executable unsliced graph beside them.
  The `/2` physical DAG must cover every selected logical node and no unselected
  node. The sliced graph, selection, candidates, and physical topology all
  participate in the fingerprint. A runtime request cannot apply a different
  selection to a stored `/2` plan; it must re-plan first.
- Adaptive fallback defaults to `error`. An explicit-baseline fallback is used
  only when the profile opts in, the ordinary explicit planner independently
  passes every constraint, and the result is emitted as `/1` with a stable
  fallback decision. The reason is stored under the existing namespaced `/1`
  metadata extension `etlantic.adaptive_fallback` and therefore changes only
  fallback-plan bytes; ordinary explicit plans gain no adaptive field or
  metadata. No failed or partial `/2` document is emitted.
- The gated 0.51 target is **Available** adaptive planning and local batch
  execution for an explicitly published combination matrix. Each participating
  engine/provider retains its own maturity, and a mixed combination inherits the
  weakest participating maturity. Nothing graduates by association.

## Prerequisites And Non-Goals

- The frozen `PipelinePlan` dataclass, deep-frozen planner-owned `/1` nests,
  explicit-engine regions, advisory physical-unit records, capability
  vocabulary, portable compiler analysis, connector negotiation, tabular
  interchange, and hybrid logical-node runtime from prior phases remain the
  foundation. Existing `/1` region and unit shapes are not the authoritative
  0.51 physical-DAG protocol.
- The 0.45 optimization protocol remains advisory and proof-gated; phase 0.51
  may consume or extend its evidence and explanation contracts but cannot let an
  optimization pass acquire runtime, data, secret, registry, or mutation
  authority.
- The 0.47 scheduler/runtime and 0.48 human-governed proposal boundaries remain
  intact. Adaptive planning does not create an autonomous execution or approval
  path.
- Explicit planning remains the default. Explicit implementation overrides and
  required engines are hard constraints. In adaptive mode, an override may
  constrain an eligible portable compiler/target; an override that selects a
  native body makes `/2` placement infeasible rather than making the body
  adaptive.
- The runtime-report namespace migration is limited to built-in engine metadata
  in `StepRunReport.metadata`. It does not rename logical-plan metadata,
  profile metadata, third-party extension keys, or physical-unit fields.
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

| Surface | Phase 0.51 lock |
|---|---|
| Profile strategy | `execution_strategy: Literal["explicit", "adaptive"] = "explicit"` |
| Placement definitions | `placement_targets` is a secret-free mapping from stable target id to engine family, implementation/compiler, optional `resources` reference, location, security domain, and version/capability evidence requirements |
| Eligible order | `eligible_targets` is an ordered, duplicate-free tuple of keys in `placement_targets`; adaptive mode requires at least one target and never discovers extra candidates from installed packages |
| Fallback | `adaptive_fallback: Literal["error", "explicit"] = "error"`; `explicit` regenerates through the existing explicit planner, returns `/1` only after independent admission, and records `{"schema": "etlantic.adaptive_fallback/1", "reason_code": ..., "input_fingerprint": ...}` only in `metadata["etlantic.adaptive_fallback"]` |
| Existing engine fields | `dataframe_engine`, `sql_engine`, and `spark_engine` define the explicit baseline and do not silently enter the adaptive candidate set |
| Portable/native boundary | Adaptive compute candidates come only from portable definitions and eligible compiler targets, including target-native lowering proved by a portable compiler. Native implementation bodies remain explicit `/1` escape hatches. Explicit profiles keep the `prefer` default; new adaptive profiles use `require`. `native` is contradictory with `/2`, and `prefer` never turns a rejected portable candidate into a native adaptive candidate |
| Override precedence | `RunRequest.implementation_overrides` → `Profile.implementation_overrides` → binding/provider and required-capability constraints → portable-transform policy → adaptive ranking; an override outside the eligible/trusted portable target set, including a native-body override, fails instead of widening it |
| Plan schemas | Keep `PLAN_SCHEMA == "etlantic.plan/1"` and `PipelinePlan` `/1`-only; add `ADAPTIVE_PLAN_SCHEMA == "etlantic.plan/2"`, `AdaptivePipelinePlan`, and a public `PlanDocument` union. Module-level `plan_from_json`, `plan_to_json`, fingerprint, and verify functions dispatch by schema without widening the `/1` dataclass |
| `/2` downgrade | No stored `/2` → `/1` downgrade. Regenerate with explicit policy; unsupported `/2` consumers reject before acceptance or external I/O |
| Unit protocol | `etlantic.physical_unit/1` is the versioned admission/execution/result protocol for all seven unit kinds; executors advertise supported plan, unit, and capability versions |
| Fusion | A backend may fuse only with an advertised fused-region capability. Otherwise the planner deterministically emits ordered single-node compute units without changing region identity or semantics |
| Selection | Existing slicing computes a canonical `selected_nodes` tuple and sliced logical graph before placement. `/2` physical coverage is exact, both forms are fingerprinted, and a different runtime selection requires a new plan |
| Runtime report metadata | Keep `etlantic.run_report/1`. New writers emit `etlantic.dataframe`, `etlantic.sql`, `etlantic.spark`, and `etlantic.spark_schema` instead of the legacy bare `dataframe`, `sql`, `spark`, and `spark_schema` keys in `StepRunReport.metadata`. Readers accept either form, remove legacy aliases during load, and prefer the namespaced value when both forms are present; migration and reserialization are deterministic and idempotent |
| Diagnostics | Reserve `PMADP1xx` policy/schema, `PMADP2xx` inventory/candidate, `PMADP3xx` solver/bounds, `PMADP4xx` physical validation, and `PMADP5xx` admission/runtime families; the ADR freezes the subrange allocation below before implementation |

### Adaptive `/2` wire invariants

`AdaptivePipelinePlan` shares stable logical identifiers with `/1` but owns a
separate closed schema. Its required adaptive sections are:

| Section | Required invariant |
|---|---|
| Logical scope | `/1`-compatible selection representation: `selected_nodes: null` means the full logical graph; otherwise it is the canonical non-empty partial selection and `logical_graph` is the matching slice. The executable node set and order agree exactly |
| Inventory | Canonical descriptors for every and only eligible placement target, eligible order, inventory fingerprint, and digest-bound evidence references |
| Candidates | The complete bounded node-target record matrix, including rejected records; explain truncation never changes this section |
| Decisions | Exactly one selected eligible candidate reference per selected node and the exact minimized objective tuple |
| Regions | A deterministic partition of selected nodes into maximal connected compatible regions; every node occurs once |
| Physical DAG | Versioned units and typed dependencies, one primary compute-unit mapping per selected node, complete additional logical attribution, and no attribution to unselected nodes |
| Protocol versions | Plan, physical-unit, capability, compiler, connector, interchange, and applicable provider contract versions used to plan |
| Integrity | One canonical fingerprint over every field above plus secret-free policy inputs; mutable live authorization is deliberately not asserted by the plan |

Unknown required sections, unit kinds, dependency kinds, or decision references
fail during deserialization. Namespaced optional metadata remains extension-only
and cannot alter placement or execution semantics.

### Placement target and candidate invariants

A profile key is a human-facing stable id, not sufficient placement identity by
itself. The planner canonicalizes every eligible target into a secret-free
descriptor and hashes all identity-bearing fields.

| Record | Required invariant |
|---|---|
| Placement target | Stable profile key; engine family; compiler or implementation id; resource reference only; location and security domain; protocol, package, and implementation versions; capability/evidence fingerprints |
| Target identity | SHA-256 of the canonical descriptor above. The eligible-target order is a separate priority input and is also fingerprinted |
| Node-target record | Exactly one record for every selected logical node × eligible target, ordered by selected-node order then eligible-target order |
| Status | `eligible` or `rejected`; rejection contains stable reason codes and never disappears from the complete pre-explain matrix |
| Eligibility proof | Required operation/function/type/semantic support, trust, locality or I/O binding where required, contract compatibility, and directional boundary evidence are explicit references, not inferred from an engine name |
| Solver input | Only eligible records enter the solver. Objective facts are normalized integers/enums; estimates that are missing or incomparable remain unavailable and cannot improve rank |
| Secret boundary | Records contain references and digests only, never resolved credentials, source rows, executable callables, or raw live-data samples |

Native-only nodes and native-body overrides still receive complete rejected
node-target records, so the candidate matrix explains infeasibility without
turning a native body into a candidate.

### Diagnostic ownership

| Range | Owner |
|---|---|
| `PMADP100–119` | Profile fields, precedence, schema selection, and `/1` compatibility |
| `PMADP120–139` | Selection, fallback, downgrade, and unsupported authoring modes |
| `PMADP200–219` | Inventory trust, identity, versions, evidence lineage, and drift |
| `PMADP220–239` | Node-target enumeration and capability rejection |
| `PMADP240–259` | Locality, pushdown, connector, contract, and directional interchange rejection |
| `PMADP300–306` | Frozen resource-limit failures listed below |
| `PMADP320–339` | Hard-constraint conflicts, no solution, objective validation, and solver replay |
| `PMADP400–429` | `/2` and physical-unit schema, topology, coverage, integrity, and tamper rejection |
| `PMADP500–519` | Whole-DAG admission and unsupported consumer/capability rejection |
| `PMADP520–549` | Dispatch, lifecycle, retry, cancellation, cleanup, validation, and publication |

Published meanings are append-only within these ranges. CLI, Python, IDE, and
notebook projections carry the same code and structured path.

The fallback `input_fingerprint` covers the logical scope, normalized adaptive
Profile fields, eligible-target descriptors/order, evidence digests, and fixed
limit-set version. It is provenance for the failed adaptive attempt, not a
fingerprint for an emitted `/2` plan.

Planning remains side-effect free. Static manifests and already-authorized
capability analyzers may contribute bounded evidence, but planning does not list
sources, resolve secrets, acquire resources, execute user transformations, or
probe a live data plane. Whole-DAG runtime preflight re-evaluates mutable
authorization and resource policy rather than trusting a planning snapshot as
live authority.

The 0.50.1 `evaluate_adaptive_candidates` helper may be reused only where its
validated data-only behavior matches the frozen 0.51 contract. Its current
node-local preference selection is not the graph objective below and must not be
promoted into the authoritative solver by renaming it or wrapping its output.

## Deterministic Resource Envelope

These are fixed 0.51 limits, not Profile knobs. Making them configurable would
expand the four-field MVP Profile contract and is deferred. The limit-set
version and values participate in every `/2` fingerprint.

| Limit | Default | Deterministic behavior at the limit |
|---|---:|---|
| Selected logical nodes | 256 | `PMADP300`; use permitted explicit fallback or fail |
| Eligible placement targets | 8 | `PMADP301`; reject profile before discovery |
| Candidates per node | 8 | `PMADP302`; reject excess rather than truncate viable candidates |
| Candidate/rejection records | 2,048 | `PMADP303`; canonical summary is explain-only, never solver input |
| Solver state expansions | 1,000,000 | `PMADP304`; no approximate assignment is returned |
| Explain evidence items per node-target record | 8 | Keep the candidate and reason codes; truncate only evidence detail with a canonical marker and omitted count |
| Serialized adaptive explain artifact | 4 MiB | `PMADP305`; emit bounded summary and retain the plan |
| Planner-owned transient budget | 256 MiB | `PMADP306`; deterministic byte accounting rejects before an over-budget allocation |

A solver work unit is one visited partial or complete assignment after hard
constraint propagation. Nodes are visited in stable topological/name order and
candidates in objective/target-identity order. Exact branch-and-bound may prune
only with a deterministic proof that the subtree cannot beat the incumbent.
Each planner-owned candidate, frontier state, and retained explanation record
is charged by canonical encoded bytes plus ADR-frozen per-record overhead; this
counter, not allocator behavior or process RSS, triggers `PMADP306`. Peak RSS
and wall-clock duration are measured as non-normative release evidence and never
change the selected assignment. The independent exhaustive oracle covers graphs
of at most eight nodes, four targets, and 65,536 complete assignments.
All at-most-eight target alternatives for a node remain visible; the explain
limit applies to supporting evidence inside each node-target record, not to the
complete candidate matrix.

## Initial Qualification Matrix

The phase must qualify at least the rows below. #95 may remove a row whose
evidence does not pass; it cannot add a row without the same evidence. Connector,
resource-provider, and engine maturity remain independent axes, so a qualified
engine pair does not graduate an unrelated provider.

| Placement combination | Physical boundary | Runtime | Target claim |
|---|---|---|---|
| Local portable compiler only | None | Local | Available after single-target physical-DAG differential evidence; arbitrary Python/native bodies are excluded |
| Polars only | None | Local | Available after single-target physical-DAG differential evidence |
| Pandas only | None | Local | Available after single-target physical-DAG differential evidence |
| DuckDB only | None | Local DuckDB target | 0.50 baseline/pushdown prerequisite passed; remains an Experimental 0.51 candidate pending independent single-target physical-DAG evidence, with no default availability claim |
| Polars → Pandas | `etlantic.interchange/1` Arrow Gate A | Local | Available after directional handoff, cleanup, and publication evidence |
| Pandas → Polars | `etlantic.interchange/1` Arrow Gate A | Local | Available after independent reverse-direction evidence |
| DuckDB ↔ Local/Polars/Pandas | Directional relation/Arrow/record-batch handoff, per target | Local | No availability claim until each direction proves schema, ownership, cleanup, retry, and publication semantics |

SQL, PySpark, DataFusion, remote warehouses, external orchestrator compilation,
durable/federated execution, streaming, and runtime-expanded graphs receive no
0.51 adaptive availability claim. The 0.50 seven-engine qualification supplies
portable semantic evidence for these engines but does not qualify their `/2`
consumer, interchange, lifecycle, or publication behavior. DuckDB therefore
remains Experimental in 0.51 until this phase's independent physical-DAG row
passes. All unqualified combinations fail closed unless a later gate adds a
qualified `/2` physical-DAG consumer and combination row.

## Workstreams

| ID | Workstream | Governing story | Deliverables | Completion evidence |
|---|---|---|---|---|
| 051-A | Policy and contracts | [#31](https://github.com/eddiethedean/etlantic/issues/31) | ADR; `/1` versus `/2` compatibility; Profile precedence; placement-target identity; unit taxonomy; bounded-search, fallback, partial-run, fusion, consumer-support, and runtime-report metadata migration rules | Accepted ADR plus profile/plan and report-metadata reader-writer matrices, production-trust, and unsupported-consumer evidence |
| 051-C | Capability inventory | [#32](https://github.com/eddiethedean/etlantic/issues/32) | Unified target/compiler/connector/locality/directional-interchange inventory; canonical pushdown vocabulary; deterministic evidence fingerprint | Truthful inventory fixtures, directional pairwise matrix, authorize-before-import tests, and secret scan |
| 051-N | Candidate enumeration | [#33](https://github.com/eddiethedean/etlantic/issues/33) | Source, sink, and portable-definition per-node candidates with exact compiler/target support analysis; native-only nodes and native-body overrides receive stable ineligible/rejection records | Complete candidate matrix across portable/I/O/native-ineligible/ambiguous/no-solution fixtures |
| 051-P | Placement selection | [#34](https://github.com/eddiethedean/etlantic/issues/34) | One graph-level constraint evaluator; versioned integer/enum objective vector; bounded deterministic search; explicit fallback records | Exhaustive small-graph oracle, seeded properties, resource budgets, and registration-randomized fingerprints |
| 051-R | Connected regions | [#35](https://github.com/eddiethedean/etlantic/issues/35) | Maximal connected compatible regions, stable identities, topological dependencies, protected semantic boundaries | Branch/join/fan-out/disconnected/security fixtures and explicit-plan compatibility goldens |
| 051-L | Physical lowering | [#36](https://github.com/eddiethedean/etlantic/issues/36) | Seven canonical unit kinds with validated dependencies, execution contract, policy/security envelopes, and directional handoffs | Physical-DAG round trips, tamper tests, interchange proofs, and secret/source-row scan |
| 051-X | Runtime authority | [#37](https://github.com/eddiethedean/etlantic/issues/37) | Whole-DAG admission; physical-unit scheduling/dispatch; explicit handoffs; fused attribution/reliability; namespaced built-in step-report metadata emission; unsupported-consumer rejection | Adaptive-versus-explicit local batch differential suite, legacy report-metadata compatibility fixtures, and compile/control-plane/remote rejection or capability tests |
| 051-E | Explain and diff | [#38](https://github.com/eddiethedean/etlantic/issues/38) | Candidate, selection, rejection, region, topology, interchange, estimate, and fallback explanations across public surfaces | Python/CLI/IDE/notebook parity, deterministic output, redaction, and size/depth-budget tests |
| 051-Q | Conformance and graduation | [#39](https://github.com/eddiethedean/etlantic/issues/39) | Public claim conformance; graph corpus; solver oracle/budgets; heterogeneous end-to-end fixture; differential semantics; legacy runtime-report compatibility; final evidence gate | Truthfulness, determinism, resource-bound, fail-closed, production-trust, report-migration, docs, and stable-foundation reports |
| 051-D | Documentation | [#40](https://github.com/eddiethedean/etlantic/issues/40) | Concepts/quickstart, operations/security/rollback, plugin participation, migration including runtime-report metadata aliases, wire/API/CLI references, release notes | Executed examples, docs build/link checks, migration examples, maturity review, and safety scan |

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

Backlog reconciliation is required before candidate implementation begins. The
issue hierarchy is operational tracking, but stale issue text cannot override
the frozen portable-only `/2` boundary.

| Backlog item | Required reconciliation |
|---|---|
| [Epic #30](https://github.com/eddiethedean/etlantic/issues/30) refined contract | Replace generic Local Python with Local portable compiler; describe fixed rather than configurable/default limits; preserve the 0.50 selection representation rather than reducing every mode to dependency closure |
| [Story #33](https://github.com/eddiethedean/etlantic/issues/33) | Replace native adaptive candidates and native/mixed fixtures with complete native-ineligibility records and explicit-fallback fixtures |
| [Task #50](https://github.com/eddiethedean/etlantic/issues/50) | Candidate kinds are source, sink, and portable compute; native-only and native-body override states are rejection reasons, not candidate kinds |
| [Task #52](https://github.com/eddiethedean/etlantic/issues/52) | Retarget entirely to native-body ineligibility, deterministic rejection, and independently valid explicit `/1` fallback coverage |
| [Task #53](https://github.com/eddiethedean/etlantic/issues/53) | Clarify that preserving `native` policy means a stable adaptive contradiction; `prefer` evaluates portable compilers only and never silently selects a native body |
| [Task #54](https://github.com/eddiethedean/etlantic/issues/54) | Assemble I/O and portable candidate records plus native-ineligibility records; do not merge native candidates into the solver matrix |
| [Story #31](https://github.com/eddiethedean/etlantic/issues/31), [story #37](https://github.com/eddiethedean/etlantic/issues/37), [task #65](https://github.com/eddiethedean/etlantic/issues/65), and [task #69](https://github.com/eddiethedean/etlantic/issues/69) | Replace generic “selection closure” wording with the exact 0.50 `null`-for-full or canonical `selected_nodes` plus sliced-graph representation |
| [Story #38](https://github.com/eddiethedean/etlantic/issues/38), [task #58](https://github.com/eddiethedean/etlantic/issues/58), and [task #74](https://github.com/eddiethedean/etlantic/issues/74) | Show all bounded target alternatives per node; apply the eight-item truncation only to supporting evidence within each node-target record |
| [Task #91](https://github.com/eddiethedean/etlantic/issues/91) | Define `PMADP306` against deterministic canonical byte accounting; retain peak RSS as measured release evidence that cannot influence the selected assignment |
| [Task #95](https://github.com/eddiethedean/etlantic/issues/95) | Name the launch row Local portable compiler rather than generic Local Python |

Until those bodies are updated, the affected acceptance criteria are not
implementation-ready. Their dependency links and milestone membership remain
valid.

## Deterministic Placement Contract

For each logical node, the adaptive planner:

1. enumerates only profile-eligible and trust-approved I/O targets and portable
   compiler/placement targets;
2. rejects candidates that cannot prove the required operations, functions,
   types, semantic modes, contracts, connector behavior, or interchange;
3. applies portable-target overrides, required engines, source/sink constraints,
   native-body ineligibility, and security policy as hard constraints;
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

A complete assignment selects exactly one eligible target for every selected
node and proves a physical boundary for every selected logical edge. Hard
constraint propagation may remove candidates but never reorder survivors.
Weakly connected components may be solved separately only when #57 includes a
proof that composition preserves the complete global tuple, including the two
ordered per-node tie-break vectors; otherwise the solver handles the selected
graph as one problem. The exhaustive oracle verifies both the monolithic and
any decomposed path.

Unknown required capability is ineligible. Unknown optional locality or benefit
is ranked below proven evidence and never becomes a favorable zero. Search uses
ADR-frozen candidate, graph, and work-unit bounds; exhaustion produces a stable
diagnostic or the explicitly permitted baseline fallback, never a wall-clock-
dependent partial answer. Fallback must independently satisfy every trust,
security, contract, capability, and interchange constraint.

## Authoritative Physical-Unit Semantics

The `/1` `PhysicalUnit` record remains advisory and unchanged. These semantics
belong only to `etlantic.physical_unit/1` records embedded in `/2`.

| Kind | Required semantics and boundary |
|---|---|
| `compute` | Executes one portable logical node or a proven same-target fused sequence. It has complete logical attribution and no publication authority |
| `transfer` | Moves a typed artifact across placement targets through one admitted directional interchange descriptor; staging ownership and cleanup are explicit |
| `collection` | Collects partitioned or distributed values into the declared consumer shape and target; it is emitted only when collection is semantically required, not as a generic transfer alias |
| `validation` | Evaluates contract or quality policy as a barrier. It is read-only with respect to publication, and fusion cannot cross it |
| `materialization` | Creates a named durable checkpoint or cache artifact with retention, ownership, idempotency, and cleanup policy |
| `reuse` | Verifies and consumes an existing artifact by fingerprint, contract, authorization, and retention state; a miss follows the preplanned dependency path and never triggers runtime re-placement |
| `publication` | Performs the externally visible sink commit and records a receipt. It is the sole publication boundary and requires idempotency or explicit unknown-outcome reconciliation |

Every unit has a stable id, kind, typed dependency ids, placement-target
identity, ordered logical-node attribution, input/output artifact contracts,
security/policy envelope, retry/attempt policy, and version evidence. Admission
rejects missing logical coverage, cycles, dangling dependencies, unowned staged
artifacts, or multiple unordered publication authorities before any I/O.

## Delivery Increments

Each increment is independently mergeable and leaves every public execution
path safe. An incomplete increment cannot advertise the claim of a later one.

| Increment | Task spine | Merge condition | Public state after merge |
|---|---|---|---|
| **I0 — contract freeze** | #41–#44, #82 | ADR accepted; Profile and `/2` schemas fixed; `/1` golden bytes pass; runtime-report metadata alias and collision rules fixed; exit-gate skeleton names every required artifact | Explicit `/1` unchanged; adaptive remains unavailable |
| **I1 — plan and explain** | #45–#68, #74–#77, #91, #93 | Inventory, node candidates, exact bounded solver, connected regions, seven-kind lowering, explain/diff, oracle, and tamper evidence pass | Adaptive `/2` may be generated and inspected behind opt-in; every execution consumer rejects it before I/O |
| **I2 — local execution** | #88–#90, #69–#73, #92 | Versioned unit protocol, whole-DAG admission, physical scheduling, lifecycle/retry/publication semantics, namespaced step-report emission, and unsupported-consumer matrix pass | Qualified local static-batch fixtures may execute; no availability claim yet |
| **I3 — qualification** | #78–#81, #83–#87, #94–#95 | Public conformance, fixed launch topology, directional pair matrix, differential semantics, documentation, security scan, and final evidence decision pass | Only the published matrix becomes Available |

### Implementation ownership

The split follows the current `etlantic.plan` wire surface,
`etlantic.planning` builder stages, and `etlantic.runtime` execution surface.
It prevents the existing `/1` planner from becoming a second adaptive solver.

| Concern | Repository ownership |
|---|---|
| Profile contract | Extend `src/etlantic/profile.py`, `src/etlantic/_profile/records.py`, and `src/etlantic/schemas/profile.schema.json`; keep existing defaults and explicit serialization goldens |
| `/2` records and codecs | Add schema-specific records under `src/etlantic/plan/adaptive_model.py`, physical records under `src/etlantic/plan/physical.py`, and `/2` codec logic under `src/etlantic/plan/adaptive_serialize.py`; module-level functions in `src/etlantic/plan/serialize.py` dispatch, while `src/etlantic/plan/model.py` stays `/1`-only |
| Adaptive planning stages | Add inventory, candidates, objective, exact solver, region, and lowering stages under `src/etlantic/planning/adaptive_*.py`; `src/etlantic/plan/planner.py` performs strategy dispatch only and retains the explicit build path |
| Admission and execution | Add the unit protocol, whole-DAG admission, and physical scheduler under `src/etlantic/runtime/`; existing `execute.py` and scheduler entry points dispatch only after schema/capability checks |
| Report migration | Update built-in runtime writers plus `src/etlantic/reports/upgrade.py`; third-party metadata is untouched |
| Public projections | Reuse `etlantic.plan`, CLI, inspection, IDE, and notebook adapters over one canonical explain/diff model rather than reimplementing placement logic per surface |
| Tests | Keep `/1` goldens in existing profile/plan/runtime suites; add focused 0.51 profile, codec, planning, physical-DAG, runtime, report-migration, consumer-rejection, and conformance suites beside their owning packages |

Public exports are additive through `etlantic.plan` and the curated root where
appropriate. No implementation task may add adaptive fields to `PipelinePlan`,
teach `/1` physical units to be authoritative, or place solver decisions in a
CLI/runtime adapter.

### Consumer admission by increment

| Consumer | I0 | I1 | I2–I3 |
|---|---|---|---|
| Python `/2` codec and verifier | Schema fixtures only | Read/write/verify supported | Supported |
| `etlantic plan`, `inspect`, explain, and diff projections | Adaptive unavailable | Opt-in `/2` planning and inspection supported | Supported |
| Local runtime and scheduler | Reject `/2` before I/O | Reject `/2` before I/O | Execute only matrix-qualified static-batch combinations after whole-DAG admission |
| Airflow/Prefect and other external compilation | Reject `/2` | Reject `/2` | Reject `/2` throughout 0.51 |
| CP1 acceptance, durable, federated, and remote workers | Reject `/2` | Reject `/2` | Reject `/2` throughout 0.51 |
| Streaming or runtime-expanded execution | Reject `/2` | Reject `/2` | Reject `/2` throughout 0.51 |
| Third-party `/2` consumer | Reject unless exact protocol support is advertised | Same | Still unavailable unless independently qualified and added to the published matrix |

Rejection happens at the first acceptance boundary, before connector discovery,
resource acquisition, data reads, staging, or mutation.

The task-level critical path is:

```text
#41 → #42/#43 → #44/#45 → #46–#54 → #55–#59
    → #62 → #60–#68 → #88/#90 → #69–#73
    → #74–#81/#91–#94 → #87 → #95
```

Documentation drafting starts once its source contract is frozen; it does not
wait for I3. #82 creates and maintains the
[0.51 exit gate](EXIT_GATE_0_51.md), while #95 alone records the final release
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
- Native implementation bodies never appear in an adaptive candidate matrix or
  `/2` physical DAG. Native-only nodes, `portable_transform_policy="native"`,
  and native-body overrides fail adaptive planning or take only the explicitly
  enabled, independently valid `/1` fallback.
- Candidate eligibility is traceable to the digest-bound 0.50.1
  requirement/support evidence. Engine names, installed packages, aggregate
  seven-engine qualification, and the 0.50 adaptive-handoff helper's selected
  value are never authoritative placement inputs by themselves.
- Runtime writers emit only the namespaced built-in step metadata keys.
  `etlantic.run_report/1` readers migrate the four 0.50 bare aliases without a
  warning or data loss, prefer an existing namespaced value on collision, drop
  the bare alias, and produce the same result on repeated migration.
- Partial-run selection preserves the 0.50 `selected_nodes` and sliced-graph
  semantics before placement; both are fingerprinted, physical coverage is
  exact, and runtime selection drift requires re-planning.
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
- Completed [0.51 exit gate](EXIT_GATE_0_51.md) with a dated #95 go/no-go
  decision and no unresolved critical/high phase finding.
- Profile/plan `/1`–`/2` reader-writer, verify-mode, unsupported-consumer, and
  deterministic-fingerprint report.
- Runtime-report metadata namespace compatibility report covering new-writer
  output, 0.50 legacy reads, collision precedence, deterministic reserialization,
  and idempotent migration.
- Capability inventory and candidate truthfulness matrix.
- Digest-bound lineage to the 0.50.1 portable baseline, requirement-support,
  pushdown, adaptive-handoff, dependency/security, and evidence-index inputs.
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
| Runtime-report metadata namespace compatibility | #41, #69–#73, #83–#87, #94 |
| Capability/candidate truthfulness | #45–#54, #78 |
| 0.50.1 evidence lineage and input drift | #45–#54, #78, #82 |
| Solver oracle and resource envelope | #55–#59, #91, #93 |
| Physical-DAG validation and interchange | #60–#68, #79 |
| Admission, execution, lifecycle, and unsupported consumers | #69–#73, #88–#92 |
| Explain/diff parity and redaction | #74–#77 |
| Fixed heterogeneous differential | #80–#81 |
| Operator/plugin/migration documentation | #83–#87, #94 |
| Evidence manifest and final maturity decision | #82, #95 |

## Follow-On Boundary

Statistics-aware costing, provider-specific economic models, telemetry feedback,
bounded runtime replanning, and additional experimental engines beyond DuckDB
require later, separately gated phases. Phase 0.51 establishes no performance
or maturity claim for an engine that has not independently passed its existing
conformance and graduation requirements.
