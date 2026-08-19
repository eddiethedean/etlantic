# Resource Providers

> **Status: Experimental in ETLantic 0.48.** Kubernetes Job
> and Spark Connect fake-backed providers ship in the bounded 0.48 envelope
> ([implementation plan](../11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_47.md));
> live cluster/cloud hardening and supported enterprise packs are 0.51.
> See the
> [Adoption, Connectivity, and Operations Plan](../11_DEVELOPMENT/ADOPTION_ECOSYSTEM_PLAN.md).

Treat this page as the operational boundary for the Experimental providers.
The `etlantic.resource_providers` entry-point group is discoverable in 0.48,
but the bundled Kubernetes implementation is fake-backed by default.

| Use instead | Link |
|---|---|
| Shipped plugins | [Plugin SDK Overview](../07_PLUGIN_SDK/OVERVIEW.md) |
| Secrets today | [Secrets Management](SECRETS_MANAGEMENT.md) |
| Protocol | [Resource Provider (SDK)](../07_PLUGIN_SDK/RESOURCE_PROVIDER.md) |

Resource providers are the compute-placement boundary (Kubernetes Jobs).
Spark Connect remains a `SparkProvider`. Connectors
(`etlantic.source/1` / `sink/1` / `storage/1`) are I/O — not this boundary.
