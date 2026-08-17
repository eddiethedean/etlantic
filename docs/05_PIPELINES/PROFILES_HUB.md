# Profiles hub

> **Status: Available in ETLantic 0.47.0.** Start here for environment,
> allowlist, and production trust. Detail pages remain authoritative.

## Read in this order

1. [Profile primer](PROFILE_PRIMER.md) — what a profile is and why it matters
2. [Profiles](PROFILES.md) — fields, resolution, JSON shape
3. [Production profiles](../06_EXECUTION/PRODUCTION_PROFILES.md) — fail-closed allowlist and pilot checklist
4. [Runtime configuration](../10_REFERENCE/RUNTIME_CONFIGURATION.md) — CLI / env / `etlantic.toml` today
5. [Configuration today](../10_REFERENCE/CONFIGURATION_TODAY.md) — shipped Profile / toml fields vs future design

## Essentials

- Prefer named profiles (`development`, `test`, `production`).
- Production fail-closed plugin trust uses **`Profile.security_mode`** (not name alone).
- Production profiles require a non-empty `plugin_allowlist`.
- Keep plugin package versions on the **same minor** as core (`==0.47.0`).
- Prefer `python -m etlantic … --profile <name>` for validate / plan / run.

## Related

- [Security howto](../01_GETTING_STARTED/SECURITY_HOWTO.md)
- [Security model](../02_FOUNDATIONS/SECURITY.md)
- [Production readiness](../06_EXECUTION/PRODUCTION_READINESS.md)
