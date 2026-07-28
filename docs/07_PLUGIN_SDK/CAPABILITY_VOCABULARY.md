# Capability Vocabulary

> **Status: Available in ETLantic 0.31.0** via `etlantic.capabilities`.

Plugins declare what they support through `PluginCapabilities`. The vocabulary
is versioned independently of package and protocol versions as
`etlantic.capabilities/1` (`CAPABILITY_VOCABULARY_VERSION`).

## Compatibility

Use `vocabulary_major_compatible(version)` to check that a declared vocabulary
string shares major `/1` with the core vocabulary. Minor or patch segments under
the same major remain compatible; a different major is not.

## Implications

Specialized flags imply their family root. Claiming a specialized capability
without the implied root is inconsistent and fails
`validate_capability_claims`.

| Claim | Implies |
|---|---|
| `sql_merge`, `sql_cte`, `sql_returning`, `sql_transactional_ddl`, `sql_atomic_rename`, `sql_catalog_inspect`, `sql_trusted_fragments` | `sql` |
| `spark_delta`, `spark_merge`, `spark_streaming`, `spark_native_exprs`, `spark_udf`, `spark_cache`, `spark_checkpoint` | `spark` |
| `orch_scheduling`, `orch_retries`, `orch_timeouts`, `orch_parallel`, `orch_sensors`, `orch_artifacts_only_xcom` | `orchestration` |
| `lazy`, `arrow_import`, `arrow_export`, `zero_copy`, `invalid_row_separation` | `dataframe` |

## Portable write extras (`write.*`)

Write and materialization capabilities are advertised as **extras** (in addition
to legacy `sql_merge` / `spark_merge` flags):

| Extra | Meaning |
|---|---|
| `write.append` | Append-only writes |
| `write.overwrite` | Full replace |
| `write.merge` / `write.upsert` | Keyed merge / upsert |
| `write.skip_if_exists` | Skip when target already exists |
| `write.partition_replace` | Partition overwrite / replace |

Missing required write extras fail closed before mutation with `PMPLAN430` /
`PMPLAN431`. Default append/overwrite remain available without explicit extras
on local/memory engines.

## Portable quality extras (`etlantic.quality/1`)

Quality rule capabilities are advertised as **extras** (not boolean
`PluginCapabilities` fields). Engines that implement the portable core should
advertise the matching keys (Polars/Pandas/`local` do in 0.31):

| Extra | Rule kind |
|---|---|
| `quality.not_null` | `not_null` |
| `quality.compare` | `compare` |
| `quality.membership` | `membership` |
| `quality.range` | `range` |
| `quality.regex` | `regex` |
| `quality.length` | `length` |
| `quality.uniqueness` | `uniqueness` |
| `quality.custom_contract` | `custom_contract` (opt-in only) |

Gates also require `invalid_row_separation`. Missing required quality extras
fail closed at plan time with `PMPLAN420` / `PMPLAN421`.

Call `capability_implications()` for the authoritative map used by validation.

## Conflicts

Vocabulary `/1` defines no hard mutual exclusions. Engines may claim both
`eager` and `lazy` when they support both execution modes.
`capability_conflicts()` returns an empty list in `/1`; future majors may add
pairs.

## Deprecation

No capability names are deprecated in `/1`. When names are retired:

- keep the boolean field through at least one minor release with a documented
  alias in `supports()`
- document the replacement and removal target in this page
- bump the vocabulary major only when removing a name or changing implication
  / conflict semantics incompatibly

## Validation

```python
from etlantic.capabilities import (
    PluginCapabilities,
    validate_capability_claims,
    vocabulary_major_compatible,
)

caps = PluginCapabilities(engine="example", sql_merge=True, sql=True)
assert not validate_capability_claims(caps)
assert vocabulary_major_compatible(caps.vocabulary_version)
```

Overstated or internally inconsistent claims should surface as actionable
findings (for example, `sql_merge` without `sql`).

## Schema

Machine-readable vocabulary documentation lives at
[`capability-vocabulary-1.json`](https://github.com/eddiethedean/etlantic/blob/main/src/etlantic/schemas/capability-vocabulary-1.json).
