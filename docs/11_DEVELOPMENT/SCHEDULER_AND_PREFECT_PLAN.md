# Local Scheduler and Prefect Integration Plan

> **Plan status: Shipped local MVP in 0.16+** (`etlantic-prefect`); remaining
> deploy and serve scope is open.
>
> **Current 0.37 boundary:** ETLantic core provides local scheduling, the
> optional Prefect package provides the Python-native local MVP, and
> `etlantic-airflow` provides external artifact compilation. Production
> profiles must explicitly select and allowlist their orchestrator.
>
> **Scope:** ETLantic core, `etlantic.orchestration`, and optional orchestrator
> packages. See [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md) and the
> [Planning Hub](PLAN_INDEX.md).
>
> **Review trigger:** Update when Prefect deploy/serve work enters scope, the
> scheduler protocol changes, or conformance claims expand.

## Decision

ETLantic will keep a small built-in local scheduler as the default development,
test, notebook, and embedded execution path. It will not embed Prefect,
Airflow, Dagster, or another orchestration framework in core.

ETLantic will:

1. Extract the domain-independent scheduling loop behind a stable scheduler
   boundary.
2. Keep ETLantic ownership of plan validation, asset resolution, plugin and
   implementation selection, physical regions, validation boundaries,
   materialization, output normalization, lifecycle events, redaction, and
   `PipelineRunReport` production.
3. Ship `etlantic-prefect` as the reference optional Python-native
   direct-execution scheduler (local MVP; deploy/serve remain future work).
4. Keep `etlantic-airflow` as the reference external artifact compiler.
5. Require every scheduler/orchestrator integration to consume a resolved
   `PipelinePlan` without re-planning it or changing observable semantics.

Prefect is not the automatic default for `development`, `test`, or
`production`. Production profiles select and allowlist an orchestrator
explicitly.

## Why retain a built-in scheduler

The local runner is more than a generic topological executor. It coordinates
ETLantic-specific semantics that no general orchestrator should own:

- Extract and Load execution boundaries
- native and portable transformation realization
- dataframe, SQL, and Spark execution regions
- typed input/output validation
- valid, invalid, and side output roles
- materialization and ownership boundaries
- retries, idempotency, callbacks, and partial-run selection
- logical identity, diagnostics, redaction, and run reports

Replacing the local runner with Prefect would still require an ETLantic adapter
containing most of this logic while adding Prefect's task, state, configuration,
and deployment model. The built-in path therefore remains the smallest
zero-service execution kernel.

## Architectural boundaries

```text
Pipeline + Profile
        ↓
validated, resolved PipelinePlan
        ↓
ready work units
(logical nodes today; physical_units when fusion scheduling lands)
        ↓
ExecutionScheduler
   ├── LocalScheduler          built in and default
   └── PrefectScheduler        optional etlantic-prefect (0.16)

PipelinePlan
        ↓
Orchestrator compiler
   └── Airflow DAG             optional etlantic-airflow
```

The scheduler boundary coordinates ready work without re-planning. It does
not compile [DTCS](../04_TRANSFORMATIONS/DTCS.md) expressions, execute dataframe operations itself, resolve
secrets during planning, or invent retry/materialization semantics. Until
fusion-driven unit scheduling lands, schedulers map selected logical nodes.

## Proposed scheduler boundary

The exact API is finalized through implementation pressure, but its conceptual
shape is:

```python
@runtime_checkable
class ExecutionScheduler(Protocol):
    @property
    def info(self) -> SchedulerInfo: ...

    def analyze(
        self,
        plan: PipelinePlan,
        *,
        context: SchedulingContext,
    ) -> SchedulerSupportReport: ...

    async def execute(
        self,
        plan: PipelinePlan,
        *,
        runtime: PipelineRuntime,
        context: SchedulingContext,
    ) -> PipelineRunReport: ...
```

`analyze()` is deterministic, side-effect free, and fail closed. `execute()`
receives the already-resolved plan and application-owned runtime services.

Required scheduler capabilities include only coordination concerns such as:

- dependency scheduling
- bounded concurrency
- sync/async callable dispatch
- cancellation and timeouts
- safe retries
- partial-run selection
- lifecycle event correlation
- artifact handoff

Engine, storage, transformation, and contract capabilities remain owned by
their existing plugins and plan descriptors.

## Relationship to `etlantic.orchestration/1`

The shipped orchestration protocol primarily models deterministic compilation,
submission, polling, cancellation, and correlation for external platforms.
The scheduler boundary is the direct-execution companion to that protocol.

**Decision (resolved in 0.15):** publish a narrowly scoped
`etlantic.scheduler/1` protocol for direct execution. Keep
`etlantic.orchestration/1` for external compile/submit/poll plugins such as
Airflow. Do not merge the two discovery systems. Shared models for retry
intent, schedule intent, capabilities, correlation, and reports are reused
across both protocols.

`LocalScheduler` and the planned `etlantic-prefect` adapter implement
`ExecutionScheduler`. `etlantic-airflow` remains an `OrchestratorPlugin`.

## 0.15: scheduler extraction and hardening

This is a companion workstream to the mandatory 0.15 Safe SQL Lowering gate.
It must not delay that gate unless the SQL runtime requires a scheduler
correction for semantic safety.

Deliver:

- inventory the existing local runner's ETLantic-specific and generic
  responsibilities
- extract one scheduling boundary without changing public run semantics
- implement `LocalScheduler` through that boundary
- preserve `Pipeline.run()` and `Pipeline.arun()` behavior
- preserve plan fingerprints and serialized plan/report schemas
- formalize readiness, completion, failure, cancellation, and timeout
  transitions for scheduled work (logical nodes in 0.15; physical-unit
  fusion remains later)
- make concurrency and retry limits explicit and bounded
- prevent scheduler code from reselecting implementations or plugins
- add scheduler capability analysis and structured diagnostics
- add private scheduler conformance fixtures
- document the direct-execution versus external-compilation distinction
- complete a Prefect adapter spike against the scheduler boundary (logical-node
  mapping until fusion-driven unit scheduling lands)

Non-goals for 0.15:

- shipping Prefect in core
- making Prefect the default
- requiring a Prefect server or Cloud account
- changing pipeline authoring
- exposing Prefect tasks, states, deployments, or configuration through the
  ETLantic public model
- replacing `etlantic-airflow`

Acceptance scenarios:

- existing local quickstarts and runtime suites produce equivalent results and
  reports through `LocalScheduler`
- two independent ready branches execute concurrently within a declared bound
- retries occur only when ETLantic's resolved retry-safety policy allows them
- cancellation and timeout produce stable ETLantic states and diagnostics
- partial runs preserve dependency closure and logical identities
- scheduler analysis performs no data access, secret resolution, or backend
  contact
- a scheduler cannot silently alter physical regions or implementation choices

Exit gate:

The built-in local path uses one explicit scheduler boundary, retains current
observable behavior, and passes the private conformance corpus. The Prefect
spike demonstrates feasibility without becoming a release dependency.

## Sibling 0.16 gate: authoring vocabulary cleanup

0.16 also removes the public `Source` / `Sink` / `binding=` compatibility
layer. That work is **independent** of Prefect packaging and is owned by the
[0.16 deletion checklist](MIGRATION_0_14_TO_0_15.md#016-deletion-checklist)
and Migration 0.15 → 0.16 — not by `etlantic-prefect`. Plan/[DPCS](../05_PIPELINES/DPCS.md)/plugin wire
names stay unchanged. See
[ROADMAP §0.16 Gate A](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md#gate-a--authoring-vocabulary-cleanup-hard).

## 0.16: optional `etlantic-prefect` (Gate B MVP)

After the 0.15 scheduler boundary is proven, publish
`etlantic-prefect` as the reference Python-native **scheduler** plugin
(`ExecutionScheduler` / `etlantic.scheduler/1`). This gate does not block
vocabulary cleanup.

Deliver:

- honor `Profile(orchestrator=...)` plus production plugin allowlisting on the
  run path (stop hard-coding only `LocalScheduler` when a non-local scheduler
  is selected)
- deterministic mapping from selected **logical nodes** to Prefect flows and
  tasks, with the same dependency closure as `LocalScheduler`
- local direct invocation without requiring a deployment for the basic path
- exact capability declaration for concurrency, retries, cancellation,
  timeouts, and artifact transport that the MVP claims
- stable mapping between ETLantic run/node identities and Prefect flow/task-run
  identities
- ETLantic-owned output normalization and `PipelineRunReport`
- redacted diagnostics and event correlation
- no Prefect object in `PipelinePlan`, contracts, or portable transformation IR
- optional dependency/package installation only
- a **minimal** public scheduler conformance suite shared with
  `LocalScheduler` where behavior already overlaps
- comparison documentation for local (scheduler), Prefect (scheduler), and
  Airflow (compiler) paths

Deferred past 0.16:

- fusion-driven `physical_units` as the execution grain
- Prefect deployment/serve and durable scheduling
- the full scheduler conformance corpus below

The plugin must not:

- decorate user transformations with Prefect APIs
- reconstruct or dynamically rediscover the logical pipeline
- reselect transformation, storage, dataframe, SQL, or Spark plugins
- pass datasets through a metadata channel intended only for small control
  payloads
- weaken ETLantic retry, transaction, validation, security, or materialization
  boundaries
- require Prefect Cloud for local execution
- implement Airflow-style `compile_plan` / DAG artifact compilation

Acceptance scenarios:

- the same resolved plan executes locally and through Prefect with equivalent
  logical results, lifecycle states, and report shape
- independent ready nodes use the configured Prefect task runner without
  changing dependencies
- unsupported scheduling requirements fail during analyze/planning
- retries are not duplicated between ETLantic and Prefect
- large artifacts use declared artifact references rather than control-plane
  payloads
- secrets remain runtime-only and absent from plans, Prefect parameters,
  diagnostics, and reports
- production selection requires explicit profile configuration and plugin
  allowlisting

Exit gate:

`etlantic-prefect` passes the minimal public scheduler conformance suite as an
optional plugin; `LocalScheduler` remains the default and `etlantic-airflow`
remains the reference external compiler.

## Default selection policy

| Context | Default or requirement |
|---|---|
| Development | built-in `LocalScheduler` |
| Tests | built-in `LocalScheduler` |
| Notebooks and embedded use | built-in `LocalScheduler` |
| Validation and planning CI | no execution scheduler required |
| Prefect execution | explicit `Profile(orchestrator="prefect")` |
| Airflow deployment | explicit compile target and `etlantic-airflow` |
| Production | explicit orchestrator plus non-empty plugin allowlist |

Unknown orchestrator names and missing plugins fail closed. The production
profile must not silently choose Prefect, Airflow, or local execution.

## Conformance requirements

The **full** scheduler suite covers:

- capability accuracy
- dependency and concurrency behavior
- sync and async units
- retries and retry-safety enforcement
- cancellation, timeout, and abandoned work
- partial-run dependency closure
- callback and lifecycle ordering
- multiple output roles
- artifact ownership and transport
- logical identity correlation
- deterministic diagnostics
- result and report equivalence
- secret and row-data exclusion from control artifacts
- bounded hostile plans and failure behavior

0.16 Gate B requires only a **minimal** public subset of the overlapping
LocalScheduler semantics. The full corpus remains a post-0.16 hardening
target.

Platform-specific capabilities run additional fixtures. Passing generic
dependency scheduling tests does not permit a plugin to claim durable
scheduling, event triggers, approvals, or distributed execution.

## Dependency and security policy

- Prefect remains an optional plugin dependency and never an ETLantic core
  dependency.
- Core imports must succeed without Prefect installed.
- Prefect discovery follows the existing entry-point trust boundary.
- Production profiles require allowlisting and compatible version policy.
- Plugin and Prefect versions appear in plan/execution evidence without secret
  values.
- ETLantic does not adopt unsafe serialization to satisfy a scheduler backend.
- Data artifacts remain outside scheduler control payloads unless explicitly
  bounded and safe.

## Documentation deliverables

- update the execution model with the scheduler/compiler distinction
- document `LocalScheduler` as the zero-service reference
- add an `etlantic-prefect` installation and execution guide when shipped
- retain Airflow as the external compilation guide
- add a local (scheduler) / Prefect (scheduler) / Airflow (compiler) decision
  table
- document profile selection and production allowlisting
- publish migration notes only if observable local-runner behavior changes
- keep vocabulary cleanup migration notes under Migration 0.15 → 0.16, not
  under the Prefect package docs

## Final success criteria

The program succeeds when ETLantic has a smaller, testable built-in scheduling
kernel; an optional Prefect `ExecutionScheduler` can coordinate the same
resolved plans via local direct invocation; Airflow compilation remains
independent; authoring vocabulary cleanup can ship without Prefect; and no
orchestrator becomes part of ETLantic's logical authoring or portable semantic
model.
