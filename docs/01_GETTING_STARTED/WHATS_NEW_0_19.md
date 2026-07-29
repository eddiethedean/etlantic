# What's New in 0.19

> **Status: Available in ETLantic 0.19.0.** Contract and configuration freeze.

ETLantic 0.19.0 freezes the logical model and plan boundary into a precise,
versioned contract before further stable surface area.

## Breaking for you if…

- Your production trust relied on profile **name** or `security_domain` → set
  `"security_mode": "production"`.
- CI used typo or generated bare profile names → they now fail with `PMCFG100`
  unless `--allow-adhoc-profile` / `allow_adhoc_profile=True`.
- Profile JSON still uses only `"bindings"` → prefer `"assets"` (`PMCFG110`).
- Persisted plans/reports omit `"schema"` → loads now fail; fingerprints are
  verified on deserialize and before compile/run.

```python
from etlantic import Profile

prod = Profile(
    name="prod-east",
    security_mode="production",
    plugin_allowlist={"local": None, "etlantic-polars": "==0.19.0"},
)
```

```bash
etlantic validate pipeline.py:P --profile typo   # PMCFG100
etlantic validate pipeline.py:P --profile typo --allow-adhoc-profile
```

Full steps: [Migration 0.18 → 0.19](../11_DEVELOPMENT/MIGRATION_0_18_TO_0_19.md).

## Contract and configuration freeze

- Deep plan immutability helpers and fingerprint verification at deserialize,
  compile, and run trust boundaries
- Explicit `Profile.security_mode` (`development` | `test` | `production`)
- Strict named profile resolution; unknown bare names fail closed unless
  `--allow-adhoc-profile` / `allow_adhoc_profile=True`
- Diagnosed legacy profile JSON `bindings` loads (`PMCFG110`)
- Plan and run-report loaders reject missing or unknown wire `schema` values
- Extension metadata namespace/budget helpers
- Public surface inventory and 0.x deprecation schedule

## Experimental DataFusion (non-blocking)

Optional `etlantic-datafusion` ships as **Experimental** Gate B (stub; no
graduated claims). It does not replace Polars and does not weaken freeze gates.

```bash
pip install 'etlantic[datafusion]==0.19.0'
```

## Upgrade

See [Migration 0.18 → 0.19](../11_DEVELOPMENT/MIGRATION_0_18_TO_0_19.md).
