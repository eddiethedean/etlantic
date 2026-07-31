# 0.37 Stable-Foundation Removal Candidates

> **Status: Executed in ETLantic 0.39.0.** First-wave removals executed in
> 0.26.0; second-wave removals executed in 0.27.0; third-wave removals executed
> in 0.28.0; remaining demoted-root and `DataContractModel` inventory
> **removed in 0.37.0**. See
> [Migration 0.36 → 0.37](MIGRATION_0_36_TO_0_37.md),
> [Migration 0.26 → 0.27](MIGRATION_0_26_TO_0_27.md), and
> [Migration 0.27 → 0.28](MIGRATION_0_27_TO_0_28.md).

## Process guard (0.25+)

- Do **not** add new indefinite keep-forever root aliases in 0.25+ PRs.
- New public symbols belong on owning modules or the curated root facade
  (`_CURATED` in `src/etlantic/__init__.py`), not `_DEMOTED_ALIASES`.
- Removals require changelog + migration note + tests (see deprecation policy).

## Candidate groups

| ID | Candidates | Owning modules | Target | Migration note |
|---|---|---|---|---|
| `REM-ROOT-DEMOTED` | warn-once root aliases in `_DEMOTED_ALIASES` | various | first wave 0.26.0; second wave **removed 0.27.0** (schema_drift + registry); third wave **removed 0.28.0** (sql/profile/lifecycle); remainder **removed 0.37.0** | Prefer owning imports. |
| `REM-DATACONTRACTMODEL` | `DataContractModel` provisional alias | `etlantic.contracts` | **removed 0.37.0** | Use ContractModel / `Data` per current contracts docs. |
| `REM-EXCEPTIONS-ROOT` | Exception types on root | `etlantic.exceptions` | **removed 0.26.0** | `from etlantic.exceptions import …` |
| `REM-PROTOCOL-CONSTS` | `*_PROTOCOL_VERSION`, `STREAMING_STABILITY`, `PLUGIN_MANIFEST_SCHEMA` | dataframe / sql / spark / orchestration / plugin_manifest | **removed 0.26.0** | Import from owning protocol modules. |
| `REM-STORAGE-ROOT` | `MemoryStorage`, `JsonStorage`, `CsvStorage`, `CallableStorage`, `NullStorage` | `etlantic.storage` | **removed 0.26.0** | `from etlantic.storage import …` |
| `REM-RUNTIME-ROOT` | `RunIntent`, `RunRequest`, `RunSelection`, `RunStatus`, `DebugSession`, `MaterializationPolicy` | `etlantic.runtime` | **removed 0.26.0** | Prefer runtime / lifecycle namespaces. |
| `REM-RELIABILITY-ROOT` | Reliability declaration types | `etlantic.reliability` | **removed 0.27.0** | Prefer `etlantic.reliability`. |
| `REM-INTERCHANGE-ROOT` | Interchange / provenance helpers | `etlantic.interchange` | **removed 0.26.0** | Prefer `etlantic.interchange`. |
| `REM-EXPERIMENTAL` | Structured Streaming APIs; `etlantic-datafusion` | spark / datafusion | **remain experimental** in 0.37 (DataFusion Gate B not graduating) | See Capabilities / Compatibility. |
| `REM-PREFECT-MVP` | Prefect scheduler MVP surface | `etlantic-prefect` | **frozen** as `scheduler/1` stable MVP in 0.36; unchanged in 0.37 | See Deployment / Prefect docs. |

Ticket placeholders (track in GitHub issues when executing waves):

- `ETLANTIC-0.37-REM-ROOT-DEMOTED` (done in 0.37.0)
- `ETLANTIC-0.37-REM-DATACONTRACTMODEL` (done in 0.37.0)
- `ETLANTIC-0.37-REM-EXPERIMENTAL` (remain experimental; no removal)

## Demoted root alias count (0.37 disposition)

`_DEMOTED_ALIASES` is empty after 0.37.0. Former demoted symbols raise via
`_REMOVED_0_37` — import from owning modules per
[MIGRATION_0_36_TO_0_37](MIGRATION_0_36_TO_0_37.md).

**Removed in 0.28.0** (third wave): all `etlantic.sql` (6), `etlantic.profile`
(6), and `etlantic.lifecycle` (5) demoted root aliases — see
[MIGRATION_0_27_TO_0_28](MIGRATION_0_27_TO_0_28.md).

**Removed in 0.37.0** (stable-foundation wave): remaining ~36 demoted root
aliases plus `DataContractModel`.

## Out of scope for removal inventory

- Curated root symbols (`Data`, `Pipeline`, `Transformation`, …) — stable
- Lazy namespaces (`etl.dataframe`, `etl.authoring`, …) — stable
- Versioned wire schemas (`etlantic.pipeline/1`, …) — evolve via schema policy, not this list
- `REM-PREFECT-MVP` — frozen stable MVP; not removed
- `REM-EXPERIMENTAL` — remain experimental; not graduated or removed in 0.37
