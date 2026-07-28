# Exit Gate 0.29 — Native Medallion Authoring (M1)

> **Status: Shipped in ETLantic 0.29.0.** Medallantic M1 native authoring and
> the core facade conformance kit land in **0.29.0**.

| Deliverable | Status |
|---|---|
| Native `MedallionPipeline` / `MedallionBuilder` / Bronze·Silver·Gold | Done |
| Fluent + declarative authoring; partial / branch / prior-result / tags | Done |
| Lowering onto public `PipelineDefinition` (no medallion in core wire) | Done |
| Facade conformance kit (`etlantic.testing.facade`) | Done |
| SparkForge IR under `medallantic.migrate.sparkforge` | Done |
| Stable `MDL1xx` construction/graph diagnostics | Done |
| Definition extension validation + plan survival of namespaced bags | Done |
| Docs: What's New / Migration / this exit gate | Done |
| Core + plugins bumped to 0.29.0 | Done |

## Acceptance checklist

- [x] Representative SparkForge / ecommerce pipelines can be authored natively
  in Medallantic without SparkForge installed
- [x] Native definitions round-trip through `etlantic.pipeline/1` JSON
- [x] Graph fingerprints match IR-adapted topologies for the ecommerce fixture
- [x] Plans are deterministic for the same definition + profile
- [x] Facade package avoids private `etlantic._*` imports (conformance kit)
- [x] No bronze/silver/gold identifiers in core wire schemas
- [x] What's New / Migration 0.28→0.29 / this exit gate pass docs gates

## Residual / follow-ons (0.30+)

- Portable quality / rule DSL (**M2 / 0.30**) — see
  [Exit gate 0.30](EXIT_GATE_0_30.md)
- Execution, state, and materialization parity (**M3 / 0.31**)
- Remaining demoted root aliases toward 1.0
- Joint burn-in band resumes at **0.36+**

## See also

- [ROADMAP § 0.29](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md#029--native-medallion-authoring)
- [Exit gate 0.28](EXIT_GATE_0_28.md)
- [Facade packages](FACADE_PACKAGES.md)
- [Medallantic roadmap](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/ROADMAP.md)
