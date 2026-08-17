# Resource Provider

!!! warning "Planned provider boundary — not a shipped entry-point protocol"
    Resource providers are not a discoverable entry-point protocol in
    ETLantic 0.46. The `etlantic.resource/1` protocol, Kubernetes Job
    `FakeKubernetes` extra (`etlantic-k8s`), and Spark Connect fake
    (`etlantic-spark-connect`) are assigned to the **0.47 planning freeze**
    ([IMPLEMENTATION_PLAN_0_47](../11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_47.md),
    [ADR-023](../11_DEVELOPMENT/adr/ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md)).
    Live Kind/cluster and live Databricks/EMR packs remain 0.51.
    None of these extras exist yet. Do not describe them as Available.

**Do not implement a package against this page until 0.47 implementation
starts.** Prefer shipped dataframe / SQL / Spark / orchestration / secrets /
observability plugins.

| Use instead | Link |
|---|---|
| Shipped protocols | [Plugin SDK Overview](OVERVIEW.md) |
| Secrets | [Secret Provider](SECRET_PROVIDER.md) |
| Local Spark session provider | [Spark Provider](SPARK_PROVIDER.md) (`etlantic-pyspark`) |
| Operator view | [Resource Providers (execution)](../06_EXECUTION/RESOURCE_PLUGINS.md) |
| Program ownership | [Adoption ecosystem plan](../11_DEVELOPMENT/ADOPTION_ECOSYSTEM_PLAN.md) |
