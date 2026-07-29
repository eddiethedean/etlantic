# Migration 0.15 → 0.16

**Status:** required for ETLantic 0.16 Gate A (authoring vocabulary cleanup).

## Summary

ETLantic 0.16 removes the public 0.15 compatibility aliases for pipeline
authoring. Prefer these names immediately:

| Removed in 0.16 | Use instead |
|---|---|
| `Source[T]` | `Extract[T]` |
| `Sink[T]` | `Load[T]` |
| `binding=` on Extract/Load | `asset=` |
| `.binding` property | `.asset` |
| `Profile(bindings=...)` | `Profile(assets=...)` |
| Mirrored profile JSON `"bindings"` | Prefer `"assets"` (writes emit assets only) |
| `RunRequest(binding_overrides=...)` | `RunRequest(asset_overrides=...)` |

Constructing or importing the removed authoring surfaces fails with a clear
`TypeError` / `ImportError` pointing at this guide.

## Wire names that stay

Plan, [DPCS](../05_PIPELINES/DPCS.md), and plugin protocols keep these names:

- `NodeKind` values `"source"` / `"sink"`
- Plan node field `binding` and plan map `bindings`
- Profile **plan snapshot** shape still uses `"bindings"` (fingerprint-stable)
- DPCS `etlantic:binding`
- Storage plugin APIs `read/write(binding=...)`
- Port wiring `Step.bindings` / `SubpipelineInstance.bindings`

Do not rename those when migrating application code.

## Before / after

```python
# 0.15 (removed)
from etlantic import Pipeline, Sink, Source

class CustomerPipeline(Pipeline):
    raw: Source[RawCustomer] = Source(binding="customer_source")
    curated: Sink[Customer] = Sink(input=normalized.result, binding="customer_sink")

profile = Profile(name="dev", bindings={"customer_source": "memory"})
```

```python
# 0.16
from etlantic import Extract, Load, Pipeline

class CustomerPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="customer_source")
    curated: Load[Customer] = Load(input=normalized.result, asset="customer_sink")

profile = Profile(name="dev", assets={"customer_source": "memory"})
```

## Profile JSON

`Profile.to_dict()` / `write_profile` emit `"assets"` only. Loading still accepts
legacy `"bindings"` keys so saved 0.15 profile files continue to open; rewrite
them with `assets` when convenient.

Plan fingerprints still serialize `profile_snapshot.bindings` only.

## Prefect (Gate B)

Optional `etlantic-prefect` is independent of this vocabulary cleanup. See
[ROADMAP §0.16](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md#016--authoring-vocabulary-cleanup-and-optional-prefect-scheduler)
and the
[Local Scheduler and Prefect Integration Plan](SCHEDULER_AND_PREFECT_PLAN.md).

## Checklist

- [x] `Source` / `Sink` public classes and exports
- [x] `binding=` constructor kwargs on Extract/Load
- [x] Public `.binding` property on Extract/Load
- [x] `Profile(bindings=...)` authoring path and mirrored JSON `bindings` emission
- [x] `RunRequest.binding_overrides` authoring path
- [x] Compatibility helpers in `_compat.py`
- [x] Docs and examples use `Extract` / `Load` / `asset=`
