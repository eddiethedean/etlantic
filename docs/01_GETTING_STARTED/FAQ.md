# Frequently Asked Questions

> **Status: Available in ETLantic 0.36.0.**

Practical questions for ETLantic **0.36.0**. Philosophy and contract taxonomy
live under [Foundations](../02_FOUNDATIONS/README.md).

## What is ETLantic?

A typed Python framework for contract-driven data pipelines. You model once,
validate before write, then run or compile on local Python, Polars, Pandas,
SQL, or Spark. It is **not** dbt, **not** a scheduler, and **not** a
dataframe engine. See [Compare](COMPARE.md) for when not to use it.

## What is a Profile?

A Profile selects engines, asset bindings, trust mode, and (optionally)
observability. Prefer named profiles (`development`, `production`) and pass
`--profile` on validate / plan / run. Fail-closed production trust uses
`security_mode="production"` plus a non-empty `plugin_allowlist` — **not** the
profile name alone. Hub: [Profiles](../05_PIPELINES/PROFILES_HUB.md).

## Why `file:Class` / `path.py:ClassName`?

CLI targets load a Python module then a class:
`pipeline.py:SamplePipeline`. That is a filesystem path plus a class name,
not a URL scheme. See [CLI — Pipeline targets](../10_REFERENCE/CLI.md).

## Where do reports go?

By default under the workspace `.etlantic/reports/` (and history under
`.etlantic/history/` when configured). Use `etlantic report list` /
`etlantic report query`. Hub: [Reports and history](../06_EXECUTION/REPORTS_AND_HISTORY.md).

## Do I need Java?

Only for PySpark. Local, Polars, Pandas, and SQL (SQLite/PostgreSQL) do not
require a JVM. See [Engine selection](ENGINE_SELECTION.md).

## Which engine should I start with?

Built-in **local** Python (Quickstart). Then Polars for a first dataframe
engine. SQL needs `etlantic-sql` (+ PostgreSQL for MERGE). PySpark needs Java.

## Must core and plugin versions match?

Yes. Pin the same minor:

```bash
python -m pip install 'etlantic==0.36.0' 'etlantic-polars==0.36.0'
```

## Why do validate/plan work but run has no data?

Validate/plan do not need source rows. Quickstart binds JSON under `data/` —
check files exist and you use the same `--profile` for validate/plan/run.

## Profile name vs `security_mode`?

Production fail-closed trust keys off `security_mode="production"` and a
non-empty `plugin_allowlist` — **not** the profile name. See
[Profiles hub](../05_PIPELINES/PROFILES_HUB.md).

## How do I pass secrets?

Use `SecretRef` — never put values in plans. Follow the
[Secrets decision tree](../10_REFERENCE/SECRETS_DECISION.md).

## Is ETLantic 0.36 production-supported?

ETLantic **0.36.0** is a **Beta** (PyPI) release for documented single-tenant
pilots—not unrestricted enterprise production. See
[Capabilities](CAPABILITIES.md) and
[Production readiness](../06_EXECUTION/PRODUCTION_READINESS.md).

## Available vs Experimental?

**Available** means supported inside the documented 0.36 pilot envelope.
**Experimental** (Structured Streaming, `etlantic-datafusion`) may change.
See [Experimental surfaces](EXPERIMENTAL_SURFACES.md).

## How does it compare to dbt / Prefect / Pandera?

| Tool | Primary job | Relationship |
|---|---|---|
| **dbt** | SQL warehouse projects | Complementary |
| **Prefect / Dagster / Airflow** | Orchestration | Complementary (Airflow compile; Prefect local MVP) |
| **Pandera / GE** | Row/table validation libraries | Complementary (ETLantic validates wiring/contracts) |

Full table and when **not** to use ETLantic: [Compare](COMPARE.md).

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
[Migration 0.35 → 0.36](../11_DEVELOPMENT/MIGRATION_0_35_TO_0_36.md).

## Can I build a GUI?

Not as a shipped product. Use programmatic authoring + optional
`etlantic-fastapi` reference adapter. See
[Application integration](../08_VISUALIZATION/APPLICATION_INTEGRATION.md).

## Where do lineage / Graphviz diagrams come from?

`Pipeline.to_mermaid()`, `etlantic viz`, and Graphviz DOT / HTML exporters.
See [Visualization](../08_VISUALIZATION/README.md).

## Related

- [Troubleshooting](TROUBLESHOOTING.md)
- [Diagnostics playbook](../10_REFERENCE/DIAGNOSTICS_PLAYBOOK.md)
- [Upgrade](UPGRADE.md)
- [Evaluator brief](EVALUATOR.md)
