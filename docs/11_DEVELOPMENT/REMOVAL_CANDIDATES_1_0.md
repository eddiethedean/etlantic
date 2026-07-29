# 1.0 Removal Candidates (inventory)

> **Status: Available in ETLantic 0.33.0.** First-wave removals executed in
> 0.26.0; second-wave removals executed in 0.27.0; third-wave removals executed
> in 0.28.0; remaining inventory continues toward 1.0. See
> [Migration 0.26 → 0.27](MIGRATION_0_26_TO_0_27.md) and
> [Migration 0.27 → 0.28](MIGRATION_0_27_TO_0_28.md).

## Process guard (0.25+)

- Do **not** add new indefinite keep-forever root aliases in 0.25+ PRs.
- New public symbols belong on owning modules or the curated root facade
  (`_CURATED` in `src/etlantic/__init__.py`), not `_DEMOTED_ALIASES`.
- Removals require changelog + migration note + tests (see deprecation policy).

## Candidate groups

| ID | Candidates | Owning modules | Target | Migration note |
|---|---|---|---|---|
| `REM-ROOT-DEMOTED` | warn-once root aliases in `_DEMOTED_ALIASES` | various | first wave 0.26.0; second wave **removed 0.27.0** (schema_drift + registry); third wave **removed 0.28.0** (sql/profile/lifecycle); complete by 1.0 | Prefer owning imports. ~36 remain demoted after 0.28.0. |
| `REM-DATACONTRACTMODEL` | `DataContractModel` provisional alias | `etlantic.contracts` | hard-error or remove by 1.0 | Use ContractModel / `Data` per current contracts docs. |
| `REM-EXCEPTIONS-ROOT` | Exception types on root | `etlantic.exceptions` | **removed 0.26.0** | `from etlantic.exceptions import …` |
| `REM-PROTOCOL-CONSTS` | `*_PROTOCOL_VERSION`, `STREAMING_STABILITY`, `PLUGIN_MANIFEST_SCHEMA` | dataframe / sql / spark / orchestration / plugin_manifest | **removed 0.26.0** | Import from owning protocol modules. |
| `REM-STORAGE-ROOT` | `MemoryStorage`, `JsonStorage`, `CsvStorage`, `CallableStorage`, `NullStorage` | `etlantic.storage` | **removed 0.26.0** | `from etlantic.storage import …` |
| `REM-RUNTIME-ROOT` | `RunIntent`, `RunRequest`, `RunSelection`, `RunStatus`, `DebugSession`, `MaterializationPolicy` | `etlantic.runtime` | **removed 0.26.0** | Prefer runtime / lifecycle namespaces. |
| `REM-RELIABILITY-ROOT` | Reliability declaration types | `etlantic.reliability` | **removed 0.27.0** | Prefer `etlantic.reliability`. |
| `REM-INTERCHANGE-ROOT` | Interchange / provenance helpers | `etlantic.interchange` | **removed 0.26.0** | Prefer `etlantic.interchange`. |
| `REM-EXPERIMENTAL` | Structured Streaming APIs; `etlantic-datafusion` | spark / datafusion | graduate or remain experimental at 1.0 | See Capabilities / Compatibility. |
| `REM-PREFECT-MVP` | Prefect scheduler MVP surface | `etlantic-prefect` | expand or freeze protocol by 1.0 | See Deployment / Prefect docs. |

Ticket placeholders (track in GitHub issues when executing waves):

- `ETLANTIC-1.0-REM-ROOT-DEMOTED`
- `ETLANTIC-1.0-REM-DATACONTRACTMODEL`
- `ETLANTIC-1.0-REM-EXPERIMENTAL`

## Demoted root alias count (0.28 snapshot)

Live counts from `src/etlantic/__init__.py` `_DEMOTED_ALIASES` after 0.28
third-wave removals (~36 remaining):

| Owning module | Approx. aliases | Target |
|---|---|---|
| `etlantic.dataframe` / `spark` / `diagnostics` / `model` | 4 each | 0.29+ |
| `etlantic.plan`, `schema_policy`, `transformation`, `contracts`, `capabilities` | 2 each | 0.29+ |
| Other singleton modules | remainder | 0.29+ |

**Removed in 0.28.0** (third wave): all `etlantic.sql` (6), `etlantic.profile`
(6), and `etlantic.lifecycle` (5) demoted root aliases — see
[MIGRATION_0_27_TO_0_28](MIGRATION_0_27_TO_0_28.md).

Exact symbols remain in source; this inventory is the authoritative **removal
planning** document for burn-in. Executing removals updates this table's Target
column and CHANGELOG.

## Out of scope for removal inventory

- Curated root symbols (`Data`, `Pipeline`, `Transformation`, …) — stable
- Lazy namespaces (`etl.dataframe`, `etl.authoring`, …) — stable
- Versioned wire schemas (`etlantic.pipeline/1`, …) — evolve via schema policy, not this list
