# Run a Local PySpark Batch

> **Status: Available in ETLantic 0.21.0.** Structured Streaming remains
> experimental.


!!! note "Repository examples"
    Companion scripts under `examples/` are not installed with the PyPI
    wheel. Clone a matching checkout (prefer the `v0.21.0` tag) and use
    `uv sync` / the documented dependency group before running them.

## Prerequisites

- Python 3.11+
- A Java runtime supported by your PySpark installation
- `etlantic-pyspark==0.21.0`

```bash
python -m pip install 'etlantic==0.21.0' 'etlantic-pyspark==0.21.0'
git clone --branch v0.21.0 https://github.com/eddiethedean/etlantic.git
cd etlantic
python examples/pyspark_local.py
```

The transformation registers a native PySpark implementation and selects it
with `Profile(name="spark-local", spark_engine="pyspark")`. The runtime also
registers the local Spark provider explicitly.

Complete source:
[`examples/pyspark_local.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/pyspark_local.py).

Managed Databricks, EMR, and Spark Connect providers are not included. See
[PySpark execution](PYSPARK_EXECUTION.md) and
[compatibility](../10_REFERENCE/COMPATIBILITY.md).
