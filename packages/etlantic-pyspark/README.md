# etlantic-pyspark

PySpark reference execution plugin **and** portable transform compiler for
[ETLantic](https://github.com/eddiethedean/etlantic) 0.43.

> **Note:** This plugin and ETLantic core use Beta classifiers for documented
> single-tenant pilots. Classifiers are not an enterprise SLA.

## Install

```bash
pip install etlantic-pyspark
# Optional Delta Lake support:
pip install "etlantic-pyspark[delta]"
```

## Native Spark plugin

```python
from etlantic import Profile

Profile(name="spark-local", spark_engine="pyspark")
```

Register `@Transformation.implementation("pyspark")` handlers that take
Spark DataFrames (or lists of contract models) and return Spark DataFrames.

### Native capabilities

- Lazy Spark region fusion with preserved logical identities
- Local Spark provider (`local[*]`) — secrets resolved only at session acquire
- Native-expression preference with UDF policy diagnostics
- Contract ↔ Spark schema mapping (lossy/unknown never guessed)
- Valid/invalid row separation
- Delta-compatible write intents (append/overwrite/merge) when Delta is enabled
- Structured Streaming foundation (**experimental**)

## Portable transform compiler

Entry point: `etlantic.transform_compilers` →
`etlantic_pyspark:create_transform_compiler`.

Claims `portable-relational-kernel/1` and `portable-relational/1`. Lowers
`dtcs.transform-plan/2` to native Spark DataFrame/Column expressions. Automatic
Python/Pandas UDF fallback is forbidden on the portable path (native UDF policy
stays separate). Default CI uses sparkless; set
`SPARKLESS_TEST_MODE=pyspark` for real JVM Catalyst checks.

**Not included:** managed cloud providers (Databricks/EMR/Connect).

## Links

[PySpark tutorial](https://etlantic.readthedocs.io/en/v0.43.0/06_EXECUTION/PYSPARK_TUTORIAL/) ·
[Compatibility](https://etlantic.readthedocs.io/en/v0.43.0/10_REFERENCE/COMPATIBILITY/) ·
[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-pyspark) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
