# Upgrade Hub

> **Status: Available in ETLantic 0.44.0.**

!!! warning "Upgraders only"
    New users: start at the [docs home green path](../README.md) or
    [Quickstart](QUICKSTART.md). This page is for migrating between minors.

Upgrade between ETLantic 0.x releases using the guides below. Always pin core
and first-party plugins to the **same minor** after upgrading.

Historical release notes: [Earlier releases](EARLIER_RELEASES.md).

## Current target

**ETLantic 0.44.0** — choose your guide:

| From version | Ordered path to 0.44 |
|---|---|
| 0.44.x | Already current |
| 0.43.x | [0.43 → 0.44](../11_DEVELOPMENT/MIGRATION_0_43_TO_0_44.md) |
| 0.42.x | [0.42 → 0.43](../11_DEVELOPMENT/MIGRATION_0_42_TO_0_43.md) → [0.43 → 0.44](../11_DEVELOPMENT/MIGRATION_0_43_TO_0_44.md) |
| 0.41.x | [0.41 → 0.42](../11_DEVELOPMENT/MIGRATION_0_41_TO_0_42.md) → [0.42 → 0.43](../11_DEVELOPMENT/MIGRATION_0_42_TO_0_43.md) → [0.43 → 0.44](../11_DEVELOPMENT/MIGRATION_0_43_TO_0_44.md) |
| 0.40.x | [0.40 → 0.41](../11_DEVELOPMENT/MIGRATION_0_40_TO_0_41.md) → [0.41 → 0.42](../11_DEVELOPMENT/MIGRATION_0_41_TO_0_42.md) → [0.42 → 0.43](../11_DEVELOPMENT/MIGRATION_0_42_TO_0_43.md) → [0.43 → 0.44](../11_DEVELOPMENT/MIGRATION_0_43_TO_0_44.md) |
| 0.39.x | [0.39 → 0.40](../11_DEVELOPMENT/MIGRATION_0_39_TO_0_40.md) |
| 0.38.x | [0.38 → 0.39](../11_DEVELOPMENT/MIGRATION_0_38_TO_0_39.md) → [0.39 → 0.40](../11_DEVELOPMENT/MIGRATION_0_39_TO_0_40.md) |
| 0.37.x | [0.37 → 0.38](../11_DEVELOPMENT/MIGRATION_0_37_TO_0_38.md) → [0.38 → 0.39](../11_DEVELOPMENT/MIGRATION_0_38_TO_0_39.md) → [0.39 → 0.40](../11_DEVELOPMENT/MIGRATION_0_39_TO_0_40.md) |
| 0.36.x | [0.36 → 0.37](../11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md) → [0.37 → 0.38](../11_DEVELOPMENT/MIGRATION_0_37_TO_0_38.md) → [0.38 → 0.39](../11_DEVELOPMENT/MIGRATION_0_38_TO_0_39.md) → [0.39 → 0.40](../11_DEVELOPMENT/MIGRATION_0_39_TO_0_40.md) |
| 0.35.x | [0.35 → 0.36](../11_DEVELOPMENT/MIGRATION_0_35_TO_0_36.md) → then the 0.36 chain above |
| 0.34.x | [0.34 → 0.35](../11_DEVELOPMENT/MIGRATION_0_34_TO_0_35.md) → then the 0.35 chain above |
| 0.33.x | [0.33 → 0.34](../11_DEVELOPMENT/MIGRATION_0_33_TO_0_34.md) → then the 0.34 chain above |
| 0.32.x | [0.32 → 0.33](../11_DEVELOPMENT/MIGRATION_0_32_TO_0_33.md) → then the 0.33 chain |
| 0.31.x | [0.31 → 0.32](../11_DEVELOPMENT/MIGRATION_0_31_TO_0_32.md) → then the 0.32 chain |
| 0.30.x | [0.30 → 0.31](../11_DEVELOPMENT/MIGRATION_0_30_TO_0_31.md) → then follow the newer rows above |
| 0.29.x | [0.29 → 0.30](../11_DEVELOPMENT/MIGRATION_0_29_TO_0_30.md) → then follow the newer rows above |
| 0.28.x | [0.28 → 0.29](../11_DEVELOPMENT/MIGRATION_0_28_TO_0_29.md) → then follow the newer rows above |
| 0.27.x | [0.27 → 0.28](../11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md) → then follow the newer rows above |
| 0.26.x | [0.26 → 0.27](../11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md) → then follow the newer rows above |
| 0.25.x | [0.25 → 0.26](../11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md) → then follow the newer rows above |
| 0.24.x | [0.24 → 0.25](../11_DEVELOPMENT/MIGRATION_0_24_TO_0_25.md) → then follow the newer rows above |
| 0.23.x | [0.23 → 0.24](../11_DEVELOPMENT/MIGRATION_0_23_TO_0_24.md) → then follow the newer rows above |
| 0.22.x | [0.22 → 0.23](../11_DEVELOPMENT/MIGRATION_0_22_TO_0_23.md) → then follow the newer rows above |
| 0.21.x | [0.21 → 0.22](../11_DEVELOPMENT/MIGRATION_0_21_TO_0_22.md) → then follow the newer rows above |
| 0.20.x | [0.20 → 0.21](../11_DEVELOPMENT/MIGRATION_0_20_TO_0_21.md) → then follow the newer rows above |
| 0.19.x | [0.19 → 0.20](../11_DEVELOPMENT/MIGRATION_0_19_TO_0_20.md) → then follow the newer rows above |
| 0.18.x | [0.18 → 0.19](../11_DEVELOPMENT/MIGRATION_0_18_TO_0_19.md) → then follow the newer rows above |
| 0.17.x | [0.17 → 0.18](../11_DEVELOPMENT/MIGRATION_0_17_TO_0_18.md) → then follow the newer rows above |
| ≤ 0.16 | Follow the [migration chain](#migration-chain-newest-first) oldest→newest until 0.40 |

### Breaking highlights on the way to 0.40

| Span | Watch for |
|---|---|
| 0.17 → 0.18 | Gate A interchange (`etlantic.interchange/1`) |
| 0.18 → 0.19 | Wire `schema` required; `security_mode`; fail-closed profiles |
| 0.19 → 0.20 | Production allowlist before plugin load; Safe I/O |
| 0.20 → 0.21 | Durable CLI workspace; `init` / `doctor`; assets vs bindings |
| 0.21 → 0.22 | Plugin SDK RC; curated `import etlantic as etl` facade |
| 0.22 → 0.23 | Resilience budgets; report persistence / retry diagnostics |
| 0.23 → 0.24 | `PipelineDefinition` / `etlantic.pipeline/1`; functional authoring; CLI JSON targets |
| 0.24 → 0.25 | Compatibility burn-in fixtures; no wire-schema reset; freeze blockers published |
| 0.25 → 0.26 | Dual-minor burn-in; first-wave root alias removals; freeze owned by 0.27 |
| 0.26 → 0.27 | Triple-minor burn-in; second-wave root removals; freeze re-scoped to 0.28+ |
| 0.27 → 0.28 | Quadruple-minor burn-in; third-wave root removals; Plugin `/1` **frozen** |
| 0.28 → 0.29 | Native MedallionPipeline authoring (M1); facade conformance kit |
| 0.29 → 0.30 | Portable quality AST + Medallantic `rules=` → quality gates (M2) |
| 0.30 → 0.31 | Execution / state / materialization (M3) |
| 0.31 → 0.32 | PySpark / Delta differential parity (M4) |
| 0.32 → 0.33 | SQLAlchemy / relational differential parity (M5) |
| 0.33 → 0.34 | Observability providers, durable run history, event consumers, and production conformance (M6) |
| 0.34 → 0.35 | Migration completion / joint freeze (M7); testing preview; pin floor `<0.36` |
| 0.35 → 0.36 | Joint compatibility burn-in; bare report metadata → namespaced; pin floor `<0.37` |
| 0.36 → 0.37 | Stable-foundation line; plugin floor `etlantic>=0.37.0,<0.38` |
| 0.37 → 0.38 | Connectivity / connector SDK; plugin floor `etlantic>=0.38.0,<0.39` |
| 0.38 → 0.39 | CP1 control-plane incubation; plugin floor `etlantic>=0.39.0,<0.40` |
| 0.39 → 0.40 | CP2 registry / persistence; plugin floor `etlantic>=0.40.0,<0.41` |
| 0.40 → 0.41 | CP3 durable work; plugin floor `etlantic>=0.41.0,<0.42` |
| 0.43 → 0.44 | Developer Intelligence (LSP / IDE / notebooks); plugin floor `etlantic>=0.44.0,<0.45` |
| 0.42 → 0.43 | CP-GA Supported-profile multi-tenant (published Beta; community non-SLA); plugin floor `etlantic>=0.43.0,<0.44` |
| 0.41 → 0.42 | CP4 policy / quotas / audit (published Beta); plugin floor `etlantic>=0.42.0,<0.43` |

Regenerate reviewed plans after upgrades that change plan fingerprints or
interchange descriptors. Review [CHANGELOG](../CHANGELOG.md).

## Migration chain (newest first)

| From → To | Guide |
|---|---|
| 0.41 → 0.42 | [MIGRATION_0_41_TO_0_42](../11_DEVELOPMENT/MIGRATION_0_41_TO_0_42.md) |
| 0.40 → 0.41 | [MIGRATION_0_40_TO_0_41](../11_DEVELOPMENT/MIGRATION_0_40_TO_0_41.md) |
| 0.39 → 0.40 | [MIGRATION_0_39_TO_0_40](../11_DEVELOPMENT/MIGRATION_0_39_TO_0_40.md) |
| 0.38 → 0.39 | [MIGRATION_0_38_TO_0_39](../11_DEVELOPMENT/MIGRATION_0_38_TO_0_39.md) |
| 0.37 → 0.38 | [MIGRATION_0_37_TO_0_38](../11_DEVELOPMENT/MIGRATION_0_37_TO_0_38.md) |
| 0.36 → 0.37 | [MIGRATION_0_36_TO_0_37](../11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md) |
| 0.35 → 0.36 | [MIGRATION_0_35_TO_0_36](../11_DEVELOPMENT/MIGRATION_0_35_TO_0_36.md) |
| 0.34 → 0.35 | [MIGRATION_0_34_TO_0_35](../11_DEVELOPMENT/MIGRATION_0_34_TO_0_35.md) |
| 0.33 → 0.34 | [MIGRATION_0_33_TO_0_34](../11_DEVELOPMENT/MIGRATION_0_33_TO_0_34.md) |
| 0.32 → 0.33 | [MIGRATION_0_32_TO_0_33](../11_DEVELOPMENT/MIGRATION_0_32_TO_0_33.md) |
| 0.31 → 0.32 | [MIGRATION_0_31_TO_0_32](../11_DEVELOPMENT/MIGRATION_0_31_TO_0_32.md) |
| 0.30 → 0.31 | [MIGRATION_0_30_TO_0_31](../11_DEVELOPMENT/MIGRATION_0_30_TO_0_31.md) |
| 0.29 → 0.30 | [MIGRATION_0_29_TO_0_30](../11_DEVELOPMENT/MIGRATION_0_29_TO_0_30.md) |
| 0.28 → 0.29 | [MIGRATION_0_28_TO_0_29](../11_DEVELOPMENT/MIGRATION_0_28_TO_0_29.md) |
| 0.27 → 0.28 | [MIGRATION_0_27_TO_0_28](../11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md) |
| 0.26 → 0.27 | [MIGRATION_0_26_TO_0_27](../11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md) |
| 0.25 → 0.26 | [MIGRATION_0_25_TO_0_26](../11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md) |
| 0.24 → 0.25 | [MIGRATION_0_24_TO_0_25](../11_DEVELOPMENT/MIGRATION_0_24_TO_0_25.md) |
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
| Missing callable reader on storage bindings | Register reader or use supported binding; expect `PMEXEC416` |
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
| Optional HTTP reference | `pip install etlantic-fastapi` matching the core minor (not the 0.39–0.43 control plane) |

See [Migration 0.23 → 0.24](../11_DEVELOPMENT/MIGRATION_0_23_TO_0_24.md).

## 0.25 configuration cheat sheet

| Change | Use instead |
|---|---|
| Assume Plugin SDK `/1` is frozen | Still freeze-eligible; blockers published — see Protocol evolution |
| Skip codec upgrade tests | Keep `tests/fixtures/burn_in/` green; run `check_pipeline_codec_burn_in.py` |
| Add new root demoted aliases | Prefer owning modules; see [Removal candidates](../11_DEVELOPMENT/REMOVAL_CANDIDATES_0_37.md) |
| Expect wire-schema reset | Stay on `/1` ids; no `pipeline/2` in 0.25 |

See [Migration 0.24 → 0.25](../11_DEVELOPMENT/MIGRATION_0_24_TO_0_25.md) and
[Wire schema ranges](../10_REFERENCE/WIRE_SCHEMA_RANGES.md).

## 0.26 configuration cheat sheet

| Change | Use instead |
|---|---|
| `from etlantic import ETLanticError`, storage, runtime, interchange helpers | Owning modules — see [Migration 0.25 → 0.26](../11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md) |
| Assume Plugin SDK `/1` is frozen | Still freeze-eligible; closure owned by **0.27** at ship time (later re-scoped to 0.28+) |
| Skip dual-minor burn-in gates | Keep `v0_24/` and `v0_25/` fixtures green |
| Expect wire-schema reset | Stay on `/1` ids; no `pipeline/2` in 0.26 |

See [Migration 0.25 → 0.26](../11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md).

## 0.27 configuration cheat sheet

| Change | Use instead |
|---|---|
| `from etlantic import` reliability / schema_drift / registry helpers | Owning modules — see [Migration 0.26 → 0.27](../11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md) |
| Assume Plugin SDK `/1` is frozen | Still freeze-eligible; closure re-scoped to **0.28+** |
| Skip triple-minor burn-in gates | Keep `v0_24/`, `v0_25/`, and `v0_26/` fixtures green |
| Expect wire-schema reset | Stay on `/1` ids; no `pipeline/2` in 0.27 |

See [Migration 0.26 → 0.27](../11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md).

## 0.28 configuration cheat sheet

| Change | Use instead |
|---|---|
| Plugin SDK `/1` | **Frozen** in 0.28 — only additive optional evolution within `/1` |
| `from etlantic import col`, `load_profile`, `Inject`, … | Owning modules — see [Migration 0.27 → 0.28](../11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md) |
| `etlantic-sparkforge` | `medallantic` (optional redirect wheel `etlantic-sparkforge==0.42.0`) |
| Skip quadruple-minor burn-in gates | Keep `v0_24/` through `v0_27/` fixtures green |
| Expect wire-schema reset | Stay on `/1` ids; no `pipeline/2` in 0.28 |

See [Migration 0.27 → 0.28](../11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md).

## 0.29 configuration cheat sheet

| Change | Use instead |
|---|---|
| New medallion pipelines | `MedallionPipeline` / `MedallionBuilder` (native M1) |
| SparkForge IR migrate | `medallantic.migrate.sparkforge` (top-level `adapt_*` still works) |
| Facade conformance | `etlantic.testing.run_facade_conformance_suite` |
| Expect portable rule DSL | Deferred to **0.30 / M2** |
| Expect wire-schema reset | Stay on `/1` ids; no `pipeline/2` in 0.29 |

See [Migration 0.28 → 0.29](../11_DEVELOPMENT/MIGRATION_0_28_TO_0_29.md).

## 0.30 configuration cheat sheet

| Change | Use instead |
|---|---|
| Medallantic `rules=` passthrough | Portable quality gates (`make_quality_gate` / `etlantic.quality`) |
| Uneexecuted bronze `rules=` | Expect `{step}__ingest` + gate nodes when rules are present |
| Engines without `quality.*` caps | Fail closed at plan (`PMPLAN420` / `PMPLAN421`); prefer Polars/Pandas |
| Quality AST helpers | `etlantic.quality` / `etl.quality` (provisional `etlantic.quality/1`) |
| Expect wire-schema reset | Stay on `/1` ids; no `pipeline/2` in 0.30 |

See [Migration 0.29 → 0.30](../11_DEVELOPMENT/MIGRATION_0_29_TO_0_30.md).

## 0.31 configuration cheat sheet

| Change | Use instead |
|---|---|
| Incremental / state runs | `IncrementalStrategy` + `StateStore` |
| Skip-if-exists writes | `WriteMode.SKIP_IF_EXISTS` / Medallantic `skip`/`ignore` |
| Live transform refs | `medallantic.callables` |
| Expect wire-schema reset | Stay on `/1` ids; no `pipeline/2` in 0.31 |

See [Migration 0.30 → 0.31](../11_DEVELOPMENT/MIGRATION_0_30_TO_0_31.md).


## 0.44 configuration cheat sheet

| Do | Don't |
|---|---|
| Pin `etlantic==0.44.0` and matching plugins / `medallantic==0.44.0` | Mix 0.43 plugins with a 0.44 core |
| Install `etlantic[lsp]` for the language server; configure editors to launch `etlantic-lsp` | Import untrusted project modules during default analysis |
| Use `etlantic watch` / IDE validate for static feedback; never auto-execute from watch | Treat VS Code CodeLens as a second execution authority |
| Keep trusted-workspace opt-in explicit, timed out, and audited | Resolve secrets or query live production schemas from analysis hosts |
| Use notebook displays without side effects; mark stale plans after cell redefines | Embed subject values in erasure/objective previews |

See [Migration 0.43 → 0.44](../11_DEVELOPMENT/MIGRATION_0_43_TO_0_44.md).

## 0.43 configuration cheat sheet

| Do | Don't |
|---|---|
| Pin `etlantic==0.43.0` and matching plugins / `medallantic==0.43.0` | Mix 0.42 plugins with a 0.43 core |
| Use Supported isolation profiles (`isolated-deployment`, `dedicated-schema`) for production multi-tenant | Claim production isolation for `shared-service` without real RLS / credentials |
| Treat capacity numbers as measured envelopes (community **non-SLA**) | Invent enterprise SLA or unbounded scale claims |
| Keep report/lineage/reliability FastAPI stubs Experimental | Treat stub empty payloads as authority |
| Apply SQLModel migrations through `003_cp4_governance`; treat snapshots as canonical restore | Skip migrations or treat entity mirrors as sole authority |
| Run CP-GA campaigns / matrices before claiming GA cells | Soft-allow cross-tenant misses or provider outages |

See [Migration 0.42 → 0.43](../11_DEVELOPMENT/MIGRATION_0_42_TO_0_43.md).

## 0.42 configuration cheat sheet

| Do | Don't |
|---|---|
| Pin `etlantic==0.42.0` and matching plugins / `medallantic==0.42.0` | Mix 0.41 plugins with a 0.42 core |
| Inject CP4 providers (`policy`, `approvals`, `quotas`, `audit`, …) when hosting protected ops | Rely on ambient process state for policy decisions |
| Apply SQLModel migration `003_cp4_governance` with prior durable migrations | Skip migration when using SQLModel CP4 stores |
| Fail closed on policy/quota/identity outage for protected ops | Soft-allow on provider outage |
| Keep subject values out of erasure plans, reports, and audit | Embed PII or secret values in durable/audit records |
| Read release notes: CP4 ≠ production multi-tenant | Claim production multi-tenant isolation before **0.43** |

See [Migration 0.41 → 0.42](../11_DEVELOPMENT/MIGRATION_0_41_TO_0_42.md).

## 0.41 configuration cheat sheet

| Do | Don't |
|---|---|
| Pin `etlantic==0.41.0` and matching plugins / `medallantic==0.41.0` | Mix 0.40 plugins with a 0.41 core |
| Inject optional `DurableWorkStore` for CP3 accept/outbox/leases | Expect core to embed a broker or worker supervisor |
| Apply SQLModel migrations `001` + `002` when using durable persistence | Rely on `create_all` alone in production |
| Fail closed on unknown effects and stale fencing tokens | Auto-retry unknown side effects without reconciliation |
| Treat preview/shadow runs as non-authority | Promote shadow effects as production authority |
| Read release notes: CP3 ≠ production multi-tenant | Claim production multi-tenant isolation before **0.43** |

See [Migration 0.40 → 0.41](../11_DEVELOPMENT/MIGRATION_0_40_TO_0_41.md).

## 0.40 configuration cheat sheet

| Do | Don't |
|---|---|
| Pin `etlantic==0.40.0` and matching plugins / `medallantic==0.40.0` | Mix 0.39 plugins with a 0.40 core |
| Prefer `RegistryProvider` for directory/revision access | Mutate revisions in place or treat dicts as multi-worker storage |
| Apply SQLModel registry migrations when using optional persistence | Rely on `create_all` alone in production |
| Treat OpenLineage export as outbound non-authority | Let transport ACKs mutate registry / promotions |
| Read release notes: CP2 ≠ production multi-tenant | Claim production multi-tenant isolation before **0.43** |

See [Migration 0.39 → 0.40](../11_DEVELOPMENT/MIGRATION_0_39_TO_0_40.md).

## 0.39 configuration cheat sheet

| Do | Don't |
|---|---|
| Pin `etlantic==0.39.0` and matching plugins / `medallantic==0.39.0` | Mix 0.38 plugins with a 0.39 core |
| Prefer `ETLanticAPI` / `include_router` for CP1 HTTP embeds | Treat `create_reference_app` as durable multi-tenant isolation |
| Keep FastAPI / SQLModel optional extras | Assume `import etlantic` pulls FastAPI |
| Treat path/header tenant ids as routing only | Use path claims as authorization authority |
| Use landing-zone submitters outside core | Embed file bytes in plans or submit bodies |
| Read release notes: CP1 ≠ production multi-tenant | Claim production multi-tenant isolation before **0.43** |

See [Migration 0.38 → 0.39](../11_DEVELOPMENT/MIGRATION_0_38_TO_0_39.md).

## 0.38 configuration cheat sheet

| Do | Don't |
|---|---|
| Pin `etlantic==0.38.0` and matching plugins / `medallantic==0.38.0` | Mix 0.37 plugins with an older core |
| Use non-empty version pins in production `plugin_allowlist` | Use `null` / empty pins (fail closed in 0.38) |
| Re-validate / re-plan after the pin bump | Assume plans from 0.35 remain bit-identical without checking |
| Expect bare report metadata keys to rewrite to namespaced keys | Leave unresolved secrets or bare secret-like keys in reports |
| Expect soft-continued runs (`CONTINUE`) to report `PARTIAL` | Treat soft-skips as overall `SUCCEEDED` / exit 0 |
| Keep transitional adapters until a major | Expect adapter removal in a major |
| Treat `etlantic.testing` burn-in helpers per What's New / exit gate | Confirm testing-foundation graduation status in Exit Gate 0.38 |

See [Migration 0.37 → 0.38](../11_DEVELOPMENT/MIGRATION_0_37_TO_0_38.md).

## 0.35 configuration cheat sheet

| Do | Don't |
|---|---|
| Pin `etlantic==0.35.0` and matching plugins | Mix 0.35 plugins with an older core |
| Re-validate / re-plan after the pin bump | Assume plans from 0.34 remain bit-identical without checking |
| Use Medallantic inventory before converting SparkForge projects | Import untrusted project code during analysis |
| Keep transitional adapters until a major | Expect adapter removal in 0.35 |

See [Migration 0.34 → 0.35](../11_DEVELOPMENT/MIGRATION_0_34_TO_0_35.md).

## 0.34 configuration cheat sheet

| Do | Don't |
|---|---|
| Pin `etlantic==0.34.0` and matching plugins | Mix 0.34 plugins with an older core |
| Configure observability and run-history providers explicitly | Treat provider delivery as pipeline semantics |
| Use `durable_audit` only with durable history and successful flush | Silently degrade a required audit delivery failure |
| Keep wire schemas on their existing `/1` identifiers | Expect a wire-schema reset |

See [Migration 0.33 → 0.34](../11_DEVELOPMENT/MIGRATION_0_33_TO_0_34.md).

## 0.33 configuration cheat sheet

| Do | Don't |
|---|---|
| Pin `etlantic==0.33.0` and matching plugins | Mix 0.33 plugins with 0.32 (or other) core |
| Use PostgreSQL when requiring `sql_merge` | Expect SQLite to advertise merge |
| Prefer `medallantic.migrate.sql.from_sql_pipeline_builder` | Embed secrets in builder metadata |
| Expect wire-schema stay on `/1` ids | Expect `pipeline/2` in 0.33 |

See [Migration 0.32 → 0.33](../11_DEVELOPMENT/MIGRATION_0_32_TO_0_33.md).

## 0.32 configuration cheat sheet

| Change | Use instead |
|---|---|
| Coarse `spark_delta` for maintenance | Fine-grained `storage.delta.*` extras |
| SparkForge live migration | `medallantic.migrate.sparkforge.from_pipeline_builder` |
| Native Column rules | Plugin-native `quality.pyspark_column` (not portable AST) |
| Expect wire-schema reset | Stay on `/1` ids; no `pipeline/2` in 0.32 |

See [Migration 0.31 → 0.32](../11_DEVELOPMENT/MIGRATION_0_31_TO_0_32.md).

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
