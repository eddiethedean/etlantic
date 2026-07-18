# Design Proposals

This section contains **unshipped** APIs, historical plans, and normative
proposals. It is deliberately separate from the ETLantic 0.13 user guide.

!!! warning "Not current API documentation"
    Do not copy unshipped interfaces from these pages into a 0.12 application.
    Start with the [current-version guide](../01_GETTING_STARTED/CURRENT_VERSION.md)
    and [capabilities](../01_GETTING_STARTED/CAPABILITIES.md).

    **Exceptions (shipped):**
    - portable **authoring** (`@Transformation.portable`, `etlantic.transform`)
      — see [Portable Transformations](../04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md)
    - portable **compiler protocol** and Polars kernel compiler — see
      [Portable Transform Compiler](../07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER.md)
      under Integrations and Execution

## Portable transformation program (history and remaining work)

- [Authoring experience (shipped 0.11)](../04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md)
- [Function catalog (shipped 0.11)](../04_TRANSFORMATIONS/PORTABLE_FUNCTIONS.md)
- [Compiler protocol (shipped 0.12; Polars kernel)](../07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER.md)
- [Implementation plan](PORTABLE_TRANSFORM_PLAN.md)
- [DTCS evolution](DTCS_PORTABLE_EVOLUTION.md)
- [DTCS 2.0 publication record](DTCS_PORTABLE_SPEC_PROPOSAL.md)
- [DTCS 3.0 Rich Portable Analytics publication record](DTCS_3_0_SPEC_PROPOSAL.md)

## Maintainer plans

- [FastAPI integration](FASTAPI_INTEGRATION_PLAN.md)
- [Schema drift](SCHEMA_DRIFT_PLAN.md)
- [Reliability](ETL_RELIABILITY_PLAN.md)
- [SQLModel integration](SQLMODEL_INTEGRATION_PLAN.md)
- [SparkForge adoption](SPARKFORGE_ADOPTION.md)

## Design-study examples

The [Examples index](../09_EXAMPLES/README.md) distinguishes CI-tested scripts
from aspirational studies. Design studies are not compatibility promises.
