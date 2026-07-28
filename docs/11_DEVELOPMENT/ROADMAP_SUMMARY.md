# Roadmap Summary

ETLantic **0.31.0** ships **Execution, State, and Materialization Semantics (M3)**.
Milestones describe capability order, not release-date commitments.

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
pre-1.0 deprecation schedule. See
[What's New in 0.19](../01_GETTING_STARTED/WHATS_NEW_0_19.md).

ETLantic **0.20.0** shipped **Trust, Isolation, and Safe I/O**:
pre-import plugin manifests, `SafeIoPolicy`, artifact/cache isolation,
outbound SSRF policy, serialization bans, versioned security events, and
release SBOM digests / attestations / OIDC-preferred publish. See
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
freeze decision (blockers published), and a published 1.0 removal inventory.
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

## Shipped: 0.31

ETLantic **0.31.0** shipped **Execution, State, and Materialization Semantics
(M3)**: live `transform_ref`, intent-driven runs, `IncrementalStrategy` /
`StateStore`, portable write intents including `skip_if_exists`, Medallantic
layer lifecycle defaults, accept-rate enforcement, and lifecycle conformance.
See [What's New in 0.31](../01_GETTING_STARTED/WHATS_NEW_0_30.md) and
[Exit gate 0.31](EXIT_GATE_0_30.md).

## Shipped: 0.31

ETLantic **0.31.0** shipped **Portable Quality and Rule Semantics (M2)**:
provisional `etlantic.quality/1`, quality-gate planning with plan-time
fail-closed capability negotiation, Polars/Pandas live portable core,
Medallantic rule DSL enforcement, and SQL/PySpark advertise+fail-closed
classification. See
[What's New in 0.31](../01_GETTING_STARTED/WHATS_NEW_0_30.md) and
[Exit gate 0.31](EXIT_GATE_0_30.md).

## Next: 0.32 — PySpark and Delta differential parity (M4)

**0.32** covers SparkForge live bridge, PySpark Column rules, Delta
capabilities, and differential fixtures. See
[ROADMAP § 0.32](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md#032--pyspark-and-delta-differential-parity).

## 0.29–0.35 — Medallantic feature parity (with ETLantic substrate)

The remaining pre-1.0 capability phases pair each Medallantic parity milestone
with the domain-neutral ETLantic substrate it exercises:

| Release | Medallantic outcome | ETLantic evolution |
|---|---|---|
| 0.29 | Native medallion authoring | Public facade lowering and conformance |
| 0.31 | Quality/rules parity | Provisional `etlantic.quality/1` + gate planning |
| 0.31 | Execution/materialization parity | State, write, retry, and transaction semantics |
| 0.32 | PySpark/SparkForge parity | Spark, Delta, storage, and debug provenance |
| 0.33 | SQL builder parity | Relational reuse, dialect, and transaction conformance |
| 0.34 | Operations/production readiness | Events, history providers, evidence, and profiles |
| 0.35 | Migration completion | Rewrite tooling, facade compatibility, and joint freeze |

Bronze/silver/gold vocabulary remains in Medallantic. Only capabilities with
domain-neutral meaning are promoted into ETLantic. See the
[full ETLantic roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md) and
[Medallantic roadmap](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/ROADMAP.md).

## 0.36–0.98

Joint ETLantic/Medallantic compatibility burn-in, then RC and Stable
Foundation. Production FastAPI control API remains **1.1**;
registry/workspaces **1.2**.

## Post-1.0 recovery and federation

Durable execution hosts remain outside ETLantic core, while ETLantic supplies
the portable evidence needed to recover safely:

- **1.3 Incremental State and Reproducibility** adds a secret-free
  execution-attempt context, checkpoint/resume evidence, and normalized
  known/unknown external-effect outcomes.
- **1.8 Remote Execution Federation** adds host-neutral recovery negotiation,
  fenced attempt attribution, resumable observation, and conformance semantics
  for retry, replay, repair, reconciliation, and manual review.

The queue, worker claim/lease store, heartbeat service, and scheduler leadership
remain responsibilities of applications and orchestrator plugins. See
[ETL Reliability and Recovery Plan](ETL_RELIABILITY_PLAN.md#durable-host-recovery-integration).

## Toward 1.0

The 1.0 goal is a stable foundation with frozen contracts (0.19), completed
trust/isolation gates (**0.20.0**), cohesive CLI (**0.21.0**), Plugin SDK with
frozen `/1` protocols (re-scoped at 0.27; closure owned by **0.28**), and
0.24 functional/JSON authoring convergence, followed by core compatibility
burn-in (**0.25** / **0.26** / **0.27** / **0.28**), joint Medallantic feature
parity (**0.29–0.35**), and joint compatibility burn-in (**0.36–0.98**).
TransformationModel incubation is deferred to post-1.0 phases.

> **Production use is supported only within the documented reference
> envelope.** See the [Evaluator Brief](../01_GETTING_STARTED/EVALUATOR.md).

Read the
[full roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md)
for milestone details.
