# Experimental surfaces (0.48)

> **Status: Available in ETLantic 0.48.0 as a map of Experimental APIs.**
> These are **not** part of the Beta Supported claim. Prefer Available paths on
> [Capabilities](CAPABILITIES.md).

| Surface | Package / area | Bound |
|---|---|---|
| Structured Streaming | `etlantic-pyspark` / streaming foundation | Experimental — batch Spark is the production path |
| DataFusion | `etlantic-datafusion` | Experimental Gate B stub — not recommended for pilots |
| OpenLineage outbound | `etlantic-openlineage` | Experimental CP2 export — cannot mutate registry; not production multi-tenant |
| Prefect deployment / serve | `etlantic-prefect` | Local direct-execution MVP only; deployment/serve remain future |
| FastAPI control plane | `etlantic-fastapi` | CP1 `ETLanticAPI` host is Available; `create_reference_app` is a thin non-CP demo |
| Kafka / registry | `etlantic-kafka` / `etlantic-schemaregistry` | Experimental fakes |
| Kubernetes / Spark Connect | `etlantic-k8s` / `etlantic-spark-connect` | Experimental fakes; live packs remain 0.51 |
| MCP | `etlantic-mcp` | Experimental FakeMcpServer; live client skip `048-M-01` |

When a page is labeled **Experimental** or **Future design**, treat APIs as
non-contractual until they graduate on Capabilities.

## Related

- [Capabilities](CAPABILITIES.md)
- [Structured Streaming](../06_EXECUTION/STRUCTURED_STREAMING.md)
- [Support policy](../11_DEVELOPMENT/SUPPORT.md)
