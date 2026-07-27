# Upgrade Hub

Upgrade between ETLantic 0.x releases using the guides below. Always pin core
and first-party plugins to the **same minor** after upgrading.

## Current target

**ETLantic 0.24.0** — choose your guide:

| From version | Ordered path to 0.24 |
|---|---|
| 0.23.x | [0.23 → 0.24](../11_DEVELOPMENT/MIGRATION_0_23_TO_0_24.md) |
| 0.22.x | [0.22 → 0.23](../11_DEVELOPMENT/MIGRATION_0_22_TO_0_23.md) → [0.23 → 0.24](../11_DEVELOPMENT/MIGRATION_0_23_TO_0_24.md) |
| 0.21.x | [0.21 → 0.22](../11_DEVELOPMENT/MIGRATION_0_21_TO_0_22.md) → 0.22→0.23 → 0.23→0.24 |
| 0.20.x | [0.20 → 0.21](../11_DEVELOPMENT/MIGRATION_0_20_TO_0_21.md) → then the 0.21 chain |
| 0.19.x | [0.19 → 0.20](../11_DEVELOPMENT/MIGRATION_0_19_TO_0_20.md) → then the 0.20 chain |
| 0.18.x | [0.18 → 0.19](../11_DEVELOPMENT/MIGRATION_0_18_TO_0_19.md) → then the 0.19 chain |
| 0.17.x | [0.17 → 0.18](../11_DEVELOPMENT/MIGRATION_0_17_TO_0_18.md) → then the 0.18 chain |
| ≤ 0.16 | Follow the [migration chain](#migration-chain-newest-first) oldest→newest until 0.24 |

### Breaking highlights on the way to 0.24

| Span | Watch for |
|---|---|
| 0.17 → 0.18 | Gate A interchange (`etlantic.interchange/1`) |
| 0.18 → 0.19 | Wire `schema` required; `security_mode`; fail-closed profiles |
| 0.19 → 0.20 | Production allowlist before plugin load; Safe I/O |
| 0.20 → 0.21 | Durable CLI workspace; `init` / `doctor`; assets vs bindings |
| 0.21 → 0.22 | Plugin SDK RC; curated `import etlantic as etl` facade |
| 0.22 → 0.23 | Resilience budgets; report persistence / retry diagnostics |
| 0.23 → 0.24 | `PipelineDefinition` / `etlantic.pipeline/1`; functional authoring; CLI JSON targets |

Regenerate reviewed plans after upgrades that change plan fingerprints or
interchange descriptors. Review [CHANGELOG](../CHANGELOG.md).

## Migration chain (newest first)

| From → To | Guide |
|---|---|
| 0.23 → 0.24 | [MIGRATION_0_23_TO_0_24](../11_DEVELOPMENT/MIGRATION_0_23_TO_0_24.md) |
| 0.22 → 0.23 | [MIGRATION_0_22_TO_0_23](../11_DEVELOPMENT/MIGRATION_0_22_TO_0_23.md) |
| 0.21 → 0.22 | [MIGRATION_0_21_TO_0_22](../11_DEVELOPMENT/MIGRATION_0_21_TO_0_22.md) |
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

## 0.22 configuration cheat sheet

| Change | Use instead |
|---|---|
| Broad root `from etlantic import …` specialist helpers | Prefer `import etlantic as etl` curated facade + lazy namespaces |
| Engine name frozensets as privilege allowlists | Capability-driven discovery / `PluginCapabilities` |
| Unversioned capability claims | `etlantic.capabilities/1` + implication rules |
| Private underscore conformance helpers | Public `etlantic.testing` suites only |
| Manual protocol pin guessing | `etlantic plugin compatibility` |

See [Migration 0.21 → 0.22](../11_DEVELOPMENT/MIGRATION_0_21_TO_0_22.md).

## 0.23 configuration cheat sheet

| Change | Use instead |
|---|---|
| Silent success when report persistence fails after publication | Inspect terminal report status; recover orphaned publications manually; expect `PMEXEC410` |
| Missing callable reader on storage bindings | Register reader or use supported binding; expect `PMEXEC412` |
| Ad hoc fault injection in production | `etlantic.testing.faults` only with `ETLANTIC_FAULT_INJECTION=1` or test contexts |
| Cross-engine interchange claims without evidence | Plan `evidence_refs` + runtime `interchange_evidence`; `reconcile_interchange_evidence` in tests |
| Unsafe SQL/file retry after partial write | Blocked at runtime with `PMEXEC501`; keep compile-time `PMORCH310` checks in CI |

See [Migration 0.22 → 0.23](../11_DEVELOPMENT/MIGRATION_0_22_TO_0_23.md).

## 0.24 configuration cheat sheet

| Change | Use instead |
|---|---|
| Class-only pipeline lifecycle | `PipelineDefinition` / `etlantic.authoring` functional builders and JSON |
| Plan JSON as authoring round-trip | Use `etlantic.pipeline/1`; keep `etlantic.plan/1` for resolved execution |
| GUI/service custom encoders | Public catalog, `EditCommand`, `etlantic.service.AuthoringService` |
| Optional HTTP reference | `pip install etlantic-fastapi==0.24.0` (not the 1.1 control plane) |

See [Migration 0.23 → 0.24](../11_DEVELOPMENT/MIGRATION_0_23_TO_0_24.md).

## Checklist

1. Pin `etlantic==X.Y.Z` and matching `etlantic-*==X.Y.Z` plugins
2. Read the migration guide for your from→to pair
3. Run `etlantic validate … --format sarif` in CI
4. Regenerate and re-review `etlantic plan … --format json`
5. Confirm production profiles set `security_mode="production"` and a non-empty `plugin_allowlist`
6. Run `etlantic plugin compatibility` for third-party plugins

## Related

- [Installation](INSTALLATION.md)
- [Capabilities](CAPABILITIES.md)
- [Optional packages](../10_REFERENCE/OPTIONAL_PACKAGES.md)
