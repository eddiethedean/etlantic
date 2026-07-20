# Upgrade Hub

Upgrade between ETLantic 0.x releases using the guides below. Always pin core
and first-party plugins to the **same minor** after upgrading.

## Current target

**ETLantic 0.21.0** — choose your guide:

| Current version | Start here |
|---|---|
| 0.20.x | [Migration 0.20 → 0.21](../11_DEVELOPMENT/MIGRATION_0_20_TO_0_21.md) |
| 0.19.x | [Migration 0.19 → 0.20](../11_DEVELOPMENT/MIGRATION_0_19_TO_0_20.md), then [0.20 → 0.21](../11_DEVELOPMENT/MIGRATION_0_20_TO_0_21.md) |
| 0.18.x | [Migration 0.18 → 0.19](../11_DEVELOPMENT/MIGRATION_0_18_TO_0_19.md), then follow the chain to 0.21 |
| ≤ 0.17 | Follow the [migration chain](#migration-chain-newest-first) below |

Regenerate reviewed plans after upgrades that change plan fingerprints or
interchange descriptors. Review
[CHANGELOG](../CHANGELOG.md).

## Migration chain (newest first)

| From → To | Guide |
|---|---|
| 0.20 → 0.21 | [MIGRATION_0_20_TO_0_21](../11_DEVELOPMENT/MIGRATION_0_20_TO_0_21.md) |
| 0.19 → 0.20 | [MIGRATION_0_19_TO_0_20](../11_DEVELOPMENT/MIGRATION_0_19_TO_0_20.md) |
| 0.18 → 0.19 | [MIGRATION_0_18_TO_0_19](../11_DEVELOPMENT/MIGRATION_0_18_TO_0_19.md) |
| 0.17 → 0.18 | [MIGRATION_0_17_TO_0_18](../11_DEVELOPMENT/MIGRATION_0_17_TO_0_18.md) |
| 0.16 → 0.17 | [MIGRATION_0_16_TO_0_17](../11_DEVELOPMENT/MIGRATION_0_16_TO_0_17.md) |
| 0.15 → 0.16 | [MIGRATION_0_15_TO_0_16](../11_DEVELOPMENT/MIGRATION_0_15_TO_0_16.md) |
| 0.14 → 0.15 | [MIGRATION_0_14_TO_0_15](../11_DEVELOPMENT/MIGRATION_0_14_TO_0_15.md) |
| 0.13 → 0.14 | [MIGRATION_0_13_TO_0_14](../11_DEVELOPMENT/MIGRATION_0_13_TO_0_14.md) |
| Older | See [Migration archive](../11_DEVELOPMENT/README.md) under Project |

## Vocabulary cheat sheet (0.16+)

| Removed | Use instead |
|---|---|
| `Source[...]` | `Extract[...]` |
| `Sink[...]` | `Load[...]` |
| `binding=` on extract/load | `asset=` |
| `DataContractModel` as primary authoring | `Data` |

## 0.19 configuration cheat sheet

| Change | Use instead |
|---|---|
| Production detection by name/`security_domain` | `security_mode="production"` |
| Unknown bare profile names | Fail closed; `--allow-adhoc-profile` |
| Legacy profile JSON `bindings` only | Prefer `assets`; diagnosed `PMCFG110` |
| Missing plan/report `schema` | Required; no silent default |

## 0.20 configuration cheat sheet

| Change | Use instead |
|---|---|
| Plugin import before allowlist check | Allowlist evaluated **before** `ep.load()` in production |
| Implicit plugin trust | Ship `etlantic-plugin-manifest.json` (first-party included); required for `security_mode="production"` |
| Unrestricted outbound HTTP from transforms | Declare `Profile.outbound` with allowed schemes/hosts |
| Ad hoc artifact/cache paths | Regenerate plans; isolation dimensions added to identity strings |
| World-writable report/schema-history roots | Write through `SafeIoPolicy`; use intentional store directories |
| Plan fingerprint only at run time | Use `verify_plan_fingerprint` / compile-time checks where applicable |

See [Migration 0.19 → 0.20](../11_DEVELOPMENT/MIGRATION_0_19_TO_0_20.md) for examples and
[Security](../02_FOUNDATIONS/SECURITY.md) for the full trust model.

## 0.21 configuration cheat sheet

| Change | Use instead |
|---|---|
| Ephemeral-only report store | Default durable `.etlantic/reports` workspace; `--ephemeral` for process-local |
| Implicit project layout | Optional `etlantic.toml` + `profiles/`; `etlantic init` scaffolds |
| Legacy profile `bindings` | Structured `assets` descriptors; `--accept-legacy-bindings` for migration only |
| Ad hoc profile JSON paths | `etlantic profile validate/show/diff/migrate` |
| `reliability plan-diff` | `etlantic plan diff` |
| Human-only plan explain | `etlantic plan explain --format human` |

See [Migration 0.20 → 0.21](../11_DEVELOPMENT/MIGRATION_0_20_TO_0_21.md) for CLI and workspace details.

## Checklist

1. Pin `etlantic==X.Y.Z` and matching `etlantic-*==X.Y.Z` plugins
2. Read the migration guide for your from→to pair
3. Run `etlantic validate … --format sarif` in CI
4. Regenerate and re-review `etlantic plan … --format json`
5. Confirm production profiles set `security_mode="production"` and a non-empty `plugin_allowlist`

## Related

- [Installation](INSTALLATION.md)
- [Capabilities](CAPABILITIES.md)
- [Optional packages](../10_REFERENCE/OPTIONAL_PACKAGES.md)
