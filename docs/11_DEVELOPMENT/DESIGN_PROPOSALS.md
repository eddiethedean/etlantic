# Design Proposals

This section contains a mixture of **unshipped** APIs, partially shipped
programs, historical implementation records, and normative proposals. It is
deliberately separate from the current ETLantic **0.35** user guide (Beta).

!!! danger "Do not start here"
    This section is **not** the user guide. Start with
    [Installation](../01_GETTING_STARTED/INSTALLATION.md) →
    [Quickstart](../01_GETTING_STARTED/QUICKSTART.md) instead.

!!! warning "Not current API documentation"
    Do not copy unshipped interfaces from these pages into a production
    application. Start with the
    [current-version guide](../01_GETTING_STARTED/CURRENT_VERSION.md)
    and [capabilities](../01_GETTING_STARTED/CAPABILITIES.md).

    Some plans also preserve shipped work:
    - portable **authoring** (`@Transformation.portable`, `etlantic.transform`)
      — see [Portable Transformations](../04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md)
    - portable **compiler protocol** and first-party compilers — see
      [Portable Transform Compiler](../07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER.md)
      under Extend
    - Gate A versioned tabular interchange — see
      [What's New in 0.18](../01_GETTING_STARTED/WHATS_NEW_0_18.md)
      (historical release notes; still accurate for Gate A)

## Portable transformation program (history and remaining work)

Current public behavior is documented in the
[DTCS integration guide](../04_TRANSFORMATIONS/DTCS.md).

- [Authoring experience (shipped 0.11)](../04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md)
- [Function catalog (shipped 0.11)](../04_TRANSFORMATIONS/PORTABLE_FUNCTIONS.md)
- [Compiler protocol (shipped 0.12; Polars kernel)](../07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER.md)
- [Implementation plan](PORTABLE_TRANSFORM_PLAN.md)
- [DTCS evolution](DTCS_PORTABLE_EVOLUTION.md)
- [DTCS 2.0 publication record](DTCS_PORTABLE_SPEC_PROPOSAL.md)
- [DTCS 3.0 Rich Portable Analytics publication record](DTCS_3_0_SPEC_PROPOSAL.md)

## Maintainer plans

Use the [Planning Hub](PLAN_INDEX.md) for the complete portfolio, current
status, document ownership, and the boundary between shipped behavior and
future work. Historical implementation records remain in the
[archive index](ARCHIVE_INDEX.md).

## Design-study examples

Aspirational design studies under `docs/09_EXAMPLES/` are **not** site nav
pages and are **not** compatibility promises. Browse them on GitHub:

[docs/09_EXAMPLES](https://github.com/eddiethedean/etlantic/tree/main/docs/09_EXAMPLES)

The [Examples index](../09_EXAMPLES/README.md) lists **runnable** CI/docs
guides only.
