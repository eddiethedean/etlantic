# Migration: 0.14 → 0.15

ETLantic 0.15 ships three themes:

1. **Safe SQL Lowering** — portable kernel + `portable-relational/1` → typed
   SQL IR (PostgreSQL reference via `etlantic-sql`)
2. **Extract / Load / asset** — public authoring vocabulary rename
3. **LocalScheduler** — direct-execution boundary for `Pipeline.run` / `arun`

Prefer the new authoring names immediately; legacy `Source` / `Sink` /
`binding=` emit `DeprecationWarning` and are removed in **0.16**.

## Safe SQL Lowering

Install `etlantic-sql==0.15.0`. Portable plans that fit the claimed SQL
compiler surface no longer require a native `@implementation("sql")` under
`portable_transform_policy="require"`. Native SQL implementations remain
selectable. Trusted SQL fragments are rejected in portable definitions.
See [SQL](../06_EXECUTION/SQL.md) and the
[portable compiler matrix](../10_REFERENCE/PORTABLE_COMPILER_MATRIX.md).

## LocalScheduler

`Pipeline.run` / `arun` enter through `LocalScheduler`. Observable report
shape and plan fingerprints are preserved. Airflow compilation is unchanged.
Optional Prefect packaging is **0.16 Gate B** (`ExecutionScheduler` MVP).
Authoring vocabulary removal (`Source` / `Sink` / `binding=`) is the
independent **0.16 Gate A**.

## Mapping table

| 0.14 (legacy) | 0.15 (preferred) | Notes |
| --- | --- | --- |
| `Source[T]` | `Extract[T]` | `Source` subclasses `Extract` |
| `Sink[T]` | `Load[T]` | `Sink` subclasses `Load` |
| `binding=` on Source/Sink | `asset=` on Extract/Load | Reject specifying both |
| `.binding` property | `.asset` | `.binding` warns |
| `Profile(bindings=...)` | `Profile(assets=...)` | One internal store |
| Profile JSON `"bindings"` | Prefer `"assets"` (mirrored `"bindings"` in 0.15) | Plans keep bindings-only snapshots |
| `RunRequest(binding_overrides=...)` | `RunRequest(asset_overrides=...)` | Same map |

## Before / after

```python
# 0.14
from etlantic import Pipeline, Sink, Source

class CustomerPipeline(Pipeline):
    raw: Source[RawCustomer] = Source(binding="customer_source")
    curated: Sink[Customer] = Sink(input=normalized.result, binding="customer_sink")

profile = Profile(name="dev", bindings={"customer_source": "memory"})
```

```python
# 0.15
from etlantic import Extract, Load, Pipeline

class CustomerPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="customer_source")
    curated: Load[Customer] = Load(input=normalized.result, asset="customer_sink")

profile = Profile(name="dev", assets={"customer_source": "memory"})
```

## Unchanged semantics

- Logical graph topology and validation rules
- Plan fingerprints for equivalent pipelines/profiles (profile snapshots still
  serialize the pre-0.15 `bindings` shape without an `assets` key)
- Runtime read/write behavior and plugin dispatch
- [DPCS](../05_PIPELINES/DPCS.md) round-trips and interface input/output roles

## Retained protocol / wire names

Do **not** rename these for compatibility:

- `NodeKind` values `"source"` / `"sink"`
- Graph / plan field `binding` on nodes; plan map `bindings` (`BindingDescriptor`)
- DPCS extension field `etlantic:binding`
- Plugin APIs: `StorageBinding.read/write(binding=...)`, SQL/Spark `*_from_binding`
- Port wiring: `Step.bindings`, `SubpipelineInstance.bindings`
- `SourceLocation` diagnostics; viz edge attribute `source`
- SQL / SparkForge metadata fields named `source`

## 0.16 deletion checklist

Remove after the 0.16 compatibility window:

- [ ] `Source` / `Sink` public classes and exports
- [ ] `binding=` constructor kwargs on Extract/Load
- [ ] Public `.binding` property on Extract/Load
- [ ] `Profile(bindings=...)` authoring path and mirrored JSON `bindings` emission
  (after consumers migrate to `assets`)
- [ ] `RunRequest.binding_overrides` authoring path
- [ ] Compatibility stubs in docs stubs (`SOURCES.md` / `SINKS.md`)
- [ ] Deprecation warning helpers dedicated to this rename

## Related docs

- [Extracts](../05_PIPELINES/EXTRACTS.md)
- [Loads](../05_PIPELINES/LOADS.md)
- [Profiles](../05_PIPELINES/PROFILES.md)
- [Roadmap summary — 0.15 Safe SQL Lowering](ROADMAP_SUMMARY.md)
