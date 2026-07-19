# Upgrade Hub

Upgrade between ETLantic 0.x releases using the guides below. Always pin core
and first-party plugins to the **same minor** after upgrading.

## Current target

**ETLantic 0.18.0** — start with
[Migration 0.17 → 0.18](../11_DEVELOPMENT/MIGRATION_0_17_TO_0_18.md) if you are
on 0.17.x.

Regenerate reviewed plans after upgrades that change plan fingerprints or
interchange descriptors. Review
[CHANGELOG](https://github.com/eddiethedean/etlantic/blob/main/CHANGELOG.md).

## Migration chain (newest first)

| From → To | Guide |
|---|---|
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

## Checklist

1. Pin `etlantic==X.Y.Z` and matching `etlantic-*==X.Y.Z` plugins
2. Read the migration guide for your from→to pair
3. Run `etlantic validate … --format sarif` in CI
4. Regenerate and re-review `etlantic plan … --format json`
5. Confirm production profiles still set a non-empty `plugin_allowlist`

## Related

- [Installation](INSTALLATION.md)
- [Capabilities](CAPABILITIES.md)
- [Optional packages](../10_REFERENCE/OPTIONAL_PACKAGES.md)
