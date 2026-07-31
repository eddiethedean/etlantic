# Public Surface Inventory (0.39)

> **Status: Available in ETLantic 0.39.0.** Canonical public surface for the
> **0.39 reference envelope**.

Machine-readable companion: [`surface-inventory.json`](https://github.com/eddiethedean/etlantic/blob/main/src/etlantic/schemas/surface-inventory.json)
(also packaged under `etlantic.schemas`). Keep this page aligned with that file.

Stability classes:

| Class | Meaning |
|---|---|
| `stable` | Supported within the documented 0.39 reference envelope |
| `provisional` | Public but may change with migration notes before a later foundation claim |
| `experimental` | May change or be removed without a stable-foundation obligation |
| `compatibility` | Historical class for 0.x root aliases; demoted aliases were **removed in 0.37.0** (hard error). Prefer owning modules |
| `private` | Underscore modules / internal helpers — do not import |

## Recommended import style

```python
import etlantic as etl
```

## SDK (root curated)

Stable root symbols (`sdk_root_stable`):

| Symbol |
|---|
| `Data`, `Transformation`, `Pipeline`, `Extract`, `Load`, `Input`, `Output` |
| `Parameter`, `Profile`, `PipelineRuntime`, `PipelinePlan` |
| `plan_pipeline`, `explain_plan`, `compile_plan` |
| `ValidationReport`, `PipelineRunReport`, `SecretRef` |

Prefer `etl.authoring` for programmatic definition APIs. `DataContractModel`
was **removed** in 0.37.0 — use `ContractModel` / `Data` (see
[Migration 0.36 → 0.37](../11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md)). Earlier
root facade alias waves:
[0.25 → 0.26](../11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md),
[0.26 → 0.27](../11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md),
[0.27 → 0.28](../11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md). Removal inventory:
[Removal candidates](../11_DEVELOPMENT/REMOVAL_CANDIDATES_0_37.md).

## Lazy namespaces

| Attribute | Module | Class |
|---|---|---|
| `etl.authoring` | `etlantic.authoring` | stable |
| `etl.service` | `etlantic.service` | stable |
| `etl.transform` | `etlantic.transform` | stable |
| `etl.dataframe` | `etlantic.dataframe` | stable |
| `etl.sql` | `etlantic.sql` | stable |
| `etl.spark` | `etlantic.spark` | stable |
| `etl.orchestration` | `etlantic.orchestration` | stable |
| `etl.viz` | `etlantic.viz` | stable |
| `etl.secrets` | `etlantic.secrets` | stable |
| `etl.testing` | `etlantic.testing` | stable (application-pipeline foundation in 0.37) |
| `etl.quality` | `etlantic.quality` | provisional |
| `etl.connectors` | `etlantic.connectors` | provisional (0.38 burn-in) |
| `etl.control_plane` | `etlantic.control_plane` | provisional (CP1 / 0.39 identity incubation) |

## Plan helpers (stable)

Foundation immutability contract for `PipelinePlan` (not full object-graph
immutability):

| Symbol | Role |
|---|---|
| `deep_freeze` | Freeze nested mappings → `MappingProxyType`, lists → tuples, sets → frozensets; dataclasses and unknown objects pass through unchanged |
| Canonical serialize | Secret-free `etlantic.plan/1` JSON with stable key ordering for fingerprints |
| `verify_plan_fingerprint` | Trust-boundary check at deserialize / compile / run |
| `resolve_profile` | Strict named profile resolution |

See the
[freeze glossary](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md#freeze-glossary-three-different-terms)
and [Planning](../05_PIPELINES/PLANNING.md#plan-immutability-contract).

## CLI (stable)

Commands: `init`, `doctor`, `profile`, `validate`, `inspect`, `plan`, `run`,
`compile`, `generate`, `diff`, `plugin`, `schema`, `reliability`, `viz`,
`report`.

Stable flags: `--allow-adhoc-profile`, `--accept-legacy-bindings`.

See [CLI](CLI.md).

## Wire schemas

Schema ids keep meaning under additive `/1` rules. That is **not** the same as
[protocol `/1` freeze](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md#freeze-glossary-three-different-terms)
(**frozen in 0.28.0** per [PROTOCOL_EVOLUTION](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md)).

| Schema ID | Class |
|---|---|
| `etlantic.pipeline/1` | stable (authoring) |
| `etlantic.plan/1` | stable (resolved execution IR — **not** authoring round-trip) |
| `etlantic.run_report/1` | stable |
| `etlantic.authoring-catalog/1` | stable (not dual-minor burn-in — tooling metadata; see [Wire schema ranges](WIRE_SCHEMA_RANGES.md)) |
| `etlantic.interchange/1` | stable |
| `etlantic.capabilities/1` | stable |
| `etlantic.quality/1` | provisional (portable quality expressions; ContractModel remains semantic authority) |
| Profile JSON | stable |
| Reliability / policy / extension bags | stable (secret-free; unknown fields fail closed where enforced) |

## Protocols

| Protocol ID | Class |
|---|---|
| `etlantic.dataframe/1` | stable |
| `etlantic.sql/1` | stable |
| `etlantic.spark/1` | stable |
| `etlantic.orchestration/1` | stable |
| `etlantic.transform-compiler/1` | stable |
| `etlantic.scheduler/1` | stable (MVP — Prefect direct-execution bounds) |
| `etlantic.source/1` | provisional (0.38 connector burn-in; ADR-015) |
| `etlantic.sink/1` | provisional (0.38 connector burn-in; ADR-015) |
| `etlantic.storage/1` | provisional (0.38 connector burn-in; ADR-015) |

Landing-zone incremental state uses wire schema `etlantic.landing_checkpoint/1`
(provisional). Concrete file identities appear only in run-scoped
`LandingReadManifest` evidence, not in static `PipelinePlan` listings.

## Foundations

| Surface | Class |
|---|---|
| `etlantic.testing` | stable |

## Optional packages

Pin to the same minor as core (`==0.39.0`). Details:
[Optional packages](OPTIONAL_PACKAGES.md).

| Package | Role |
|---|---|
| `etlantic-polars` | Polars dataframe engine + portable compiler |
| `etlantic-pandas` | Pandas dataframe engine + eager portable compiler |
| `etlantic-sql` | Native SQL engine + portable SQL lowering |
| `etlantic-pyspark` | PySpark engine + portable compiler |
| `etlantic-airflow` | Airflow DAG compiler (`etlantic compile --target airflow`) |
| `etlantic-prefect` | Prefect direct-execution scheduler |
| `etlantic-keyring` | OS keyring secret provider |
| `etlantic-sqlmodel` | SQLModel ↔ contract bridge |
| `medallantic` | Engine-agnostic medallion facade and SparkForge migration adapter |
| `etlantic-fastapi` | Thin FastAPI authoring/service reference adapter (shipped since 0.24) |
| `etlantic-datafusion` | **Experimental** DataFusion stub (Gate B; not graduated) |

## See also

- [API Reference](API_REFERENCE.md)
- [Optional packages](OPTIONAL_PACKAGES.md)
- [Diagnostic-code stability tiers](DIAGNOSTIC_STABILITY_TIERS.md)
- [Protocol Evolution](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md)
