# etlantic-pyspark

PySpark reference execution plugin **and** portable transform compiler for
[ETLantic](https://github.com/eddiethedean/etlantic) 0.50.

> **Note:** This plugin and ETLantic core use Beta classifiers for documented
> single-tenant pilots. Classifiers are not an enterprise SLA.

## Install

```bash
pip install etlantic-pyspark
# Optional Delta Lake support:
pip install "etlantic-pyspark[delta]"
```

## Portable transform compiler

```python
from etlantic import Profile

Profile(
    name="spark-local",
    spark_engine="pyspark",
    portable_transform_policy="require",
)
```

Entry point: `etlantic.transform_compilers` →
`etlantic_pyspark:create_transform_compiler`.

Claims `portable-relational-kernel/1` and `portable-relational/1`. Lowers
`dtcs.transform-plan/2` to native Spark DataFrame/Column expressions. This is
the recommended transformation path and remains eligible for adaptive
execution. Automatic Python/Pandas UDF fallback is forbidden.

## Native Spark plugin

Register `@Transformation.implementation("pyspark")` handlers only for Spark
behavior outside the portable compiler's claims. They take Spark DataFrames
(or lists of contract models), return Spark DataFrames, pin the step to
PySpark, and are not eligible for adaptive execution.

### Native capabilities

- Lazy Spark region fusion with preserved logical identities
- Local Spark provider (`local[*]`) — secrets resolved only at session acquire
- Native-expression preference with UDF policy diagnostics
- Contract ↔ Spark schema mapping (lossy/unknown never guessed)
- Valid/invalid row separation
- Delta-compatible write intents (append/overwrite/merge) when Delta is enabled
- Structured Streaming foundation (**experimental**)

Native UDF policy stays separate. Default CI uses sparkless; set
`SPARKLESS_TEST_MODE=pyspark` for real JVM Catalyst checks.

**Not included:** managed cloud providers (Databricks/EMR/Connect).

## Links

[PySpark tutorial](https://etlantic.readthedocs.io/en/v0.50.1/06_EXECUTION/PYSPARK_TUTORIAL/) ·
[Compatibility](https://etlantic.readthedocs.io/en/v0.50.1/10_REFERENCE/COMPATIBILITY/) ·
[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-pyspark) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
