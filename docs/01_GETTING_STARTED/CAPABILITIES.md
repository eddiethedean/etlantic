# Current Capabilities and Limitations

ETLantic 0.14.0 is an alpha release. This page is the shortest answer to
"What can I use today?"

## Available in 0.14

| Capability | Status |
|---|---|
| Typed data, transformation, and pipeline models | Available |
| Structural and semantic validation | Available |
| ODCS, DTCS, and DPCS generation and loading | Available |
| Profiles and deterministic, secret-free pipeline plans | Available |
| Local synchronous and asynchronous execution | Available |
| Python transformation implementations | Available |
| Memory, callable, JSON, CSV, and no-write storage | Available |
| Run reports, structured logging, and local debugging | Available |
| Runtime secret references and env/file providers | Available |
| Dataframe execution protocol (`etlantic.dataframe/1`) | Available |
| Polars plugin (eager + lazy preservation) | Available (`etlantic-polars`) |
| Pandas plugin (eager compatibility) | Available (`etlantic-pandas`) |
| Portable Pandas compiler (kernel + relational `/1`, eager-only) | Available (`etlantic-pandas`) |
| Public `etlantic.testing.portable_transform_conformance` | Available |
| Optional Arrow interchange | Available when PyArrow is installed |
| SQL execution protocol (`etlantic.sql/1`) | Available |
| SQL plugin (PostgreSQL reference) | Available (`etlantic-sql`) |
| Spark execution protocol (`etlantic.spark/1`) | Available |
| PySpark plugin + local Spark provider (native `@implementation`) | Available (`etlantic-pyspark`) |
| Portable PySpark transform compiler (kernel + relational `/1`) | Available (`etlantic-pyspark`) |
| Lazy Spark region fusion (native Spark path) | Available |
| Delta-compatible write intents | Available (fail-closed without Delta) |
| Structured Streaming foundation | **Experimental** |
| Orchestration protocol (`etlantic.orchestration/1`) | Available |
| Airflow reference compiler | Available (`etlantic-airflow`) |
| Schedule / retry / artifact-ref mapping | Available |
| CLI compile / generate / diff / plugin / schema / reliability / viz | Available |
| Plugin allowlists and version pins | Available |
| SARIF diagnostics and file schema history | Available |
| File-backed report store and report compare | Available |
| Mermaid, Graphviz DOT, HTML lineage, JSON lineage | Available |
| IDE command/result JSON schemas | Available |
| Optional keyring secret provider | Available (`etlantic-keyring`) |
| Optional SQLModel bridge | Available (`etlantic-sqlmodel`) |
| Optional OpenTelemetry adapter | Available (`etlantic[otel]`) |
| Agent guidance generators | Available |
| SparkForge migration adapter | Available (`etlantic-sparkforge`) |
| DTCS 3.0 Transformation Plan models and Rich Portable Analytics profiles | Available through `dtcs>=0.13` |
| `@Transformation.portable` / `etlantic.transform` authoring → `dtcs.transform-plan/2` | Available |
| `Profile.portable_transform_policy` (`prefer` / `require` / `native`) | Available |
| Portable Polars compiler (kernel + `portable-relational/1`) | Available (`etlantic-polars`) |
| Portable PySpark compiler (kernel + `portable-relational/1`) | Available (`etlantic-pyspark`) |
| Portable Pandas compiler (kernel + `portable-relational/1`, eager) | Available (`etlantic-pandas`) |
| Public portable transform conformance suite | Available (`etlantic.testing.run_portable_transform_conformance_suite`) |

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
| Portable SQL lowering and profile graduation | Planned for 0.15+ |
| Dedicated deployment / multi-worker ops guide | Partial — see [Ops Pilot](../06_EXECUTION/OPS_PILOT.md) |

## CI starter

```bash
etlantic validate path/to/pipeline.py:MyPipeline --profile production --format sarif
etlantic plan path/to/pipeline.py:MyPipeline --profile production --format json
```

Production profiles require a non-empty `Profile.plugin_allowlist`. Never put
secrets in plans, reports, or CI logs. See
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
