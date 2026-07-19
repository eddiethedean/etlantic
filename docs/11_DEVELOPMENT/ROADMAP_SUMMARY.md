# Roadmap Summary

ETLantic is an alpha project moving toward a stable, secure modeling and plugin
platform. Milestones describe capability order, not release-date commitments.

## 0.14 shipped

ETLantic 0.14.0 completed the first three-engine portable relational baseline:

- Pandas joined Polars and PySpark with kernel +
  `portable-relational/1` compilation;
- the Pandas compiler provides eager, index-neutral semantics;
- `etlantic.testing.run_portable_transform_conformance_suite` became a public
  SDK contract for official and third-party compilers;
- CI added public conformance for all three engines, three-engine
  differentials, and property coverage for core portable semantics.

See [What's New in 0.14](../01_GETTING_STARTED/WHATS_NEW_0_14.md) and
[Capabilities](../01_GETTING_STARTED/CAPABILITIES.md) for the shipped boundary.

## Next: 0.15 (Safe SQL Lowering)

Alongside Safe SQL Lowering, 0.15 also prefers the **Extract / Load / asset**
authoring vocabulary (`Source` / `Sink` / `binding=` warn; remove in 0.16).
See [Migration 0.14 → 0.15](MIGRATION_0_14_TO_0_15.md).

The **mandatory** 0.15 milestone is safe portable SQL lowering for the
already-shipped claim set (kernel + `portable-relational/1`):

- lower portable plans into ETLantic's typed `etlantic.sql/1` IR;
- preserve safe identifiers and bound parameters (no interpolation);
- fail at planning for dialect gaps instead of using raw SQL or UDF
  approximations;
- keep `require` fail-closed and allow `prefer` to select an **explicit
  native** SQL implementation only — never silent portable emulation;
- extend public conformance fixtures to the SQL realization;
- keep PostgreSQL via `etlantic-sql` as the reference dialect.

Native `@implementation("sql")` remains the supported SQL path until those
portable SQL claims ship.

### 0.15 continuation (not the 0.15 exit gate)

Richer portable profiles (window, string-advanced, conversion, complex
types/values, statistics, reshape, relational-extended, temporal-IANA,
nondeterministic) graduate **one family at a time** only after two independent
compilers pass shared fixtures. That work is sequenced after the SQL vertical
slice; it is not a separate 0.16 milestone and is not required to close 0.15.

## Toward 1.0

The 1.0 goal is a stable foundation with:

- stable authoring, Plugin SDK, plan, event, result, and run-report contracts;
- documented compatibility, deprecation, and schema-migration policies;
- completed security gates for plugin provenance, secret handling, artifact and
  cache isolation, network constraints, audit evidence, and bounded work;
- conformance and acceptance coverage across reference engines and
  orchestrators;
- complete executable tutorials, references, and migration guides.

> **Do not productionize ETLantic before the 1.0 security release gate
> closes.** Version 0.14.0 is alpha; available allowlists and version pins do
> not make the product production-ready. See the
> [Evaluator Brief](../01_GETTING_STARTED/EVALUATOR.md).

Read the
[full roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md)
for milestone details, acceptance scenarios, and release gates.
