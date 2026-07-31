# Storage Plugin

!!! warning "Planned for 0.38—not a shipped 0.37 entry-point protocol"
    Storage plugins are not a discoverable entry-point protocol in ETLantic
    0.37. Prefer shipped dataframe / SQL / Spark / orchestration plugins and
    [Storage today](../06_EXECUTION/STORAGE_TODAY.md).

**Do not implement a package against this page.** The 0.38 connectivity program
will define the public storage protocol and reference connectors, including the
[local file landing-zone connector](../11_DEVELOPMENT/LANDING_ZONE_CONNECTOR_PLAN.md)
(batch snapshot and incremental directory/glob modes; continuous triggers in
0.39+).

| Use instead | Link |
|---|---|
| What works today | [Storage today](../06_EXECUTION/STORAGE_TODAY.md) |
| Extract / Load assets | [Extracts](../05_PIPELINES/EXTRACTS.md), [Loads](../05_PIPELINES/LOADS.md) |
| Shipped engines | [Plugin SDK Overview](OVERVIEW.md) |
| Program ownership | [Adoption ecosystem plan](../11_DEVELOPMENT/ADOPTION_ECOSYSTEM_PLAN.md#data-connectivity-and-connector-sdk) |
| Directory / CSV landing zones | [Landing-zone file connector plan](../11_DEVELOPMENT/LANDING_ZONE_CONNECTOR_PLAN.md) |
