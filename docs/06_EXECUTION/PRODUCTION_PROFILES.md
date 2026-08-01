# Production Profiles

> **Status: Available in ETLantic 0.41.0.**

ETLantic 0.41.0 treats production configuration as an explicit trust boundary
via `Profile.security_mode == "production"`. The built-in `production` profile
is a template, not a deployable setup.

## Built-in production fails closed

`production_profile()` sets `security_mode="production"`, strict validation,
and the `production` security domain label, but its `plugin_allowlist` and
`assets` are empty. Validation therefore emits `PMPLUG401` until the allowlist
is non-empty. Real pipelines also need their logical extract and load assets
resolved.

This command is **expected to fail** (empty allowlist → `PMPLUG401`, exit `11`).
Do not copy it into CI as a working gate — use an explicit JSON profile instead:

```bash
# Expected to FAIL: built-in production template has an empty plugin_allowlist
python -m etlantic validate package.pipeline:CustomerPipeline --profile production
```

## Write an explicit profile

Keep resolved secret values out of profile files. Use `SecretRef` when a
profile needs a secret reference.

```python
from etlantic import Profile
from etlantic.profile import write_profile

profile = Profile(
    name="customer-production",
    dataframe_engine="polars",
    security_mode="production",
    security_domain="production",
    validation_policy="strict",
    plugin_allowlist={
        "etlantic-polars": "==0.41.0",
    },
    assets={
        "customer_source": "json",
        "customer_sink": "json",
    },
    portable_transform_policy="require",
)
write_profile(profile, "profiles/customer-production.json")
```

## Fail-closed plugin trust

When `security_mode` is `production`, unknown plugins are rejected unless they
appear on `plugin_allowlist`. Names and `security_domain` alone do **not**
enable production fail-closed behavior.

## Legacy bindings

Prefer `assets` in profile JSON. Legacy `bindings`-only files fail closed with
`PMCFG111` unless `accept_legacy_bindings=True` / `--accept-legacy-bindings`.
Migrate with `etlantic profile migrate`.

See [Profiles](../05_PIPELINES/PROFILES.md) and
[Migration 0.20 → 0.21](../11_DEVELOPMENT/MIGRATION_0_20_TO_0_21.md).
