---
name: etlantic
description: Validate, plan, compile, and generate ETLantic pipelines safely.
---

# ETLantic skill

Use public CLI commands (`validate`, `inspect`, `plan`, `run`, `compile`,
`generate`, `diff`, `plugin`, `schema`, `reliability`, `viz`, `report`) and
public SDK imports (`etlantic.dataframe`, `.sql`, `.spark`, `.orchestration`,
`.viz`, `.secrets`, `.testing`).

Never write secret values into plans or reports. Production profiles require
`plugin_allowlist`. Schema observe/acknowledge must not store source rows.
Medallion bronze/silver/gold stay in SparkForge / etlantic-sparkforge — never
in core. Airflow compile needs the optional `etlantic-airflow` package.
