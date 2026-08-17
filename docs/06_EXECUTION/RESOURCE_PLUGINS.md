# Resource Providers

> **Status: planned design — not shipped in ETLantic 0.46.** Kubernetes Job
> and Spark Connect **Experimental fakes** are assigned to the 0.47 planning
> freeze ([IMPLEMENTATION_PLAN_0_47](../11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_47.md));
> live cluster/cloud hardening and supported enterprise packs are 0.51.
> See the
> [Adoption, Connectivity, and Operations Plan](../11_DEVELOPMENT/ADOPTION_ECOSYSTEM_PLAN.md).

**Do not implement against this page.** There is no discoverable
`etlantic.resource_providers` entry-point group in 0.46.

| Use instead | Link |
|---|---|
| Shipped plugins | [Plugin SDK Overview](../07_PLUGIN_SDK/OVERVIEW.md) |
| Secrets today | [Secrets Management](SECRETS_MANAGEMENT.md) |
| Design stub | [Resource Provider (SDK)](../07_PLUGIN_SDK/RESOURCE_PROVIDER.md) |

Resource providers remain a **future** dependency-injection boundary for
compute placement (Kubernetes Jobs, managed Spark sessions). Until that
protocol ships, acquire connections and credentials through profile assets,
secret providers, and engine plugins already documented as Available.
Connectors (`etlantic.source/1` / `sink/1` / `storage/1`) are I/O — not
this boundary.
