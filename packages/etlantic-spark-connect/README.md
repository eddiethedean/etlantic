# etlantic-spark-connect (Experimental / Preview)

Version **0.47.0** (lockstep with ETLantic core).
Fake-first Spark Connect `SparkProvider` for [ETLantic](https://github.com/eddiethedean/etlantic).
Live Databricks/EMR/Spark Connect endpoints are opt-in via
`ETLANTIC_SPARK_CONNECT_URL` and are skipped in CI (`047-S-01`).

**Maturity:** Experimental (Alpha classifier). Pin with core.

## Install

```bash
pip install 'etlantic-spark-connect==0.47.0'
```

Core dependency: `etlantic>=0.47.0,<0.48`. No Databricks/EMR SDK in the default extra.

## Entry points

| Group | Name | Factory |
|---|---|---|
| `etlantic.spark_providers` | `spark-connect` | `etlantic_spark_connect:create_provider` |
