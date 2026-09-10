---
title: ETLantic 0.51 Implementation Plan
description: Implementation-grade plan for deterministic adaptive heterogeneous execution planning and executable physical DAGs.
plan_status: current
plan_last_reviewed: 0.50.1
---

# ETLantic 0.51 Implementation Plan

> **Status: Phase 0 contract freeze accepted after published ETLantic 0.50.1.**
> [ADR-025](adr/ADR-025-ADAPTIVE-EXECUTION-AND-PHYSICAL-DAG.md) freezes the
> adaptive boundary. Later increments remain evidence-gated; acceptance does
> not claim that adaptive planning or physical-unit execution is available.

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

## Architecture Summary

The existing explicit planner remains intact and is selected by the default
Profile strategy. A thin strategy dispatch in `etlantic.plan.planner` routes an
opted-in adaptive request through a separate, data-only planning pipeline. The
adaptive path consumes the already-sliced logical graph, normalized Profile
policy, authorize-before-load target inventory, and immutable 0.50.1 evidence;
it emits a closed `etlantic.plan/2` document. The local runtime admits that
document as a whole and then schedules physical-unit dependencies. It never
re-runs placement or silently walks the logical graph.

```text
Pipeline/Profile/RunRequest
  -> existing validation and selection slicing
  -> strategy dispatch
       explicit -> existing /1 builder -> existing logical runtime
       adaptive -> inventory -> candidates -> exact solver -> regions
                -> physical lowering -> /2 validation/fingerprint
                -> whole-DAG live admission -> physical scheduler
  -> shared report/explain/diff projections
```

The `/1` and `/2` model classes, builders, and execution paths are deliberately
separate. Shared module-level codecs and public projections may dispatch on the
schema, but a `/1` object never acquires authoritative physical semantics and a
`/2` consumer never falls back to `/1` behavior by accident.

## Change Boundary

### Problem

ETLantic 0.50.1 can execute portable transformations on several engines, but
placement is still selected explicitly and the local scheduler treats physical
units as advisory. There is no public contract that can choose a complete
heterogeneous assignment, prove every boundary, persist it as an authoritative
physical DAG, and execute exactly that DAG.

### Desired outcome

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

### In scope

- four additive Profile policy fields and their JSON Schema/round-trip rules;
- a separate public `etlantic.plan/2` model, JSON Schema, canonical codec,
  fingerprint, and verification path;
- a bounded, side-effect-free inventory, candidate matrix, hard-constraint
  filter, exact placement solver, connected-region builder, and physical DAG
  lowerer;
- authoritative local static-batch execution of the seven physical-unit kinds;
- whole-DAG live admission, dependency scheduling, dispatch, retries,
  cancellation, cleanup, validation, and publication attribution;
- adaptive explain/diff projections through existing Python, CLI, IDE, and
  notebook surfaces;
- the built-in `StepRunReport.metadata` namespace migration;
- public provider conformance helpers, compatibility fixtures, resource gates,
  the fixed Local/Polars/Pandas launch corpus, documentation, and release
  evidence.

### Touched surface

| Area | Existing ownership | Expected 0.51 change |
|---|---|---|
| Profile | `src/etlantic/profile.py`, `src/etlantic/_profile/records.py`, `src/etlantic/schemas/profile.schema.json` | Add and validate adaptive fields; preserve old document reads and explicit `/1` snapshots |
| Plan wire | `src/etlantic/plan/model.py`, `serialize.py`, `upgrade.py`, `__init__.py`, `pipeline-plan.schema.json` | Keep `/1` frozen; add schema-specific `/2` records, schema, codec dispatch, fingerprint, and public union |
| Planning | `src/etlantic/plan/planner.py`, `src/etlantic/planning/` | Add strategy dispatch and isolated adaptive stages; reuse selection slicing and validated evidence only |
| Capability/trust | `src/etlantic/transform/`, `connectors/`, `resources/`, `plugins/`, `interchange/tabular/` | Read bounded descriptors through existing authorize-before-load paths; add only versioned adaptive projection/conformance records |
| Runtime | `src/etlantic/runtime/execute.py`, `scheduler.py`, `orchestrator.py`, `executors/` | Add `/2` admission and physical scheduling/dispatch without changing `/1` scheduling |
| Reports | `src/etlantic/extensions.py`, `src/etlantic/reports/upgrade.py`, built-in writers in `runtime/orchestrator.py` | Migrate four built-in step keys while retaining `etlantic.run_report/1` |
| Public projections | `src/etlantic/plan/explain.py`, `diff.py`, CLI, IDE/LSP and notebook adapters | Dispatch over `PlanDocument`; project records without replanning |
| First-party launch targets | local compiler plus `packages/etlantic-polars` and `packages/etlantic-pandas` | Advertise/verify required physical execution and fusion support; no unrelated compiler semantics expansion |
| Tests/evidence/docs | `tests/profile`, `tests/plan`, `tests/runtime`, `tests/compatibility`, `tests/portable_conformance`, `scripts/`, `docs/` | Add 0.51 contract, oracle, differential, security, migration, and release evidence |

### Explicitly out of scope

- native transformation bodies as adaptive candidates;
- SQL, PySpark, DataFusion, DuckDB, remote warehouses, external orchestrators,
  durable/federated workers, streaming, and runtime-expanded graph execution as
  **Available** `/2` consumers;
- cost currency, live statistics, trial execution, telemetry feedback,
  speculative execution, or runtime replanning;
- multi-node fragment-cover search, overlapping fragments, or join reordering;
- a stored `/2` to `/1` downgrade or mutation of `/1` wire records;
- renaming third-party metadata, logical-plan metadata, or unrelated extension
  keys;
- fixing unrelated engine/compiler defects unless they invalidate a proposed
  0.51 qualification row.

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

### Required behavior

The public Profile additions are exactly these four fields:

```python
execution_strategy: Literal["explicit", "adaptive"] = "explicit"
placement_targets: dict[str, PlacementTarget] = field(default_factory=dict)
eligible_targets: tuple[str, ...] = ()
adaptive_fallback: Literal["error", "explicit"] = "error"
```

`PlacementTarget` is a frozen public value with these fields and no secret
payload:

```python
engine: str
compiler: str | None = None
executor: str | None = None
connector: str | None = None
resource: str | None = None
location: str = "local"
security_domain: str = "default"
required_capabilities: tuple[str, ...] = ()
version_constraints: dict[str, str] = field(default_factory=dict)
```

The enclosing mapping key is the stable human-facing target id. `compiler`,
`executor`, `connector`, and `resource` are discovery/reference keys, never
import paths or live objects. `resource` refers to a key in `Profile.resources`.
`version_constraints` maps the referenced package/protocol identity to a
specifier accepted by the existing plugin compatibility machinery. The
canonical discovered descriptor—not the Profile key alone—produces the target
identity fingerprint.

Profile construction and `Profile.from_dict()` reject an unknown strategy or
fallback, blank target ids, duplicate eligible ids, eligible ids missing from
`placement_targets`, unknown target fields, non-string references, an adaptive
profile with no eligible targets, and resolved secret-like values anywhere in a
target. Adaptive planning also rejects non-local orchestrators, streaming, and
runtime-expanded graphs in 0.51. Explicit profiles may carry dormant target
definitions, but the existing `/1` profile snapshot projection omits all four
adaptive fields so ordinary `/1` bytes remain unchanged.

The public return contract is:

- `Pipeline.plan()` and `plan_pipeline()` return `PipelinePlan` for explicit
  strategy and `AdaptivePipelinePlan` for successful adaptive strategy;
- `plan_pipeline_with_report()` returns `PlanDocument | None` plus the existing
  validation report;
- `plan_from_json()`, `plan_to_json()`, `plan_fingerprint()`, and
  `verify_plan_fingerprint()` accept/return the public `PlanDocument` union and
  dispatch strictly by `schema`;
- `Pipeline.run()` and `Pipeline.arun()` continue returning
  `PipelineRunReport`; the runtime dispatch is internal and schema-driven;
- explain and diff return the existing JSON-serializable public projection
  shapes with additive adaptive sections; and
- compile, control-plane, durable, remote, federated, streaming, and unknown
  third-party consumers reject `/2` with `PMADP500` before external I/O.

Profile shape errors remain `ValueError`/schema-validation errors. Adaptive
planning infeasibility uses `PipelineValidationError` with one or more stable
`PMADP1xx`–`PMADP3xx` diagnostics. Wire/integrity errors use the existing
`UnsupportedPlanSchemaError` or `ValueError` boundary. Admission or execution
failures use `PipelineExecutionError` with `PMADP4xx`–`PMADP5xx`. No error path
returns a partial `/2` plan.

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

The following codes are the minimum frozen set. Implementations may add codes
only inside the owning range and must update the diagnostic catalog and public
fixtures in the same change.

| Code | Required trigger |
|---|---|
| `PMADP100` | Unknown `execution_strategy` or `adaptive_fallback` value |
| `PMADP101` | Invalid placement-target shape, identity field, or secret-like value |
| `PMADP102` | Duplicate/unknown eligible target or adaptive mode with no eligible target |
| `PMADP103` | Adaptive mode requested for a non-local orchestrator |
| `PMADP120` | `portable_transform_policy="native"` or a native-only selected node in adaptive mode |
| `PMADP121` | Run/Profile override names a target outside the eligible trusted portable set |
| `PMADP122` | Runtime selection differs from the fingerprinted `/2` logical scope |
| `PMADP123` | Explicit fallback requested but the independent `/1` plan is invalid or unavailable |
| `PMADP124` | Stored `/2` downgrade requested |
| `PMADP200` | Target, plugin, provider, connector, or adapter fails trust/allowlist admission |
| `PMADP201` | Target identity or protocol/version descriptor is incomplete or conflicting |
| `PMADP202` | Required evidence is missing, invalid, unqualified, or has drifted |
| `PMADP220` | Candidate matrix is incomplete, duplicated, or references an unknown node/target |
| `PMADP221` | Portable requirement is unsupported, unavailable, conditional, or unknown where proof is required |
| `PMADP222` | No eligible portable definition/compiler exists for a selected compute node |
| `PMADP240` | Required source/sink locality or pushdown is not positively proved |
| `PMADP241` | Producer/consumer contract or security policy makes a boundary infeasible |
| `PMADP242` | Required directional interchange/collection/materialization path is unavailable |
| `PMADP300`–`PMADP306` | The corresponding fixed resource limit in the table below is exceeded |
| `PMADP320` | No complete feasible assignment exists after hard constraints |
| `PMADP321` | Candidate objective facts or resulting objective tuple are invalid |
| `PMADP322` | Solver replay/oracle evidence does not reproduce the selected assignment |
| `PMADP400` | Unknown `/2` section, unit kind, dependency kind, or protocol version |
| `PMADP401` | Adaptive plan/unit fingerprint or referenced identity does not verify |
| `PMADP402` | Physical DAG has a cycle, dangling dependency, or invalid topological order |
| `PMADP403` | Physical-to-logical coverage is missing, duplicate, or includes unselected nodes |
| `PMADP404` | Artifact ownership, cleanup authority, or publication authority is invalid |
| `PMADP500` | Consumer does not advertise exact `/2` and physical-unit protocol support |
| `PMADP501` | Whole-DAG live admission detects authorization, capability, resource, or evidence drift |
| `PMADP502` | Static-batch restriction is violated by streaming or runtime graph expansion |
| `PMADP520` | Planned target executor or unit kind cannot be dispatched exactly |
| `PMADP521` | A unit dependency fails or is cancelled; dependents are not started |
| `PMADP522` | Retry, timeout, or cancellation policy cannot preserve logical semantics |
| `PMADP523` | Staged-artifact cleanup fails and requires operator reconciliation |
| `PMADP524` | Publication outcome is unknown and requires idempotent reconciliation |

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

## Cross-Cutting Invariants

- **Validation:** a `/2` document is executable only after schema, fingerprint,
  logical coverage, topology, unit protocol, candidate-decision, target, and
  evidence-reference validation all succeed.
- **Determinism:** canonical ordering is derived from sliced logical topological
  order, eligible-target order, stable ids, and canonical JSON. Registry or map
  insertion order, process hash seed, timing, concurrency, and allocator state
  cannot change a plan or explanation.
- **Type and contract safety:** every physical edge names an input/output
  artifact contract. A conversion, collection, or transfer exists only when a
  directional mechanism proves the required fidelity.
- **Trust:** static manifest evaluation and allowlist authorization precede
  plugin/provider loading. Planning never imports a denied candidate merely to
  explain its denial.
- **Data safety:** planning is data-free and secret-free. Plans, explanations,
  diagnostics, reports, evidence, and failure messages contain references,
  digests, bounded metadata, and redacted public configuration only.
- **Runtime authority:** no physical unit starts until whole-DAG admission has
  succeeded. Runtime cannot add a target, unit, edge, fallback, or placement.
- **Lifecycle:** each staged artifact has one owner and deterministic cleanup
  authority. Dependents never run after an unsatisfied dependency. Cancellation
  stops new scheduling before cleanup/reconciliation.
- **Publication:** publication units are the only sink-commit authority. Retry
  requires idempotency or an explicit reconciliation protocol; an unknown
  outcome is never reported as success.
- **Idempotency:** codec migration, plan verification, report-key migration,
  admission of unchanged inputs, and cleanup of already-removed owned staging
  artifacts are repeatable with the same result.
- **Compatibility:** explicit `/1` planning and execution do not traverse any
  adaptive stage. Existing public plugin protocols remain valid for explicit
  use even when they do not participate in `/2`.

## Edge Cases and Failure Modes

| Case | Required outcome |
|---|---|
| Empty graph or empty partial selection | Existing selection validation fails; no inventory discovery occurs |
| Duplicate or missing eligible target | Profile validation emits `PMADP102`; no plugin load occurs |
| Eligible target package absent | Candidate is `rejected` with unavailable evidence; planning continues only if another complete assignment exists |
| Native-only selected node or native override | Complete rejection records use `PMADP120`/`PMADP121`; permitted fallback independently produces `/1`, otherwise planning fails |
| Unknown required capability or stale evidence digest | Candidate is ineligible with `PMADP202` or `PMADP221`; unknown never scores as zero or favorable |
| Multiple disconnected branches on one target | Separate connected regions with deterministic ids and dependencies |
| Fan-out across targets | One producer artifact has explicit ownership; each directional transfer/collection is represented and cleanup is ordered after all consumers |
| Join with incompatible input targets | Solver includes all required input boundaries or rejects the assignment; it cannot collect implicitly at runtime |
| Validation/materialization/publication boundary inside a same-target run | Fusion stops at the boundary; the corresponding physical unit remains explicit |
| Resource limit reached exactly | Value at the published ceiling is accepted; the first value above it emits the matching `PMADP30x` outcome |
| Solver exhaustion before a complete optimum | No approximate `/2`; emit `PMADP304` and fail or regenerate an admitted `/1` fallback |
| Tampered, cyclic, incomplete, or unknown `/2` | Deserialize/verify/admission fails before discovery or I/O with `PMADP400`–`PMADP404` |
| Runtime target/version/authorization drift | Whole-DAG admission emits `PMADP501`; zero units start |
| Runtime selection differs from stored scope | Emit `PMADP122`; require replanning |
| Unit failure with concurrent ready work | Stop admitting newly dependent work; honor cancellation policy, await/cancel already-running independent work as declared, then clean owned staging |
| Cancellation during transfer/materialization | Do not publish; close handles and clean only owned artifacts; record cleanup or reconciliation diagnostics |
| Publication timeout or lost acknowledgement | Record `PMADP524` unknown outcome; do not retry unless the connector proves idempotent reconciliation |
| Legacy and namespaced report key collide | Namespaced value wins, bare alias is removed, no warning is emitted, and a second migration is identical |
| Unsupported `/2` consumer | Emit `PMADP500` at its first acceptance boundary before connector/resource/plugin activity |

## Security and Reliability Contract

Planning receives immutable public descriptors only. It may read bounded static
manifests and checked-in evidence after authorization, but cannot resolve a
`SecretRef`, open a connector, list a source, acquire a resource, execute a
compiler target, invoke user code, or perform a write. Production discovery
uses the existing plugin, optimization-pass, schema-registry, and
resource-provider allowlists; connector and interchange admission also preserve
tenant, workspace, environment, security-domain, residency, classification,
masking, and outbound policy.

Runtime admission rechecks every mutable authorization, selected package and
protocol version, resource reference, connector, compiler/executor, contract,
and directional handoff. Admission is atomic with respect to scheduling: either
the complete DAG is admitted or no unit is submitted. The scheduler uses a
bounded ready queue and existing concurrency/timeout controls. Unit result
recording precedes dependent readiness, and publication receipts or explicit
unknown outcomes are durable in the run report before final success is emitted.

## Compatibility Contract

| Compatibility axis | Required 0.51 behavior |
|---|---|
| Existing Python API | Current Profile, Pipeline, planner, runtime, explain, diff, and report calls remain source-compatible; additions are optional and additive |
| Explicit behavior | Default strategy is `explicit`; ordinary plans retain canonical `/1` bytes, fingerprints, logical scheduling, outputs, and failure behavior |
| Profile documents | Older Profile JSON loads with adaptive defaults. New Profile JSON may contain the four additive fields; explicit `/1` snapshots omit them |
| Plan documents | New readers accept `/1` and `/2`; `PipelinePlan` and `PLAN_SCHEMA` remain `/1`; old readers/consumers reject `/2`; no downgrade exists |
| Run reports | Schema remains `etlantic.run_report/1`; four 0.50 bare step aliases read silently and normalize to namespaced keys; unknown third-party keys follow existing policy |
| Plugins | Existing protocol implementations remain valid for explicit execution. Adaptive participation requires exact advertised protocol/capability/evidence support and never occurs by installation alone |
| Runtime versions | Python 3.11, 3.12, and 3.13 remain supported; Linux, macOS, and Windows core behavior remains gated in CI |
| Optional dependencies | Core import and explicit local operation remain optional-dependency clean; adaptive target packages are loaded only when selected and authorized |
| Persisted state | Existing `/1` plans, Profile fixtures, run reports, artifacts, checkpoints, and publication receipts remain readable under their current retention guarantees |

## Recommended Implementation

The required behavior above is authoritative. Internal names may adapt when the
repository makes a different private split materially simpler, provided public
types, wire fields, diagnostics, invariants, ACs, and evidence remain unchanged.

- Use frozen `slots=True` dataclasses plus existing `deep_freeze`/`mutable_copy`
  conventions for `/2` records. Keep each record's validation next to its
  `to_dict`/`from_dict` implementation.
- Introduce `adaptive_model.py`, `physical.py`, and `adaptive_serialize.py`
  instead of adding conditional fields to `plan/model.py`. Let
  `plan/serialize.py` parse the schema and delegate.
- Represent inventory, candidates, solver state, and explanations as immutable
  data records. Do not pass live plugin objects beyond the discovery/analyzer
  boundary; retain stable keys and evidence digests.
- Build one pure hard-constraint predicate and one pure objective function used
  by both the production branch-and-bound solver and independent test oracle.
  The oracle enumerates independently but compares the same frozen objective
  tuple.
- Build regions and physical units from the chosen assignment in separate pure
  stages. Validate after each stage and again at wire/runtime admission.
- Add `AdaptiveAdmission` and `PhysicalScheduler` collaborators behind the
  existing local scheduler rather than branching throughout
  `LocalOrchestrator`. Existing engine execution helpers remain target adapters.
- Reuse the current report model and add a narrow migration helper for the four
  engine aliases. Do not introduce `etlantic.run_report/2` for this migration.
- Generate release evidence through dedicated `scripts/check_adaptive_0_51.py`
  and bounded fixture builders; do not hand-edit passing status into evidence.

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

Phase 0 performs these body updates before production code begins. The plan is
ready to start at Phase 0; the stale text is an administrative sequencing gate,
not an unresolved architecture decision. Existing dependency links and
milestone membership remain valid.

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

## Concrete Implementation Sequence

Each phase below is a reviewable merge boundary. A later phase may be developed
in parallel only against merged contracts from its dependencies. New public
behavior remains unavailable until the phase's merge gate passes.

### Phase 0 — Contract and backlog freeze

- **Goal:** remove contradictory task language and record every public/wire
  decision before production code.
- **Files:** new ADR under `docs/11_DEVELOPMENT/adr/`; this plan; the exit gate;
  diagnostic and surface inventories; GitHub #30–#95 bodies identified in the
  backlog-reconciliation table.
- **Behavior:** freeze the four Profile fields, `PlacementTarget`, `/2` and
  physical-unit schemas, exact diagnostics, resource limits, consumer matrix,
  metadata aliases, fallback, selection, and rollback rules.
- **Verification:** `scripts/check_docs.py`, `scripts/check_surface_inventory.py`,
  `scripts/check_diagnostic_stability.py`, docs build, and a machine-readable
  contract fixture consumed by later tests.
- **Depends on:** nothing. **Merge gate:** #41 and #82 accepted; contradictory
  backlog language removed. No production implementation starts before this
  gate.

### Phase 1 — Profile policy and report-reader compatibility

- **Goal:** introduce opt-in policy without changing explicit planning and make
  legacy report reads ready before new writers ship.
- **Files:** `src/etlantic/profile.py`, `_profile/records.py`,
  `schemas/profile.schema.json`, `extensions.py`, `reports/upgrade.py`, public
  exports, profile templates, `tests/profile/test_adaptive_profile_0_51.py`, and
  `tests/reports/test_metadata_namespace_0_51.py`.
- **Behavior:** validate/canonicalize `PlacementTarget` and the four fields;
  preserve old Profile reads; preserve explicit `/1` snapshot bytes; migrate
  the four bare built-in step aliases with namespaced-wins collision behavior.
- **Verification:** constructor/schema negatives, JSON round trips, secret-key
  rejection, old fixture loads, explicit `/1` goldens, no-warning migration,
  collision, idempotency, and deterministic reserialization.
- **Depends on:** Phase 0. **Merge gate:** #42 plus the reader half of the
  metadata migration pass; adaptive planning still returns an unavailable
  diagnostic.

### Phase 2 — Closed `/2` and physical-unit wire model

- **Goal:** make adaptive plans representable and verifiable without making
  them executable.
- **Files:** new `src/etlantic/plan/adaptive_model.py`, `physical.py`,
  `adaptive_serialize.py`, new `schemas/adaptive-pipeline-plan.schema.json` and
  `schemas/physical-unit.schema.json`; dispatch changes in `plan/serialize.py`,
  `plan/upgrade.py`, `plan/__init__.py`, and curated root exports;
  `tests/plan/test_adaptive_wire_0_51.py`.
- **Behavior:** implement `AdaptivePipelinePlan`, every required nested record,
  `PlanDocument`, strict schema dispatch, canonical fingerprinting, deep freeze,
  unknown-field/kind rejection, and no downgrade. `/1` classes and bytes remain
  unchanged.
- **Verification:** `/2` round-trip and JSON Schema parity, verify true/false,
  one-field tampering for every section, unknown section/unit/dependency,
  missing decision references, deep immutability, `/1` golden matrix, and old
  consumer rejection.
- **Depends on:** Phase 1. **Merge gate:** #43–#44; all execution consumers
  still reject `/2` with `PMADP500`.

### Phase 3 — Trusted inventory and evidence lineage

- **Goal:** produce the complete bounded set of Profile-eligible target
  descriptors without touching a data plane.
- **Files:** new `src/etlantic/planning/adaptive_inventory.py`; bounded adapters
  over `transform/discovery.py`, plugin coordinator, connectors, resources, and
  tabular interchange; `tests/planning/test_adaptive_inventory_0_51.py`.
- **Behavior:** validate Profile ids first; authorize manifests before load;
  resolve only eligible keys; canonicalize target identity/version/capability
  descriptors; bind exact 0.50.1 evidence digests; build the directional
  interchange matrix; reject drift and denied targets explicitly.
- **Verification:** randomized registry order, denied-import sentinels, missing
  package/version/protocol/evidence cases, duplicate identity, directional
  handoff asymmetry, bounded metadata, and secret/source-row scans.
- **Depends on:** Phase 2. **Merge gate:** #45–#49; inventory fingerprint and
  diagnostics reproduce from fixture inputs.

### Phase 4 — Complete candidate matrix

- **Goal:** explain eligibility for every selected node × eligible target before
  optimization.
- **Files:** new `src/etlantic/planning/adaptive_candidates.py` and candidate
  records in the `/2` model; `tests/planning/test_adaptive_candidates_0_51.py`.
- **Behavior:** enumerate source, sink, and portable compute records only;
  preserve one record per matrix cell; invoke bounded `analyze()` but never
  `compile()`, `execute()`, or user code; apply overrides and native
  ineligibility; derive objective facts solely from proved evidence.
- **Verification:** complete/duplicate/missing cell checks, portable exact and
  lowering support, unavailable compiler, unknown required capability,
  source/sink locality, native-only/native override, explicit fallback input,
  and analyzer side-effect sentinels.
- **Depends on:** Phase 3. **Merge gate:** #50–#54; matrix size and ordering are
  deterministic and every rejection has a stable code.

### Phase 5 — Exact bounded placement solver

- **Goal:** select the globally best complete feasible assignment or return one
  stable failure.
- **Files:** new `adaptive_objective.py` and `adaptive_solver.py`;
  `tests/planning/test_adaptive_solver_0_51.py`, independent
  `tests/planning/adaptive_oracle.py`, and resource-gate script support.
- **Behavior:** apply one hard-constraint predicate; compare the frozen tuple;
  traverse in canonical order; count work units/bytes; use only proof-safe
  branch-and-bound; emit a complete decision set, `PMADP320`, or a permitted
  independently generated `/1` fallback.
- **Verification:** exhaustive oracle through the published small-graph bound,
  seeded graph/registry permutations, tie-break boundaries, disconnected
  component equivalence, exact-limit/over-limit cases, replay seeds, and proof
  that wall-clock timing cannot affect output.
- **Depends on:** Phase 4. **Merge gate:** #55–#59, #91, and solver portions of
  #93 pass with identical fingerprints across repeated runs.

### Phase 6 — Connected regions and physical lowering

- **Goal:** turn an assignment into one closed, executable physical topology.
- **Files:** new `adaptive_regions.py`, `adaptive_lowering.py`, physical
  validators, `tests/planning/test_adaptive_regions_0_51.py`, and
  `tests/plan/test_physical_dag_0_51.py`.
- **Behavior:** partition maximal connected compatible regions; preserve every
  protected boundary; lower seven unit kinds and every cross-region edge;
  assign typed dependencies, contracts, ownership, lifecycle, retry,
  publication authority, and complete logical attribution.
- **Verification:** chains, diamonds, joins, fan-out, disconnected same-target
  branches, partial selections, all protected boundaries, fused/unfused parity,
  all seven kinds, cycle/dangling/coverage tampering, handoff direction, cleanup
  ownership, and publication uniqueness.
- **Depends on:** Phase 5. **Merge gate:** #60–#68; schema round trips and
  physical validation pass before explain or runtime integration.

### Phase 7 — Explain and diff projections

- **Goal:** expose decisions without recomputing them.
- **Files:** `src/etlantic/plan/explain.py`, `diff.py`, CLI plan/inspect/diff
  commands, IDE/LSP schemas/commands, notebook adapter, and
  `tests/plan/test_adaptive_explain_0_51.py`.
- **Behavior:** project every selected/lower-ranked/rejected alternative,
  objective component, region/fusion boundary, physical edge, handoff,
  unavailable estimate, truncation marker, and fallback from the stored plan.
- **Verification:** Python/CLI/IDE/notebook JSON parity, semantic diff fixtures,
  no-replanning sentinels, ordering permutations, 4 MiB boundary, per-record
  evidence truncation, and secret/source-row redaction.
- **Depends on:** Phase 6. **Merge gate:** #74–#77; explicit explain/diff
  fixtures remain compatible.

### Phase 8 — Whole-DAG admission and physical execution protocol

- **Goal:** define the live trust boundary and executor contract before any `/2`
  unit can run.
- **Files:** new `src/etlantic/runtime/adaptive_admission.py`,
  `physical_protocol.py`, and `physical_scheduler.py`; dispatch changes in
  `runtime/execute.py`, `scheduler.py`, executor registry, and explicit
  rejection adapters; `tests/runtime/test_adaptive_admission_0_51.py`.
- **Behavior:** require exact plan/unit/capability versions; recheck every live
  dependency; admit atomically before resource acquisition; reject unsupported
  consumers and runtime selection drift; construct the ready queue solely from
  physical dependencies.
- **Verification:** import/load/I/O/mutation sentinels for every admission
  failure, capability/version/authorization drift, unsupported consumer matrix,
  streaming/runtime-expansion rejection, dependency order, and concurrency
  bounds.
- **Depends on:** Phase 6; may proceed in parallel with Phase 7. **Merge gate:**
  #88, #90, #92; `/2` remains execution-disabled until Phase 9 adapters pass.

### Phase 9 — Local adapters, lifecycle, and report writers

- **Goal:** execute only the initially qualified local static-batch topologies
  with `/2` as authority.
- **Files:** physical scheduler/admission modules, `runtime/orchestrator.py`,
  existing dataframe/local execution helpers, Polars/Pandas packages as needed,
  and `tests/runtime/test_adaptive_execution_0_51.py`.
- **Behavior:** dispatch compute to the planned compiler/executor; execute
  transfer/collection/materialization/validation/reuse/publication units;
  preserve logical retry/cancellation/timeout/publication semantics and fused
  step attribution; emit only namespaced built-in step metadata.
- **Verification:** unit failure injection at every boundary, concurrent branch
  ordering, retry-safe and unsafe publication, cancellation during handoff,
  cleanup/reconciliation, partial run, fused attribution, report migration, and
  adaptive-versus-explicit output/lifecycle differential tests.
- **Depends on:** Phases 6 and 8. **Merge gate:** #69–#73 and #89; only fixture-
  gated Local/Polars/Pandas combinations can execute.

### Phase 10 — Public conformance, documentation, and graduation

- **Goal:** prove and publish exactly the supported 0.51 claim.
- **Files:** `src/etlantic/testing/adaptive.py`, fixed conformance fixtures,
  `scripts/check_adaptive_0_51.py`, evidence directory, concepts/quickstart,
  operations/rollback, backend participation, migration/API/CLI docs, roadmap,
  and release notes.
- **Behavior:** expose third-party conformance without granting maturity; run
  the fixed Polars→Pandas and reverse topology; publish weakest-link maturity;
  keep every unqualified row Experimental/unavailable; provide rollback for new,
  queued, and in-flight `/2` work.
- **Verification:** #78–#87 and #93–#95 evidence, full CI on Python 3.11–3.13
  and supported OSes, all existing release/stable-foundation gates, docs build
  and links, runnable examples, and final no-go review.
- **Depends on:** Phases 7 and 9. **Merge gate:** #95 records a dated decision
  and every required artifact in the exit gate verifies from its command.

## Acceptance Criteria

- **AC-001 — Explicit compatibility:** A Profile without
  `execution_strategy="adaptive"` produces the same canonical `/1` bytes,
  fingerprint, selected logical graph, runtime behavior, and observable report
  as 0.50.1 for every compatibility fixture.
- **AC-002 — Profile contract:** The four adaptive fields and
  `PlacementTarget` round-trip through Python and JSON Schema; every invalid,
  duplicate, missing, unknown, or secret-bearing form is rejected with the
  specified error before discovery.
- **AC-003 — Adaptive wire:** A successful adaptive plan is a deeply immutable,
  schema-valid `AdaptivePipelinePlan` with schema `etlantic.plan/2`; all required
  sections round-trip canonically and participate in fingerprint verification.
- **AC-004 — Wire/consumer rejection:** Unknown or tampered `/2` content and
  every unsupported `/2` consumer fail with the specified diagnostic before
  connector discovery, resource acquisition, data reads, staging, or mutation;
  no stored downgrade is available.
- **AC-005 — Fallback:** With fallback `error`, infeasibility returns no plan.
  With fallback `explicit`, only a separately valid explicit build returns `/1`
  and exactly one `etlantic.adaptive_fallback` metadata record; no partial or
  approximate `/2` is emitted or run.
- **AC-006 — Portable/override boundary:** Request overrides take precedence
  over Profile overrides. An eligible portable-target override constrains the
  matrix; an ineligible target, native body, native-only node, or `native`
  policy fails adaptively or follows AC-005 without executing user code.
- **AC-007 — Trusted inventory:** The inventory contains every and only ordered
  Profile-eligible targets whose manifests pass all applicable allowlists before
  load; canonical identities include the frozen placement fields and versions.
- **AC-008 — Evidence lineage:** Every positive capability, lowering, locality,
  pushdown, contract, and handoff fact references validated immutable evidence,
  including the exact 0.50.1 input digest; missing or drifted evidence makes the
  affected candidate ineligible.
- **AC-009 — Candidate truthfulness:** The stored matrix has exactly one record
  for every selected node × eligible target, retains all rejections, and admits
  only supported source, sink, or portable-compute candidates. Installed engine
  names and unknown evidence never establish eligibility or positive rank.
- **AC-010 — Exact deterministic placement:** For identical logical scope,
  Profile, target inventory, and evidence, planning returns the same complete
  assignment, objective tuple, explanation, and `/2` fingerprint across process
  hash seeds and semantic-preserving graph/registry permutations; the assignment
  matches the independent oracle corpus.
- **AC-011 — Resource bounds:** Every published count/byte/work-unit ceiling
  accepts its exact boundary and rejects the first excess with `PMADP300`–
  `PMADP306`; timing and measured RSS never select a different assignment.
- **AC-012 — Selection:** Full, `run_one`, `run_until`, and explicit-node
  selections retain the 0.50.1 canonical sliced graph and `selected_nodes`
  representation; `/2` covers exactly that scope, and a different runtime
  selection emits `PMADP122`.
- **AC-013 — Connected regions/fusion:** Every selected node occurs in exactly
  one maximal connected compatible region. Disconnected same-target branches
  remain separate, and fusion never crosses a frozen effect, retry, checkpoint,
  selection, security, validation, materialization, or publication boundary.
- **AC-014 — Physical DAG:** All seven unit kinds validate and round-trip; every
  logical node and edge has exact physical attribution, every cross-target edge
  has an executable directional boundary, topology is acyclic, and ownership,
  cleanup, validation, and publication authority are unambiguous.
- **AC-015 — Explain/diff:** Python, CLI, IDE, and notebook projections expose
  the same stored selections, lower-ranked viable alternatives, rejections,
  objective values, regions, fusion decisions, physical topology, handoffs,
  unavailable estimates, and fallback without replanning; output is bounded,
  deterministic, and redacted.
- **AC-016 — Atomic admission:** The local runtime verifies the complete live
  `/2` dependency set and mutable policy before starting any unit. Any trust,
  version, capability, contract, resource, authorization, selection, or evidence
  drift starts zero units and emits the owning `PMADP4xx`/`PMADP5xx` diagnostic.
- **AC-017 — Runtime authority:** For a qualified adaptive plan, the local
  scheduler derives readiness only from physical-unit dependencies and dispatches
  exactly the stored target/unit; it never walks the logical graph as a fallback
  or performs runtime placement.
- **AC-018 — Lifecycle and publication:** Dependency failure, retry, timeout,
  cancellation, transfer, collection, materialization, reuse, validation,
  cleanup, and publication preserve explicit-baseline semantics. Publication is
  committed once or recorded as an explicit unknown outcome requiring
  reconciliation, and fused units retain per-logical-step attribution.
- **AC-019 — Report migration:** New built-in writers emit only
  `etlantic.dataframe`, `etlantic.sql`, `etlantic.spark`, and
  `etlantic.spark_schema`. Readers silently normalize 0.50 bare aliases,
  namespaced values win collisions, aliases disappear, and repeat migration and
  reserialization are identical under `etlantic.run_report/1`.
- **AC-020 — Differential semantics:** The fixed Local-only, Polars-only,
  Pandas-only, Polars→Pandas, and Pandas→Polars fixtures produce equivalent
  outputs, validation outcomes, logical lifecycle/report attribution, retry,
  cancellation, cleanup, and publication results under adaptive and explicit
  plans.
- **AC-021 — Fail-closed non-scope:** Streaming/runtime-expanded graphs and
  compile, Airflow, Prefect, control-plane, durable, remote, federated, or
  unqualified third-party `/2` consumers reject with stable diagnostics before
  external I/O.
- **AC-022 — Security:** Production planning never loads or selects a denied
  plugin, optimization pass, connector, resource provider, or applicable
  schema-registry adapter, never crosses the frozen policy domains, and no plan,
  evidence, diagnostic, explanation, report, or fixture contains a resolved
  secret or source row.
- **AC-023 — Qualification truthfulness:** Only rows with passing independent
  evidence are marked Available; DuckDB remains Experimental unless its own row
  passes, and all other engine/provider/consumer combinations retain their
  prior or unavailable maturity.
- **AC-024 — Release integrity:** All affected core, planner, optimizer,
  interchange, runtime, plugin, conformance, compatibility, stable-foundation,
  packaging, documentation, and supported Python/OS CI gates pass, with no open
  critical/high defect attributable to 0.51.

## Verification Matrix

| Acceptance | Preferred proof | Required fixture, suite, or artifact |
|---|---|---|
| AC-001 | Compatibility + integration | `/1` byte/fingerprint burn-in matrix; explicit runtime differential |
| AC-002 | Unit + contract + static gate | Adaptive Profile constructor/from-dict tests and Profile JSON Schema |
| AC-003 | Contract + property | `/2` round-trip, deep-freeze, schema parity, canonical-order properties |
| AC-004 | Contract + security integration | Tamper/unknown-field matrix and pre-I/O consumer sentinels |
| AC-005 | Integration + compatibility | No-solution/exhaustion/fallback matrix and `/1` metadata golden |
| AC-006 | Unit + integration | Request/Profile precedence, native-ineligible, and no-user-code fixtures |
| AC-007 | Security integration + property | Authorize-before-load sentinels and randomized inventory order |
| AC-008 | Contract + compatibility | 0.50.1 digest lineage, missing/drifted/invalid evidence fixtures |
| AC-009 | Unit + property | Complete Cartesian matrix, duplicate/missing record, truthful support tests |
| AC-010 | Oracle + property | Exhaustive small-graph oracle and seeded metamorphic campaign |
| AC-011 | Boundary + static gate | Exact/first-excess limits and deterministic byte/work accounting report |
| AC-012 | Compatibility + integration | Existing selection corpus plus `/2` coverage and runtime drift rejection |
| AC-013 | Unit + property | Chain/diamond/join/fan-out/disconnected and protected-boundary goldens |
| AC-014 | Contract + property + security | Seven-kind round trips, topology/tamper matrix, ownership/publication checks |
| AC-015 | Contract + parity + security | Python/CLI/IDE/notebook goldens, truncation limits, secret/source-row scan |
| AC-016 | Integration + fault injection | Whole-DAG admission matrix with zero-I/O/zero-unit-start sentinels |
| AC-017 | Integration | Physical dependency scheduler traces and no-logical-fallback sentinel |
| AC-018 | Integration + chaos | Per-unit failure/cancellation/retry/cleanup/publication campaign |
| AC-019 | Migration + compatibility | 0.50 report fixtures, collision/idempotency/no-warning writer-reader matrix |
| AC-020 | Differential integration | Fixed five-row launch corpus with output and lifecycle comparisons |
| AC-021 | Security integration | Unsupported consumer/static-batch rejection matrix |
| AC-022 | Security + static gate | Production allowlist matrix and recursive secret/source-row scans |
| AC-023 | Contract + manual release decision | Signed evidence manifest, weakest-link matrix, #95 go/no-go record |
| AC-024 | CI + packaging + docs | Full `checks.yml`, release/stable-foundation scripts, wheel tests, docs/link build |

## Risks

| Risk | Consequence | Mitigation / blocking gate |
|---|---|---|
| `/2` logic leaks into `/1` | Breaks stable bytes, readers, or explicit runtime | Separate models/builders; AC-001 goldens on every contract/runtime merge |
| Installed plugin is treated as eligible | Trust bypass or nondeterministic inventory | Profile-closed ids and authorize-before-load sentinels; AC-007/AC-022 |
| Candidate analysis performs live work | Data/secret exposure during planning | Data-only analyzer protocol, hostile sentinels, immutable evidence; AC-008/AC-009 |
| Solver objective is ambiguous or local-greedy | Non-optimal or nondeterministic placement | Frozen tuple, single predicate, exhaustive oracle, replay seeds; AC-010/AC-011 |
| Region fusion erases semantic boundaries | Incorrect retry, validation, or publication behavior | One conservative boundary predicate and fused/unfused differentials; AC-013/AC-018 |
| Runtime silently falls back to logical scheduling | Executed work differs from inspected/fingerprinted plan | Schema dispatch plus no-logical-fallback sentinel; AC-016/AC-017 |
| Partial admission starts work before a late failure | Reads/mutations occur under invalid policy | Atomic whole-DAG admission with per-dependency I/O sentinels; AC-016 |
| Handoff cancellation leaks staging | Resource leak or stale data reuse | Explicit ownership/cleanup units and chaos cases; AC-014/AC-018 |
| Publication acknowledgement is lost | Duplicate writes or false success | Idempotency/reconciliation contract and `PMADP524`; AC-018 |
| Explain truncation changes solver input | Display budget alters selected placement | Store complete bounded matrix in `/2`; truncate only projection evidence; AC-009/AC-015 |
| 0.50 evidence drifts after planning | Unsupported target selected from stale claims | Digest-bound lineage at planning and live admission; AC-008/AC-016 |
| Scope expands to all seven portable engines | Unproven consumer/lifecycle claims delay or weaken release | Fixed launch matrix and weakest-link graduation; AC-021/AC-023 |

## Known Pre-existing Problems and Follow-Up Candidates

- [#127](https://github.com/eddiethedean/etlantic/issues/127) tracks a
  PostgreSQL 16 arm64 non-final Greek sigma parity mismatch found during this
  audit. It is outside the initial Local/Polars/Pandas qualification matrix and
  does not block 0.51, but it blocks any future PostgreSQL/SQL adaptive
  availability claim until resolved and evidenced.
- The bare built-in step-report keys are pre-existing 0.50.1 output, but their
  bounded compatibility migration is explicitly in scope through AC-019; it is
  not a general metadata cleanup mandate.
- Existing `/1` physical units are advisory and the scheduler walks logical
  nodes. That is the central in-scope gap, not permission to redesign unrelated
  scheduler, control-plane, or orchestration APIs.
- Statistics-aware costing, provider economics, telemetry feedback, runtime
  replanning, and additional `/2` consumers remain candidate later epics. They
  are not defects in this change.

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

## Definition of Done

Phase 0.51 is done only when:

1. AC-001 through AC-024 are demonstrated by the linked verification artifacts;
2. every in-scope public field, wire record, diagnostic, migration, and runtime
   behavior matches the accepted ADR and this plan;
3. explicit `/1`, legacy Profile/report, plugin, and persisted-artifact
   compatibility is preserved;
4. all required evidence is generated by its recorded command and verifies from
   a clean checkout;
5. supported Python/OS, package, documentation, security, compatibility,
   conformance, differential, and stable-foundation CI is green;
6. no unresolved critical/high correctness, security, compatibility, data-loss,
   or publication finding attributable to 0.51 remains;
7. documentation and examples describe only behavior and maturity proven by the
   final evidence matrix; and
8. #95 records the dated go/no-go decision, evidence owners, residual risks,
   rollback trigger, and exact Available/Experimental/unavailable rows.

Repository-wide perfection is not part of this definition. Independently
confirmed pre-existing defects outside the change boundary remain follow-up
work unless they invalidate an in-scope qualification row or make safe
implementation impossible.

## Plan Decision

**READY FOR IMPLEMENTATION.** Phase 0 is the mandatory first implementation
increment: reconcile the identified backlog wording and accept the ADR before
merging production code. This sequencing gate contains no unresolved product or
architecture decision; all later phases consume the contracts frozen here.
