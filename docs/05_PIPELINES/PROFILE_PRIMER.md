# Profile primer

Profiles bind a portable pipeline to a concrete environment: engines, assets,
trust policy, and validation strictness. This page helps you pick the right
profile shape for local work, CI, and production.

## Built-in profile names

| Profile | Typical use | Trust posture |
|---------|-------------|---------------|
| **`local`** | Default for CLI when `--profile` is omitted; in-process Python records | Open plugin discovery; `security_mode` defaults to development |
| **`development`** | Tutorials and local dataframe/SQL work | Open discovery; relaxed validation unless overridden |
| **`production`** | Staging and production runs | Fail-closed: non-empty `plugin_allowlist`, manifests, optional capability probes |

The CLI defaults to **`local`**; most tutorials pass **`development`**. Use the
same profile for `validate`, `plan`, and `run` in one workflow. See
[CLI reference](../10_REFERENCE/CLI.md).

## JSON profiles vs built-ins

Built-in names resolve from ETLantic templates. For reproducible deployment,
store a JSON profile and pass its path:

```bash
etlantic plan my_pipeline.py:MyPipeline --profile profiles/prod.json
```

Load and save profiles through the SDK:

```python
from etlantic.profile import load_profile, write_profile, production_profile

profile = production_profile(
    plugin_allowlist={"etlantic-polars": "==0.21.0"},
    assets={"raw": "s3://bucket/raw", "curated": "warehouse.curated"},
)
write_profile(profile, "profiles/prod.json")
loaded = load_profile("profiles/prod.json")
```

Profile JSON is read and written through **safe I/O** confined to the profile
file's parent directory (see [Architecture — 0.20 trust delta](../02_FOUNDATIONS/ARCHITECTURE.md#020-trust-and-safe-io-delta)).

## Key fields

### `security_mode`

Explicit trust tier: `development`, `test`, or `production`. Production mode
requires a **non-empty** `plugin_allowlist` and static plugin manifests before
load. Prefer setting `security_mode` explicitly in JSON rather than inferring
from the profile name alone.

### `plugin_allowlist`

Maps plugin distribution names (or entry-point names) to version constraints.
In production, an empty allowlist rejects every discovered plugin. Example:

```json
"plugin_allowlist": {
  "etlantic-polars": "==0.21.0",
  "etlantic-sql": "==0.21.0"
}
```

See [Production profiles](../06_EXECUTION/PRODUCTION_PROFILES.md) and
[prod.example.json](../01_GETTING_STARTED/prod.example.json).

### `assets` vs legacy `bindings`

Prefer **`assets`** for logical-to-physical maps (extract/load locations).
Legacy **`bindings`** keys still load but emit diagnostic `PMCFG110`; migrate
to `assets` in new profiles.

### Engines and orchestrator

- `dataframe_engine`: `local`, `polars`, or `pandas`
- `sql_engine`: `null` or `sql` (requires `etlantic-sql`)
- `spark_engine`: `null`, `pyspark`, or `spark`
- `orchestrator`: `local`, `airflow`, `prefect`, etc.

Keep plugin package versions on the **same minor** as core (`0.21.x` with
`0.20.0` core).

### Optional 0.20 trust controls

- `require_plugin_probe`: spawn an isolated capability probe before load (production fail-closed on failure)
- `validation_policy`: `standard` or `strict` (strict requires bindings and implementations)
- `portable_transform_policy`: `native`, `prefer`, or `require`

## When to use which profile

```text
Quick CLI check (no plugins)     →  local (default)
Tutorial / dataframe dev         →  development
CI validate + plan               →  development or checked-in JSON
Production deploy                →  production JSON + allowlist + assets
```

## Related reading

- [Profiles](PROFILES.md) — full profile model
- [Production profiles](../06_EXECUTION/PRODUCTION_PROFILES.md)
- [Security model](../02_FOUNDATIONS/SECURITY.md)
- [Migration 0.19 → 0.20](../11_DEVELOPMENT/MIGRATION_0_19_TO_0_20.md)
