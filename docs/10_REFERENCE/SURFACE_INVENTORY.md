# Public Surface Inventory (0.23)

Machine-readable companion: [`surface-inventory.json`](https://github.com/eddiethedean/etlantic/blob/main/src/etlantic/schemas/surface-inventory.json)
(also packaged under `etlantic.schemas`).

Stability classes:

| Class | Meaning |
|---|---|
| `stable` | Supported within the documented 0.23 reference envelope |
| `provisional` | Public but may change with migration notes before 1.0 |
| `experimental` | May change or be removed without 1.0 obligation |
| `compatibility` | Pre-1.0 root alias (warn once); prefer the owning namespace |
| `private` | Underscore modules / internal helpers — do not import |

## Recommended import style

```python
import etlantic as etl
```

`from etlantic import Data, Pipeline` and public submodule imports remain
supported. Specialist helpers demoted off the root in 0.23 stay importable as
compatibility aliases (DeprecationWarning once per process) — prefer
`etl.sql`, `etl.spark`, etc.

## SDK (root curated)

| Symbol | Class |
|---|---|
| `Data`, `Transformation`, `Pipeline`, `Extract`, `Load` | stable |
| `Input`, `Output`, `Parameter`, `Profile`, `PipelineRuntime` | stable |
| `PipelinePlan`, `plan_pipeline`, `explain_plan` | stable |
| `ValidationReport`, `PipelineRunReport` | stable |
| `SecretRef`, `compile_plan`, `__version__` | stable |
| `DataContractModel` | provisional (deprecated alias of `Data`) |
| Demoted former root symbols (`col`, `SqlQuery`, …) | compatibility |
| Structured Streaming APIs | experimental |
| `etlantic._*` | private |

## Lazy namespaces

| Attribute | Module | Class |
|---|---|---|
| `etl.transform` | `etlantic.transform` | stable |
| `etl.dataframe` | `etlantic.dataframe` | stable |
| `etl.sql` | `etlantic.sql` | stable |
| `etl.spark` | `etlantic.spark` | stable |
| `etl.orchestration` | `etlantic.orchestration` | stable |
| `etl.viz` | `etlantic.viz` | stable |
| `etl.secrets` | `etlantic.secrets` | stable |
| `etl.testing` | `etlantic.testing` | stable |

Plan helpers `verify_plan_fingerprint` / `deep_freeze` remain stable via
`etlantic.plan`. `resolve_profile` remains stable via `etlantic.profile`.

## CLI

`init`, `doctor`, `validate`, `inspect`, `plan`, `profile`, `run`, `compile`,
`generate`, `diff`, `plugin`, `schema`, `reliability`, `viz`, `report` —
**stable** within 0.23.

`--allow-adhoc-profile` on validate/plan/run — **stable** (opt-in fail-open for
unknown bare profile names; default is fail-closed `PMCFG100`).
`--accept-legacy-bindings` — **stable** (opt-in for legacy `bindings`; default
fail-closed `PMCFG111`). `--workspace`, `--ephemeral`, and `--preview`
(on `run` / `compile`) — **stable**.

## Wire schemas

| Schema ID | Class |
|---|---|
| `etlantic.plan/1` | stable |
| `etlantic.run_report/1` | stable |
| `etlantic.interchange/1` | stable (Gate A) |
| `etlantic.capabilities/1` | stable |
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

CI drift: `scripts/check_surface_inventory.py` bidirectionally compares this
inventory to the curated `etlantic.__all__` and namespace ownership table.

## Planned 0.24 additions

The following are roadmap commitments, not members of the 0.23 inventory:

- `PipelineDefinition` and the `etlantic.pipeline/1` wire schema;
- functional constructors and lifecycle functions matching class authoring;
- authoring catalogs, immutable edit commands, and stable diagnostic paths;
- uniform semantic-artifact dictionary/JSON codecs;
- transport-neutral application-service request/response models;
- a thin optional FastAPI/OpenAPI reference adapter.

They become public only when the 0.24 surface inventory, schemas, compatibility
tests, and exit gate land. See the
[0.24 Programmatic Authoring Plan](../11_DEVELOPMENT/PROGRAMMATIC_AUTHORING_0_24.md).
