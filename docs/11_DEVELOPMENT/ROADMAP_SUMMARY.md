# Roadmap Summary

ETLantic **0.23.0** ships **Runtime Resilience and Performance Budgets** on
top of the 0.22 Plugin SDK RC. Milestones describe capability order, not
release-date commitments.

## Shipped: 0.15 through 0.20

ETLantic **0.15.0** closed Safe SQL Lowering and the LocalScheduler companion.

ETLantic **0.16.0** shipped authoring vocabulary cleanup and optional
`etlantic-prefect` `ExecutionScheduler`.

ETLantic **0.17.0** shipped portable coverage expansion (platform + Wave 1/2
on Polars + PySpark). Pandas and SQL remain kernel + `portable-relational/1`.

ETLantic **0.18.0** shipped Gate A versioned tabular interchange
(`etlantic.interchange/1`) for Polars↔Pandas. See
[What's New in 0.18](../01_GETTING_STARTED/WHATS_NEW_0_18.md).

ETLantic **0.19.0** shipped the **Contract and Configuration Freeze**:
deep plan immutability, fingerprint trust-boundary verify, `security_mode`,
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

## Next: 0.24

ETLantic **0.24** is **Programmatic Authoring and Lossless JSON** (planned).
Class and functional authoring become two views of one canonical
`PipelineDefinition`. A new wire document `etlantic.pipeline/1` is the
lossless authoring codec — distinct from resolved `etlantic.plan/1` and from
ODCS/DTCS/DPCS.

Sequenced work packages: WP1 definition model → WP2 codecs/schema → WP3
functional builders ∥ WP4 lifecycle-on-definitions → WP5 artifact codec
consistency → WP6 CLI JSON targets and docs → WP7 application and
visual-builder integration → WP8 API service boundary and FastAPI reference.

A JSON-loaded pipeline validates, plans, and runs without its originating
Python class after referenced implementations and plugins resolve under normal
trust policy. Executable code and secrets stay outside serialization.

An independent GUI will be able to discover a machine-readable component
catalog, render forms and node palettes, apply immutable graph edits, connect
compatible ports, map diagnostics to fields/nodes/edges, preview validation and
planning, and import/export canonical JSON using only public APIs. The milestone
includes an independent visual-builder fixture as proof, but does not add a
production GUI or hosted control plane to ETLantic core.

The GUI-facing workflow can sit behind a FastAPI application. ETLantic will
provide OpenAPI-compatible schemas, transport-neutral service request/response
models, stable errors, concurrency and idempotency fields, asynchronous
run/status contracts, and host-supplied policy-context hooks. A thin FastAPI
reference adapter and generated frontend client fixture will prove the
integration. FastAPI, authentication, persistence, queues, and production
hosting remain optional application concerns rather than core dependencies.
This reference boundary feeds, but does not replace, the production FastAPI
Control API planned for 1.1.

See [ROADMAP.md](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md#024--programmatic-authoring-and-lossless-json).

## Toward 1.0

The 1.0 goal is a stable foundation with frozen contracts (0.19), completed
trust/isolation gates (**0.20.0**), cohesive CLI (**0.21.0**), Plugin SDK with
frozen `/1` protocols (post-0.22 RC feedback), and 0.24 functional/JSON
authoring convergence, then compatibility burn-in (0.25–0.98).
TransformationModel incubation is deferred to post-1.0 phases.

> **Production use is supported only within the documented reference
> envelope.** See the [Evaluator Brief](../01_GETTING_STARTED/EVALUATOR.md).

Read the
[full roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md)
for milestone details.
