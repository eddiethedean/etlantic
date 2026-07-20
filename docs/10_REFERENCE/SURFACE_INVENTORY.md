# Public Surface Inventory (0.20)

Machine-readable companion: [`surface-inventory.json`](https://github.com/eddiethedean/etlantic/blob/main/src/etlantic/schemas/surface-inventory.json)
(also packaged under `etlantic.schemas`).

Stability classes:

| Class | Meaning |
|---|---|
| `stable` | Supported within the documented 0.21 reference envelope |
| `provisional` | Public but may change with migration notes before 1.0 |
| `experimental` | May change or be removed without 1.0 obligation |
| `private` | Underscore modules / internal helpers — do not import |

## SDK (root)

| Symbol | Class |
|---|---|
| `Data`, `Transformation`, `Pipeline`, `Extract`, `Load` | stable |
| `Input`, `Output`, `Parameter`, `Profile`, `PipelineRuntime` | stable |
| `PipelinePlan`, `plan_pipeline`, `explain_plan` | stable |
| `verify_plan_fingerprint`, `deep_freeze` (via `etlantic.plan`) | stable |
| `ValidationReport`, `PipelineRunReport` | stable |
| `SecretRef`, `compile_plan` | stable |
| `DataContractModel` | provisional (deprecated alias of `Data`) |
| Structured Streaming APIs | experimental |
| `etlantic._*` | private |

## CLI

`validate`, `inspect`, `plan`, `run`, `compile`, `generate`, `diff`, `plugin`,
`schema`, `reliability`, `viz`, `report` — **stable** within 0.20.

`--allow-adhoc-profile` on validate/plan/run — **stable** (opt-in fail-open for
unknown bare profile names; default is fail-closed `PMCFG100`).

## Wire schemas

| Schema ID | Class |
|---|---|
| `etlantic.plan/1` | stable (nested defs tightening through 0.20) |
| `etlantic.run_report/1` | stable |
| `etlantic.interchange/1` | stable (Gate A) |
| Profile JSON + `security_mode` | stable |
| IDE command/result JSON | provisional |

## Plugin protocols

| Protocol | Class |
|---|---|
| `etlantic.dataframe/1` | stable |
| `etlantic.sql/1` | stable |
| `etlantic.spark/1` | stable |
| `etlantic.orchestration/1` | stable |
| `etlantic.scheduler/1` | provisional (Prefect MVP) |
| `etlantic.transform-compiler/1` | stable |
| `etlantic-datafusion` (if installed) | experimental |

## Diagnostic families

`PM*`, `PMPLUG*`, `PMCFG*`, `PMXFORM*` — **stable** codes; new codes may be
added. See [Diagnostics](DIAGNOSTICS.md).

CI drift: `scripts/check_surface_inventory.py` (optional) compares this
inventory to `etlantic.__all__`.
