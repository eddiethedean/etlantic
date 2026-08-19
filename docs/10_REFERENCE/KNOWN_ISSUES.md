# Known Limitations

> **Status: Available in ETLantic 0.48.0.**

ETLantic **0.48.x** is a **Beta** release suitable for documented
single-tenant reference deployments and Supported multi-tenant profiles.
0.x releases may still introduce breaking API changes between minor versions.
**CP-GA** graduated production multi-tenant for `isolated-deployment` /
`dedicated-schema`; `shared-service` remains Experimental; community **non-SLA**.
**CP1–CP4 alone ≠ GA** — use the support matrix, not a single CP gate.

| ID | Component | Affected | Symptom | Workaround | Status |
|---|---|---|---|---|---|
| DOC-001 | Release maturity | All adopters | Breaking API changes possible between 0.x minors | Pin `etlantic==0.48.0` and matching plugins; follow Upgrade hub | Open (Beta) |
| DOC-026 | Control plane | Multi-tenant hosts | Treating CP1–CP4 alone as GA isolation | Use Supported profiles only; see [cp_ga_support_matrix_0_43.json](../11_DEVELOPMENT/cp_ga_support_matrix_0_43.json) | By design |
| DOC-002 | Portable transforms | Polars / PySpark vs Pandas / SQL | Advanced portable families graduate unevenly across engines | Use [Portable compiler matrix](PORTABLE_COMPILER_MATRIX.md); keep Pandas/SQL on kernel + relational `/1` | Partial |
| DOC-003 | Portable window | Window frames | Explicit `rowsBetween` / `rangeBetween` fail closed; `first_value` / `last_value` use ordered partition semantics | Avoid frame clauses until claimed; watch `portable-window/2` | Open |
| DOC-004 | Portable semantics | Three-state / maps | Distinct `missing`/`invalid` fail closed without `semantic_mode:three_state_distinct`; Polars does not claim `dtcs:map` | Prefer `dtcs:object` on Polars; use PySpark for `dtcs:map` | Open |
| DOC-005 | Portable authoring | Closed syntax | Actions, arbitrary Python tracing, raw SQL expressions, silent UDF fallback excluded | Stay within documented portable IR; use native implementations for excluded ops | By design |
| DOC-006 | [DTCS](../04_TRANSFORMATIONS/DTCS.md) 3.0 families | Facades / compilers | Facades may emit IR for unclaimed families; first-party compilers reject at analyze | Check claimed profiles before authoring advanced DTCS families | By design |
| DOC-007 | Runtime | Local execution | In-process only; not a distributed scheduler | Use Airflow/Prefect/external schedulers for multi-process orchestration | By design |
| DOC-008 | Spark providers | Cloud Spark | 0.47 ships Kubernetes and Spark Connect Experimental fakes, not live managed providers | Run local `etlantic-pyspark` or your own provider; live packs remain planned for 0.51 | Open |
| DOC-009 | Orchestration | Compilers / schedulers | Airflow via `etlantic-airflow` (compile-only); Prefect local MVP via `etlantic-prefect`; Dagster / expanded Prefect compilers not shipped | Use shipped Airflow compile or Prefect local path | Partial |
| DOC-010 | Streaming | Structured Streaming | APIs experimental since 0.7+ | Prefer batch Spark for production-shaped pilots | Experimental |
| DOC-011 | SQL safety | SQL plugins | Untrusted raw SQL is not treated as safe | Use typed expression model and dialect identifier/parameter APIs | By design |
| DOC-012 | SQL MERGE | SQLite / non-PG | `MERGE` / upsert implemented for PostgreSQL (`sql_merge=True`); SQLite and others fail closed | Use PostgreSQL when merge is required | Partial |
| DOC-013 | SQL dialects | Tier A verification | SQLite in-memory runs are not evidence of PostgreSQL-specific behavior | Exercise the dialect you deploy | By design |
| DOC-014 | SQL topology | Cross-database | Cross-database joins and distributed transactions unsupported | Keep joins within one engine/database | By design |
| DOC-015 | Polars materialization | LazyFrames / workspace | LazyFrames collect only at plan-declared boundaries; durable JSON workspace needs records | Collect before durable materialization | By design |
| DOC-016 | Durable workspace | Native frames | Durable storage rejects native frames/LazyFrames (fail closed) | Materialize to supported record/JSON forms | Open |
| DOC-017 | Pandas | Lazy mode | Requiring `lazy` fails at planning | Keep Pandas eager (`lazy=False`) | By design |
| DOC-018 | Interchange | Arrow | Cross-engine Arrow path needs optional PyArrow; else copy fallback | `pip install 'etlantic[arrow]'` when lossless Arrow is required | Partial |
| DOC-019 | Interchange | Dtypes | Not every Polars/Pandas dtype maps losslessly | Treat ambiguous mappings as diagnostics; normalize contracts | Open |
| DOC-020 | Plugin capabilities | Cancellation / threads | Cancellation and thread-safety flags not fully enforced by reference plugins | Do not rely on those capability ads for safety | Open |
| DOC-021 | Documentation | Design pages | Future-design pages describe later-0.x intent | Check page status and [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md) | By design |
| DOC-022 | Reports | History store | Process-local / file report history is not a durable report database or audit SoR | Export to application-owned storage; see Reports and history | By design |
| DOC-023 | Storage | In-memory | Intended for local development and tests | Use file/SQL/Spark backends for durable data | By design |
| DOC-024 | Plans | Hand edits | Generated plans drift after incompatible schema changes | Regenerate plans; do not hand-edit IR | By design |
| DOC-025 | Docs vs PyPI | `main` docs | Docs on `main` / RTD `latest` may briefly lead a published tag | Pin installs; prefer RTD `stable` or versioned docs — [Documentation versioning](../01_GETTING_STARTED/DOCUMENTATION_VERSIONING.md) | Open |

Release-specific fixes and changes are recorded in the
[changelog](../CHANGELOG.md).
