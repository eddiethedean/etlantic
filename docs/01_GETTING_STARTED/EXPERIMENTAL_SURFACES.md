# Experimental surfaces (0.34)

> **Status: Available in ETLantic 0.38.0 as a map of Experimental APIs.**
> These are **not** part of the Beta pilot claim. Prefer Available paths on
> [Capabilities](CAPABILITIES.md).

| Surface | Package / area | Bound |
|---|---|---|
| Structured Streaming | `etlantic-pyspark` / streaming foundation | Experimental — batch Spark is the production path |
| DataFusion | `etlantic-datafusion` | Experimental Gate B stub — not recommended for pilots |
| Prefect deployment / serve | `etlantic-prefect` | Local direct-execution MVP only; deployment/serve remain future |
| FastAPI control plane | `etlantic-fastapi` | Thin authoring/service **reference** adapter; [first-class control-plane program](../11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md) is planned, not shipped |

When a page is labeled **Experimental** or **Future design**, treat APIs as
non-contractual until they graduate on Capabilities.

## Related

- [Capabilities](CAPABILITIES.md)
- [Structured Streaming](../06_EXECUTION/STRUCTURED_STREAMING.md)
- [Support policy](../11_DEVELOPMENT/SUPPORT.md)
