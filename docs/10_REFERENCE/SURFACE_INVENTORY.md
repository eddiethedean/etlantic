# Public Surface Inventory (0.25)

Machine-readable companion: [`surface-inventory.json`](https://github.com/eddiethedean/etlantic/blob/main/src/etlantic/schemas/surface-inventory.json)
(also packaged under `etlantic.schemas`). Regenerated from that file for the
**0.25 reference envelope**.

Stability classes:

| Class | Meaning |
|---|---|
| `stable` | Supported within the documented 0.25 reference envelope |
| `provisional` | Public but may change with migration notes before 1.0 |
| `experimental` | May change or be removed without 1.0 obligation |
| `compatibility` | Pre-1.0 root alias (warn once); prefer the owning namespace |
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

Prefer `etl.authoring` for programmatic definition APIs. Provisional root:
`DataContractModel` (prefer ODCS / `Data` paths). Demoted pre-1.0 root aliases
warn once — see [MIGRATION_0_21_TO_0_22](../11_DEVELOPMENT/MIGRATION_0_21_TO_0_22.md).

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
| `etl.testing` | `etlantic.testing` | stable |

## Plan helpers (stable)

| Symbol | Notes |
|---|---|
| `verify_plan_fingerprint` | Trust boundary check at deserialize / compile / run |
| `deep_freeze` | Freezes nested mappings → `MappingProxyType`, lists → tuples, sets → frozensets; dataclasses and unknown objects pass through unchanged |
| `resolve_profile` | Strict named profile resolution |

## CLI (stable)

Commands: `init`, `doctor`, `profile`, `validate`, `inspect`, `plan`, `run`,
`compile`, `generate`, `diff`, `plugin`, `schema`, `reliability`, `viz`,
`report`.

Stable flags: `--allow-adhoc-profile`, `--accept-legacy-bindings`.

See [CLI](CLI.md).

## Wire schemas

Schema ids keep meaning under additive `/1` rules. That is **not** the same as
[protocol `/1` freeze](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md#freeze-glossary-three-different-terms)
(still open in 0.25).

| Schema ID | Class |
|---|---|
| `etlantic.pipeline/1` | stable (authoring) |
| `etlantic.plan/1` | stable (resolved execution IR — **not** authoring round-trip) |
| `etlantic.run_report/1` | stable |
| `etlantic.authoring-catalog/1` | stable |
| `etlantic.interchange/1` | stable |
| `etlantic.capabilities/1` | stable |
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
| `etlantic.scheduler/1` | provisional |

## Optional packages

Pin to the same minor as core (`==0.25.0`). Details:
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
| `etlantic-sparkforge` | SparkForge adapter (medallion stays here, not in core) |
| `etlantic-fastapi` | Thin FastAPI authoring/service reference adapter (shipped since 0.24) |
| `etlantic-datafusion` | **Experimental** DataFusion stub (Gate B; not graduated) |

## See also

- [API Reference](API_REFERENCE.md)
- [Optional packages](OPTIONAL_PACKAGES.md)
- [Protocol Evolution](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md)
