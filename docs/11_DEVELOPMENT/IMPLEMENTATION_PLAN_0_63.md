---
title: ETLantic 0.63 Implementation Plan
description: Implementation-grade plan for brownfield metadata bridges and orchestration compilers.
plan_status: current
plan_last_reviewed: 2026-10-12
---

# ETLantic 0.63 Implementation Plan

Phase 0.63 lets existing projects adopt ETLantic incrementally through static
metadata readers, semantic comparison, safe skeleton generation, and
orchestration compilers. The
[adoption ecosystem plan](ADOPTION_ECOSYSTEM_PLAN.md) governs brownfield and
interoperability boundaries.

## Outcome

Teams can import metadata from real dbt and ETL projects without executing their
code, identify what ETLantic can and cannot preserve, generate reviewable
skeletons, compile qualified pipelines to Dagster or Argo, integrate Prefect
through its managed adapter, and compare
old and new paths side by side without a flag-day migration.

This phase moves from 0.59 to 0.63 after insertion of the
[0.59–0.62 scheduling and execution integration program](ETLANTIC_RUNTIME_PLAN.md).
Its adoption outcomes remain, with demand-gated compiler delivery and the
accepted [package simplification work](PACKAGE_SCOPE_CONSOLIDATION_PLAN.md).

## Prerequisites And Non-Goals

- 0.59–0.62 supplies explicit schedule/execution and HTTP trigger contracts.
  Imported schedules retain their selected timer, endpoint, occurrence identity,
  and execution placement; unsupported platform semantics receive fidelity
  diagnostics rather than a silent approximation.

- 0.56 public services supply execution and control for adopted pipelines;
  migration tools preserve imported specification choices and use that authority.
- 0.57 supplies the transport-independent backend, authorized schedule services,
  complete role factories, provider schema inspection, and role supervision;
  adopters use those public contracts rather than assemble another service graph.
- 0.58 supplies the qualified managed Prefect deployment/dispatch adapter.
  Brownfield migration reuses its accepted references, targeted execution,
  correlation, schedule admission, and effect/publication authority. Broader
  dynamic plan semantics require new conformance or explicit rejection; a
  migration bridge cannot silently broaden the initial static-batch `/1` matrix.
- Stable registry identities, semantic plan diff, generated-code preservation,
  and conformance protocols from earlier phases are available, including 0.46
  bounded dynamic-control identities and capability rules.
- 0.55 inferred models may provide reviewable starting contracts for migration
  skeletons. A draft inferred from observed data is not an accepted contract
  until the owner reviews and binds it to a stable source.
- Readers parse supported static artifacts only; they do not execute Jinja,
  macros, Python project code, hooks, or package installation.
- External dbt or orchestration ownership can remain authoritative. Import does
  not silently transfer ownership to ETLantic.
- Dagster/Argo packages require a named adoption project before creation and
  their own artifact/SDK isolation and fidelity matrix; no shared runtime clone.
  Missing demand defers that compiler explicitly in the release decision.
- Compilers reject semantics they cannot preserve; they do not approximate
  retries, partitions, schedules, assets, state, policy, dynamic mapping,
  branch/failure/compensation behavior, or external effects.

## Workstreams

| ID | Workstream | Deliverables | Completion evidence |
|---|---|---|---|
| 063-D | dbt bridge | Manifest/catalog/run-results readers; model/source/test/exposure/metric metadata; stable identity mapping | Versioned public dbt artifact corpus with no code/Jinja execution |
| 063-M | ETL migration model | Sources, transforms, joins, filters, assertions, schedules, retries, partitions, dynamic maps/reduces, conditions, failure/compensation paths, effects, ownership, fidelity states | Representative framework-neutral migration fixtures |
| 063-G | Skeleton generation | Safe ETLantic project skeletons, TODO/fidelity markers, user-region preservation, repeatable regeneration | Golden output and incremental re-run tests |
| 063-S | Semantic diff | Source/field/transform/quality/state/schedule/dynamic-control/effect comparison with explicit unsupported/lossy results | Side-by-side fixture report and false-equivalence tests |
| 063-O | Orchestration interoperability | Dagster definitions compiler, Prefect fidelity/migration integration over the 0.58 managed adapter, Argo workflow compiler, including truthful 0.46 dynamic-control lowering/rejection | Backend conformance and rejection matrix; Prefect admission and execution authority retained |
| 063-V | Side-by-side validation | Shadow/dual-run correlation, bounded result/quality/lineage comparison, cutover evidence | Realistic incremental migration campaign |
| 063-F | Fixture and testing consolidation | Versioned adoption corpus plus shared conformance/fault injection/reference fakes in existing `etlantic.testing`; published identity/entry-point migration; conditional testing-wheel decision | Independent conformance consumer, compatibility tests, no production registration on fixture import; fewer release units after retirement |
| 063-C | Engine boundary and helpers | Move concrete Polars fusion execution/inspection behind one qualified plugin capability; centralize identical parameter/literal/constant/output helpers in existing public modules after [DTCS](../04_TRANSFORMATIONS/DTCS.md) ownership check | Exact qualified/rejected fusion cases and engine conformance unchanged; no universal compiler or new engine-base wheel |
| 063-H | Existing HTTP clients | Foundry/registry consume one outbound policy/conformance; provider auth, pagination, effect-aware retry and error mapping stay adapters | DNS/connect and trusted-private destination, redirect, timeout, byte/redaction parity; conditional HTTP wheel only with two real shared-client consumers and duplicate removal |
| 063-P | Adapter packaging and retirement | Foundry transport/codecs/connectors and SQL internal modularization; PostgreSQL driver extra with migration; SDK install measurements; retire redirect/fixture release owners only after declared windows | SQLite without psycopg, resolver/install compatibility, measured benefits, SparkForge/fake migration and release exclusion after window |

## Delivery Sequence

1. Freeze fidelity vocabulary and the framework-neutral migration model.
2. Implement static dbt artifact readers against versioned fixtures.
3. Add semantic diff and safe skeleton generation before orchestration output.
4. Qualify only demand-backed Dagster/Argo compilers and Prefect interoperability
   independently, preserving each protocol and capability boundary.
5. Add side-by-side validation and incremental ownership/cutover workflows.
6. Deliver engine/helper, existing-client, fixture and adapter-packaging cleanup
   as separate changes. Organize existing testing modules before deciding whether
   a testing wheel replaces actual ownership; move Medallantic campaigns to its
   repository tests. Do not couple these refactors to a new engine support matrix.
7. Apply recorded migration windows before removing SparkForge or fake-only
   release units. Publish per-artifact/backend matrices and conditional/deferred
   package decisions with named evidence.

## Exit Gates

- Brownfield inspection performs no project code, Jinja, hook, macro, dependency,
  secret, network, or data execution.
- Every imported element has provenance and an exact, lossy, unsupported, or
  externally-owned fidelity status.
- Skeleton generation is deterministic, reviewable, preserves user regions, and
  does not overwrite existing ownership without an explicit operation.
- Semantic diff never labels unsupported behavior equivalent.
- Each compiler preserves declared semantics or fails before emitting a runnable
  artifact with a stable capability diagnostic.
- Supported map/reduce and conditional/failure/compensation constructs retain
  stable logical and expanded identities, bounds, retry/replay behavior, and
  report correlation on every compiler that claims them.
- A realistic project adopts ETLantic incrementally, retains an external owner
  where chosen, runs side-by-side, and produces cutover evidence without a
  flag-day rewrite.

- Core calls one qualified fusion provider capability without concrete engine
  imports at that seam; existing accepted/rejected behavior remains identical.
- Exact helper duplicates have one public owner; engine null/type/timezone,
  aggregation/dialect and lazy/eager lowering stay in their plugins.
- Foundry and registry agree on configured outbound policy, including actual
  network behavior and trusted private deployments. Any HTTP wheel has two real
  client consumers and removes duplicate implementation, not just URL helpers.
- Reference fakes preserve published identities/entry points through a migration;
  importing fixtures cannot register production plugins. A testing wheel is
  created only with independent conformance consumption and replacement value;
  repository/domain campaigns are not moved into its runtime distribution.
- SQLite-only SQL installation avoids psycopg through a documented driver-extra
  transition; CLI extraction remains deferred without measured SDK benefit.
- SparkForge and superseded fixture packages leave routine releases only after
  their recorded compatibility windows; historic distributions remain usable.

## Required Release Evidence

- Static-reader no-execution security report.
- Import fidelity and semantic-diff corpus.
- Generator determinism/preservation report.
- Per-backend compiler conformance and rejection matrix.
- Incremental brownfield migration case study with side-by-side evidence.
- F05/F06/F08/F09/F10/F11 boundary, helper, HTTP, install and retirement evidence;
  explicit conditional `etlantic-testing`/`etlantic-http` decisions.
