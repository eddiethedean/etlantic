# Production Profiles

ETLantic 0.21.0 treats production configuration as an explicit trust boundary
via `Profile.security_mode == "production"`. The built-in `production` profile
is a template, not a deployable setup.

## Built-in production fails closed

`production_profile()` sets `security_mode="production"`, strict validation,
and the `production` security domain label, but its `plugin_allowlist` and
`assets` are empty. Validation therefore emits `PMPLUG401` until the allowlist
is non-empty. Real pipelines also need their logical extract and load assets
resolved.

This command is expected to fail for a pipeline that needs production
configuration:

```bash
etlantic validate package.pipeline:CustomerPipeline --profile production
```

## Write an explicit profile

Keep resolved secret values out of profile files. Use `SecretRef` when a
profile needs a secret reference.

```python
from etlantic import Profile, write_profile

profile = Profile(
    name="customer-production",
    dataframe_engine="polars",
    security_mode="production",
    security_domain="production",
    validation_policy="strict",
    plugin_allowlist={
        "etlantic-polars": "==0.21.0",
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

Prefer `assets` in profile JSON. Legacy `bindings`-only files load with
warning `PMCFG110`. Use `Profile.from_dict(..., accept_legacy_bindings=False)`
in CI to fail closed.

See [Profiles](../05_PIPELINES/PROFILES.md) and
[Migration 0.18 → 0.19](../11_DEVELOPMENT/MIGRATION_0_18_TO_0_19.md).
