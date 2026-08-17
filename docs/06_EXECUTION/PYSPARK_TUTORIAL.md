# Run a Local PySpark Batch

> **Status: Available in ETLantic 0.47.0.** Structured Streaming remains
> experimental.

!!! warning "Clone-assisted path"
    PySpark demos need repository `examples/` and a Java runtime. They are
    **not** a PyPI-only Quickstart continuation. Prefer local/Polars first.

## Prerequisites

- Python 3.11–3.13
- A JDK supported by your PySpark build (CI uses **Java 17** for
  `real-pyspark`)
- `JAVA_HOME` pointing at that JDK (not only `java` on `PATH`)
- `etlantic-pyspark==0.47.0`

## JDK / JAVA_HOME / platform notes

PySpark starts a local JVM. Gateway failures usually mean Java is missing,
wrong major, or `JAVA_HOME` is unset.

| Platform | Typical setup |
|---|---|
| Ubuntu / Debian | `sudo apt install openjdk-17-jdk`; export `JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64` |
| macOS (Homebrew) | `brew install openjdk@17`; follow brew's `JAVA_HOME` hint |
| Windows | Install a Temurin/OpenJDK 17 MSI; set User `JAVA_HOME` to the JDK root |

Verify before running demos:

```bash
java -version
echo "$JAVA_HOME"   # PowerShell: echo $env:JAVA_HOME
python -c "import pyspark; print(pyspark.__version__)"
```

Apple Silicon and Windows both work when the JDK and PySpark wheels match the
architecture; prefer the same Java major your cluster uses. Managed
Databricks / EMR / Spark Connect providers are **not** included in 0.38.

## Install and run (clone companion)

```bash
python -m pip install 'etlantic==0.47.0' 'etlantic-pyspark==0.47.0'
git clone --branch v0.47.0 https://github.com/eddiethedean/etlantic.git
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

## Delta constraints

Delta Lake is **optional**. Without `delta-spark`, the plugin does not advertise
merge / Delta storage capabilities and Delta-required plans fail closed.

```bash
python -m pip install 'etlantic-pyspark[delta]==0.47.0'
# or: python -m pip install 'delta-spark>=3.0,<4'
```

Constraints in 0.38:

- Capabilities require an importable `delta.tables.DeltaTable`.
- Non-Delta MERGE / UPSERT fails closed (no silent overwrite fallback).
- `merge_keys` must be safe identifiers.
- Portable quality compilers on PySpark remain fail-closed (use native Column
  rules where documented).

See [PySpark execution](PYSPARK_EXECUTION.md) and
[compatibility](../10_REFERENCE/COMPATIBILITY.md).
