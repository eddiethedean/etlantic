# 1.0 Removal Candidates (inventory)

> **Status: Available in ETLantic 0.26.0.** First-wave removals executed in
> 0.26.0; remaining inventory continues toward 1.0. See
> [Migration 0.25 → 0.26](MIGRATION_0_25_TO_0_26.md).

## Process guard (0.25+)

- Do **not** add new indefinite keep-forever root aliases in 0.25 PRs.
- New public symbols belong on owning modules or the curated root facade
  (`_CURATED` in `src/etlantic/__init__.py`), not `_DEMOTED_ALIASES`.
- Removals require changelog + migration note + tests (see deprecation policy).

## Candidate groups

| ID | Candidates | Owning modules | Target | Migration note |
|---|---|---|---|---|
| `REM-ROOT-DEMOTED` | ~116 warn-once root aliases in `_DEMOTED_ALIASES` | various (see below) | first wave removed 0.26.0; **second wave planned 0.27**; complete by 1.0 | Prefer owning imports. 37 high-traffic symbols removed in 0.26.0; ~79 remain demoted. |
| `REM-DATACONTRACTMODEL` | `DataContractModel` provisional alias | `etlantic.contracts` | hard-error or remove by 1.0 | Use ContractModel / `Data` per current contracts docs. |
| `REM-EXCEPTIONS-ROOT` | Exception types on root | `etlantic.exceptions` | **removed 0.26.0** | `from etlantic.exceptions import …` |
| `REM-PROTOCOL-CONSTS` | `*_PROTOCOL_VERSION`, `STREAMING_STABILITY`, `PLUGIN_MANIFEST_SCHEMA` | dataframe / sql / spark / orchestration / plugin_manifest | **removed 0.26.0** | Import from owning protocol modules. |
| `REM-STORAGE-ROOT` | `MemoryStorage`, `JsonStorage`, `CsvStorage`, `CallableStorage`, `NullStorage` | `etlantic.storage` | **removed 0.26.0** | `from etlantic.storage import …` |
| `REM-RUNTIME-ROOT` | `RunIntent`, `RunRequest`, `RunSelection`, `RunStatus`, `DebugSession`, `MaterializationPolicy` | `etlantic.runtime` | **removed 0.26.0** | Prefer runtime / lifecycle namespaces. |
| `REM-RELIABILITY-ROOT` | Reliability declaration types | `etlantic.reliability` | **planned 0.27** | Prefer `etlantic.reliability`. |
| `REM-INTERCHANGE-ROOT` | Interchange / provenance helpers | `etlantic.interchange` | **removed 0.26.0** | Prefer `etlantic.interchange`. |
| `REM-EXPERIMENTAL` | Structured Streaming APIs; `etlantic-datafusion` | spark / datafusion | graduate or remain experimental at 1.0 | See Capabilities / Compatibility. |
| `REM-PREFECT-MVP` | Prefect scheduler MVP surface | `etlantic-prefect` | expand or freeze protocol by 1.0 | See Deployment / Prefect docs. |

Ticket placeholders (track in GitHub issues when executing waves):

- `ETLANTIC-1.0-REM-ROOT-DEMOTED`
- `ETLANTIC-1.0-REM-DATACONTRACTMODEL`
- `ETLANTIC-1.0-REM-EXPERIMENTAL`

## Demoted root alias count (0.25 snapshot)

Generated from `src/etlantic/__init__.py` `_DEMOTED_ALIASES` (not including
`DataContractModel`, which is handled separately):

| Owning module | Approx. aliases |
|---|---|
| `etlantic.reliability` | 12 |
| `etlantic.interchange` | 11 |
| `etlantic.exceptions` | 8 |
| `etlantic.schema_drift` | 8 |
| `etlantic.sql` | 7 |
| `etlantic.spark` | 6 |
| `etlantic.registry` | 6 |
| `etlantic.runtime` | 6 |
| `etlantic.profile` | 6 |
| Other modules | remainder (~116 total) |

Exact symbols remain in source; this inventory is the authoritative **removal
planning** document for burn-in. Executing removals updates this table's Target
column and CHANGELOG.

## Out of scope for removal inventory

- Curated root symbols (`Data`, `Pipeline`, `Transformation`, …) — stable
- Lazy namespaces (`etl.dataframe`, `etl.authoring`, …) — stable
- Versioned wire schemas (`etlantic.pipeline/1`, …) — evolve via schema policy, not this list
