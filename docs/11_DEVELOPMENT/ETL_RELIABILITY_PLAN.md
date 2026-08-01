# ETL Reliability and Recovery Plan

> **Plan status: partially shipped, living cross-release plan.**
>
> **Current 0.41 boundary:** Public reliability models, provider protocols,
> and local CLI inspection and preview workflows are available. Durable
> managed history, control-plane coordination, federation, cost-aware
> selection, and human-governed automation remain planned.
>
> **Authority:** [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md) and the
> [CLI reference](../10_REFERENCE/CLI.md) define current behavior. This plan
> owns the remaining reliability outcomes and graduation criteria. See the
> [Planning Hub](PLAN_INDEX.md).
>
> **Review trigger:** Update when reliability CLI/provider scope changes or a
> roadmap reliability gate passes.

## Purpose

An ETL pipeline can be structurally valid and still produce an untrustworthy
result. Inputs may be stale or incomplete, retries may repeat side effects,
backfills may overwrite the wrong partitions, two backend implementations may
disagree, and an apparently successful load may not reconcile with its source.

ETLantic should model and coordinate these reliability concerns without
becoming a scheduler, execution engine, storage system, or statistical
monitoring platform.

The core should own:

- portable intent;
- static analysis;
- deterministic planning;
- capability negotiation;
- normalized observations and evidence;
- policy decisions;
- impact and repair planning;
- reports and diagnostics.

Plugins and providers should perform backend-specific inspection, execution,
measurement, persistence, and notification.

## Scope

This plan covers thirteen related capability families:

1. freshness and partition completeness;
2. incremental invalidation and repair planning;
3. idempotency and retry safety;
4. explicit write and materialization semantics;
5. reconciliation;
6. backfill planning;
7. cross-backend implementation parity;
8. plan and environment drift;
9. data-quality trends;
10. statistical data drift;
11. pipeline and step delivery objectives, deadlines, and escalation;
12. bounded dynamic mapping and explicit control flow;
13. streaming record-error, dead-letter, and schema-registry reliability.

These are operational models, policies, observations, and evidence. They are
not additional top-level contract standards.

## Shared Reliability Model

Each capability should follow a consistent lifecycle:

```text
Declared expectation or intent
              │
              ▼
Observation or proposed operation
              │
              ▼
Normalized evidence
              │
              ▼
Policy evaluation
              │
              ▼
Decision and affected graph
              │
              ▼
Execution, remediation, or review
              │
              ▼
Durable report and history
```

Shared models should include:

- stable subject identity;
- profile, environment, workspace, and security domain;
- observation time and provenance;
- evidence and confidence;
- policy revision and decision;
- affected nodes, fields, partitions, and artifacts;
- acknowledgement, approval, and remediation references;
- deterministic fingerprints where possible.

## Delivery Objectives, Deadlines, and Escalation

### Problem

A pipeline may be structurally correct and produce valid data while still
missing the time at which its output is useful. Timeouts limit individual
operations; they do not express a portable delivery objective or prove that a
miss was detected, routed, escalated, and later recovered.

### Model

A versioned `DeliveryObjective` should describe:

- pipeline, step, output, or data-product subject identity;
- reference point such as scheduled, queued, started, source-ready, fixed time,
  or an explicitly registered custom provider reference;
- warning and hard deadlines, grace periods, timezone, and calendar;
- owner, severity, policy revision, and notification route references;
- repeat, deduplication, acknowledgement, escalation, and recovery behavior;
- whether a missed objective warns, blocks publication, opens an approval, or
  only records evidence.

Evaluation must use durable clock and run/event history, survive process loss,
and emit distinct approaching, breached, acknowledged, escalated, recovered,
and unknown outcomes. Notification providers own transport; ETLantic owns the
portable objective, policy decision, dedupe identity, and normalized evidence.

### Acceptance

- equivalent objective inputs produce the same deadline and dedupe identity;
- API or worker restart cannot lose or duplicate a required breach/recovery
  transition;
- calendar, clock-skew, late-event, and historical-average inputs are explicit
  and bounded;
- notification routes are authorized before delivery and never receive
  resolved secrets, source rows, or protected metadata beyond their policy;
- failure of a required routing provider produces durable undelivered evidence
  and follows an explicit retry/escalation policy.

## Bounded Dynamic Mapping and Explicit Control Flow

### Problem

Static fan-out cannot express a run whose partitions or work items are known
only after an authorized upstream operation. Arbitrary Python branching cannot
be made portable, replayable, or safe merely by observing it at runtime.

### Model

ETLantic should model explicit, versioned constructs for:

- map and reduce over a declared collection, partition set, or provider
  enumeration;
- conditional branches based on typed, bounded decision evidence;
- failure branches and compensation paths;
- stable child identities derived from plan, parent, map key, and input
  snapshot identity;
- expansion, nesting, concurrency, payload, duration, and total-work limits;
- branch selection, skipped work, retries, cancellation, resume, replay, and
  report aggregation.

Expansion never grants new plugin, secret, network, tenant, or write authority.
Every scheduler and compiler must preserve the declared semantics or reject the
plan before emitting work.

### Acceptance

- identical declared inputs produce identical child identities, dependency
  closure, branch decisions, and normalized report structure;
- bounds fail before unbounded work or state is accepted;
- retry, cancellation, resume, and replay cannot duplicate completed mapped
  effects or silently bypass a failure/compensation branch;
- unsupported dynamic semantics fail capability negotiation rather than being
  flattened into an inequivalent static graph.

## Streaming Record Errors, Dead Letters, and Schema Registries

### Problem

Stream-level retry and late-data handling do not define what happens to one
malformed, incompatible, or repeatedly failing record. Silent skipping, unsafe
offset advancement, or payload-bearing diagnostics can lose data or expose it.

### Model

Streaming providers should support explicit record-error policies for fail,
skip, quarantine, and dead-letter outcomes. A policy should declare retry
bounds, offset/checkpoint behavior, external DLQ identity, retention,
authorization, deduplication, redrive, and reconciliation. ETLantic records only
bounded identifiers and outcome metadata; provider-owned DLQ storage holds any
payload under its own access policy.

A schema-registry provider protocol should normalize subject/schema identity,
format, version, compatibility mode, lookup, registration authority, cache
freshness, outage behavior, and evolution evidence. The reference path should
cover Avro, Protobuf, and JSON Schema through a Confluent-compatible provider
without making that vendor or its SDK a core dependency.

### Acceptance

- a poison record cannot create an unbounded retry loop or silently advance an
  offset/checkpoint contrary to policy;
- redrive is idempotent, provenance-linked, and reconciled with original
  failure and checkpoint evidence;
- unauthorized principals cannot enumerate or retrieve DLQ payloads through
  ETLantic metadata APIs;
- incompatible, ambiguous, stale, or unavailable schema-registry results follow
  an explicit fail-closed policy and never silently reinterpret an event.

## Durable Host Recovery Integration

### Boundary

Applications and orchestrator plugins own durable job admission, SQL/queue
records, worker claims, leases, heartbeats, fencing, scheduler leadership,
retry timing, and process recovery. ETLantic core must not become a queue,
scheduler, worker supervisor, or database.

ETLantic should provide the portable semantic evidence those hosts need to
decide whether a failed or abandoned execution may be retried, resumed,
reconciled, or must stop for review.

### Portable execution-attempt context

A future versioned attempt context should carry only host-neutral values:

- logical run and attempt identity;
- immutable pipeline definition and plan fingerprints;
- run intent and selection;
- prior attempt/report reference;
- retry/replay/resume reason;
- idempotency scope/key references without secret material;
- available durable artifact and checkpoint references;
- cancellation/deadline context;
- correlation and trace identifiers;
- host fencing token as opaque evidence when needed by providers.

The context must be serializable, secret-free, and optional for local
single-attempt execution. ETLantic must not interpret a host lease as proof of
side-effect safety.

### Recovery classification

Normalized reports and provider results should distinguish:

- no externally visible effect began;
- effect is known not committed;
- effect is known committed;
- effect outcome is unknown;
- checkpoint/artifact was durably published;
- cleanup or compensation completed/failed.

An unknown commit outcome is not an ordinary transient failure. Automatic retry
must fail closed unless the plan/provider supplies a valid deduplication,
transaction, reconciliation, or idempotency proof.

### Resume and checkpoint contract

ETLantic should expose enough stable evidence for a host to request:

- whole-run retry;
- replay from the original inputs/state;
- resume from a durable publication boundary;
- minimum-safe repair closure;
- reconciliation-only/manual-review flow.

Resume is legal only when the checkpoint/artifact binds to the exact plan,
pipeline revision, input snapshot, implementation identities, security domain,
and state transition. Checkpoint advancement remains compare-and-swap and
commit-after-materialization. A failed or no-write attempt cannot advance it.

### Plugin/provider conformance

Execution and storage plugins should declare and test:

- cancellation and timeout behavior;
- transaction/commit boundary;
- idempotency scope and duplicate suppression;
- retry and resume capability;
- checkpoint/artifact durability;
- unknown-outcome and reconciliation behavior;
- attempt-aware report attribution.

Hosts may impose a stricter retry limit or refuse resume. They must never
weaken an ETLantic unsafe-retry or unknown-outcome decision.

### Acceptance

- a process may disappear after any execution boundary without ETLantic
  reporting a false success;
- a conforming host can make a deterministic retry/resume/manual-review
  decision from the plan and normalized attempt evidence;
- two attempts remain distinguishable while contributing to one logical run
  history;
- a stale/fenced host cannot use ETLantic evidence to legitimize an otherwise
  rejected state or publication commit;
- reports, checkpoints, and recovery diagnostics contain no secret values.

## Freshness and Partition Completeness

### Problem

A source may exist and match its schema while still being too old, missing
expected partitions, or only partially published.

### Model

Freshness expectations should describe:

- maximum acceptable age;
- event-time, ingestion-time, publication-time, or source-revision basis;
- expected schedule or availability window;
- grace period and timezone;
- authoritative timestamp or provider capability;
- behavior when no new data is expected.

Partition-completeness expectations should describe:

- partition key and logical partition domain;
- expected ranges or enumerated partitions;
- allowed lateness;
- minimum counts or control manifests;
- partial-publication indicators;
- late, missing, duplicate, and unexpected partition handling.

### Planning and runtime

ETLantic should support:

- preflight freshness checks;
- partition-manifest inspection;
- waiting, warning, blocking, or skipping according to policy;
- a distinct `NO_NEW_DATA` outcome rather than treating it as failure;
- downstream impact for stale or incomplete inputs;
- freshness and completeness evidence in `PipelineRunReport`.

Live checks require explicit provider authority and never occur during static
planning.

## Incremental Invalidation and Repair Planning

### Problem

When an input partition, source snapshot, contract, implementation, or output
changes, teams need the smallest safe rerun rather than a blind full rebuild.

### Model

The planner should combine:

- changed subjects and partitions;
- dataset and column lineage;
- state cursors, watermarks, and checkpoints;
- artifact identities and validity;
- transformation determinism and side effects;
- materialization and publication boundaries;
- contract and schema impact;
- downstream reuse rules.

### Outputs

A `RepairPlan` should explain:

- invalidated and reusable artifacts;
- minimum upstream and downstream closure;
- partitions or ranges to recompute;
- state that must remain unchanged;
- unsafe side effects;
- required approvals;
- expected writes and reconciliation checks;
- why each node was included or excluded.

Repair execution must consume an ordinary `RunRequest` and `PipelinePlan`
extension rather than introduce a separate runtime.

## Idempotency and Retry Safety

### Problem

Retries, reruns, backfills, and resumed runs can duplicate writes, events, API
calls, and other side effects.

### Model

Transformations, sinks, callbacks, and providers should declare:

- pure or side-effecting behavior;
- deterministic or nondeterministic behavior;
- idempotency scope and key;
- retry safety;
- transaction boundary;
- deduplication support;
- compensation or rollback capability;
- externally visible effect;
- maximum safe attempts.

Idempotency is conditional. A merge may be idempotent only for a stable key,
source snapshot, predicate, and write policy.

### Validation

The planner should:

- reject retries for undeclared or unsafe side effects;
- ensure idempotency keys include the correct run, input, partition, or effect
  identity;
- prevent retry policy from crossing transaction or publication boundaries;
- distinguish retry, replay, resume, and intentional duplicate processing;
- record the safety proof and residual risk in the plan.

## Explicit Write and Materialization Semantics

### Problem

Generic `write` and `save` operations hide destructive behavior, portability
limitations, and materialization costs.

### Write intent

Portable write intents should initially include:

- append;
- insert-only;
- replace;
- replace selected partitions;
- merge or upsert;
- create-table-as;
- insert-select;
- snapshot publication;
- delete propagation;
- slowly changing dimension strategies;
- validate-only and no-write modes.

Each intent should declare keys, matching behavior, schema-evolution policy,
transaction needs, conflict behavior, and idempotency assumptions.

### Materialization intent

Materialization should describe:

- in-memory, lazy, cached, temporary, durable, or external-reference form;
- persistence lifetime and cleanup;
- reuse and invalidation rules;
- serialization and interchange format;
- partitioning and ordering;
- security classification and encryption;
- whether materialization is required for validation, retry, branching,
  orchestration, or backend transition.

Plugins must either preserve requested semantics, select an explicitly approved
fallback, or fail compilation before execution.

## Reconciliation

### Problem

A successful write does not prove that source and destination agree.

### Model

Reconciliation checks should support:

- row and distinct-key counts;
- accepted, rejected, inserted, updated, and deleted counts;
- control totals and aggregates;
- checksums or fingerprints;
- partition coverage;
- source-to-sink lag;
- key-set comparison;
- referential checks;
- bounded tolerance and rounding rules.

Checks may compare sources, intermediate artifacts, sinks, manifests, or
independent control systems.

### Evidence

Providers calculate backend-specific evidence. ETLantic normalizes:

- compared subjects and snapshots;
- metric definitions;
- expected and observed values;
- tolerances;
- completeness and confidence;
- policy decision;
- remediation and affected downstream nodes.

Reconciliation failures should be distinguishable from transformation,
validation, and publication failures.

## Backfill Planning

### Problem

Backfills are often improvised scripts with unclear scope, cost, write
behavior, and side effects.

### Model

A `BackfillRequest` should describe:

- temporal, partition, key, or snapshot range;
- inclusive and exclusive bounds;
- source and contract revisions;
- profile and implementation selection;
- write and existing-output behavior;
- concurrency and rate limits;
- notification and callback policy;
- checkpoint isolation;
- reconciliation requirements;
- approval and cost budgets.

### Preview

Before execution, a backfill plan should show:

- dependency closure;
- partitions, batches, and estimated task count;
- selected backends and implementations;
- materialization and publication boundaries;
- expected scans, writes, and destructive operations;
- side effects suppressed or permitted;
- estimated resources, duration, and cost with confidence;
- idempotency and retry assessment;
- state transitions and rollback constraints.

Backfill execution uses ordinary plans, reports, policies, and provider
interfaces.

## Cross-Backend Implementation Parity

### Problem

Pandas, Polars, SQL, and PySpark implementations of one transformation may
differ in null behavior, precision, ordering, timezone handling, or invalid
record treatment.

### Conformance model

Transformation authors should define shared fixtures, properties, or generated
cases. The parity harness should compare:

- output contracts and normalized schemas;
- values within declared tolerance;
- null and missing-value behavior;
- numeric precision and rounding;
- date, timestamp, and timezone behavior;
- ordering guarantees;
- duplicate and key behavior;
- valid and invalid outputs;
- side effects and write intent;
- deterministic replay;
- diagnostics and lineage evidence.

Results should classify implementations as conforming, conditionally
conforming, nonconforming, or not comparable.

Backend-specific differences may be documented capabilities, but cannot be
silently treated as equivalent semantics.

## Plan and Environment Drift

### Problem

The logical pipeline may remain unchanged while production behavior changes
because profiles, plugins, implementations, policies, statistics, bindings, or
optimizer decisions changed.

### Tracked identity

ETLantic should fingerprint:

- logical pipeline and contract revisions;
- resolved profile;
- environment and capability inventory;
- plugin, provider, and implementation versions;
- selected implementations;
- policy bundle;
- optimization inputs and decisions;
- `PipelinePlan`;
- compiled backend artifacts.

### Comparison

Plan and environment drift should identify:

- implementation selection changes;
- new materialization or backend boundaries;
- write, retry, validation, or security-policy changes;
- resource and cost changes;
- plugin or provider upgrades;
- capability gain or loss;
- binding and secret-reference changes without exposing values;
- optimizer decisions that materially change execution.

Policies may record, warn, require approval, or block deployment and execution.

## Data-Quality Trends

### Problem

One run may pass while quality gradually deteriorates.

### Metrics

ETLantic should normalize time-series evidence such as:

- null, invalid, duplicate, and rejection rates;
- record and partition counts;
- distinct-key counts and cardinality;
- referential-integrity results;
- validation latency and failure rates;
- reconciliation deltas;
- freshness and completeness;
- schema and statistical drift frequency.

Providers store and query metric history. ETLantic defines metric identity,
dimensions, policy inputs, report summaries, and trend diagnostics.

Initial trend analysis should use explainable rules such as thresholds, moving
windows, percentage changes, and consecutive violations. Advanced anomaly
detection remains provider-driven.

## Statistical Data Drift

### Problem

Data meaning may change without a schema change, such as a categorical code
becoming a full name or a numeric distribution shifting significantly.

### Observations

Statistical observations may include:

- null and missing rates;
- cardinality and new categorical values;
- min, max, quantiles, mean, and variance;
- length and pattern summaries;
- frequency sketches and histograms;
- referential and uniqueness rates;
- bounded distribution-distance measures.

### Privacy and safety

Statistical profiling is opt-in and must declare:

- selected fields and metrics;
- sampling and confidence;
- row, byte, cardinality, and time budgets;
- classification and privacy policy;
- retention and sharing scope;
- prohibited sensitive fields;
- redaction or aggregation requirements.

Raw values, unrestricted category sets, and sensitive exemplars must not enter
plans, diagnostics, reports, prompts, or general-purpose metric stores.

Statistical drift is evidence, not proof of a defect. Policies should generally
warn or require review before blocking unless an organization explicitly
defines a mandatory gate.

## CLI and API

Planned commands include:

```text
etlantic freshness check
etlantic partitions check
etlantic impact data
etlantic repair explain
etlantic repair plan
etlantic backfill plan
etlantic reconcile
etlantic implementations compare
etlantic plan diff
etlantic environment diff
etlantic quality trends
etlantic data-drift inspect
etlantic objectives check
etlantic objectives history
etlantic erasure plan
etlantic erasure status
etlantic stream dead-letters inspect
etlantic stream redrive plan
etlantic stream schemas check
```

The Python API, CLI, FastAPI integration, IDE, notebooks, and AI tooling should
share the same request, result, policy, and evidence models.

## Reporting and Developer Experience

`PipelineRunReport` should include normalized evidence for:

- freshness and completeness;
- invalidation and reuse;
- retry and idempotency decisions;
- writes and materializations;
- reconciliation;
- backfill scope and progress;
- implementation identity and parity status;
- plan and environment drift;
- quality trends;
- statistical drift;
- delivery-objective calculation, breach, escalation, delivery, acknowledgement,
  and recovery;
- dynamic expansion and branch decisions, child summaries, skipped work, and
  bound exhaustion;
- record-error disposition, dead-letter identity, offset/checkpoint decision,
  redrive, reconciliation, and schema-registry evidence.

IDE and notebook tooling should offer:

- freshness and incomplete-partition indicators;
- repair and backfill previews;
- unsafe-retry and destructive-write diagnostics;
- reconciliation results;
- implementation comparison;
- plan and environment diffs;
- bounded quality and drift charts;
- objective/deadline timelines, escalation state, and recovery evidence;
- dynamic-map child and branch views with stable identities and explicit bounds;
- dead-letter/redrive and schema-compatibility views that never expose payloads;
- navigation to affected models, policies, fields, and sinks.

AI tools may explain evidence and propose repairs, tests, adapters, or policy
changes, but cannot approve destructive writes, backfills, retries, baseline
changes, or production execution.

## Security

These capabilities can require powerful access and reveal sensitive metadata.

Required controls include:

- read-only inspection credentials where possible;
- separate inspect, plan, approve, execute, and acknowledge authorities;
- bounded scans, samples, profiles, and history queries;
- explicit destructive-write and backfill approval;
- tenant and security-domain isolation;
- no secret values in fingerprints, comparisons, or reports;
- no source, event, dead-letter, or data-subject value in objective, expansion,
  branch, DLQ, registry, erasure, or notification evidence;
- privacy review for statistical metrics;
- integrity-protected evidence used for deployment or recovery decisions;
- audit events for repair, backfill, retry override, baseline, and policy
  decisions;
- fail-closed behavior when safety or write semantics are unknown.

## Testing

Conformance testing should cover:

- timezone and schedule boundaries for freshness;
- missing, late, duplicate, and partial partitions;
- invalidation closure and artifact reuse;
- retry matrices across pure, idempotent, transactional, compensatable, and
  unsafe operations;
- write-intent behavior across SQL, Spark, dataframe, and storage plugins;
- reconciliation tolerance and snapshot identity;
- backfill partitioning, state isolation, cancellation, and resume;
- cross-backend null, precision, ordering, timezone, and invalid-data behavior;
- plan and environment fingerprint stability;
- quality-trend windows and notification deduplication;
- statistical-drift privacy budgets and bounded execution;
- objective clock, timezone, calendar, restart, dedupe, escalation, and recovery
  behavior;
- deterministic expansion, branch, replay, cancellation, compensation, and
  bound-exhaustion behavior;
- poison-record retry/offset matrices, DLQ authorization/redrive/retention, and
  Avro/Protobuf/JSON Schema registry compatibility and outage behavior.

## Roadmap Placement

Rows before 0.39 preserve the plan's original implementation decomposition;
they do not independently claim that every item in a row is shipped. Use the
current boundary at the top of this page and
[Capabilities](../01_GETTING_STARTED/CAPABILITIES.md) for availability.
Rows from 0.39 onward are future sequence.

| Release | Reliability capabilities |
|---|---|
| 0.3 | Portable policies, intent models, evidence schemas, fingerprints |
| 0.4 | Local retry safety, repair selection, backfill requests, reports |
| 0.5 | Dataframe parity, quality metrics, reconciliation evidence |
| 0.6 | SQL write intents, transactions, reconciliation, plan evidence |
| 0.7 | Spark and Delta writes, partition completeness, backfill semantics |
| 0.8 | Orchestrator mapping for retries, repair, backfills, and reports |
| 0.9 | CLI, provider protocols, conformance suites, drift comparisons |
| [0.39](IMPLEMENTATION_PLAN_0_39.md) | FastAPI inspection, planning, approval, and history routes |
| [0.40](IMPLEMENTATION_PLAN_0_40.md) | Registry and workspace history for plans, environments, and quality |
| [0.41](IMPLEMENTATION_PLAN_0_41.md) | Incremental invalidation, repair, state, and reproducibility |
| [0.42](IMPLEMENTATION_PLAN_0_42.md) | Governance, delivery objectives, deadline/escalation routing, governed erasure, approvals, budgets, destructive-write policy |
| [0.43](IMPLEMENTATION_PLAN_0_43.md) | Integrated multi-tenant control-plane graduation |
| [0.44](IMPLEMENTATION_PLAN_0_44.md) | IDE and notebook previews, diagnostics, and trend displays |
| [0.45](IMPLEMENTATION_PLAN_0_45.md) | Cost-aware repair, materialization, and implementation selection |
| [0.46](IMPLEMENTATION_PLAN_0_46.md) | Bounded dynamic control flow, streaming record errors/DLQs, schema registries, and continuous reliability |
| [0.48](IMPLEMENTATION_PLAN_0_48.md) | Human-governed repair and migration proposals |

## Success Criteria

ETLantic succeeds when a developer can determine:

- Is the input fresh and complete?
- What changed and what must be rebuilt?
- Is retry or replay safe?
- What exactly will be written or materialized?
- Did source and destination reconcile?
- What will a backfill touch and cost?
- Do all implementations preserve the same semantics?
- Why did the physical plan or environment change?
- Is data quality degrading over time?
- Did the data distribution change within approved privacy limits?
- Will the pipeline or step meet its delivery objective, and was a miss routed,
  escalated, and recovered correctly?
- What dynamic work and branch decisions were created, and were all bounds and
  replay guarantees preserved?
- What happened to every rejected stream record, did checkpoint state remain
  safe, and was schema compatibility proven?

The core principle is:

> ETLantic makes reliability intent explicit, turns runtime behavior into
> comparable evidence, and plans safe recovery without owning the execution
> engines that perform the work.
