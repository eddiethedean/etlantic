---
title: ETLantic 0.52 Implementation Plan
description: Implementation-grade contract for adaptive placement planning, physical lowering, and explainability without execution.
plan_status: current
plan_last_reviewed: 0.51.0
---

# ETLantic 0.52 Implementation Plan

Adaptive Planning, Physical Lowering, and Explainability

Status: implementation contract

Target release: 0.52

Governing architecture: [ADR-025](adr/ADR-025-ADAPTIVE-EXECUTION-AND-PHYSICAL-DAG.md)

Predecessor contract: [Implementation Plan 0.51](IMPLEMENTATION_PLAN_0_51.md)

Evidence ledger: [Exit Gate 0.51](EXIT_GATE_0_51.md)

## 1. Decision and Release Outcome

Release 0.52 implements deterministic **adaptive placement planning** and emits
an inspectable `etlantic.plan/2` document. It does not execute an adaptive plan.

The release outcome is:

1. resolve the selected logical graph without changing its logical order;
2. build a trusted, target-scoped inventory from the profile;
3. construct a complete node-by-target candidate matrix;
4. solve placement with the frozen exact objective and deterministic tie-breaks;
5. derive maximal safe regions;
6. lower the selected assignment into the seven-kind physical DAG;
7. serialize, explain, and diff the resulting `/2` document; and
8. reject `/2` at every execution boundary before discovery, resource access,
   invalidation, or user I/O.

The governing data flow is:

```text
Pipeline + Profile + selection
            |
            v
strategy-aware validation ---- explicit strategy ----> existing /1 planner
            |
            v
canonical admitted slice
            |
            v
discover -> evaluate -> authorize -> filter references -> load
            |
            v
trusted target inventory + directional handoff evidence
            |
            v
complete candidate matrix -> exact deterministic solver
            |
            v
safe regions -> seven-kind physical DAG -> etlantic.plan/2
            |
            +--------> explain / diff (stored evidence only)

etlantic.plan/2 --------X execution, compilation, scheduling, orchestration
```

The `/1` planner remains the compatibility path. Existing explicit profiles
must not pay adaptive discovery or validation costs and must retain their
current plan bytes, diagnostics, reports, and behavior.

## 2. Repository Ground Truth

This contract is based on the repository state and public issue ledger at the
start of 0.52 implementation.

| Area | Current state | 0.52 obligation |
|---|---|---|
| Package version | Root package is `0.51.0`; supported Python is 3.11–3.13. | Preserve the support matrix and bump versions only in the release phase. |
| Profile | `execution_strategy`, `placement_targets`, `eligible_targets`, and `adaptive_fallback` are implemented. | Consume the frozen fields; do not introduce a second configuration model. |
| Wire model | `AdaptivePipelinePlan`, `PlanDocument`, `CandidateRecord`, `AdaptiveDecision`, `AdaptiveRegion`, and `PhysicalDAG` exist. | Populate them from real planning and tighten generated-plan semantics without making historical valid `/2` documents unreadable. |
| Planner | `plan_pipeline()` rejects adaptive planning with `PMADP221`. | Replace that sentinel with strategy dispatch. |
| Report planner | `plan_pipeline_with_report()` reaches the `/1` builder directly. | Route both public entry points through exactly the same strategy dispatch so adaptive input can never be serialized as `/1`. |
| Definition/class entry points | `Pipeline` and `PipelineDefinition` wrap the current planning path. | Provide identical selection, diagnostics, report, and return-type behavior. |
| Validation | Implementation support is resolved against the explicit engine before adaptive inventory exists. | Make validation strategy-aware; an adaptive profile must be validated against eligible targets, not pre-rejected by the explicit engine. |
| Plugin lifecycle | Discovery, evaluation, authorization, and loading are separated, but group helpers can load every allowed plugin in a group. | Filter to the references declared by eligible targets after authorization and before loading. |
| CLI bootstrap | `etlantic plan` performs broad plugin setup before planning. | Avoid broad loading for adaptive mode; use the target-scoped lifecycle. |
| Runtime bootstrap | `arun_pipeline()` initializes runtime plugins before it asks for a plan. | Reject adaptive execution before runtime/plugin initialization. |
| Explain/diff | Public projectors are typed and implemented for `PipelinePlan`. | Accept `PlanDocument`; preserve `/1` output and add `/2` projections. |
| CLI plan diff | The schema-prefix branch calls `PipelinePlan.from_dict()`. | Decode through `plan_from_json()` so `/2` is accepted and verified. |
| Consumers | Core compile, scheduler, orchestrator, remote, Prefect, and CP1 have `/2` rejection guards. | Audit ordering and prove every rejection happens before side effects. |
| Optimization | Optimization is a `/1` logical-plan facility. | Reject `/2`; it is not placement authority in 0.52. |
| Persistence | No planner persistence migration is required. | Do not add a database or persist source rows. |
| Dependencies | `packaging` and `jsonschema` are already available. | Add no required third-party runtime dependency for the planner. |
| CI | Ruff, formatting, pyright, core/full tests, docs, surface inventory, diagnostics, and wheel tests are present. | Extend these gates with deterministic adaptive evidence and cross-platform assertions. |

The live 0.52 milestone contains stories #32–#36 and #38; implementation tasks
#45–#68, #74–#77, #91, and #93 are part of this contract. Runtime/admission
tasks assigned to 0.53 and conformance/graduation tasks assigned to 0.54 remain
outside this release.

## 3. Change Boundary

### 3.1 Problem

ETLantic already has a frozen adaptive wire family, profile model, rejection
contract, and evidence vocabulary. It does not yet have an implementation that
turns a supported selected logical graph into a trustworthy `/2` plan. The
remaining work cannot be treated as an extension of the existing `/1` greedy
planner: candidate truth, placement, boundaries, physical lowering, and
explainability must share one deterministic proof model.

### 3.2 Desired behavior

Given the same canonical pipeline, profile, installed authorized plugin set,
and evidence corpus, every supported platform must produce the same:

- inventory identities and evidence references;
- candidate matrix and rejection reasons;
- selected assignment and objective tuple;
- regions and physical DAG;
- canonical JSON, fingerprint, and plan ID; and
- explain and diff projections.

### 3.3 In scope

- strategy-aware dispatch for every public planning entry point;
- canonical full-pipeline and partial-selection admission;
- trusted target inventory and directional handoff evidence;
- complete portable candidate analysis;
- exact deterministic placement with the frozen objective;
- resource-budget enforcement and a small exhaustive oracle;
- safe-region derivation and optional proven fusion;
- deterministic lowering to compute, transfer, collection, validation,
  materialization, reuse, and publication units;
- `/2` serialization, integrity verification, explain, and diff;
- CLI, Python, notebook, and IDE surface parity;
- early rejection at all non-planning consumers;
- generated evidence and CI/release gates.

### 3.4 Explicitly out of scope

- executing, compiling, scheduling, submitting, or resuming a `/2` plan;
- admission protocols, workers, leases, checkpoints, retries, and recovery;
- native `@Transformation.implementation(engine)` bodies as adaptive
  candidates;
- streaming, runtime-expanded, conditional, map/reduce, compensation, or
  failure graphs, and unflattened subpipelines;
- cost models, telemetry learning, background replanning, remote fragments, or
  plan mutation after serialization;
- optimization passes as placement authority or applying optimization to `/2`;
- a `/2` to `/1` downgrade or implicit adaptive availability in `run`;
- a new plan schema major, profile schema, state store, or database migration;
- Medallion bronze/silver/gold behavior, which belongs to SparkForge or
  medallantic; and
- changing 0.53 execution or 0.54 graduation scope.

### 3.5 Expected touched surfaces

The implementation may change the existing planner, builder, authoring
lifecycle, validation, public `Pipeline` methods, plugin discovery/evidence
adapters, wire validation, explain/diff projectors, CLI/IDE/notebook adapters,
consumer rejection guards, tests, evidence generators, docs, and release pins.

The planning implementation should be split into focused modules equivalent to:

```text
etlantic/planning/
  adaptive_limits.py
  adaptive_scope.py
  adaptive_inventory.py
  adaptive_candidates.py
  adaptive_constraints.py
  adaptive_objective.py
  adaptive_solver.py
  adaptive_regions.py
  adaptive_lowering.py
  adaptive_builder.py
```

Names may follow existing package conventions, but responsibilities must not be
collapsed into CLI code, runtime code, or plugin-specific implementations.

## 4. Public Contract and Required Behavior

### 4.1 Strategy dispatch and return types

1. `Profile.execution_strategy == "explicit"` uses the existing `/1` planner.
2. `Profile.execution_strategy == "adaptive"` uses the 0.52 adaptive builder.
3. `plan_pipeline()`, `plan_pipeline_with_report()`, `Pipeline.plan()`, and the
   corresponding `PipelineDefinition` path use one shared dispatcher.
4. Public planning return annotations use `PlanDocument` where both schemas are
   possible. The report-returning API returns the same plan document as the
   non-reporting API plus its report; it must not plan twice.
5. Explicit planning must bypass adaptive inventory, plugin loading, evidence
   collection, solver initialization, and adaptive limits.
6. Adaptive validation must not require the explicit `dataframe_engine` or a
   profile-wide implementation override to support every selected transform.
7. A successfully generated adaptive plan has `schema == "etlantic.plan/2"`.
   A successfully generated explicit plan remains `etlantic.plan/1`.

### 4.2 Admitted logical graph and selection

The 0.52 admitted graph contains only resolved `source`, `step`, and `sink`
nodes. Subpipelines must already be flattened by the existing authoring layer.
All other logical graph kinds fail with `PMADP502`.

Selection semantics are:

- no selection means the complete admitted graph;
- partial selection means the existing canonical upstream-closed slice;
- the planner must not invent sinks, publications, or external boundaries for
  nodes outside the selected slice;
- stable Kahn topological order is used, with lexical node ID as the ready-set
  tie-break; and
- logical edge order is the tuple `(source_node_id, target_node_id,
  source_port, target_port)` after normalized defaults.

The 256-node limit is checked after selection/flattening and before discovery or
plugin loading. Cycles, unresolved references, or ambiguous ports fail through
existing validation before adaptive analysis.

### 4.3 Overrides and fallback

For adaptive direct planning, an implementation override value identifies an
eligible **target ID**, not an engine name. The target must be present in
`Profile.eligible_targets` and viable for that node or planning fails with the
frozen override diagnostics. Profile overrides are the only current source;
the precedence position of a future request-scoped override remains reserved
as defined by ADR-025.

`portable_transform_policy` applies before candidate construction:

- `require`: a non-portable selected transform fails validation;
- `prefer`: portable implementations are candidates and a native body is still
  never an adaptive candidate; and
- native bodies do not become candidates merely because their engine matches a
  placement target.

`adaptive_fallback == "explicit"` may be used only when adaptive planning has
no valid candidate assignment for an otherwise valid request. It builds a
fresh `/1` plan through the existing explicit path; it never converts a partial
`/2` object. Target-ID overrides are translated to the selected target's engine
only for that independent explicit build. The report must record the adaptive
failure diagnostic, fallback decision, chosen explicit engine, and that no `/2`
artifact was emitted.

Fallback must not hide invalid profile shape, fingerprint/schema corruption,
oracle divergence, budget-accounting defects, unexpected exceptions, or
security/trust failures.

### 4.4 Trusted target inventory

The inventory is driven solely by `Profile.eligible_targets`, in declared
priority order. It contains one deterministic descriptor for every declared
target ID. A denied or unavailable target is represented by a safe static
descriptor so the matrix can contain explicit rejection records; it is never
loaded and exposes no secret-bearing error payload.

For each target, the lifecycle is:

```text
discover metadata
  -> evaluate compatibility and policy
  -> authorize against production allowlists
  -> filter to compiler/executor/connector/resource references named by target
  -> load only those authorized references needed for positive evidence
```

Authorization must happen before import, instantiation, entry-point invocation,
resource resolution, credential lookup, or network access. Group-wide loading
helpers are not valid for adaptive planning unless they accept and enforce the
post-authorization reference set.

A positively usable target records:

- target ID, engine, location, and security domain;
- normalized target constraints and required capabilities;
- resolved package/distribution identities and versions;
- protocol/compiler/capability fingerprints;
- authorization decision and non-secret reason code; and
- immutable evidence references used by candidate and handoff analysis.

Version constraints are interpreted with `packaging` specifier semantics.
Target identity is a SHA-256 digest over canonical JSON containing the target
ID, normalized profile descriptor, resolved implementation identities and
versions, capabilities, trust decision, and evidence fingerprints. Two target
IDs resolving to the same execution identity fail with `PMADP201`; aliases may
not create fake placement diversity.

Evidence references must be repository-independent content identities. Paths,
timestamps, hostnames, process IDs, and enumeration order are excluded. The
0.50 portable evidence index is the baseline corpus; missing, stale, or
incompatible evidence produces a negative decision, never an optimistic one.

Handoff evidence is directional and keyed by producer identity, consumer
identity, data-contract/schema fingerprint, format, batching/collection mode,
durability, and both capability fingerprints. Evidence from A to B does not
prove B to A.

### 4.5 Complete candidate matrix

For every selected logical node and every eligible target, the planner emits
exactly one `CandidateRecord`, ordered by canonical node order and declared
target priority. The matrix therefore has `node_count * target_count` records,
including denied, unavailable, unsupported, and constrained targets.

Candidate analysis is pure and bounded. It may inspect canonical definitions,
authorized metadata, capability manifests, and signed/fingerprinted evidence.
It must not compile, execute user code, instantiate runtime resources, resolve
credentials, access source/sink systems, or perform network I/O.

Each record contains:

- eligibility and the frozen reason code;
- normalized capability and constraint facts;
- `proven_local_io_nodes` contribution for a source or sink only when locality
  is positively proven;
- `proven_pushdown_actions` contribution only when semantic parity and target
  support are positively proven;
- applicable handoff/boundary facts; and
- no more than eight ordered evidence references.

If more than eight evidence items support a cell, retain the first seven by
canonical evidence identity and use the eighth entry as:

```text
etlantic.evidence-truncated/1:omitted=<N>
```

The marker is evidence of truncation, not proof of capability. A node with no
viable candidate produces `PMADP320` (or the more specific frozen diagnostic)
and either the permitted explicit fallback or no plan. The planner must never
emit a partial candidate matrix or silently remove a target.

### 4.6 Constraints and exact objective

Hard constraints include candidate eligibility, overrides, capability/version
requirements, location and security-domain policy, directional handoff support,
materialization/durability requirements, validation/publication requirements,
and the frozen portable-only rule.

For a complete assignment the minimized lexicographic objective is exactly:

```text
(
  -proven_local_io_nodes,
  -proven_pushdown_actions,
  cross_target_logical_edges,
  collection_units,
  durable_materialization_units,
  -safely_fusible_logical_edges,
  target_priority_vector,
  target_identity_vector,
)
```

The stored wire tuple remains flat. For `N` selected nodes it contains six
scalar integers, followed by `N` target-priority integers, followed by `N`
target-identity strings. Its generated-plan length is therefore `6 + 2N`.
The plan metadata records the frozen objective, solver, and adaptive-limits
version identifiers.

The first implementation is an exact deterministic branch-and-bound solver.
It uses canonical node order, candidate order, branching order, lower bounds,
and incumbent comparison. An expansion is charged immediately before exploring
a complete or partial assignment: expansion 1,000,000 is allowed; the next
attempt fails with `PMADP304`. Component-wise solving is allowed only with a
checked proof that no hard constraint or objective term crosses components.

For graphs with at most eight selected nodes and four targets, and no more than
65,536 Cartesian assignments, tests run an independent exhaustive oracle. Any
objective or assignment disagreement is `PMADP306`, fails closed, and is never
eligible for fallback.

### 4.7 Frozen resource limits

| Resource | Limit | Required behavior |
|---|---:|---|
| Selected logical nodes | 256 | Reject before discovery when exceeded. |
| Eligible targets/candidates per node | 8 | Reject invalid profile/scope before matrix construction. |
| Candidate records | 2,048 | Reject before allocating a larger matrix. |
| Solver expansions | 1,000,000 | Allow the limit; reject the next expansion. |
| Evidence references per cell | 8 | Apply the deterministic truncation marker. |
| Explain output | 4 MiB UTF-8 | Emit the deterministic bounded summary. |
| Planner transient budget | 256 MiB | Reject before the next charged allocation would cross it. |

Transient accounting is deterministic and independent of interpreter object
size. The charged size is:

- canonical compact JSON UTF-8 byte length plus 64 bytes per live inventory,
  candidate, boundary, or explain record;
- canonical compact encoding byte length plus 128 bytes per live solver
  frontier/incumbent record, containing only node index, candidate identities,
  partial objective, and lower bound; and
- exact byte length for owned canonical serialization buffers.

An object is charged once to its current owner, ownership transfer is explicit,
and released objects stop contributing. Shared strings are charged to the
owning canonical record rather than globally interned. Before every charged
allocation the counter checks the prospective total and raises `PMADP303` if it
would exceed 256 MiB. RSS and wall-clock measurements may be recorded as CI
evidence but are not planning inputs or conformance decisions.

### 4.8 Regions and fusion

A selected logical edge is a hard boundary if any of the following applies:

- source and destination target identities differ;
- protected effect, retry, checkpoint, or state semantics require separation;
- the selection boundary is partial;
- security-domain policy requires a boundary;
- validation, durable materialization, or publication is required; or
- directional handoff evidence is absent or negative.

After hard edges are removed, regions are maximal weakly connected components
with one target identity. Membership and region ordering are canonical.

Region IDs are SHA-256 content identities over target identity, ordered member
IDs, execution mode, policy/security facts, planner version, and fusion
evidence. A region ID is not a runtime cache key and must not incorporate a
hostname, process identity, timestamp, or filesystem path.

Fusion is optional. A region may emit a fused compute unit only when positive
capability/evidence proves aggregate semantics safe. Otherwise the same region
is retained and emits deterministic single-node compute units. The lack of
fusion evidence must not make an otherwise valid assignment invalid.

### 4.9 Physical lowering

The physical DAG uses only the frozen kinds below.

| Kind | Emission rule |
|---|---|
| `compute` | Covers each selected source, step, or sink exactly once as its primary logical execution, individually or as a proven fused group. |
| `transfer` | Represents a supported cross-target handoff; records directional handoff evidence and data contract. |
| `collection` | Represents a required distributed-to-collected transition; never inferred from convenience. |
| `validation` | Represents a declared validation boundary that cannot remain inside the compute unit. |
| `materialization` | Represents a required durable boundary/checkpoint with proven target support. |
| `reuse` | Represents a proven reusable artifact reference; it never reads or validates the artifact during planning. |
| `publication` | Represents the commit/publication boundary for a selected sink that declares such semantics. |

Physical unit IDs are content-derived from kind, target identity, ordered
logical coverage, normalized inputs/outputs, policy facts, and relevant
evidence. Units are topologically ordered with unit ID as the ready-set
tie-break.

Every selected logical node has exactly one primary compute coverage. Every
selected logical edge maps to exactly one continuous physical path. A selected
sink that requires commit semantics has exactly one publication unit. A partial
selection ending before a sink does not invent one. Transfer, collection,
validation, materialization, reuse, and publication units may not claim primary
logical-node coverage.

The finished DAG must pass physical schema validation, acyclicity, coverage,
edge-path, boundary, target, and evidence checks. Violations use `PMADP400`–
`PMADP404` and no `/2` plan is returned.

### 4.10 Serialization and integrity

0.52 uses the existing `etlantic.plan/2` and `etlantic.physical-unit/1` wire
families. No new schema major is introduced.

Canonical JSON and hashing follow the frozen `/2` codec:

- calculate the fingerprint over the complete canonical document excluding
  only `fingerprint` and `plan_id`;
- set `plan_id` from the frozen prefix plus the first 16 hexadecimal characters
  of the fingerprint;
- validate both the model and JSON Schema on generated output; and
- on read, `verify=False` skips fingerprint comparison only—it does not skip
  model/schema validation.

Malformed, ambiguous, unsupported, or tampered documents fail with the frozen
typed plan errors. No code path returns a partly populated `AdaptivePipelinePlan`.

Historical `/2` documents that satisfied the 0.51 public reader remain readable
and inspectable. Stricter objective length and lowering completeness apply to
plans generated by 0.52; they must not be retroactively imposed in a way that
breaks legitimate hand-built or persisted 0.51 documents.

### 4.11 Explain and diff

Public explain and diff functions accept `PlanDocument`. They project stored
plan evidence only and must never rerun inventory, candidate analysis, solving,
or lowering.

For `/1`, existing output is byte-compatible unless an explicit fallback report
adds a separately namespaced adaptive-fallback section. For `/2`, explain adds a
stable adaptive namespace containing:

- inventory identity and target order;
- every node decision and all alternatives;
- eligibility/rejection reason codes and bounded evidence references;
- exact objective components and target vectors;
- region membership, boundaries, and fusion decision; and
- physical units, logical coverage, and transfer/materialization/publication
  reasons.

Explain clearly labels the artifact planning-only and non-executable in 0.52.

If the full compact UTF-8 explain artifact would exceed 4 MiB, emit diagnostic
`PMADP305` and a deterministic summary containing plan fingerprint, objective,
selected target mapping, region/unit/candidate counts, per-reason counts, and a
SHA-256 digest of the omitted canonical detail. The plan remains valid.

Diff is schema-aware. It separates semantic changes (selected graph, target
assignment, hard constraints, regions, physical topology) from explanatory
changes (alternative evidence or reason text). Cross-schema `/1` versus `/2`
diffs report the schema and capability boundary rather than coercing either
document. CLI decoding must use `plan_from_json()`.

CLI, Python, notebook, and IDE adapters expose equivalent information.
`plan optimize` and `plan explain --optimization` reject `/2` with `PMADP500`
until an explicit future contract makes optimization adaptive-aware.

### 4.12 No execution in 0.52

Every run/arun, compile, scheduler, orchestrator, remote, Prefect, CP1, worker,
and other execution consumer must reject `/2` with `PMADP500` at admission.
The rejection must occur before:

- runtime or plugin discovery/loading;
- cache invalidation or checkpoint mutation;
- resource-provider or credential resolution;
- connector construction or source/sink I/O;
- compiler invocation, submission, scheduling, or network access; and
- execution lifecycle hooks or user code.

Planning-specific inventory is permitted only inside the adaptive planning
path and remains subject to authorize-before-load.

## 5. Implementation Design

### 5.1 Shared adaptive builder

Create one internal adaptive builder that accepts a validated pipeline/profile,
canonical selection, and a report collector. Both reporting and non-reporting
public APIs call it. The builder returns an immutable `/2` model only after all
phases complete.

The builder sequence is fixed:

1. dispatch and validate profile shape;
2. resolve/validate the selected logical slice;
3. enforce pre-discovery limits;
4. build trusted inventory;
5. construct and validate the complete matrix;
6. solve and optionally compare with the oracle;
7. derive regions and lower the physical DAG;
8. validate model/schema/semantic invariants;
9. canonicalize, fingerprint, and assign the plan ID; and
10. produce report projections from the completed in-memory evidence.

### 5.2 Deterministic traversal without graph mutation

Do not reorder user-owned graph containers to obtain determinism. Build
canonical tuples for selected nodes, edges, targets, candidates, regions, and
units and use those tuples throughout planning. Freeze records at phase
boundaries so later phases cannot amend the evidence that justified an earlier
decision.

### 5.3 Shared boundary and objective evaluators

Candidate feasibility, solver scoring, region construction, physical lowering,
explain, and the exhaustive oracle must call the same pure boundary predicates
and objective-component definitions. The oracle may enumerate independently,
but it must not duplicate subtly different scoring semantics.

### 5.4 Safe plugin adapter

Add a target-reference filter between authorization and load. Preserve existing
plugin lifecycle APIs for explicit planning. Tests must use plugins whose module
import and entry-point invocation leave observable sentinels, proving denied and
unreferenced plugins were never loaded.

### 5.5 Plan construction

Construct the completed model initially without fingerprint and plan ID, compute
the canonical fingerprint once, then construct the final immutable model with
both integrity fields. No setter-based finalization or post-hash mutation is
permitted.

### 5.6 Evidence generation

Conformance evidence is generated by a checked-in script from tests and public
artifacts. JSON evidence files are canonical, contain no secrets/source rows,
and are not hand-edited. A failure to regenerate an identical artifact from an
unchanged tree is a release failure.

## 6. Non-Negotiable Invariants

1. Explicit strategy never enters adaptive discovery or solving.
2. Adaptive strategy never emits `/1` unless the configured, eligible fallback
   independently succeeds.
3. A selected native implementation is never an adaptive candidate.
4. Inventory is limited to declared eligible targets and authorization precedes
   loading.
5. Denied or unreferenced plugins cannot be imported as a planning side effect.
6. Candidate analysis never executes user code or accesses external data.
7. The candidate matrix is a complete Cartesian product in canonical order.
8. Every positive capability, locality, pushdown, fusion, reuse, and handoff
   claim has immutable evidence.
9. Absence or ambiguity of evidence is negative, not permissive.
10. The objective and all tie-breaks are exact and deterministic.
11. The small-case oracle and optimized solver must agree exactly.
12. Limits are enforced before the allocation or expansion that would exceed
    them.
13. Every selected node has exactly one primary physical compute coverage.
14. Every selected logical edge has exactly one physical path.
15. Region and unit IDs are content-derived and environment-independent.
16. `/2` serialization is canonical and tampering is detected by default.
17. Explain/diff consume stored evidence and never replan.
18. `/2` reaches no execution or compilation side effect in 0.52.
19. Reports, diagnostics, plans, and evidence contain neither secrets nor source
    rows.
20. Existing valid `/1` output remains compatible.

## 7. Edge Cases and Failure Semantics

| Case | Required result |
|---|---|
| Empty eligible target list | Profile validation failure; no discovery. |
| More than eight eligible targets | Frozen limit diagnostic; no discovery. |
| More than 256 selected nodes | `PMADP300`; no discovery. |
| Matrix would exceed 2,048 cells | `PMADP301`; no matrix allocation. |
| Unknown target in override | `PMADP121`; no solver. |
| Overridden target is known but ineligible | `PMADP122`; report exact rejection evidence. |
| Native-only selected transformation | `PMADP120`; no native fallback inside adaptive planning. |
| Target denied by allowlist | Safe negative inventory/matrix record; plugin not loaded. |
| Plugin metadata throws or is malformed | Typed inventory rejection with redacted message; never expose exception locals or secrets. |
| Missing or stale portable evidence | Negative candidate/handoff result. |
| Duplicate target execution identity | `PMADP201`; no solver. |
| No viable candidate for a node | `PMADP320`, then only the configured eligible explicit fallback. |
| Required cross-target handoff unproven | Assignment infeasible; consider another assignment, then fail/fallback. |
| Solver expansion 1,000,001 | `PMADP304`; no plan and no fallback. |
| Deterministic budget would cross 256 MiB | `PMADP303` before allocation. |
| Solver/oracle mismatch | `PMADP306`; fail closed and no fallback. |
| No fusion evidence | Valid unfused compute units within the same region. |
| Partial selection ends before sink | No invented publication unit. |
| Physical graph is cyclic or lacks coverage/path | `PMADP400`–`PMADP404`; no serialization. |
| Explain detail exceeds 4 MiB | `PMADP305` plus deterministic summary; plan remains valid. |
| Tampered `/2` input | Integrity error before explain/diff/consumer use unless fingerprint verification alone was explicitly disabled. |
| `/2` passed to optimization | `PMADP500`; no optimization pass is run. |
| `/2` passed to any execution consumer | `PMADP500` before discovery, resource access, or I/O. |
| Explicit profile after 0.52 | Existing `/1` result and behavior. |

Unexpected exceptions are wrapped only at established public boundaries, retain
their safe causal classification for logs, and expose a stable redacted
diagnostic to users. Broad `except Exception` fallback into `/1` is forbidden.

## 8. Security and Reliability Requirements

- Production plugin, optimization-pass, schema-registry, and resource-provider
  allowlists continue to fail closed.
- Adaptive planning does not weaken the production `plugin_allowlist` because a
  target appears in `placement_targets`.
- Inventory identities and evidence store package/capability fingerprints and
  metadata only; never credential values, environment dumps, or source rows.
- Exception messages from plugins are treated as untrusted and redacted before
  entering reports or plan evidence.
- Canonical inputs exclude absolute paths, timestamps, random values, locale,
  hash iteration order, network state, and process state.
- Security-domain transitions require positive directional handoff evidence and
  explicit policy permission.
- Reuse records describe an identity and proof only; planning never opens a
  cache artifact to confirm it.
- Solver, explain, and serialization limits prevent adversarial graph/evidence
  amplification.
- Model and JSON Schema validation are both mandatory for generated output.
- Tests verify zero side effects at rejected execution boundaries with sentinel
  plugins, resources, hooks, connectors, and I/O adapters.

## 9. Compatibility Contract

| Surface | Compatibility promise |
|---|---|
| Explicit profiles | Same `/1` schema and canonical bytes for unchanged inputs. |
| Public planning imports | Existing names remain; union return typing is additive. |
| `plan_pipeline_with_report()` | Same explicit behavior; adaptive now correctly returns `/2` plus report. |
| Profile JSON | Existing 0.51 fields and defaults remain unchanged. |
| `/1` reader/writer | Unchanged. |
| `/2` reader/writer | Existing valid 0.51 documents remain readable; 0.52-generated documents satisfy stricter generation invariants. |
| Explain/diff | Existing `/1` projections remain stable; `/2` sections are additive and namespaced. |
| CLI | Existing explicit commands remain; adaptive plan/explain/diff become available, while run/compile/optimize remain rejected. |
| IDE/notebook | Match CLI/Python semantics without independent planning logic. |
| Plugins | Existing explicit lifecycle remains; adaptive loading is a narrower authorized subset. |
| Official packages | Continue pinning `etlantic>=0.51,<0.52` until coordinated 0.52 release updates. |
| Diagnostics | Existing codes retain meaning; new behavior uses the frozen `PMADP` ranges. |
| Persistence | No migration. |

## 10. Acceptance Criteria

### AC-052-001 — Unified strategy dispatch

All public function, class, and definition planning entry points, including
reporting variants, produce `/1` for explicit and `/2` for adaptive through one
dispatcher. Adaptive input can never reach the `/1` builder accidentally.

### AC-052-002 — Explicit compatibility

Golden explicit plans, reports, diagnostics, selections, and no-plugin-load
sentinels are byte-for-byte unchanged for the supported matrix.

### AC-052-003 — Scope and mode admission

Full and partial canonical slices are deterministic. Unsupported graph kinds,
cycles, ambiguous ports, non-portable selected bodies, and pre-discovery limit
violations fail with the frozen diagnostic and no side effects.

### AC-052-004 — Trusted, target-scoped inventory

Inventory represents every eligible target, enforces version/capability/trust
constraints, detects duplicate identities, and proves denied or unreferenced
plugins are not imported or loaded.

### AC-052-005 — Evidence lineage

Portable and directional handoff evidence is immutable, fingerprinted,
repository-independent, bounded, and traceable from decisions and physical
boundaries. Missing evidence is negative.

### AC-052-006 — Candidate truth and purity

The matrix has exactly one ordered record per selected node/eligible target,
and candidate analysis performs no compilation, execution, credential lookup,
resource instantiation, external I/O, or user-code invocation.

### AC-052-007 — Overrides and fallback

Target-ID overrides use the frozen precedence and diagnostics. Explicit fallback
occurs only for eligible no-assignment failures, builds independently, records
the reason, and never hides security, corruption, budget, oracle, or unexpected
failures.

### AC-052-008 — Exact solver and oracle

The solver minimizes the exact frozen objective and agrees with the exhaustive
oracle on every case within the oracle bounds, including adversarial tie cases.

### AC-052-009 — Determinism and limits

Repeated runs, hash seeds, supported Python versions, Linux/macOS, and insertion
orders produce identical `/2` bytes. All frozen limits have below/at/above tests
and deterministic diagnostics.

### AC-052-010 — Regions and fusion

Regions are maximal under the frozen boundary predicate, IDs are stable, and
fusion occurs only with positive proof; lack of proof produces a deterministic
unfused region.

### AC-052-011 — Complete physical DAG

All seven unit kinds have positive/negative fixtures. Logical coverage, path,
boundary, topological-order, evidence, and publication invariants pass, and
tampered DAGs fail closed.

### AC-052-012 — Integrity

Generated `/2` plans pass model and schema validation, round-trip canonically,
and detect mutations of every hashed section. `verify=False` bypasses only
fingerprint comparison.

### AC-052-013 — Explainability and bounds

Explain exposes all stored decisions without replanning. Full output stays
within 4 MiB or produces the exact `PMADP305` deterministic summary.

### AC-052-014 — Semantic diff

Diff detects assignment, constraint, region, physical-topology, and evidence
changes; distinguishes semantic from explanatory differences; and handles
cross-schema comparisons without coercion.

### AC-052-015 — Surface parity

Python, CLI, IDE, and notebook plan/explain/diff surfaces decode through the
public union codec and agree on plan identity, objective, decisions, and errors.

### AC-052-016 — No execution side effects

Every `/2` execution, compilation, scheduling, orchestration, remote, Prefect,
CP1, worker, and optimization path raises `PMADP500` before plugin/runtime
initialization, resource resolution, invalidation, lifecycle hooks, or I/O.

### AC-052-017 — Security and redaction

Production allowlists fail closed; cross-domain boundaries require proof; and
plans, reports, diagnostics, snapshots, and generated evidence contain no
secret values, environment dumps, absolute repository paths, or source rows.

### AC-052-018 — Evidence and release gates

The adaptive evidence suite regenerates canonical artifacts, repository docs
and surface/diagnostic checks pass, wheels pass smoke tests on supported Python,
and all 0.52 issue links are satisfied or explicitly deferred outside scope.

## 11. Verification Matrix

| Acceptance criterion | Primary proof | Required suite/gate |
|---|---|---|
| AC-052-001 | Entry-point parity and report identity fixtures | planner API, authoring lifecycle, CLI tests |
| AC-052-002 | Golden `/1` bytes and no-adaptive-sentinel fixtures | existing planner snapshots plus compatibility matrix |
| AC-052-003 | Full/partial/unsupported graph fixtures | adaptive scope and validation tests |
| AC-052-004 | Fake distributions, versions, allowlists, import sentinels | inventory and plugin lifecycle tests |
| AC-052-005 | Fixed evidence corpus and directional A→B/B→A cases | portable evidence and handoff conformance |
| AC-052-006 | Cartesian cardinality/order and hostile analyzer fixtures | candidate matrix conformance |
| AC-052-007 | Override precedence and classified failure table | override/fallback matrix |
| AC-052-008 | Solver versus independent exhaustive enumeration | solver oracle/property suite |
| AC-052-009 | Seeds, insertion permutations, OS/Python, thresholds | determinism and resource-budget CI |
| AC-052-010 | Boundary truth table and fusion proof fixtures | region conformance |
| AC-052-011 | Seven-kind golden DAGs plus mutation tests | physical DAG conformance |
| AC-052-012 | Schema/model round-trip and section-by-section tampering | adaptive wire/integrity suite |
| AC-052-013 | Stored-evidence spies and 4 MiB boundary fixtures | explain conformance |
| AC-052-014 | Same-schema and cross-schema goldens | semantic diff conformance |
| AC-052-015 | One fixture exercised through four public surfaces | consumer/surface matrix |
| AC-052-016 | Side-effect sentinels at every consumer | adaptive consumer matrix |
| AC-052-017 | Secret/source-row/path canaries and policy matrices | security/redaction scan |
| AC-052-018 | Reproducible generated JSON and release smoke tests | exit-gate script, docs, wheels, CI |

Property tests must use a recorded seed in failure output. Golden files are
canonical artifacts produced by public codecs, not normalized after the fact.

## 12. Implementation Phases and Merge Gates

Each phase is independently reviewable. A later phase must not compensate for
an unmet earlier merge gate.

### Phase A — Entry, scope, and compatibility guard

**Issues:** preparation for #32–#36 and #38.

**Work:**

- introduce shared strategy dispatch;
- fix `plan_pipeline_with_report()` and authoring lifecycle parity;
- make validation strategy-aware;
- implement canonical selected-slice admission and pre-discovery limits;
- add `PlanDocument` typing without changing `/1` serialization; and
- move adaptive run rejection ahead of runtime/plugin initialization.

**Tests:** explicit golden corpus, all public entry points, full/partial slices,
unsupported modes, no-load/no-I/O sentinels.

**Merge gate:** AC-052-001 through AC-052-003 and the early part of AC-052-016
pass; existing `/1` snapshots are unchanged.

### Phase B — Trusted inventory and evidence

**Issues:** #32, #45–#49.

**Work:**

- implement target-scoped discover/evaluate/authorize/filter/load;
- normalize descriptors and version constraints;
- compute identities and detect duplicates;
- ingest portable evidence and construct directional handoff records; and
- enforce inventory/evidence limits and redaction.

**Tests:** fake entry points with import sentinels, production allowlists,
missing/malformed/stale evidence, duplicate identities, directional handoffs,
canonical identity across paths and enumeration orders.

**Dependency:** Phase A canonical scope and profile validation.

**Merge gate:** AC-052-004, AC-052-005, and inventory portions of AC-052-017
pass with no denied/unreferenced plugin load.

### Phase C — Candidate and constraint matrix

**Issues:** #33, #50–#54.

**Work:**

- build the complete Cartesian matrix;
- implement portable capability, version, locality, pushdown, security, and
  override facts;
- centralize boundary feasibility;
- implement evidence truncation; and
- classify no-candidate failures and permitted fallback.

**Tests:** matrix cardinality/order, every frozen reason, native-body exclusion,
hostile side-effect analyzers, overrides, zero-candidate nodes, exact evidence
cap, and fallback classification.

**Dependency:** Phase B immutable inventory/evidence.

**Merge gate:** AC-052-006 and AC-052-007 pass; every matrix cell is explainable.

### Phase D — Exact placement solver

**Issues:** #34, #55–#59, #91, and solver/resource portions of #93.

**Work:**

- implement objective evaluation and deterministic branch-and-bound;
- implement hard-constraint propagation and safe lower bounds;
- implement exact expansion/transient accounting;
- add independent bounded exhaustive oracle; and
- serialize objective and solver/limits versions.

**Tests:** hand-calculated objectives, tie hierarchy, infeasible handoffs,
below/at/above expansion and memory limits, oracle corpus, randomized small
graphs with recorded seeds, hash-seed and insertion-order reproducibility.

**Dependency:** Phase C complete immutable matrix.

**Merge gate:** AC-052-008 and solver/resource parts of AC-052-009 pass with
zero oracle divergence.

### Phase E — Regions and physical lowering

**Issues:** #35, #36, #60–#68, and lowering portions of #93.

**Work:**

- derive maximal regions with the shared boundary predicate;
- apply proven optional fusion;
- lower all seven physical unit kinds;
- derive content IDs and canonical topological order; and
- validate coverage, logical paths, boundaries, targets, and evidence.

**Tests:** boundary truth table, maximality, safe/unsafe fusion, positive and
negative fixtures for every kind, partial selection, cross-domain/cross-target
handoffs, physical mutation and cycle tests.

**Dependency:** Phase D selected assignment and objective.

**Merge gate:** AC-052-010 through AC-052-012 pass; generated `/2` plans
round-trip identically.

### Phase F — Explain, diff, and public surfaces

**Issues:** #38, #74–#77.

**Work:**

- make explain/diff schema-aware over `PlanDocument`;
- add adaptive stored-evidence projections and semantic diff;
- implement deterministic bounded explain output;
- fix CLI diff decoding through `plan_from_json()`; and
- provide CLI/Python/IDE/notebook parity and optimization rejection.

**Tests:** no-replanning spies, `/1` golden compatibility, `/2` explain and diff
goldens, 4 MiB boundary, cross-schema diff, malformed/tampered inputs, surface
parity.

**Dependency:** Phase E complete and verified `/2` documents.

**Merge gate:** AC-052-013 through AC-052-015 pass.

### Phase G — Rejection audit, evidence, and release

**Issues:** completion of #91/#93 and the 0.52 portions of the milestone.

**Work:**

- audit all consumers and move guards ahead of side effects;
- generate the complete evidence ledger;
- run security/path/secret/source-row scans;
- update public surface inventory, diagnostics snapshots, docs, versions, and
  official package pins in coordinated release order; and
- run supported wheel/platform smoke tests.

**Tests:** consumer sentinels, whole suite, docs/link checks, surface inventory,
diagnostic stability, package compatibility, evidence reproducibility.

**Dependency:** Phases A–F.

**Merge gate:** AC-052-016 through AC-052-018 pass, all prior gates remain green,
and no `/2` execution success exists anywhere in the repository.

## 13. Required Evidence Artifacts

0.52 extends the evidence ledger frozen by 0.51 under:

```text
docs/11_DEVELOPMENT/evidence/adaptive_0_51/
```

The following artifact names remain stable and are regenerated with 0.52 rows:

- `adaptive_inventory_conformance_0_51.json`
- `adaptive_solver_conformance_0_51.json`
- `adaptive_resource_budget_0_51.json`
- `adaptive_physical_dag_conformance_0_51.json`
- `adaptive_runtime_conformance_0_51.json`
- `adaptive_consumer_matrix_0_51.json`
- `adaptive_explain_identity_0_51.json`
- `adaptive_security_matrix_0_51.json`
- `adaptive_e2e_0_51.json`
- `FINDINGS.md`

Use a checked-in generator equivalent to
`scripts/check_adaptive_0_52.py --write` and a non-writing CI check that compares
fresh canonical output with the committed artifacts. The artifacts must record:

- repository revision and public schema/version identities, but not absolute
  checkout paths;
- scenario ID, acceptance criterion, expected/actual diagnostic, and result;
- deterministic plan/inventory/matrix/objective/region/DAG fingerprints where
  applicable;
- supported Python/platform rows;
- side-effect sentinel counts; and
- secret/source-row/path scan results.

The 0.50 portable baseline, pushdown, requirement-support, adaptive-handoff,
dependency, and security evidence is referenced by content identity rather than
copied or rewritten.

## 14. Risks and Mitigations

| Risk | Consequence | Mitigation / release proof |
|---|---|---|
| Adaptive dispatch diverges across wrappers | Wrong schema or duplicate planning | One dispatcher and entry-point identity tests. |
| Validation assumes explicit engine | Valid adaptive plan rejected before inventory | Strategy-aware validation fixtures with heterogeneous targets. |
| Broad plugin bootstrap runs first | Unauthorized code import or secret access | Filter after authorization, import sentinels, early CLI/runtime ordering tests. |
| Evidence is optimistic or stale | Unsafe candidate/handoff/fusion | Fingerprinted compatibility evidence; missing/ambiguous is negative. |
| Objective implementation drifts | Nondeterministic or suboptimal placement | One evaluator, hand calculations, exhaustive oracle. |
| Branch-and-bound explodes | Planner resource exhaustion | Frozen node/target/matrix/expansion/memory limits and prospective charging. |
| Memory accounting follows Python internals | Cross-version nondeterminism | Canonical serialized-size accounting, with RSS informational only. |
| Regions hide required boundaries | Incorrect physical semantics | Shared predicate and exhaustive boundary truth table. |
| Fusion changes semantics | Invalid aggregate execution | Positive proof only; deterministic unfused fallback. |
| Physical graph is plausible but incomplete | Future runtime cannot execute safely | Exact coverage/path/publication validators and mutation tests. |
| Explain triggers replanning | Output varies or loads plugins | Stored-evidence-only projectors with spies. |
| New `/2` generation rules break old documents | 0.51 compatibility regression | Separate reader compatibility tests from generated-plan conformance. |
| Rejection occurs after bootstrap | Side effects despite 0.52 no-execution promise | Sentinel audit for every consumer. |
| Plans leak operational data | Credential or source-data exposure | Structured evidence, redaction, canary scans, no raw plugin exception text. |

## 15. Known Follow-up Candidates

- GitHub issue #127, PostgreSQL portable lowercase-sigma parity on arm64, is a
  known evidence/platform follow-up unless its fixture becomes part of a 0.52
  candidate claim. It must remain negative evidence until proven.
- 0.53 owns whole-DAG admission, local execution, lifecycle/retry/checkpoint
  semantics, runtime protocol support, and executable consumer rows.
- 0.54 owns ecosystem conformance, broader documentation, migration guidance,
  and graduation of adaptive execution support.
- Cost estimation, telemetry-driven placement, remote fragment execution, and
  replanning require later ADRs and schema/version decisions.

The current report-dispatch bypass, explicit-engine validation coupling, broad
adaptive plugin bootstrap, and late runtime rejection are **not** follow-ups;
they are in-scope 0.52 correctness and security obligations.

## 16. Definition of Done

0.52 is complete only when:

- every AC-052 criterion and merge gate is green;
- unchanged explicit inputs produce unchanged `/1` output;
- adaptive planning produces canonical, verified, fully explainable `/2` plans;
- exact solver/oracle, resource, physical-DAG, and deterministic platform
  evidence is committed and reproducible;
- no denied/unreferenced plugin or execution consumer causes a side effect;
- every `/2` execution/compile/schedule/optimize path fails before side effects;
- public docs, schemas, diagnostics, type surfaces, and packages agree;
- no secret, source row, absolute checkout path, or nondeterministic field exists
  in plans, reports, diagnostics, snapshots, or evidence; and
- the issue ledger maps every 0.52 item to implementation and proof, with no
  silent transfer of runtime work into this release.

## 17. Plan Decision

**READY FOR IMPLEMENTATION.**

The repository already contains the frozen profile, wire, diagnostic, and
consumer-boundary foundations required for this work. The phases above close
the identified entry-point, trust, determinism, lowering, explainability, and
no-execution gaps without requiring a new schema major or a persistence
migration.
