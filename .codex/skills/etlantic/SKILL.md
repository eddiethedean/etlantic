---
name: etlantic
description: Validate, plan, compile, and generate ETLantic pipelines safely.
---

# ETLantic skill

Use public CLI commands (`init`, `doctor`, `validate`, `inspect`, `plan`, `profile`, `run`, `compile`, `generate`, `diff`, `plugin`, `schema`, `reliability`, `erasure`, `viz`, `report`, `watch`, `stream`) and
prefer `import etlantic as etl` (curated root + lazy namespaces) or
public SDK imports (`etlantic.dataframe`, `.sql`, `.spark`, `.orchestration`, `.viz`, `.secrets`, `.testing`, `.quality`, `.connectors`, `.control_plane`, `.optimization`, `.streaming`).

For FastAPI, use `ETLanticAPI` / `include_router` / `create_app` for the CP1
control plane. `create_reference_app` is only a thin, non-CP authoring demo.
Continuous landing-zone directory watchers are optional submitters, never core
behavior. `etlantic watch` is read-only static revalidation (no execution).

Never write secret values into plans or reports. Production profiles require
`plugin_allowlist`. Schema observe/acknowledge must not store source rows.
Medallion bronze/silver/gold stay in SparkForge / medallantic — never
in core. Airflow compile needs the optional `etlantic-airflow` package.
