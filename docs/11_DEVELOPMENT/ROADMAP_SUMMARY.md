# Roadmap Summary

ETLantic **0.34.0** shipped **Operations, Evidence, and Production Readiness
(M6)**. **0.35 / M7** is the next planned milestone. Milestones describe
capability order, not release-date commitments.

| Horizon | Release | Outcome | Evidence / status |
|---|---:|---|---|
| Current | 0.34 | Operations, evidence, and production readiness (M6) | [Shipped](EXIT_GATE_0_34.md) |
| Next | 0.35 | Migration completion and joint freeze (M7) | Planned |
| Foundation | 0.36–0.38 | Joint burn-in → release candidate → stable foundation | Planned |
| Post-foundation | 0.39–0.53 | Connectivity → control plane → intelligence, federation, adoption, operations, providers, and modeling incubation | Planned |

“Planned” records capability order only. It does not imply a release date or
that the capability is available in the current package.

## Cross-cutting UI/UX sequence

The [User Interface and Experience Plan](UI_UX_PLAN.md) adds five phased
outcomes without creating conflicting release numbers:

1. CLI clarity, actionable diagnostics, target discovery, and guided recovery.
2. A React architecture spike followed by an interactive, accessible,
   self-contained pipeline HTML workspace; the dependency-free static renderer
   remains the portable fallback.
3. A local run dashboard and visual plan/report comparison.
4. Watch mode, LSP, editor previews, and profile/impact explanations in 0.45.
5. A hosted, governed experience after the 0.40–0.44 control-plane gates,
   culminating in the read-only-first 0.51 Operator Console.

All views remain projections of the same public artifacts and must preserve
redaction, safe-I/O, authorization, accessibility, and bounded rendering.

## Shipped: 0.15 through 0.20

ETLantic **0.15.0** closed Safe SQL Lowering and the LocalScheduler companion.

ETLantic **0.16.0** shipped authoring vocabulary cleanup and optional
`etlantic-prefect` `ExecutionScheduler`.

ETLantic **0.17.0** shipped portable coverage expansion (platform + Wave 1/2
on Polars + PySpark). Pandas and SQL remain kernel + `portable-relational/1`.

ETLantic **0.18.0** shipped Gate A versioned tabular interchange
(`etlantic.interchange/1`) for Polars↔Pandas. See
[What's New in 0.18](../01_GETTING_STARTED/WHATS_NEW_0_18.md).

ETLantic **0.19.0** shipped the **Contract and Configuration Freeze** (see
[freeze glossary](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md#freeze-glossary-three-different-terms)):
plan nest freeze helpers (`deep_freeze` on mappings/lists/sets — not full
object-graph immutability), fingerprint trust-boundary verify, `security_mode`,
strict profile resolution, wire schema gates, surface inventory, and
0.x deprecation schedule. See
[What's New in 0.19](../01_GETTING_STARTED/WHATS_NEW_0_19.md).

ETLantic **0.20.0** shipped **Trust, Isolation, and Safe I/O**:
pre-import plugin manifests, `SafeIoPolicy`, artifact/cache isolation,
outbound SSRF policy, serialization bans, versioned security events, and
release SHA-256 digests / attestations / OIDC-preferred publish. See
[What's New in 0.20](../01_GETTING_STARTED/WHATS_NEW_0_20.md) and
[Exit gate 0.20](EXIT_GATE_0_20.md).

## 0.18 Gate A (still current)

Gate A = **0.18.0** (interchange baseline). DataFusion remains a
**non-blocking** Gate B experiment (`etlantic-datafusion` Experimental;
not graduated).

## Shipped: 0.21

ETLantic **0.21.0** shipped **Cohesive CLI and Authoring Experience**:
`init`, `doctor`, profile commands, durable workspace, declarative assets,
`plan diff`, and cross-invocation reports. See
[What's New in 0.21](../01_GETTING_STARTED/WHATS_NEW_0_21.md) and
[Exit gate 0.21](EXIT_GATE_0_21.md).

## Shipped: 0.22

ETLantic **0.22.0** shipped the **Plugin SDK Release Candidate**:
capability-driven engine identity, `etlantic.capabilities/1`, hardened
public conformance (including Spark), curated `import etlantic as etl`,
`etlantic plugin compatibility`, and out-of-monorepo
`etlantic-plugin-echo`. Protocol `/1` is freeze-eligible, not frozen
(superseded — frozen in 0.28.0). See
[What's New in 0.22](../01_GETTING_STARTED/WHATS_NEW_0_22.md) and
[Exit gate 0.22](EXIT_GATE_0_22.md).

## Shipped: 0.23

ETLantic **0.23.0** shipped **Runtime Resilience and Performance Budgets**:
committed microbenchmark baselines with CI gates, public fault injection,
SafeIoPolicy-unified persistence proofs, cancellation/timeout terminal
semantics, interchange evidence reconciliation, write-mode retry matrix, and
real PySpark + Airflow import CI. See
[What's New in 0.23](../01_GETTING_STARTED/WHATS_NEW_0_23.md) and
[Exit gate 0.23](EXIT_GATE_0_23.md).

## Shipped: 0.24

ETLantic **0.24.0** shipped **Programmatic Authoring and Lossless JSON**:
canonical `PipelineDefinition`, `etlantic.pipeline/1`, functional builders,
definition lifecycle, CLI JSON targets, authoring catalog/edits, service
facade, and `etlantic-fastapi` reference adapter. See
[What's New in 0.24](../01_GETTING_STARTED/WHATS_NEW_0_24.md) and
[Exit gate 0.24](EXIT_GATE_0_24.md).

## Shipped: 0.25

ETLantic **0.25.0** / **0.25.1** shipped **Compatibility Burn-In (first slice)**:
`etlantic.pipeline/1` and sibling codec upgrade fixtures, Plugin SDK `/1`
freeze decision (blockers published), and a published 0.38 removal inventory.
See [What's New in 0.25](../01_GETTING_STARTED/WHATS_NEW_0_25.md) and
[Exit gate 0.25](EXIT_GATE_0_25.md).

## Shipped: 0.26

ETLantic **0.26.0** shipped **Compatibility Burn-In (second slice)**:
dual-minor burn-in proof (0.24→0.25→0.26), freeze re-scoped to 0.27, and
first-wave root alias removals. See
[What's New in 0.26](../01_GETTING_STARTED/WHATS_NEW_0_26.md) and
[Exit gate 0.26](EXIT_GATE_0_26.md).

## Shipped: 0.27

ETLantic **0.27.0** shipped **Compatibility Burn-In (third slice)**:
triple-minor burn-in proof (0.25→0.26→0.27), freeze re-scoped to 0.28+, and
second-wave root alias removals (reliability, schema_drift, registry). See
[What's New in 0.27](../01_GETTING_STARTED/WHATS_NEW_0_27.md) and
[Exit gate 0.27](EXIT_GATE_0_27.md).

## Shipped: 0.28

ETLantic **0.28.0** shipped **Compatibility Burn-In (fourth slice)**:
quadruple-minor burn-in proof (0.26→0.27→0.28), Plugin SDK `/1` **frozen**,
third-wave root alias removals, Medallantic M0 closeout, and facade package
discipline. See
[What's New in 0.28](../01_GETTING_STARTED/WHATS_NEW_0_28.md) and
[Exit gate 0.28](EXIT_GATE_0_28.md).

## Shipped: 0.29

ETLantic **0.29.0** shipped **Native Medallion Authoring (M1)**:
`MedallionPipeline` / builder surfaces, facade conformance kit, and SparkForge
IR under `medallantic.migrate.sparkforge`. See
[What's New in 0.29](../01_GETTING_STARTED/WHATS_NEW_0_29.md) and
[Exit gate 0.29](EXIT_GATE_0_29.md).

## Shipped: 0.30

ETLantic **0.30.0** shipped **Portable Quality and Rules Parity (M2)**:
provisional `etlantic.quality/1`, Medallantic `rules=` → quality gates, and
quality conformance. See
[What's New in 0.30](../01_GETTING_STARTED/WHATS_NEW_0_30.md) and
[Exit gate 0.30](EXIT_GATE_0_30.md).

## Shipped: 0.31

ETLantic **0.31.0** shipped **Execution, State, and Materialization Semantics
(M3)**: live `transform_ref`, intent-driven runs, `IncrementalStrategy` /
`StateStore`, portable write intents including `skip_if_exists`, Medallantic
layer lifecycle defaults, accept-rate enforcement, and lifecycle conformance.
See [What's New in 0.31](../01_GETTING_STARTED/WHATS_NEW_0_31.md) and
[Exit gate 0.31](EXIT_GATE_0_31.md).

## Shipped: 0.32

ETLantic **0.32.0** shipped **PySpark and Delta Differential Parity (M4)**:
see [What's New in 0.32](../01_GETTING_STARTED/WHATS_NEW_0_32.md) and
[Exit gate 0.32](EXIT_GATE_0_32.md).

## Shipped: 0.33

ETLantic **0.33.0** shipped **SQLAlchemy and Relational Differential Parity
(M5)**: dialect tiers, live `SqlPipelineBuilder` bridge, Moltres rules, and
SQLite/PostgreSQL differential fixtures. See
[What's New in 0.33](../01_GETTING_STARTED/WHATS_NEW_0_33.md) and
[Exit gate 0.33](EXIT_GATE_0_33.md).

## Shipped: 0.34

ETLantic **0.34.0** shipped **Operations, Evidence, and Production Readiness
(M6)**: observability/run-history/event-consumer protocols, runtime bridge,
production conformance, and Medallantic explain/lifecycle/profile templates.
See [What's New in 0.34](../01_GETTING_STARTED/WHATS_NEW_0_34.md) and
[Exit gate 0.34](EXIT_GATE_0_34.md).

## Next: 0.35 — Migration completion and joint freeze (M7)

**0.35** covers SparkForge migration inventory, joint freeze prep, and the
public application-pipeline testing preview in `etlantic.testing`. See
[ROADMAP § 0.35](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md#035--migration-completion-and-joint-freeze).

## 0.29–0.35 — Medallantic feature parity (with ETLantic substrate)

The remaining 0.x foundation phases pair each Medallantic parity milestone
with the domain-neutral ETLantic substrate it exercises:

| Release | Medallantic outcome | ETLantic evolution |
|---|---|---|
| 0.29 | Native medallion authoring | Public facade lowering and conformance |
| 0.30 | Quality/rules parity | Provisional `etlantic.quality/1` + gate planning |
| 0.31 | Execution/materialization parity | State, write, retry, and transaction semantics |
| 0.32 | PySpark/SparkForge parity | Spark, Delta, storage, and debug provenance |
| 0.33 | SQL builder parity | Relational reuse, dialect, and transaction conformance |
| 0.34 | Operations/production readiness | Events, history providers, evidence, and profiles |
| 0.35 | Migration completion | Rewrite tooling, facade compatibility, and joint freeze |

Bronze/silver/gold vocabulary remains in Medallantic. Only capabilities with
domain-neutral meaning are promoted into ETLantic. See the
[full ETLantic roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md) and
[Medallantic roadmap](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/ROADMAP.md).

## Foundation sequence: 0.36–0.38

- **0.36:** joint ETLantic/Medallantic compatibility burn-in, including
  cross-engine application-pipeline test cases
- **0.37:** stable-foundation release-candidate rehearsal with an independent
  user of the public testing API
- **0.38:** stable foundation, including deterministic and bounded
  application-pipeline testing helpers

## 0.39 — First-class data connectivity

The former TransformationModel slot now belongs to the higher-adoption data
connectivity and connector SDK program:

- versioned source, sink, and storage provider protocols;
- secret-free logical bindings and capability negotiation;
- connector development and conformance tooling;
- local, object-storage/Parquet, open-table-format, cloud-warehouse, and
  relational reference paths;
- explicit incremental cursor, transaction, publication, reconciliation, and
  cleanup semantics;
- measurable connector maturity and support levels.

TransformationModel incubation moves to 0.53. See the
[Adoption, Connectivity, and Operations Plan](ADOPTION_ECOSYSTEM_PLAN.md).

## First-class control-plane program

The multi-tenant control plane is a planned first-class feature program rather
than an indefinite residual:

- **0.40 / CP1:** typed API, identity context, authorization, and idempotency
- **0.41 / CP2:** tenant/workspace registry, persistence isolation, stable
  metadata identities, and outbound OpenLineage preview
- **0.42 / CP3:** durable submission, leases, fencing, state, recovery, and
  bounded GitOps preview workspaces
- **0.43 / CP4:** policy, quotas, audit evidence, preview promotion controls,
  and release-candidate proof
- **0.44 / CP-GA:** integrated production graduation after every gate passes

The program remains outside the 0.34 single-tenant envelope and never treats
in-process Python context as a tenant boundary. See the
[Multi-Tenant Control Plane Plan](MULTI_TENANT_CONTROL_PLANE_PLAN.md).

## Remaining post-foundation 0.x sequence

- **0.45:** developer intelligence, LSP, IDE, and static analysis
- **0.46:** planner and optimization SDK
- **0.47:** streaming and event-driven pipelines
- **0.48:** remote execution federation with Kubernetes and a managed Spark
  reference provider
- **0.49:** AI-assisted, human-governed engineering
- **0.50:** brownfield adoption bridges for dbt, Dagster, Prefect, and Argo
- **0.51:** read-only-first operator console
- **0.52:** managed runtime and enterprise provider packs
- **0.53:** TransformationModel incubation

These are assigned post-control-plane phases with explicit acceptance gates.
The roadmap does not reserve a 1.0 or 1.x phase.

## Post-foundation recovery and federation

Durable execution hosts remain outside ETLantic core, while ETLantic supplies
the portable evidence needed to recover safely:

- **0.42 / CP3 Incremental State and Reproducibility** adds a secret-free
  execution-attempt context, checkpoint/resume evidence, and normalized
  known/unknown external-effect outcomes.
- **0.48 Remote Execution Federation** adds host-neutral recovery negotiation,
  fenced attempt attribution, resumable observation, and conformance semantics
  for retry, replay, repair, reconciliation, and manual review.

The queue, worker claim/lease store, heartbeat service, and scheduler leadership
remain responsibilities of applications and orchestrator plugins. See
[ETL Reliability and Recovery Plan](ETL_RELIABILITY_PLAN.md#durable-host-recovery-integration).

## Stable foundation at 0.38

The 0.38 goal is a stable foundation with frozen contracts (0.19), completed
trust/isolation gates (**0.20.0**), cohesive CLI (**0.21.0**), Plugin SDK with
frozen `/1` protocols (re-scoped at 0.27; closure owned by **0.28**), and
0.24 functional/JSON authoring convergence, followed by core compatibility
burn-in (**0.25** / **0.26** / **0.27** / **0.28**), joint Medallantic feature
parity (**0.29–0.35**), joint compatibility burn-in (**0.36**), release
candidate (**0.37**), and stable foundation (**0.38**).
TransformationModel incubation is deferred to **0.53** so connectivity,
interoperability, operations, and provider work can precede it.

> **Production use is supported only within the documented reference
> envelope.** See the [Evaluator Brief](../01_GETTING_STARTED/EVALUATOR.md).

Read the
[full roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md)
for milestone details.
