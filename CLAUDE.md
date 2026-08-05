# CLAUDE.md — ETLantic


## Purpose

Guide coding agents working in ETLantic projects. Prefer public CLI and SDK
surfaces; fail closed on secrets, plugin trust, and schema mutations.

## Public CLI

`etlantic init`, `etlantic doctor`, `etlantic validate`, `etlantic inspect`, `etlantic plan`, `etlantic profile`, `etlantic run`, `etlantic compile`, `etlantic generate`, `etlantic diff`, `etlantic plugin`, `etlantic schema`, `etlantic reliability`, `etlantic erasure`, `etlantic viz`, `etlantic report`, `etlantic watch`

## Public SDK imports

Recommended: `import etlantic as etl` (curated root + lazy namespaces).

Also supported: `etlantic.dataframe`, `etlantic.sql`, `etlantic.spark`,
`etlantic.orchestration`, `etlantic.viz`, `etlantic.secrets`,
`etlantic.testing`, `etlantic.quality`, `etlantic.connectors`,
`etlantic.control_plane`, `etlantic.optimization`

## FastAPI dual surface

- **CP1 control plane:** `ETLanticAPI` / `include_router` / `create_app`
  (durable accept, authz, `/health` + `/ready`)
- **Non-CP reference:** `create_reference_app` (thin authoring demo only)
- Continuous directory watchers are **not** in core; use optional submitters
  (for example `etlantic_fastapi.landing_sensor`)

## Security

- Never embed secret values in plans, reports, contracts, or agent guidance.
- Production profiles require Profile.plugin_allowlist and fail closed.
- Production profiles that enable optimization require Profile.optimization_pass_allowlist and fail closed.
- Schema history stores fingerprints/metadata only — never source rows.
- Prefer public SDK imports; do not rely on private underscore modules.
- Medallion bronze/silver/gold stay in SparkForge / medallantic — never in core.

## Workflows

1. Validate before generate/compile: `etlantic validate TARGET --format json`
2. Plan deterministically: `etlantic plan TARGET --format json`
3. Compile only from a valid plan (requires `etlantic-airflow` for `--target airflow`):
   `etlantic compile TARGET --target airflow -o dags/`
4. Emit CI diagnostics as SARIF: `etlantic validate TARGET --format sarif`
5. Use `etlantic.testing` conformance suites for third-party plugins
6. Diagrams: `Pipeline.to_mermaid()` or `etlantic.viz` / `etlantic viz`

## Claude-specific notes

- Prefer editing contracts/pipelines over inventing backend-specific DAGs.
- When unsure, run `etlantic plan explain` and attach JSON output.
