# Run a Local PySpark Batch

> **Status: Available in ETLantic 0.34.0.** Structured Streaming remains
> experimental.

!!! warning "Clone-assisted path"
    PySpark demos need repository `examples/` and a Java runtime. They are
    **not** a PyPI-only Quickstart continuation. Prefer local/Polars first.

## Prerequisites

- Python 3.11+
- A Java runtime supported by your PySpark installation
- `etlantic-pyspark==0.34.0`

## Install and run (clone companion)

```bash
python -m pip install 'etlantic==0.34.0' 'etlantic-pyspark==0.34.0'
git clone --branch v0.34.0 https://github.com/eddiethedean/etlantic.git
cd etlantic
python examples/pyspark_local.py
```

The transformation registers a native PySpark implementation and selects it
with `Profile(name="spark-local", spark_engine="pyspark")`. The runtime also
registers the local Spark provider explicitly.

Complete source:
[`examples/pyspark_local.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/pyspark_local.py).

## Expected output

Spark may print JVM, hostname, or native-library warnings before the report.
Those lines are environment-specific. The stable ETLantic portion is:

```text
profile:  spark-local
status:   succeeded
summary:  total=3 ok=3 failed=0 skipped=0 cancelled=0
steps:
  - raw: succeeded
  - normalized: succeeded
  - curated: succeeded
```

Run identifiers and durations vary. A Java gateway error means the local Spark
runtime did not start; it is not an expected successful result.

Managed Databricks, EMR, and Spark Connect providers are not included. See
[PySpark execution](PYSPARK_EXECUTION.md) and
[compatibility](../10_REFERENCE/COMPATIBILITY.md).
