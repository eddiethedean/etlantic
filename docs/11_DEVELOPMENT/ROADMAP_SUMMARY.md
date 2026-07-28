# Roadmap Summary

ETLantic **0.26.0** ships **Compatibility Burn-In (second slice)**.
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
`etlantic-plugin-echo`. Protocol `/1` is freeze-eligible, not frozen. See
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
dual-minor burn-in proof (0.24→0.25→0.26), freeze owned by 0.27, and
first-wave root alias removals. See
[What's New in 0.26](../01_GETTING_STARTED/WHATS_NEW_0_26.md) and
[Exit gate 0.26](EXIT_GATE_0_26.md).

## Next: 0.27

**Compatibility Burn-In (third slice)** — planned: triple-minor proof
(0.25→0.26→0.27), Protocol `/1` freeze closure or re-scope, and second-wave
root removals (`REM-RELIABILITY-ROOT` + demoted wave). See
[What's New in 0.27](../01_GETTING_STARTED/WHATS_NEW_0_27.md) (planned),
[Exit gate 0.27](EXIT_GATE_0_27.md), and
[Migration 0.26 → 0.27](MIGRATION_0_26_TO_0_27.md) (planned).

## Later: 0.28–0.98

Continued compatibility burn-in, then RC and Stable Foundation. Production
FastAPI control API remains **1.1**; registry/workspaces **1.2**.

## Toward 1.0

The 1.0 goal is a stable foundation with frozen contracts (0.19), completed
trust/isolation gates (**0.20.0**), cohesive CLI (**0.21.0**), Plugin SDK with
frozen `/1` protocols (0.25–0.26 freeze closure), and 0.24 functional/JSON
authoring convergence, then compatibility burn-in (**0.25** / **0.26** /
**0.27** slices, then 0.28–0.98 continued). TransformationModel incubation is
deferred to post-1.0 phases.

> **Production use is supported only within the documented reference
> envelope.** See the [Evaluator Brief](../01_GETTING_STARTED/EVALUATOR.md).

Read the
[full roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md)
for milestone details.
