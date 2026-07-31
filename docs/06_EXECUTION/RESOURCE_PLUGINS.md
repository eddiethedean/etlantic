# Resource Providers

> **Status: planned design — not shipped in ETLantic 0.37.** Kubernetes and
> managed execution reference proof is assigned to 0.47; supported enterprise
> provider packs are assigned to 0.51. See the
> [Adoption, Connectivity, and Operations Plan](../11_DEVELOPMENT/ADOPTION_ECOSYSTEM_PLAN.md).

**Do not implement against this page.** There is no discoverable resource-provider
entry-point group in 0.37.

| Use instead | Link |
|---|---|
| Shipped plugins | [Plugin SDK Overview](../07_PLUGIN_SDK/OVERVIEW.md) |
| Secrets today | [Secrets Management](SECRETS_MANAGEMENT.md) |
| Design stub | [Resource Provider (SDK)](../07_PLUGIN_SDK/RESOURCE_PROVIDER.md) |

Resource providers remain a **future** dependency-injection boundary for
databases, secret managers, and compute. Until that protocol ships, acquire
connections and credentials through profile assets, secret providers, and
engine plugins already documented as Available.
