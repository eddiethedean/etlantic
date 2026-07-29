# Frequently Asked Questions

Practical questions for ETLantic **0.33.0**. Philosophy and contract taxonomy
live under [Foundations](../02_FOUNDATIONS/README.md).

## What is ETLantic?

A typed Python framework for contract-driven data pipelines. You model once,
validate before write, then run or compile on local Python, Polars, Pandas,
SQL, or Spark. It is **not** dbt, **not** a scheduler, and **not** a
dataframe engine.

## Is ETLantic 0.33 production-supported?

ETLantic **0.33.0** is a **Beta** (PyPI) release for documented single-tenant
pilots—not unrestricted enterprise production. See
[Capabilities](CAPABILITIES.md) and
[Production readiness](../06_EXECUTION/PRODUCTION_READINESS.md).

## Available vs Experimental?

**Available** means supported inside the documented 0.33 pilot envelope.
**Experimental** (Structured Streaming, `etlantic-datafusion`) may change.
See [Experimental surfaces](EXPERIMENTAL_SURFACES.md).

## How does it compare to dbt / Prefect / Pandera?

| Tool | Primary job | Relationship |
|---|---|---|
| **dbt** | SQL warehouse projects | Complementary |
| **Prefect / Dagster / Airflow** | Orchestration | Complementary (Airflow compile; Prefect local MVP) |
| **Pandera / GE** | Row/table validation libraries | Complementary (ETLantic validates wiring/contracts) |

Full table: [Compare](COMPARE.md).

## Which engine should I start with?

Built-in **local** Python (Quickstart). Then Polars for a first dataframe
engine. SQL needs `etlantic-sql` (+ PostgreSQL for MERGE). PySpark needs Java.
See [Engine selection](ENGINE_SELECTION.md).

## Must core and plugin versions match?

Yes. Pin the same minor:

```bash
python -m pip install 'etlantic==0.33.0' 'etlantic-polars==0.33.0'
```

## Why do validate/plan work but run has no data?

Validate/plan do not need source rows. Quickstart binds JSON under `data/` —
check files exist and you use the same `--profile` for validate/plan/run.

## Profile name vs `security_mode`?

Production fail-closed trust keys off `security_mode="production"` and a
non-empty `plugin_allowlist` — **not** the profile name. See
[Profile primer](../05_PIPELINES/PROFILE_PRIMER.md).

## How do I pass secrets?

Use `SecretRef` — never put values in plans. Follow the
[Secrets decision tree](../10_REFERENCE/SECRETS_DECISION.md).

## Can one transformation run on multiple engines?

Yes with `@Transformation.portable` and matching plugins. Coverage differs —
see [Portable Compiler Matrix](../10_REFERENCE/PORTABLE_COMPILER_MATRIX.md).

## Builders / JSON without classes?

Yes since 0.24. See
[Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md).

## Why does `from etlantic import SomeError` fail?

Many root aliases were removed in 0.26/0.27. Import from owning modules
(`etlantic.exceptions`, `etlantic.runtime`, …). See
[Exceptions](../10_REFERENCE/EXCEPTIONS.md).

## Does ETLantic include medallion bronze/silver/gold?

No — those stay in SparkForge / `medallantic`. See
[Medallantic](../09_MEDALLANTIC/README.md) and
[Migration 0.32 → 0.33](../11_DEVELOPMENT/MIGRATION_0_32_TO_0_33.md).

## Can I build a GUI?

Not as a shipped product. Use programmatic authoring + optional
`etlantic-fastapi` reference adapter. See
[Application integration](../08_VISUALIZATION/APPLICATION_INTEGRATION.md).

## Where do lineage / Graphviz diagrams come from?

`Pipeline.to_mermaid()`, `etlantic viz`, and Graphviz DOT / HTML exporters.
See [Visualization](../08_VISUALIZATION/README.md).

## Related

- [Troubleshooting](TROUBLESHOOTING.md)
- [Upgrade](UPGRADE.md)
- [Evaluator brief](EVALUATOR.md)
