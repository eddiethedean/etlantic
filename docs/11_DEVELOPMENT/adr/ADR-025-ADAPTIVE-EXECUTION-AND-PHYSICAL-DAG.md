# ADR-025: Adaptive Execution and Physical-DAG Contract

Date: 2026-09-10
Status: Accepted (ETLantic 0.51 Phase 0 contract freeze)

## Context

ETLantic 0.50.1 provides a published portable-transformation baseline and
canonical explicit `etlantic.plan/1` plans.  It does not provide a public,
authoritative adaptive placement or physical-DAG execution contract.  The
0.51 plan introduces that capability for static batch graphs while preserving
the explicit planner, its bytes, and its runtime behavior.

Without a contract freeze, an implementation could widen `/1`, treat an
installed engine or native body as an adaptive candidate, perform discovery or
I/O while planning, vary placement with map order or timing, or let an
unsupported consumer walk a `/2` logical graph.  Those outcomes would break
the 0.50.1 compatibility and trust boundaries.

This ADR is the Phase 0 acceptance record for task #41.  The evidence manifest
and release decision remain owned by #82 and #95 respectively.  Acceptance of
this ADR authorizes later implementation increments; it does not mark any
adaptive execution combination Available.

Authoritative companion documents are the
[0.51 implementation plan](../IMPLEMENTATION_PLAN_0_51.md), the
[0.51 exit gate](../EXIT_GATE_0_51.md), and the machine-readable
[`contract_freeze_0_51.json`](../evidence/adaptive_0_51/contract_freeze_0_51.json).

## Decision

### Separate, opt-in plan families

- `execution_strategy="explicit"` remains the default.  Explicit planning and
  execution retain `etlantic.plan/1`, canonical bytes, fingerprints, logical
  scheduling, and report behavior.
- `execution_strategy="adaptive"` is opt-in.  A successful adaptive plan uses
  only `etlantic.plan/2` and the embedded `etlantic.physical_unit/1` protocol.
- `PipelinePlan` and `PLAN_SCHEMA` stay `/1`-only.  `AdaptivePipelinePlan` and
  `PlanDocument` are separate public types.  Schema-dispatching codecs may
  accept both; neither type acquires the other type's authority.
- A stored `/2` document is never downgraded to `/1`.  An opted-in fallback
  independently invokes the explicit planner and produces a `/1` document
  with exactly one `etlantic.adaptive_fallback` metadata record.

### Profile policy and precedence

The public Profile additions are frozen as:

```python
execution_strategy: Literal["explicit", "adaptive"] = "explicit"
placement_targets: dict[str, PlacementTarget] = field(default_factory=dict)
eligible_targets: tuple[str, ...] = ()
adaptive_fallback: Literal["error", "explicit"] = "error"
```

`PlacementTarget` is a frozen, secret-free descriptor containing engine,
optional compiler/executor/connector/resource references, location, security
domain, required capabilities, and version constraints.  It contains stable
keys and evidence requirements only; it never carries import paths, resolved
credentials, live backend objects, source rows, or executable callables.

Eligible targets are ordered, duplicate-free keys in `placement_targets`.
Adaptive mode requires at least one eligible target.  Profile construction and
JSON Schema reject blank or unknown keys, duplicate eligible keys, unknown
fields, non-string references, and secret-like values before discovery.

Precedence is frozen as:

```text
RunRequest.implementation_overrides
  -> Profile.implementation_overrides
  -> binding/provider and required-capability constraints
  -> portable_transform_policy
  -> adaptive ranking
```

An override may constrain an already eligible, trusted portable target; it
cannot widen the candidate set.  Native bodies, native-only nodes, and
`portable_transform_policy="native"` are infeasible for `/2` and use the
explicit fallback only when it is opted in and independently valid.

### Candidate trust and deterministic placement

Adaptive planning is data-only and side-effect free.  It enumerates only
Profile-eligible targets that pass applicable authorization before plugin,
provider, connector, or resource loading.  Positive capability, locality,
pushdown, contract, lowering, and handoff claims require immutable evidence
references, including the exact 0.50.1 input digests.  Missing, unknown, or
drifted evidence is ineligible; engine installation alone establishes nothing.

The candidate matrix contains exactly one source, sink, or portable-compute
record for every selected logical node × eligible target.  Rejected records
remain in the matrix with stable reasons.  Candidates, decisions, regions,
physical units, profile inputs, evidence references, and the frozen limits all
participate in the `/2` fingerprint.

The exact minimized objective is:

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

All ordering is canonical: sliced logical topological/name order, then eligible
target order and stable target identity.  Timing, map insertion order, process
hash seed, and allocator behavior cannot affect the resulting plan.

### Fixed limits and selection representation

The following are protocol limits, not Profile configuration:

| Limit | Value | Diagnostic |
|---|---:|---|
| Selected logical nodes | 256 | `PMADP300` |
| Eligible targets | 8 | `PMADP301` |
| Candidates per node | 8 | `PMADP302` |
| Candidate/rejection records | 2,048 | `PMADP303` |
| Solver state expansions | 1,000,000 | `PMADP304` |
| Serialized adaptive explain artifact | 4 MiB | `PMADP305` |
| Planner-owned transient budget | 256 MiB | `PMADP306` |

`selected_nodes: null` denotes the complete logical graph.  A partial plan
stores the canonical non-empty 0.50 selection tuple and the exact sliced graph.
The `/2` physical DAG covers every selected node and no other node.  A request
with a different selection must re-plan and receives `PMADP122`.

### Physical-DAG authority and consumer boundary

`etlantic.physical_unit/1` defines the authoritative `compute`, `transfer`,
`collection`, `validation`, `materialization`, `reuse`, and `publication`
units.  Each unit has stable identity, typed dependencies, ordered logical
attribution, target identity, contracts, policy/security envelope, ownership,
retry semantics, and protocol evidence.  A publication unit is the sole
sink-commit authority.

The local runtime validates the entire live physical DAG before resource
acquisition, reads, staging, or mutation.  It schedules only physical
dependencies and never re-places work or falls back to logical scheduling.

| Consumer | 0.51 contract |
|---|---|
| `/2` codec, verifier, inspection, explain, and diff | Strict schema dispatch; support follows the increment gate |
| Local runtime | Reject before I/O until qualified static-batch physical execution passes |
| Compile, Airflow, Prefect, and external orchestrators | Reject `/2` with `PMADP500` before discovery or I/O |
| Control-plane, durable, federated, and remote workers | Reject `/2` throughout 0.51 |
| Streaming and runtime-expanded graphs | Reject `/2` throughout 0.51 |
| Third-party consumer | Reject unless exact protocol support is independently qualified and published |

### Report metadata migration

`etlantic.run_report/1` remains unchanged.  New first-party writers emit only
`etlantic.dataframe`, `etlantic.sql`, `etlantic.spark`, and
`etlantic.spark_schema` in `StepRunReport.metadata`.  Readers silently migrate
the four 0.50 bare aliases at that step-metadata boundary only; namespaced
values win collisions, aliases are removed, and repeat migration and
reserialization are deterministic and idempotent.  Other report, profile,
logical-plan, third-party, and physical-unit metadata is not renamed.

### Security, diagnostics, and rollback

All planning and evidence surfaces remain secret-free and source-row-free.
Adaptive placement cannot weaken authorization, tenant, environment,
residency, masking, classification, contract, retry-safety, or publication
boundaries.  Production allowlists authorize before loading every applicable
extension family.

Diagnostic ownership is frozen:

| Family | Responsibility |
|---|---|
| `PMADP100–119` | Profile policy, precedence, and `/1` compatibility |
| `PMADP120–139` | Selection, fallback, and unsupported authoring modes |
| `PMADP200–219` | Inventory trust, identity, versions, evidence lineage |
| `PMADP220–259` | Candidate, locality, contract, and interchange rejection |
| `PMADP300–306` | Resource limits |
| `PMADP320–339` | Constraint conflicts and deterministic solving |
| `PMADP400–429` | `/2` and physical topology/integrity validation |
| `PMADP500–519` | Admission and unsupported consumers |
| `PMADP520–549` | Dispatch, lifecycle, cleanup, and publication |

On semantic divergence, authorization/evidence drift, unsafe lifecycle or
publication behavior, fingerprint nondeterminism, or data exposure, adaptive
planning is disabled, stored `/2` plans stop being accepted, owned staged
artifacts are reconciled under recorded ownership, and new work is re-planned
explicitly.  Stored `/2` plans are never silently downgraded.

## Consequences

- Later 0.51 increments have stable public and wire contracts to implement.
- Existing explicit workflows remain independent of adaptive modules.
- The initial Available matrix is deliberately narrow; unqualified rows remain
  unavailable or Experimental until #95 records evidence-backed graduation.
- Every new `/2` consumer and provider must satisfy the same fail-closed,
  evidence, and lifecycle boundary before it can be added to the matrix.

## Alternatives rejected

| Alternative | Reason rejected |
|---|---|
| Add adaptive fields or authoritative units to `/1` | Breaks frozen `/1` bytes and confuses explicit authority |
| Treat installed engines or native bodies as candidates | Violates portable-only and authorize-before-load requirements |
| Use local greedy placement or timing-dependent heuristics | Cannot reproduce the complete frozen objective |
| Allow runtime re-placement or logical scheduling fallback | Makes stored inspection/fingerprint diverge from executed work |
| Make bounds configurable Profile fields | Expands the four-field policy contract and destroys reproducibility |
| Rename generic metadata keys repository-wide | Exceeds the narrow `StepRunReport.metadata` migration scope |
| Mark 0.51 combinations Available at contract freeze | Qualification requires independently generated evidence and #95 |

## Compatibility

This ADR is additive.  It preserves 0.50.1 explicit Profile documents, `/1`
plans, fingerprints, runtime behavior, plugin protocols, and run-report
readability.  New adaptive documents require new-reader support and fail closed
at all unsupported boundaries.  Core remains optional-dependency clean; target
packages load only when selected and authorized.

## See also

- [IMPLEMENTATION_PLAN_0_51](../IMPLEMENTATION_PLAN_0_51.md)
- [EXIT_GATE_0_51](../EXIT_GATE_0_51.md)
- [ADR-021](ADR-021-OPTIMIZER-PASS-PROTOCOL.md)
- [ADR-022](ADR-022-DYNAMIC-CONTROL-AND-STREAMING.md)
- [ADR-023](ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md)
