---
title: ETLantic 0.53 Implementation Plan
description: Bounded architecture and implementation contract for qualified local adaptive physical-DAG execution.
plan_status: current
plan_last_reviewed: 0.52.0
---

# ETLantic 0.53 Implementation Plan

Local Adaptive Physical-DAG Execution

This document is an implementation contract, not implementation or release
approval. It owns increment I2 and Phases 8–9 of the
[adaptive program](IMPLEMENTATION_PLAN_0_51.md). It does not take over the
independent [0.54 qualification decision](IMPLEMENTATION_PLAN_0_54.md).

**REQUIRED BEHAVIOR** defines this release boundary. **RECOMMENDED IMPLEMENTATION**
allows internal adaptation while preserving that behavior. Proposed interfaces
become public API only after implementation, documentation, and verification.

## Architecture Summary

Keep explicit `/1` planning and logical execution independent. Add this local
`/2` branch:

```text
resolve static scope/request -> data-only adaptive planning/executable lowering
 -> verify stored executable envelope and exact qualified support row
 -> authorize/resolve all live dependencies -> atomic admission with pinned adapters
 -> enter runtime session/acquire resources -> physical dependency scheduler
 -> seven-kind executor protocol -> logical reports + cleanup/reconciliation
```

The stored physical DAG is scheduling authority. The logical graph supplies
contract resolution, provenance and selection verification, never an alternative
ready queue. Compute executes exact planned portable members. Source compute
reads/normalizes; sink compute prepares/validates. Only publication commits.

Admission is atomic permission to start, not a distributed transaction or a
promise that external state cannot change afterward. Later failures stop work
safely without substitution, placement, logical fallback, or downgrade.

## Repository Ground Truth

Baseline: commit `6299e6f3df91746f441731aca5fe84744dd2f627`, package **0.52.0**,
inspected **2026-09-13**, initially clean working tree.

| Inspected surface | Actual repository behavior | Consequence |
|---|---|---|
| Specifications/issues | [ADR-025](adr/ADR-025-ADAPTIVE-EXECUTION-AND-PHYSICAL-DAG.md), [0.51 program](IMPLEMENTATION_PLAN_0_51.md), [0.52 plan](IMPLEMENTATION_PLAN_0_52.md), [0.52 exit gate](EXIT_GATE_0_52.md), ROADMAP §§ 0.53–0.54; live epic [#30](https://github.com/eddiethedean/etlantic/issues/30), story [#37](https://github.com/eddiethedean/etlantic/issues/37), tasks #69–#73, #88–#90, #92 | Local runtime is this increment; broader old task wording does not authorize SQL/Spark/durable execution. |
| Planner/extensions | `src/etlantic/planning/adaptive.py` contains inventory, solver, regions and lowering. Public dispatch is `plan/planner.py`, `pipeline.py`, `authoring/lifecycle.py` | Extend existing lowering and dispatch; no second solver. |
| Generated plans | Plans/regions/unit policies are `planning-only`; compute units are singletons even in multi-node regions. Sources/sinks have compute units; sinks also have publication units | Add fingerprinted executable descriptors; distinguish regions from fusion; split sink preparation from commit. |
| Public wire | `plan/adaptive_model.py`, `physical.py`, `adaptive_serialize.py`, public `plan` exports and adaptive JSON Schema exist. Generated-only checks explicitly key on `0.52` | Add 0.53 generated checks without breaking historical readability or allowing planner-label bypass. |
| Runtime | `runtime/execute.py:arun_pipeline()` rejects adaptive before runtime initialization. `LocalScheduler` and `LocalOrchestrator.execute()` reject `/2`. Host owns logical waves, attempts, validation, artifacts, publication and reports | Separate physical loop; extract/reuse host operations without invoking its logical loop. |
| Executor extension | `runtime/executors/protocol.py` is step-level `EngineExecutor`; reserved registry is unwired and source/sink dataframe methods are incomplete | Separate typed physical protocol and exact resolver; engine-family matching is insufficient. |
| Backends | `transform/compiler.py`, `transform/local_compiler.py`, `dataframe/protocol.py`, `runtime/dataframe_exec.py`, Polars/Pandas packages expose portable/dataframe operations | Reuse pinned public operations; no native body or helper-triggered rediscovery. |
| Interchange | `interchange/tabular` provides Gate A descriptor, validation, fidelity, bounds and evidence; runtime lookup currently uses `/1` boundaries | `/2` transfer stores/executes its exact descriptor; no consumer-side mechanism selection. |
| Persistence/resources | `runtime/artifacts.py` holds native handles in memory and collectible workspace JSON; `runtime/incremental.py` has memory/file stores; resource protocol separates acquire/release. Connector models/session/CDK publication helpers model committed/rolled-back/unknown and cleanup/reconciliation receipts | Reuse vocabulary and safe primitives; no DB/control-plane/state-format migration. |
| Reports/tests | `etlantic.run_report/1`, status enums and lifecycle provenance already exist. Host emits namespaced backend metadata; `tests/reports/test_metadata_namespace_0_51.py` covers old aliases. Runtime selection/reliability, planner wire/tamper and Gate A runtime tests exist | Preserve report schema and silent reader migration; verify physical writers before migration. |
| Docs/examples | API plan/runtime, planning/capability guides and portable examples exist; `examples/interchange_polars_pandas.py` uses native bodies | Add portable adaptive example; do not relabel native example as adaptive evidence. |
| Dependencies | Core Python `>=3.11`, Pydantic `>=2.12,<3`, AnyIO `>=4,<5`; Polars `>=1.0,<2`, Pandas `>=2.2,<3`, optional PyArrow `>=14`. Plugins currently require core `>=0.52.0,<0.53` | Preserve optional imports/backend ranges; coordinate release version constraints/lock. Installation is not qualification. |
| CI/runtime matrix | `ci.yml` calls `checks.yml`: Linux/macOS/Windows × Python 3.11/3.12/3.13, Ruff/format, Pyright, core/optional tests, docs, diagnostics/protocol/surface, security/manifests/release, wheels, portable/adaptive evidence, benchmarks | Retain gates and add physical runtime matrix. No Python 3.14 qualification claim. |

Focused baseline executed before planning:

```bash
.venv/bin/python -m pytest -q \
  tests/plan/test_adaptive_planner_0_52.py \
  tests/plan/test_adaptive_wire_0_51.py \
  tests/runtime/test_scheduler_dispatch.py \
  tests/runtime/test_selection.py \
  tests/runtime/test_reliability_runtime.py
```

Result: **77 passed, 3 existing namespace warnings in wire fixtures, 24.90 s**.
This proves baseline behavior, not the proposed feature. Full gates were
inspected, not executed during planning.

## Change Boundary

### Problem and Desired Outcome

0.52 can inspect authoritative physical plans but cannot execute them. The
existing host would reject or reinterpret work through logical scheduling,
implicit conversions and sink-side commits. Admission, exact dispatch and
fused-member lifecycle are not yet executable contracts.

After 0.53, built-in local SDK/CLI/scheduler execution runs an internally
qualified static-batch `/2` row after whole-DAG live admission. Traces match
stored dependencies/targets; outputs, validation, logical outcomes, retries,
cancellation, cleanup and publication match explicit baselines, or unsupported
policies fail earlier safely. Other consumers stay closed. Execution remains
**Experimental/fixture-qualified**, never Available before 0.54.

### In Scope

- Data-only executable lowering using existing placement/contract/evidence.
- Versioned physical protocol, minimum public conformance, complete live
  admission, exact support-row matching and scoped selected-dependency loading.
- Physical scheduling and local implementations of compute, transfer,
  collection, validation, materialization, reuse and publication.
- Member attempts/middleware/events/report projection; owned/shared artifact
  lifecycle, timeout/cancellation/cleanup, receipts and reconciliation obligations.
- SDK, definition authoring, local CLI and stored-plan LocalScheduler execution;
  partial selection, unsupported consumers, differential/failure fixtures.
- Required API/schema/diagnostic/reference/example/CI/packaging and 0.53 evidence.

### Touched Surface

| Area | Expected files/modules |
|---|---|
| Planning/public request | `plan/planner.py`, `pipeline.py`, `authoring/lifecycle.py`, existing resolution/context helpers as needed |
| Executable IR | `planning/adaptive.py`, `plan/adaptive_model.py`, `plan/physical.py`, adaptive Schema and explain projection |
| Runtime | `execute.py`, `scheduler.py`, `orchestrator.py`, `dataframe_exec.py`, `artifacts.py`, `events.py`; new `adaptive_admission.py`, `physical_protocol.py`, `physical_scheduler.py`, `physical_host.py`, `adaptive_support.py` under `runtime/` |
| Adapters/trust | Exact registry/new physical adapters under `runtime/executors/`; scoped runtime discovery in `lifecycle/runtime.py` and plugin coordinator/lifecycle; existing public portable/dataframe/Gate A/storage/connector primitives |
| Exports/packages | `runtime/__init__.py`, minimum `testing` helper, protocol/surface/diagnostic inventories; small additive Polars/Pandas hooks only if necessary; release version constraints/manifests/lock |
| Verification/docs | Focused `tests/runtime/physical/`, existing compatibility/consumer suites, `scripts/check_adaptive_0_53.py`, evidence/exit gate, API/CLI/planning/capability references, one portable example, CI |

Small shared-helper extraction is allowed to preserve semantics. Unrelated
engine refactoring, documentation redesign and repository-wide repair are not
required. A defect outside these behaviors is follow-up work unless it prevents
safe implementation of a required row.

## Public Contract — REQUIRED BEHAVIOR

### Entry Points, Defaults and Request Capture

1. Explicit remains default. Existing `/1` calls, canonical bytes/fingerprints,
   runtime and step plugin protocols remain unchanged; no adaptive stage runs.
2. Existing `Pipeline.run/arun`, `run_pipeline/arun_pipeline`, local CLI
   `etlantic run` and `LocalScheduler` dispatch by actual plan schema. Runtime
   signatures and `PipelineRunReport` returns remain.
3. Add optional keyword-only `request: RunRequest | None = None` to
   `plan_pipeline`, `plan_pipeline_with_report`, `Pipeline.plan` and definition
   planning dispatch. This captures **adaptive** execution inputs before
   lowering. `None` uses Profile defaults, existing selection and a default
   request. Supplying the new keyword with an explicit profile produces
   validation diagnostic `PMADP522`; do not widen `/1` to serialize it.
4. Adaptive `arun_pipeline` passes its request through the same planner.
   Apply parameter/binding/implementation overrides before validation and
   candidate construction in frozen precedence order. Overrides cannot widen
   eligibility or select native bodies. Capture intent/materialization/
   invalidation/retry/timeout/cancellation/execution-relevant metadata too.
   Never resolve credentials while planning.
5. Non-default request selection and an explicit `selection` must normalize
   identically or fail `PMADP122`. Default-all request selection lets existing
   `selection` retain its meaning. Stored partial execution requires exactly
   the stored canonical scope, never re-slicing.
6. Built-in `LocalScheduler.analyze/execute` accepts `PlanDocument` with schema
   dispatch. Analysis returns `SchedulerSupportReport`, reads metadata only
   and grants no live authority. Stored `/2` execution independently verifies
   and admits every invocation. No new raw-JSON CLI runner is required.
7. Old `ExecutionScheduler` and `EngineExecutor` contracts remain valid for
   explicit third-party use. Installation or advertising a schema string alone
   grants no `/2` authority.

### Fixed Envelope and Support Gate

No new Profile flag, environment bypass or user-editable topology qualification
is added. Existing adaptive opt-in plus a packaged internally qualified matrix
is the gate.

Required families: **Local-only**, **Polars-only**, **Pandas-only**,
**Polars→Pandas**, **Pandas→Polars**. Directional rows have exactly one
cross-target cut; Local is the host, not a third placement target. Single-target
fixtures cover chains, one diamond and fan-out with independent consumers;
directional fixtures cover a chain and separate ports at the same cut. Chain
patterns allow lengths through the existing 256-selected-node limit.
Diamond/fan-out/multi-port patterns are finite named fixture signatures, not
arbitrary DAG support. Fused/unfused variants and partial slices require
signature coverage of their own.

Topology pattern IDs and exact shapes are:

| Pattern | Shape (node names below are role labels, not required user names) |
|---|---|
| `chain/1` | One source, zero or more ordered portable steps, optional terminal sink; all selected nodes form one path. Partial slices preserve that path and may end before the sink. |
| `diamond/1` | One source feeds two portable steps; both feed one two-input portable join step; that step feeds one sink. Single target only. |
| `fanout/1` | One source feeds one shared portable step; it feeds two portable leaf steps, each feeding its own sink. Single target only. |
| `dual-port-chain/1` | One source feeds one producer step with two output ports; each port feeds a different input of one consumer step; that step feeds one sink. One directional cut between producer and consumer. |

Directional `chain/1` rows require non-empty contiguous producer and consumer
target segments. Fusion may replace only an ordered contiguous step subsequence
whose contracted inputs/outputs preserve the pattern and whose stored evidence
proves the policy boundary rules. Boundary units remain explicit; a pattern is
matched over logical roles plus their physical realizations, never engine count
alone. Unknown pattern IDs reject. Packaged support records have closed fields:
`schema`, `row_id`, `pattern`, `target_families`, `version_requirements`,
`unit_kinds`, `contract_profiles`, `io_families`, `policy_modes`, `evidence_refs`,
`maturity`; schema is `etlantic.adaptive_support/1` and maturity in this increment
is `Experimental`. Runtime support data is packaged and digest-bound separately
from generated campaign reports, avoiding an evidence/plan fingerprint cycle.

Rows specify topology/port pattern, target relationships, executor/compiler/
package/protocol versions, portable baseline/fidelity, I/O families, allowed
unit kinds/policies and content-addressed passing evidence. Matching may ignore
user node names; it preserves kinds, wiring, boundaries, target relationships
and policy requirements. Engine names alone cannot match. Missing/unmatched or
unsupported rows fail `PMADP500`; drift fails `PMADP501`, before effects.

| Surface | Initial supported behavior |
|---|---|
| Sources | Built-in memory and local JSON/CSV records, contract and safe-read policy; normalize into assigned target |
| Sinks | Built-in memory replacement, null/no-write and local JSON/CSV **overwrite** through physical publication and safe atomic file primitives |
| Other sink modes | Append, merge/upsert, skip-if-exists, callable writers and unqualified connector writers reject before I/O; explicit behavior stays |
| Intents | Standard and validate/no-write. Incremental/backfill/replay and other lifecycle intents/state requirements reject `PMADP522` |
| Materialization | In-memory and named local workspace record checkpoints using existing serializers; no remote cache/provider |
| Reuse | Existing producer dependency followed by local artifact verification/selection; no producer skipping or placement on miss |
| Validation | Existing contract/quality/freshness/schema policy when qualified; unsupported capability rejects rather than run unvalidated |

Rows may subdivide requirements, never remove a required family, widen this
boundary or advertise Available. Packaging ranges mean installation
compatibility; evidence identifies exact tested backend versions.

### Executable `/2` Serialization

Retain top-level `/2` shape and seven-kind enum. Add data-only records inside
existing namespaced metadata/envelope maps:

- New generated plan marker: `etlantic.planner_version="0.53"`.
- Executable plans/regions: `etlantic.execution="local-static-batch/1"`;
corresponding unit policy uses this execution value. Without a qualified
executable envelope, a plan remains planning-only.
- `plan.metadata["etlantic.runtime"]`, schema `etlantic.adaptive_runtime/1`:
  canonical effective request, support-row reference, policy/binding/contract
  definition fingerprints and exact package/protocol/evidence references.
  Exclude runtime IDs/times; retain only secret/config references.
- Compute `metadata["etlantic.implementations"]`, ordered by `logical_nodes`:
  portable `ImplementationDescriptor` serialization for steps; data-only
  source-read/sink-prepare descriptors for source/sink nodes. Store canonical
  portable definition/digest and exact compiler, never callable/native body,
  import expression, backend handle or unresolved compiler choice.
- Transfer `metadata["etlantic.interchange"]`: exact `InterchangeDescriptor`,
  existing target/port routes and directional handoff evidence. Distinct port
  edges keep distinct descriptors.
- Retry policy: effective attempts/backoff/filter, member retry-safety,
  timeout/cancellation. Ownership: artifact/port identities, borrowed/shared/
  copied semantics, cleanup owner/scope and retention. Boundary requirement maps
  identify exact validation/collection/checkpoint/reuse/sink operation; truthy
  flags alone do not authorize execution.

These participate in existing canonical unit/region/plan fingerprints. New
record schemas are closed and reject unknown fields/versions. Generated checks
must apply to 0.52 and 0.53 with additional executable validation for 0.53.
Admission always validates executable completeness regardless of planner label;
changing markers and recomputing a fingerprint cannot bypass checks.

Historical valid 0.51 foundation/0.52 planning-only `/2` remains readable,
verifiable, explainable, diffable and reserializable under existing guarantees.
Execution rejects it `PMADP500`; fresh planning creates an executable plan.
Never mutate/downgrade stored `/2`. Explain derives `planning_only` from the
stored envelope, separately reports qualification/availability, and performs
no live discovery. Stored capability claims are not live admission.

Adaptive plan generation outside the execution matrix retains the existing
0.52 planning capability and emits a 0.53 **planning-only** plan. It must not
invent a support row. A non-default execution request whose policy cannot be
lowered fails planning with `PMADP522`. A local run of an unmatched planning
topology fails admission with `PMADP500`; planning success is not execution
permission. An opted-in explicit fallback is possible only during planning
under the existing fallback contract, never after a stored `/2` is admitted or
rejected. The public run helper may execute an independently generated `/1`
fallback through the explicit path after its normal admission.

### Physical Executor Protocol

Expose provider contracts in `etlantic.runtime.physical_protocol` and re-export
from `etlantic.runtime`. Identity: **`etlantic.physical_unit/1`**, independent of
plan version. Use frozen data-only records; live context/handles are not wire
models.

| Type | Required contract |
|---|---|
| `PhysicalExecutorInfo` | Stable identity/package/version, supported plan/unit versions and kinds, capability fingerprint/evidence refs |
| `PhysicalUnitSupport` | Supported boolean, tuple of bounded structured code/unit/target/path/reason findings, protocol identity |
| `PhysicalArtifactHandle` | Existing `ArtifactRef`, live value, target identity, ownership and cleanup token; live value cannot serialize |
| `PhysicalUnitContext` | Exact plan/unit, run/unit attempt IDs, member counters, admitted adapters, effective policy, input handles and event/report services; no discovery access |
| `PhysicalLogicalOutcome` | Logical name/status/attempts/implementation/counts/failure stage/code/safe metrics; times may vary |
| `PhysicalUnitResult` | Protocol and unit/target ID, terminal `UnitStatus`, output handles, logical outcomes, safe diagnostics and optional existing commit/cleanup receipts |
| `PhysicalUnitFailure` | Typed execution error with unit/target/member attribution, safe code/stage/message and optional unknown receipt; no raw exception payload in wire summary |

Freeze these methods:

```python
class PhysicalUnitExecutor(Protocol):
    @property
    def info(self) -> PhysicalExecutorInfo: ...
    def analyze(self, plan: AdaptivePipelinePlan,
                unit: PhysicalUnit) -> PhysicalUnitSupport: ...
    async def execute(self, context: PhysicalUnitContext) -> PhysicalUnitResult: ...
    async def cancel(self, context: PhysicalUnitContext) -> None: ...
    async def cleanup(self, context: PhysicalUnitContext,
                      result: PhysicalUnitResult | None) -> tuple[CleanupReceipt, ...]: ...
```

Analysis does no compile/execute/acquire/secret resolution/source read/data
filesystem probe/staging/commit. Execution returns a terminal result or raises
attributed failure/cancellation. Cancel/cleanup tolerate partial initialization
and repetition. Result serialization emits safe summaries/refs, never live
values/context. Unknown versions/kinds fail closed; no wildcard negotiation.

Exact resolution uses admitted target identity + stored executor identity +
unit kind/protocol. A composite adapter may delegate to pinned compiler/plugin,
never substitute them. No new third-party entry-point group is required.
Add `etlantic.testing.run_physical_unit_conformance_smoke(executor, *, fixtures)`
using public imports for basic protocol behavior; comprehensive provider
qualification/maturity remains 0.54.

### Whole-DAG Live Admission

Before runtime session/lifespan, acquire, read, data probe/staging, artifact
invalidation, publication or external history write:

1. Verify schema/fingerprint, targets/decisions/regions, logical coverage and
   port routes, topology, unit/envelope versions, support row, static-batch
   restrictions and canonical request scope.
2. Validate captured policies/inputs against live execution. Scope drift is
   `PMADP122`; ineligible override `PMADP121`; changed request/binding/contract
   or live evidence `PMADP501`.
3. Evaluate allowlists/static trust before loading. Check all inventory
   evidence/version refs, including unused targets through installed metadata.
   Only selected runtime dependencies may load. Manual/resident extensions
   receive the same authorization/evidence checks.
4. Resolve every selected compiler/executor/dataframe/source/sink/storage/
   resource/applicable schema adapter. Unqualified providers reject without
   acquisition. Recheck exact package/protocol/capability/evidence digests,
   contract definitions, authorization/security/residency and every handoff.
5. Run all unit support analyses and check cleanup/publication authority,
   immutable descriptors and policy bounds. Last-dependency failure still
   starts nothing: zero reads/staging/mutation/commit.
6. Return an internal run-local admission result with pinned live adapters and
   immutable descriptors. Only it permits session entry. It is not serializable
   or reusable across runs/profile/registry changes.

Zero-I/O excludes authorized Python module loading/distribution metadata access;
it includes execution resources, data/filesystem probes and external writes.
Denied extensions are never imported. Authorized factories/analysis must be
side-effect-free under their trust contract; this is not a sandbox for malicious
installed authorized code.

Snapshot registries/policies per run; concurrent calls cannot mutate each
other's admission/adapter state. Recheck authorization at effects where the
existing provider contract requires it. Later revocation/failure stops affected
work, never redirects it.

### Scheduler and Unit Semantics

Every stored data/control/lifecycle dependency must succeed and its result must
be recorded before dependent readiness. Register outputs atomically before
releasing dependents. Ready ties use stored topological order then unit ID.
Completion order may vary, semantic outcomes may not.

Concurrency: captured Profile execution setting, else captured request
`metadata["concurrency"]`, else **4**, preserving existing precedence. `/2`
requires non-boolean integer `>=1`; attempts `>=1`, finite backoff `>=0`,
configured finite timeouts/abandonment `>0`. Invalid policies reject `PMADP522`
before effects. Active units never exceed concurrency; retry backoff retains
its unit slot. No new global scheduler or configurable ceiling.

| Kind | Required semantics |
|---|---|
| Compute/source | Safe admitted read, contract-check/normalize to planned target, typed output handles; no commit |
| Compute/step | Stored portable definition on pinned compiler; fused strategy is **ordered member interpreter**, one existing compiler execution per member with private intermediates; no native body/runtime fusion |
| Compute/sink | Gather routed inputs, prepare payload and assigned validation/schema work; pending logical sink completion; no write/state advance |
| Transfer | Exactly stored Polars↔Pandas Arrow Gate A mechanism/fidelity/ownership; conversion once here, not again implicitly in consumer; owned staging cleanup |
| Collection | Declared finite local partition/native value to stored consumer shape through admitted operations/bounds; not transfer alias/distributed execution |
| Validation | Stored contract/quality barrier and existing outcome, output valid handles; fail/reject/quarantine/warn/observe only where row proves behavior |
| Materialization | Owned named record checkpoint via safe atomic workspace serialization; ref/data/contract/producer fingerprints/retention metadata; unsupported serialization fails before writing |
| Reuse | After stored producer dependencies, verify existing fingerprint/contract/auth/ownership/retention. Hit selects artifact; safe miss/expiry/staleness selects already-planned producer result; malformed/unauthorized fails; no inserted work |
| Publication | Sole commit after stored barriers; receipt before readiness/sink success/admitted state advance; no-write suppression performs no sink effect |

Existing compute→materialization→reuse layout deliberately preserves producer
execution. Cache savings/producer skipping/runtime miss branches are not claims.
No new dependency kind is needed.

Use run-local plan/unit/port/attempt or generation identities. Failed attempts
leave no available partial output. Route handles by physical ports, not broad
logical-name lookup. Borrowed values are not destroyed. Shared values live
until all consumers are terminal; owned copies/staging have one cleanup owner.
Data checkpoint files may contain rows; metadata/plans/reports/evidence may not.

### Lifecycle, Failure, Retry and Cancellation

- Exactly one final report per selected logical node; boundary units enrich
  traces/reports without increasing logical counts. Empty boundary
  `logical_nodes` derives attribution from stored node/port routes, verified
  during admission.
- Fused members start in stored order. Successful prefix remains successful;
  failing member is failed/timed-out/cancelled; later unstarted members are
  skipped on failure or cancelled on run cancellation. Safe retry repeats only
  the failing member with private prefix inputs; successful members do not
  repeat. No fusion across effect/validation/publication/materialization/
  retry/state/security/selection boundaries.
- Preserve per-member counters, middleware/hooks, validation, metrics and exact
  implementation identity. Cancellation between members starts none later.
  Unit success needs every member and complete owned outputs.
- Failed/cancelled dependency blocks dependents (`PMADP521`). Independent
  branches may finish under existing local partial-run semantics. Each sink
  requires its own stored barriers; no new all-sinks transaction.
- Retry uses captured policy/safety. Unsafe/unprovable policy rejects admission
  `PMADP522`; ambiguity never authorizes retry. Step timeout is a hard member
  deadline, not retried, matching current host. Run timeout includes backoff.
- Cancellation stops scheduling, requests cancel, drains active work, then
  shield-cleans owned artifacts/resources. Normal completion leaves no runner
  tasks pending. Follow existing async cancellation propagation convention.
- Native work exceeding configured abandonment is abandoned; fence late results
  from registration/publication. Do not free in-flight/borrowed buffers early;
  record unresolved cleanup. Fake cancellable adapters do not prove native
  cancellation. Shielded cleanup uses the configured abandonment bound; without
  one, cooperative cleanup drains fully.
- Cleanup is repeatable; already-removed owned staging is success. Failure emits
  `PMADP523` with safe artifact/owner obligations, prevents entirely successful
  run status and retains primary execution/publication failure.

### Publication, Persistence and Repeated Operations

Reuse `CommitReceipt`, `CleanupReceipt`, `ReconciliationResult` and source
publication-barrier semantics. File adapter uses safe atomic overwrite and
**destination-scoped writer lock**, not generic JSON/CSV adaptive writes. Memory
atomically replaces prepared value; null/validate/no-write writes nothing.

Publication ID derives from run ID + plan fingerprint + publication-unit ID,
stable across retries in that run. New run means new operation, not global
idempotency. Content digests support reconciliation, not authorization.
Concurrent file writers serialize; receipts identify each effect. Cross-process
exactly-once, crash-resumable scheduling and deduplication of separate runs are
not claims.

Committed receipt precedes readiness/sink success/state advance/report
persistence. Definite rollback may retry only under admitted safety. Timeout,
cancel or lost acknowledgement at commit becomes **unknown**, `PMADP524`, blocks
blind retry and affected state advance. Existing reconciliation can prove commit
or rollback; unresolved stays failed/partial with safe identifiers and explicit
obligation. Preparing a payload is never evidence of commit.

Report persistence failure after commit preserves existing published-but-report-
failed diagnostics and cannot repeat commit. Use existing safe workspace
receipt/sidecar primitives; do not add DB migrations, migrate checkpoints/reports/
receipts/control-plane records or infer crash recovery from local sidecars.

### Errors, Reports and Compatibility

| Code | Required meaning |
|---|---|
| `PMADP103/120/121/122/124` | Non-local orchestration, native/ineligible override, scope drift, stored downgrade; retain existing meanings |
| `PMADP400`–`PMADP404` | Schema/version/integrity/topology/coverage/ownership/publication-authority validation |
| `PMADP500` | Unsupported consumer/protocol/support row or planning-only envelope |
| `PMADP501` | Live authorization/package/capability/resource/binding/contract/request/evidence drift |
| `PMADP502` | Streaming/runtime expansion |
| `PMADP520` | Exact dispatch/result identity cannot be honored; never substitute |
| `PMADP521` | Failed/cancelled dependency |
| `PMADP522` | Invalid/unqualified execution policy |
| `PMADP523/524` | Cleanup obligation; unknown publication/reconciliation |

Admission raises `PipelineExecutionError(code=..., stage="admission")`;
planning uses existing validation/report variants. After admission, failures
follow existing terminal report/async cancellation behavior. Bound diagnostic
unit/target/member/path context; no raw backend reprs, credentials, rows or
private paths. CLI retains existing exit-code mapping and report formats.

Keep `etlantic.run_report/1`, lifecycle schema and status enums. Store trace in
`PipelineRunReport.metadata["etlantic.physical_execution"]`: protocol identity,
stored plan/support row, ordered per-unit summaries/provenance and safe receipt/
obligation refs. Step attribution may use that namespace too. Backend step
metrics emit only `etlantic.dataframe`, `etlantic.sql`, `etlantic.spark`,
`etlantic.spark_schema`; reader migration is not a substitute for writer
compliance. Keep legacy silent alias removal, namespaced collision precedence
and idempotent reserialization. Do not rename third-party metadata.

No resolved secrets/rows/native handles in plans/explain/events/reports/evidence
or error/receipt summaries. Keep handles process-local, public conformance free
of private imports and core free of mandatory optional backend/Arrow imports.
Preserve Python/OS/dependency and existing persisted-data compatibility.

## Invariants and Security/Reliability Requirements

These are objectively verifiable requirements for this change:

1. Complete admission precedes every execution effect, even final dependency
   failure; no external persistence of an admission report.
2. Production applicable plugin/optimization/schema/resource allowlists stay
   fail-closed; manual/resident adapters cannot bypass trust.
3. Stored physical edges/targets are sole scheduling/dispatch authority; no
   runtime placement, fallback, native substitution or extra work.
4. Complete typed/validated output and required barriers precede readiness/
   affected commit; partial/late outputs never become reusable.
5. Shared/borrowed/owned artifact consistency and cleanup ownership are preserved.
6. Committed or unresolved unknown effects cannot repeat through retry/report/
   cancellation/cleanup; affected state advances only after proved commit.
7. Logical reports/events/physical traces agree with stored provenance and totals.
8. Sensitive metadata is recursively isolated from live data; safe root confinement
   and locking apply to file execution.
9. Concurrent run adapter maps/counters/artifacts/receipts remain isolated.
10. Explicit `/1` remains independent in bytes, lifecycle and plugin behavior.

## Edge Cases and Failure Modes

| Case | Required outcome |
|---|---|
| Empty scope/DAG | Existing non-empty scope/wire rejection before acquisition |
| Empty rows/all invalid/nullable Arrow zero-row schema | Preserve typed empty artifact and policy outcome; missing is not empty |
| Missing source/file | Attributed post-admission read failure; no affected publication |
| Unknown version/kind, cycle/dangling/duplicate port route, recomputed tamper | Strict pre-effect rejection |
| Last dependency/manual plugin/contract/handoff drift | Whole-DAG rejection, zero earlier starts |
| Broader/narrower stored partial request | `PMADP122`, no re-slice |
| Multiple ports same target pair | Separate routed transfer results, no alias/conversion repetition |
| Diamond/fan-out opposite completion order | Dependencies and shared lifetime; one cleanup authority |
| Fused middle failure/retry/timeout | Preserved prefix, deterministic counters/statuses, no premature later start |
| Cancellation before admission/backoff/handoff/materialize/commit | Stop scheduling; owned cleanup/late-result fencing; commit ambiguity is unknown |
| Reuse hit/miss/expiry/stale/unauthorized/malformed | Verified hit or stored producer result; unsafe state fails, no placement |
| Cleanup raises/already deleted | Primary failure plus obligation, or repeatable owned-cleanup success |
| Concurrent same runtime/destination | Isolated mutable state, serialized file commit |
| Report failure after commit | Publication retained, no repeat |
| Historic `/2` or unsupported consumer | Readability preserved where supported; reject before acceptance/effects |

## Acceptance Criteria

Stable IDs define this change. Original six phase headings are refined:
`AC-053-01` → AC-004–007; `AC-053-02` → AC-008–009;
`AC-053-03` → AC-010–017; `AC-053-04` → AC-018–019;
`AC-053-05` → AC-020–021; `AC-053-06` → AC-002/022/024.

| ID | Observable requirement |
|---|---|
| **AC-001** | Existing explicit `/1` canonical bytes/fingerprints and runtime/plugin outcomes remain; adaptive discovery/admission counters stay zero. |
| **AC-002** | SDK/class/definition/CLI/stored LocalScheduler execute every required qualified family; unmatched topology/target/policy/version rejects before effects. Default stays explicit. |
| **AC-003** | Adaptive planning variants capture identical effective input and emit verified round-trippable executable descriptors. Historic `/2` stays readable but rejects execution; envelope/marker tamper cannot bypass validation. |
| **AC-004** | Any admission failure, including last dependency, starts zero units/session/resources/reads/data probes/staging/invalidation/commits/history writes. |
| **AC-005** | Denied installed/manual/resident adapters are not newly loaded/used; exact live authorization/version/capability/resource/binding/contract/directional-evidence drift rejects whole DAG with attributed code. |
| **AC-006** | Public executor analysis is metadata-only; unsupported versions/kinds reject, exact stored dispatch/result identity is enforced, explicit step executor behavior remains usable. |
| **AC-007** | Runtime scope/input drift rejects before effects, scope with `PMADP122`; overrides apply before planning and cannot enlarge eligibility/select native bodies. |
| **AC-008** | Trace shows every dependency succeeds/results register before dependent start; no logical/region ready loop or runtime insertion/replacement. |
| **AC-009** | Peak active units never exceeds captured concurrency; invalid bool/integer/range/nonfinite policies reject; ready ordering follows stored topology/ID. |
| **AC-010** | Source/portable singleton/fused/sink prepare uses exact target and preserves typed empty/nullable outputs; sink prepare commits zero and native body invokes zero. |
| **AC-011** | Both real Arrow directions execute stored descriptor/fidelity/ownership and distinct port routes; one conversion, no implicit second handoff. |
| **AC-012** | Collection executes declared finite shape/bounds, has distinct trace and refuses unqualified distributed/collection policy. |
| **AC-013** | Required validation/schema/freshness outcomes precede affected publication; failed barrier commits zero; unsupported policy rejects admission. |
| **AC-014** | Materialization yields complete owned safe checkpoint/ref or no partial available output; safe reuse hit/miss/expiry/stale follows stored producer path; unauthorized/malformed fails without placement. |
| **AC-015** | Fused middle failure yields preserved prefix, attributed failing member and deterministic unstarted outcomes; safe retry repeats only failing member, unsafe policy rejects, step timeout never retries. |
| **AC-016** | Failed dependency blocks downstream while independent branches preserve explicit partial-run semantics; every selected logical node has one terminal report. |
| **AC-017** | Cancellation/run timeout stops scheduling, drains/cancels and cleans owned work or records abandonment/obligation; late result cannot register/publish and borrowed/in-flight buffers survive safely. |
| **AC-018** | Only publication commits; qualified memory/file overwrite/no-write matches baseline; committed receipt precedes sink success/state advance, generic retry repeats no committed effect. |
| **AC-019** | Ack loss/commit timeout/cancel yields unknown + `PMADP524`, no blind retry/state advance and retained reconciliation IDs; cleanup/report failure retains known commit without repeating it. |
| **AC-020** | Events/trace/logical report agree with stored unit/target/members; boundary units add no logical count, and stable semantic projections match explicit fixtures excluding variable IDs/times. |
| **AC-021** | Writers emit namespaced metrics before migration; old aliases migrate silently/collision-idempotently; recursive projections contain no resolved secret/row/native handle. |
| **AC-022** | Compile/optimize/external scheduler/CP acceptance/durable/service/remote/federated/streaming/dynamic paths reject `/2` before acceptance/acquire/external I/O; no durable qualification claim. |
| **AC-023** | Concurrent/separate runs isolate pins/counters/artifacts/receipt IDs; shared lifetime and repeatable cleanup hold; failure yields `PMADP523` owner obligations. |
| **AC-024** | Public smoke, five-family differential/failure campaigns and non-writing evidence gate pass on required environments; matrix/docs advertise only Experimental/fixture-qualified; core wheel imports without optional backends. |

## Verification Matrix

Every AC needs executed proof, not self-declared flags. Proposed new tests live
under `tests/runtime/physical/`; organizing differently is allowed with equivalent
coverage. Retain meaningful surrounding fixtures.

| AC | Preferred proof | Demonstration |
|---|---|---|
| AC-001 | Compatibility + integration | `/1` goldens/no-adaptive sentinels and existing runtime/selection/reliability/dataframe/plugin suites |
| AC-002 | Integration + contract | Five-family class/definition/CLI/stored scheduler parity and negative support signatures |
| AC-003 | Contract + compatibility | Runtime record/unit schemas; historical wire fixtures; recomputed tamper/marker matrix; planner variant parity |
| AC-004 | Security integration | Every effect sentinel including lifespan/history and final-dependency failure injection |
| AC-005 | Security integration | Allowlist/manual/resident matrix; per-family exact digest/auth/binding/contract/handoff drift and load counters |
| AC-006 | Contract + static gate | Public executor smoke, analysis no-effect, unknown versions/kinds, malformed result identity, explicit regressions |
| AC-007 | Compatibility + integration | Full/null/partial selection and every override/changed input; native invocation sentinel |
| AC-008 | Integration + property | Chain/diamond/data/control/lifecycle traces, seeded completion permutations, results-before-ready/no-logical-loop assertions |
| AC-009 | Unit + integration | Policy boundaries/NaN/infinity/bool, peak active count/ready order/backoff slots |
| AC-010 | Real-backend integration + differential | Local/Polars/Pandas portable/empty/null and operation baselines; prepare zero-commit |
| AC-011 | Contract + real-backend integration | Both Arrow directions/ports, schema/ownership/conversion count, failure/cancel cleanup |
| AC-012 | Unit + integration | Finite collection bounds/shapes, distinct trace, unsupported distributed/native shape |
| AC-013 | Integration + differential | Passing/failing and row-qualified warn/observe policies, barriers-before-commit and unsupported policy |
| AC-014 | Integration + compatibility | Safe checkpoint round trip/write/serialization failure; hit/miss/expiry/stale/tampered/unauthorized, no extra producer |
| AC-015 | Integration + fault injection | Every member failure, prefix hooks/counters, safe/unsafe retry, member timeout/cancel between members |
| AC-016 | Integration + differential | Failed/independent branch, downstream no-start and terminal logical/partial outcomes |
| AC-017 | Real-backend integration + fault injection | Pre-admission/backoff/transfer/materialize cancellation; native drain/abandon/late fencing, run timeout |
| AC-018 | Integration + differential | Memory/JSON/CSV overwrite/null/validate/no-write; locks, receipt-before-success, commit counters/source barrier |
| AC-019 | Integration + fault injection | Ack loss/timeout/cancel/reconciliation matrix, repeated unknown refusal and post-commit report/cleanup failure |
| AC-020 | Contract + differential | Fused/unfused provenance, one-member counts and semantic projections |
| AC-021 | Migration + security/static gate | Existing metadata migration fixtures, writer-before-reader, recursive sensitive-marker/handle scans |
| AC-022 | Security integration + compatibility | Public consumer no-load/no-I/O/no-accept matrix; explicit worker/compiler/CP regressions |
| AC-023 | Integration + fault injection | Concurrent same-runtime/destination, isolated state, shared final-consumer cleanup/repetition/failure receipts |
| AC-024 | Static gate + integration + manual | Executed digest-bound evidence, wheel imports, environment results, portable example and truthful docs |

Differentials use existing portable ordering/null/type/numeric rules. Compare
outputs, validation, logical statuses, attempts, cleanup and commit outcomes.
Normalize only variable run/attempt IDs, timestamps and durations; do not erase
substantive implementation/validation/retry/error differences.

## Implementation Phases — RECOMMENDED IMPLEMENTATION

Dependencies/required behavior are mandatory; internal helper layout can adapt.
Keep each execution row closed until its real qualification evidence passes.

| Phase | Goal and modules | Required behavior/tests | Docs/config/migration | Dependencies |
|---|---|---|---|---|
| **1. Protocol/envelope** | Physical protocol/exact registry; existing lowering/IR/Schema/public request dispatch | AC-003/006/007/009, historic wire and `/1` identity. Keep singleton lowering default; implement fused interpreter fixtures without new fusion optimizer | Protocol/schema/surface/diagnostics, adaptive-only request keyword; no persistence migration | Shipped 0.52; runtime still rejects |
| **2. Admission/support** | `adaptive_admission.py`, `adaptive_support.py`, scoped discovery, scheduler analysis | AC-002/004–007/022; all drift/last-dependency/denied-load/no-effect sentinels and matcher | Support-row schema/failure stages; rows remain disabled | Phase 1 |
| **3. Scheduler/host** | `physical_scheduler.py`, `physical_host.py`, extracted lifecycle/report operations, physical routing/events | AC-008/009/015–017/020/023 with fake adapters: dependencies, permutations, concurrency, member retry, cancellation/fencing; logical regressions after extraction | Trace/lifecycle reference; no new status or old executor redefinition | Phases 1–2; fakes do not qualify rows |
| **4. Real adapters/boundaries** | Local/dataframe compiler adapters, Gate A, artifact/checkpoint helpers; small public package hooks if needed | AC-010–014/017/021: actual Local/Polars/Pandas, both Arrow directions/ports, typed empty/null, ownership, safe materialize/reuse, native cancellation | Artifact sidecar/ownership/optional installation; existing persisted formats unchanged | Phase 3; no actual commit until Phase 5 |
| **5. Publication/entry** | Publication adapter/receipts/safe I/O; execute/local scheduler/CLI | AC-002/018/019/021–023: session after admission, no-write, locks, commit/ack/report/cleanup faults, repeated/concurrent/public entry parity | Supported modes, CLI formats/codes, reconciliation/disable/drain guidance | Phase 4 and safe Phase 3 lifecycle |
| **6. Evidence/exit** | Runtime compatibility/differential/security tests, verifier, packaged support data, CI/docs/example | All ACs and existing gates. Enable only proven rows; required backend jobs cannot qualify skipped tests | 0.53 exit gate/matrix/API/schema/report/portable example; coordinated release constraints/manifests/lock, unchanged backend ranges | Phases 1–5; no Available claims |

Phase 6 retains Ruff/format/Pyright, relevant core/optional suites, docs,
diagnostics/protocol/surface/security/manifests/release/wheel gates and portable
0.50/adaptive 0.52 evidence. Add Local tests to existing Linux/macOS/Windows ×
Python 3.11/3.12/3.13 core jobs. Run real Polars/Pandas/Arrow positive and
lifecycle fixtures on that matrix with pinned tested backend versions. Broader
backend-version/provider/performance/graduation campaigns remain 0.54.

### Evidence Artifacts

Use distinct `docs/11_DEVELOPMENT/evidence/adaptive_0_53/` with index and
AC/test traceability:

- Whole-DAG admission/drift/zero-effect matrix.
- Executor protocol and physical scheduler conformance.
- Five-family exact local matrix with both Arrow directions and versions.
- Member retry/cancellation/cleanup/publication failure campaign.
- Adaptive/explicit differential and attribution report.
- Unsupported consumers, historic wire/report compatibility, redaction matrix.
- Environment/wheel/documentation/example results.

`check_adaptive_0_53.py --write` executes campaigns and writes evidence; default
non-writing mode executes/verifies and rejects stale/missing/skipped-required/
fabricated proof. Bind source/tests/package/support inputs without self-referential
digests. Retain historical evidence meanings. If current-tree 0.52 verifier
assumes every local adaptive call rejects, narrowly update superseded harness
assertions to an unsupported/planning-only row or historical contract. Do not
exempt the old gate, rewrite its release claims or call 0.53 execution a 0.52
regression.

## Risks

| Risk | Mitigation |
|---|---|
| Planning-only/marker tamper gains authority | Label-independent executable validation + fresh planning; AC-003/004 |
| Shared host extraction changes `/1` | Separate loops/small operations, goldens/runtime regressions; AC-001 |
| Installation/engine name/arbitrary graph inherits qualification | Exact packaged pattern/evidence matcher; AC-002/022/024 |
| Implicit conversion bypasses transfer | Routed handle path/conversion-count sentinel; AC-011 |
| Fusion changes retry/timeouts | Ordered member interpreter/private prefix/counters; AC-015/020 |
| Native cancellation mistaken for completion | Real tests/drain/abandon/fencing/buffer lifetime; AC-017/023 |
| Lost acknowledgement/report persistence repeats effect | Explicit receipts/unknown/obligations; AC-018/019 |
| Mutable runtime races | Per-run pins/context/artifacts and destination locks; AC-005/023 |
| Old rejection-only evidence gate conflicts | Retain historical/negative claim, adapt superseded assertions only; AC-024 |
| Broad package ranges advertised qualified | Exact tested row/environment versions; 0.54 owns graduation |

## Explicit Non-Scope

- SQL/DuckDB/DataFusion/PySpark/Spark Connect or other adaptive engines.
- Durable/control-plane/service/remote/federated workers, distributed providers,
  external compilation, streaming/dynamic/runtime-expanded graphs.
- Native eligibility, runtime replanning/fusion/speculation/telemetry placement,
  approximate solving or new optimizer behavior.
- General graphs beyond named rows; multi-cut/three-target/Local↔dataframe
  placement; all-sink/global transactions.
- New incremental/backfill/replay; callable/unqualified connector writers;
  adaptive append/merge/upsert/skip-if-exists.
- Producer-skipping cache reuse/miss branches/remote caches, DB or persisted-state
  migrations, crash-resumable execution/cross-run exactly-once or sandboxing
  malicious installed authorized code.
- Generic/third-party metadata renaming, whole-runtime consolidation, unrelated
  engine/docs repair, Python 3.14 or backend-major upgrades.
- 0.54 comprehensive provider/version/performance qualification, availability
  graduation and final go/no-go decision.

## Known Pre-existing Problems and Follow-Up Candidates

GitHub was available; open issues were searched and applicable existing issues
read. No duplicate follow-up issue is necessary.

| Finding | Classification / tracking |
|---|---|
| ROADMAP/Planning Hub retain stale 0.51 status beside published 0.52; forward table mislabels foundation row | Docs follow-up [#86](https://github.com/eddiethedean/etlantic/issues/86); update only statements required to describe this change truthfully, not global navigation cleanup |
| Native interchange example cannot qualify portable adaptive | Existing quickstart work [#83](https://github.com/eddiethedean/etlantic/issues/83); add required portable fixture/example, retain existing native example |
| Old #70/#73 include SQL/Spark; #90/#92 mention supported durable paths | [#30](https://github.com/eddiethedean/etlantic/issues/30) staged contracts govern; prove rejection here, do not implement broader paths |
| Reserved incomplete registry/planning-only envelopes/version-specific generated checks | **In-scope gaps**, [#88](https://github.com/eddiethedean/etlantic/issues/88), [#90](https://github.com/eddiethedean/etlantic/issues/90), #69–#73; not a reason for global refactoring |

No unrelated production defect was independently established by focused
inspection. Three baseline namespace warnings are existing wire fixture
behavior, not confirmed release failures. Unrun gates cannot be called
pre-existing failures.

## Definition of Done

All AC-001…AC-024 have executed passing proof; required explicit/wire/report/
plugin/runtime compatibility is preserved; five-family local and unsupported
rows match docs/evidence; no substantive regression or security/publication/
data-loss release blocker attributable to this change remains.

Relevant existing gates and new verifier pass. Exceptions are independently
reproduced on unchanged baseline, recorded with scope/follow-up and do not make
this runtime unsafe. Docs/example match behavior; evidence is reproducible,
digest-bound and secret/row-free. 0.54 graduation remains pending. The repository
need not be globally defect-free.

## Plan Decision

The shipped planner and backend primitives provide the foundation. Executable
envelope/admission/scheduler/adapter/lifecycle/evidence work is explicitly
assigned. No unresolved architectural decision blocks this bounded contract.

**READY FOR IMPLEMENTATION**
