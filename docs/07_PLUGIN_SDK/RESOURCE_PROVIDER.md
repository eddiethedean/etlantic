# Resource Provider

> **Status: Available in ETLantic 0.47.0** as a discoverable core protocol
> (`etlantic.resource/1`). The Kubernetes extra is **Experimental**.

`etlantic.resource_providers` is the entry-point group. Production profiles
that select a resource provider require `Profile.resource_provider_allowlist`
(`PMRES140`).

| Package | Maturity | Fake | Live |
|---|---|---|---|
| `etlantic-k8s` | Experimental (Alpha) | `FakeKubernetes` | skip `047-K-01` (`ETLANTIC_K8S_CONTEXT`) |

Do not embed kubeconfig secrets in schedules or plans. Spark Connect is a
`SparkProvider` (`etlantic.spark_providers`), not a resource provider.

| Use instead | Link |
|---|---|
| Spark session provider | [Spark Provider](SPARK_PROVIDER.md) |
| Secrets | [Secret Provider](SECRET_PROVIDER.md) |
| Operator view | [Resource Providers (execution)](../06_EXECUTION/RESOURCE_PLUGINS.md) |
