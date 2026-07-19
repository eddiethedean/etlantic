# Migration: 0.14 → 0.15 (Extract / Load / asset)

ETLantic 0.15 introduces a public authoring vocabulary rename. Semantics are
unchanged: extracts still introduce data, loads still publish data, and
profiles still resolve logical names to providers. This is a second 0.15 theme
alongside **Safe SQL Lowering** (see the roadmap); it does not replace that
exit gate.

Package versioning for this vocabulary work may land under **Unreleased** until
the 0.15 release is cut. Prefer the new names immediately; legacy names emit
`DeprecationWarning` and are scheduled for removal in **0.16**.

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
- DPCS round-trips and interface input/output roles

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
