# Current Capabilities and Limitations

ETLantic **0.14.0** is a **published alpha** release on PyPI. This page is the
shortest answer to "What can I use today?"

## Recommended first production-like pilot

Controlled pilot only (see [Evaluator](EVALUATOR.md) and
[Production readiness](../06_EXECUTION/PRODUCTION_READINESS.md)):

1. Core + local/file storage (`examples/quickstart.py`, `examples/file_storage.py`)
2. Optional one engine: Polars **or** Pandas **or** SQL **or** local PySpark
3. Explicit production `Profile` JSON with `plugin_allowlist`
4. CI `validate --format sarif` + reviewed `plan` JSON
5. No multi-tenant sharing of a process; no unresolved security Gaps from the
   [Security](../02_FOUNDATIONS/SECURITY.md) chapter

## Available in 0.14

### Core authoring and validation

| Capability | Status |
|---|---|
| Typed data, transformation, and pipeline models | Available |
| Structural and semantic validation | Available |
| ODCS, DTCS, and DPCS generation and loading | Available |
| Profiles and deterministic, secret-free pipeline plans | Available |
| `@Transformation.portable` / `etlantic.transform` → `dtcs.transform-plan/2` | Available |
| `Profile.portable_transform_policy` (`prefer` / `require` / `native`) | Available |
| DTCS 3.0 plan models / Rich Portable Analytics profiles | Available (install `dtcs>=0.13,<1`; normative content floor `dtcs` 0.14.0 where specs say so) |

### Local execution and storage

| Capability | Status |
|---|---|
| Local synchronous and asynchronous execution | Available |
| Python transformation implementations | Available |
| Memory, callable, JSON, CSV, and no-write storage | Available |
| Run reports, structured logging, and local debugging | Available |
| Runtime secret references and env/file providers | Available |

### Optional engines and portable compilers

| Capability | Status |
|---|---|
| Dataframe protocol + Polars plugin (eager/lazy) | Available (`etlantic-polars`) |
| Pandas plugin (eager) | Available (`etlantic-pandas`) |
| Portable Polars compiler (kernel + relational `/1`) | Available |
| Portable PySpark compiler (kernel + relational `/1`) | Available |
| Portable Pandas compiler (kernel + relational `/1`, eager) | Available |
| Public portable transform conformance suite | Available |
| Optional Arrow interchange | Available when PyArrow is installed |
| SQL protocol + PostgreSQL reference plugin | Available (`etlantic-sql`) |
| Spark protocol + local provider + native impl path | Available (`etlantic-pyspark`) |
| Lazy Spark region fusion (native path) | Available |
| Delta-compatible write intents | Available (fail-closed without Delta) |
| Airflow reference compiler | Available (`etlantic-airflow`) |

### Operations and security tooling

| Capability | Status |
|---|---|
| CLI compile / generate / diff / plugin / schema / reliability / viz | Available |
| Plugin allowlists and version pins | Available |
| SARIF diagnostics and file schema history | Available |
| File-backed report store and report compare | Available |
| Mermaid, Graphviz DOT, HTML lineage, JSON lineage | Available |
| IDE command/result JSON schemas | Available |
| Optional keyring / SQLModel / OpenTelemetry / SparkForge | Available |
| Agent guidance generators | Available |

### Experimental

| Capability | Status |
|---|---|
| Structured Streaming foundation | **Experimental** |

## Not included in 0.14

| Capability | Status |
|---|---|
| `MERGE` / upsert in the reference SQL plugin | Not implemented (`sql_merge=False`; fail closed) |
| Managed Spark providers (Databricks/EMR/Connect) | Future / optional adapters |
| Event sensors / Dagster / Prefect compilers | Future plugins |
| Full LSP server productization | Continues in 1.5 |
| Registry-backed schema history | Continues in 1.2 |
| FastAPI control plane | Continues in 1.1 |
| Full SparkForge engine retirement inside SparkForge | Progressive path (see migration guide) |
| Stable 1.0 compatibility guarantees | Not yet |
| Portable SQL lowering (kernel + `portable-relational/1`) | Planned for **0.15** (exit gate) |
| Advanced portable profile graduation (window, reshape, …) | Planned for **0.15 continuation** after the SQL gate (not the 0.15 exit gate) |
| Dedicated deployment / multi-worker ops guide | Partial — see [Ops Pilot](../06_EXECUTION/OPS_PILOT.md) |

## CI starter

```bash
etlantic validate path/to/pipeline.py:MyPipeline --profile ./profiles/prod.json --format sarif
etlantic plan path/to/pipeline.py:MyPipeline --profile ./profiles/prod.json --format json
```

Production profiles require a non-empty `Profile.plugin_allowlist` in an
explicit Profile JSON file (the built-in `production` name is empty and
fail-closed). Never put secrets in plans, reports, or CI logs. See
[Production profiles](../06_EXECUTION/PRODUCTION_PROFILES.md),
[Runtime configuration](../10_REFERENCE/RUNTIME_CONFIGURATION.md),
[Ops Pilot](../06_EXECUTION/OPS_PILOT.md), and the
[Evaluator brief](EVALUATOR.md).

```bash
pip install etlantic                 # core only — no engines
pip install etlantic-polars          # Polars reference plugin
pip install etlantic-pandas          # Pandas compatibility plugin
pip install etlantic-sql             # PostgreSQL SQL reference plugin
pip install etlantic-pyspark         # PySpark reference plugin
pip install etlantic-airflow         # Airflow DAG compiler
pip install etlantic-keyring         # OS keyring secret provider
pip install etlantic-sqlmodel        # SQLModel contract bridge
pip install etlantic-sparkforge      # SparkForge → ETLantic adapter
pip install 'etlantic[polars]'
pip install 'etlantic[pandas]'
pip install 'etlantic[dataframes]'   # polars + pandas
pip install 'etlantic[sql]'          # alias: postgresql
pip install 'etlantic[pyspark]'      # alias: spark
pip install 'etlantic[airflow]'
pip install 'etlantic[keyring]'
pip install 'etlantic[sqlmodel]'
pip install 'etlantic[sparkforge]'
pip install 'etlantic[otel]'         # alias: observability
pip install 'etlantic[arrow]'
pip install 'etlantic-polars[arrow]'
```

See [Installation](INSTALLATION.md) for verification and from-source contributor setup.

Core never imports Polars, Pandas, PyArrow, NumPy, database drivers, PySpark,
Airflow, SQLModel, keyring, OpenTelemetry, or SparkForge unless extras are
installed. Medallion bronze/silver/gold types are never part of core.

## Next Step

Continue with [Quickstart](QUICKSTART.md), or read the
[Evaluator brief](EVALUATOR.md) if you are assessing the project for adoption.
